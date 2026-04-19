"""Cooperative input locking — queue agent actions while the user is active.

Platform implementations:
  - macOS : CGEventTap (CoreGraphics)
  - Windows: WH_MOUSE_LL / WH_KEYBOARD_LL low-level hooks

Usage::

    monitor = InputActivityMonitor()
    monitor.start()
    ...
    if not monitor.is_user_active():
        do_agent_action()
    else:
        await monitor.wait_for_idle(timeout=10.0)
    ...
    monitor.stop()
"""

from __future__ import annotations

import asyncio
import logging
import sys
import threading
import time
from typing import Callable

logger = logging.getLogger(__name__)

# Seconds of quiet time before the user is considered idle.
_DEFAULT_IDLE_THRESHOLD = 0.5


class InputActivityMonitor:
    """Detect user mouse/keyboard activity and expose an idle-wait API.

    The monitor is platform-agnostic at the API level; the underlying event
    listener is selected at construction time via ``sys.platform``.

    Args:
        idle_threshold: Seconds without input before :py:meth:`is_user_active`
            returns ``False``.  Defaults to 500 ms.
        on_activity: Optional callback invoked each time new user activity is
            detected.  Runs on the monitor's background thread.
    """

    def __init__(
        self,
        idle_threshold: float = _DEFAULT_IDLE_THRESHOLD,
        on_activity: Callable[[], None] | None = None,
    ) -> None:
        self._idle_threshold = idle_threshold
        self._on_activity = on_activity
        self._last_activity: float = 0.0  # epoch seconds; 0 = never seen
        self._running = False
        self._lock = threading.Lock()

        # Back-end chosen at construction time.
        if sys.platform == "darwin":
            self._backend: _InputBackend = _MacOSBackend(self._record_activity)
        elif sys.platform == "win32":
            self._backend = _WindowsBackend(self._record_activity)
        else:
            logger.warning(
                "InputActivityMonitor: unsupported platform %r — activity detection disabled.",
                sys.platform,
            )
            self._backend = _NullBackend(self._record_activity)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Install the platform hook and begin monitoring."""
        if self._running:
            return
        self._running = True
        self._backend.start()
        logger.debug("InputActivityMonitor started (%s backend)", sys.platform)

    def stop(self) -> None:
        """Remove the platform hook and stop monitoring."""
        if not self._running:
            return
        self._running = False
        self._backend.stop()
        logger.debug("InputActivityMonitor stopped")

    def is_user_active(self) -> bool:
        """Return ``True`` if user input was seen within the idle threshold."""
        with self._lock:
            last = self._last_activity
        if last == 0.0:
            return False
        return (time.monotonic() - last) < self._idle_threshold

    async def wait_for_idle(self, timeout: float | None = None) -> bool:
        """Async wait until the user has been idle for at least *idle_threshold* seconds.

        Args:
            timeout: Maximum seconds to wait.  ``None`` means wait forever.

        Returns:
            ``True`` if the user became idle within *timeout*, ``False`` if the
            wait timed out.
        """
        poll_interval = max(0.05, self._idle_threshold / 10)
        deadline = None if timeout is None else (time.monotonic() + timeout)

        while self.is_user_active():
            if deadline is not None and time.monotonic() >= deadline:
                return False
            await asyncio.sleep(poll_interval)

        return True

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _record_activity(self) -> None:
        """Called by the backend on every detected input event."""
        with self._lock:
            self._last_activity = time.monotonic()
        if self._on_activity:
            try:
                self._on_activity()
            except Exception:  # pragma: no cover
                logger.exception("InputActivityMonitor on_activity callback raised")


# ---------------------------------------------------------------------------
# Abstract backend
# ---------------------------------------------------------------------------


class _InputBackend:
    """Internal protocol: each platform implements start / stop."""

    def __init__(self, callback: Callable[[], None]) -> None:
        self._callback = callback

    def start(self) -> None:  # pragma: no cover
        raise NotImplementedError

    def stop(self) -> None:  # pragma: no cover
        raise NotImplementedError


# ---------------------------------------------------------------------------
# macOS backend — CGEventTap
# ---------------------------------------------------------------------------


class _MacOSBackend(_InputBackend):
    """Listen for mouse and keyboard events via ``CGEventTap``.

    The tap runs on a private ``CFRunLoop`` in a daemon thread so it does not
    block the calling thread and is automatically cleaned up when the process
    exits.
    """

    def __init__(self, callback: Callable[[], None]) -> None:
        super().__init__(callback)
        self._thread: threading.Thread | None = None
        self._run_loop = None  # CFRunLoopRef stored after the thread starts

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True, name="cg-event-tap")
        self._thread.start()

    def stop(self) -> None:
        if self._run_loop is not None:
            try:
                from Quartz import CFRunLoopStop  # type: ignore[import]

                CFRunLoopStop(self._run_loop)
            except Exception:
                logger.debug("CGEventTap: could not stop run loop", exc_info=True)
        if self._thread is not None:
            self._thread.join(timeout=2.0)

    def _run(self) -> None:  # pragma: no cover — runs in a thread
        try:
            from Quartz import (  # type: ignore[import]
                CFMachPortCreateRunLoopSource,
                CFRunLoopAddSource,
                CFRunLoopGetCurrent,
                CFRunLoopRun,
                CGEventMaskBit,
                CGEventTapCreate,
                CGEventTapEnable,
                kCFRunLoopCommonModes,
                kCGEventFlagMaskCommand,
                kCGEventKeyDown,
                kCGEventLeftMouseDown,
                kCGEventMouseMoved,
                kCGEventRightMouseDown,
                kCGEventScrollWheel,
                kCGHeadInsertEventTap,
                kCGSessionEventTap,
                kCGTapDisabledByTimeout,
                kCGTapDisabledByUserInput,
            )
        except ImportError:
            logger.warning("pyobjc-framework-Quartz not available — CGEventTap disabled.")
            return

        callback = self._callback

        def _tap_callback(proxy, event_type, event, refcon):  # noqa: ANN001
            if event_type in (kCGTapDisabledByTimeout, kCGTapDisabledByUserInput):
                CGEventTapEnable(tap, True)
                return event
            callback()
            return event

        mask = (
            CGEventMaskBit(kCGEventMouseMoved)
            | CGEventMaskBit(kCGEventLeftMouseDown)
            | CGEventMaskBit(kCGEventRightMouseDown)
            | CGEventMaskBit(kCGEventScrollWheel)
            | CGEventMaskBit(kCGEventKeyDown)
        )

        tap = CGEventTapCreate(
            kCGSessionEventTap,
            kCGHeadInsertEventTap,
            0,  # kCGEventTapOptionListenOnly
            mask,
            _tap_callback,
            None,
        )

        if tap is None:
            logger.warning(
                "CGEventTap: could not create event tap — "
                "grant Input Monitoring in System Settings > Privacy & Security."
            )
            return

        source = CFMachPortCreateRunLoopSource(None, tap, 0)
        self._run_loop = CFRunLoopGetCurrent()
        CFRunLoopAddSource(self._run_loop, source, kCFRunLoopCommonModes)
        CGEventTapEnable(tap, True)
        _ = kCGEventFlagMaskCommand  # keep import happy
        CFRunLoopRun()


# ---------------------------------------------------------------------------
# Windows backend — WH_MOUSE_LL / WH_KEYBOARD_LL
# ---------------------------------------------------------------------------


class _WindowsBackend(_InputBackend):
    """Listen for global mouse and keyboard events via low-level Win32 hooks."""

    def __init__(self, callback: Callable[[], None]) -> None:
        super().__init__(callback)
        self._thread: threading.Thread | None = None
        self._thread_id: int | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True, name="win-input-hook")
        self._thread.start()

    def stop(self) -> None:
        if self._thread_id is not None:
            try:
                import ctypes  # noqa: PLC0415

                ctypes.windll.user32.PostThreadMessageW(self._thread_id, 0x0012, 0, 0)  # WM_QUIT
            except Exception:
                logger.debug("WinHook: could not post WM_QUIT", exc_info=True)
        if self._thread is not None:
            self._thread.join(timeout=2.0)

    def _run(self) -> None:  # pragma: no cover — runs in a thread
        try:
            import ctypes  # noqa: PLC0415
            import ctypes.wintypes  # noqa: PLC0415
        except ImportError:
            logger.warning("ctypes not available — Windows input hook disabled.")
            return

        import ctypes.wintypes as wintypes  # noqa: PLC0415

        WH_MOUSE_LL = 14
        WH_KEYBOARD_LL = 13
        HC_ACTION = 0

        callback = self._callback

        HOOKPROC = ctypes.CFUNCTYPE(ctypes.c_long, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)

        def _hook_proc(nCode, wParam, lParam):  # noqa: ANN001
            if nCode == HC_ACTION:
                callback()
            return ctypes.windll.user32.CallNextHookEx(None, nCode, wParam, lParam)

        proc = HOOKPROC(_hook_proc)

        mouse_hook = ctypes.windll.user32.SetWindowsHookExW(WH_MOUSE_LL, proc, None, 0)
        keyboard_hook = ctypes.windll.user32.SetWindowsHookExW(WH_KEYBOARD_LL, proc, None, 0)

        if not mouse_hook or not keyboard_hook:
            logger.warning("WinHook: SetWindowsHookExW failed — input detection disabled.")
            return

        import threading as _threading  # noqa: PLC0415

        self._thread_id = _threading.current_thread().ident

        msg = wintypes.MSG()
        while ctypes.windll.user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            ctypes.windll.user32.TranslateMessage(ctypes.byref(msg))
            ctypes.windll.user32.DispatchMessageW(ctypes.byref(msg))

        ctypes.windll.user32.UnhookWindowsHookEx(mouse_hook)
        ctypes.windll.user32.UnhookWindowsHookEx(keyboard_hook)


# ---------------------------------------------------------------------------
# Null backend — unsupported platforms
# ---------------------------------------------------------------------------


class _NullBackend(_InputBackend):
    """No-op backend for platforms without a native implementation."""

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass
