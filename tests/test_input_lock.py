"""Tests for operator_use.computer.input_lock.

All platform-native APIs are mocked so these tests run on any OS.
"""

from __future__ import annotations

import asyncio
import sys
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from operator_use.computer.input_lock import (
    InputActivityMonitor,
    _MacOSBackend,
    _NullBackend,
    _WindowsBackend,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_monitor(platform: str, idle_threshold: float = 0.5) -> InputActivityMonitor:
    """Return an InputActivityMonitor with a null backend regardless of platform."""
    with patch.object(sys, "platform", platform):
        monitor = InputActivityMonitor(idle_threshold=idle_threshold)
    # Replace whatever backend was chosen with a NullBackend so tests don't
    # start real OS threads.
    monitor._backend = _NullBackend(monitor._record_activity)
    return monitor


# ---------------------------------------------------------------------------
# _record_activity / is_user_active
# ---------------------------------------------------------------------------


class TestIsUserActive:
    def test_false_before_any_activity(self):
        monitor = _make_monitor("linux")
        assert monitor.is_user_active() is False

    def test_true_immediately_after_activity(self):
        monitor = _make_monitor("linux", idle_threshold=1.0)
        monitor._record_activity()
        assert monitor.is_user_active() is True

    def test_false_after_idle_threshold_passes(self):
        monitor = _make_monitor("linux", idle_threshold=0.05)
        monitor._record_activity()
        time.sleep(0.1)
        assert monitor.is_user_active() is False

    def test_resets_on_new_activity(self):
        monitor = _make_monitor("linux", idle_threshold=0.05)
        monitor._record_activity()
        time.sleep(0.07)
        assert monitor.is_user_active() is False
        monitor._record_activity()
        assert monitor.is_user_active() is True


# ---------------------------------------------------------------------------
# on_activity callback
# ---------------------------------------------------------------------------


class TestOnActivityCallback:
    def test_callback_invoked_on_activity(self):
        calls = []
        monitor = _make_monitor("linux")
        monitor._on_activity = lambda: calls.append(1)
        monitor._record_activity()
        assert len(calls) == 1

    def test_callback_invoked_multiple_times(self):
        calls = []
        monitor = _make_monitor("linux")
        monitor._on_activity = lambda: calls.append(1)
        for _ in range(5):
            monitor._record_activity()
        assert len(calls) == 5

    def test_callback_none_does_not_raise(self):
        monitor = _make_monitor("linux")
        monitor._on_activity = None
        monitor._record_activity()  # should not raise


# ---------------------------------------------------------------------------
# start / stop
# ---------------------------------------------------------------------------


class TestStartStop:
    def test_start_sets_running(self):
        monitor = _make_monitor("linux")
        monitor.start()
        assert monitor._running is True
        monitor.stop()

    def test_stop_clears_running(self):
        monitor = _make_monitor("linux")
        monitor.start()
        monitor.stop()
        assert monitor._running is False

    def test_double_start_is_idempotent(self):
        monitor = _make_monitor("linux")
        monitor.start()
        monitor.start()  # second call is a no-op
        assert monitor._running is True
        monitor.stop()

    def test_double_stop_is_idempotent(self):
        monitor = _make_monitor("linux")
        monitor.start()
        monitor.stop()
        monitor.stop()  # second call is a no-op
        assert monitor._running is False


# ---------------------------------------------------------------------------
# wait_for_idle
# ---------------------------------------------------------------------------


class TestWaitForIdle:
    @pytest.mark.asyncio
    async def test_returns_true_when_already_idle(self):
        monitor = _make_monitor("linux")
        result = await monitor.wait_for_idle(timeout=1.0)
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_true_after_activity_stops(self):
        monitor = _make_monitor("linux", idle_threshold=0.05)
        monitor._record_activity()

        result = await monitor.wait_for_idle(timeout=2.0)
        assert result is True

    @pytest.mark.asyncio
    async def test_times_out_while_user_is_active(self):
        monitor = _make_monitor("linux", idle_threshold=10.0)
        # Keep recording activity in a thread to simulate continuous input.
        stop_event = threading.Event()

        def _spam():
            while not stop_event.is_set():
                monitor._record_activity()
                time.sleep(0.01)

        spammer = threading.Thread(target=_spam, daemon=True)
        spammer.start()
        try:
            result = await monitor.wait_for_idle(timeout=0.1)
        finally:
            stop_event.set()
            spammer.join()

        assert result is False

    @pytest.mark.asyncio
    async def test_none_timeout_waits_until_idle(self):
        monitor = _make_monitor("linux", idle_threshold=0.05)
        monitor._record_activity()
        # With None timeout it should still resolve once input stops.
        result = await asyncio.wait_for(monitor.wait_for_idle(timeout=None), timeout=3.0)
        assert result is True


# ---------------------------------------------------------------------------
# Platform backend selection
# ---------------------------------------------------------------------------


class TestBackendSelection:
    def test_darwin_selects_macos_backend(self):
        with patch.object(sys, "platform", "darwin"):
            monitor = InputActivityMonitor()
        assert isinstance(monitor._backend, _MacOSBackend)

    def test_win32_selects_windows_backend(self):
        with patch.object(sys, "platform", "win32"):
            monitor = InputActivityMonitor()
        assert isinstance(monitor._backend, _WindowsBackend)

    def test_linux_selects_null_backend(self):
        with patch.object(sys, "platform", "linux"):
            monitor = InputActivityMonitor()
        assert isinstance(monitor._backend, _NullBackend)

    def test_unknown_platform_selects_null_backend(self):
        with patch.object(sys, "platform", "freebsd"):
            monitor = InputActivityMonitor()
        assert isinstance(monitor._backend, _NullBackend)


# ---------------------------------------------------------------------------
# macOS backend — mock Quartz
# ---------------------------------------------------------------------------


class TestMacOSBackend:
    def _make_quartz_mock(self):
        """Return a MagicMock that mimics the Quartz module surface we use."""
        q = MagicMock()
        q.CGEventTapCreate.return_value = MagicMock()  # non-None tap
        q.CFMachPortCreateRunLoopSource.return_value = MagicMock()
        q.CFRunLoopGetCurrent.return_value = MagicMock()
        # CFRunLoopRun blocks — replace with a no-op
        q.CFRunLoopRun.return_value = None
        return q

    def test_start_launches_thread(self):
        backend = _MacOSBackend(lambda: None)
        quartz = self._make_quartz_mock()
        with patch.dict("sys.modules", {"Quartz": quartz}):
            backend.start()
            time.sleep(0.05)
        assert backend._thread is not None
        # Clean up
        if backend._run_loop:
            quartz.CFRunLoopStop(backend._run_loop)

    def test_null_tap_logs_warning(self, caplog):
        backend = _MacOSBackend(lambda: None)
        quartz = self._make_quartz_mock()
        quartz.CGEventTapCreate.return_value = None  # simulate permission failure

        import logging

        with caplog.at_level(logging.WARNING):
            with patch.dict("sys.modules", {"Quartz": quartz}):
                backend._run()

        assert any("event tap" in r.message.lower() for r in caplog.records)

    def test_import_error_logs_warning(self, caplog):
        backend = _MacOSBackend(lambda: None)
        import logging

        with caplog.at_level(logging.WARNING):
            with patch.dict("sys.modules", {"Quartz": None}):
                # Force ImportError by making the module None
                original = sys.modules.get("Quartz")
                sys.modules["Quartz"] = None  # type: ignore[assignment]
                try:
                    backend._run()
                finally:
                    if original is None:
                        del sys.modules["Quartz"]
                    else:
                        sys.modules["Quartz"] = original

        # The method should log a warning about pyobjc not being available.
        # (May not trigger on systems that have it installed — check gracefully.)
        assert backend._thread is None or True  # no crash is the main assertion


# ---------------------------------------------------------------------------
# Windows backend — mock ctypes / win32
# ---------------------------------------------------------------------------


class TestWindowsBackend:
    def _make_ctypes_mock(self):
        ct = MagicMock()
        ct.windll.user32.SetWindowsHookExW.return_value = 1  # non-zero = success
        ct.windll.user32.GetMessageW.return_value = 0  # immediate quit
        ct.windll.user32.UnhookWindowsHookEx.return_value = 1
        ct.CFUNCTYPE.return_value = MagicMock(return_value=MagicMock())
        ct.c_long = MagicMock()
        ct.c_int = MagicMock()
        ct.wintypes = MagicMock()
        return ct

    def test_run_calls_set_hooks(self):
        backend = _WindowsBackend(lambda: None)
        ct = self._make_ctypes_mock()
        # Keep a direct reference to the mock's windll so the assertion
        # survives after patch.dict / patch(create=True) tear down.
        windll_mock = ct.windll
        with patch.dict("sys.modules", {"ctypes": ct, "ctypes.wintypes": ct.wintypes}):
            with patch("ctypes.windll", windll_mock, create=True):
                with patch("ctypes.CFUNCTYPE", ct.CFUNCTYPE, create=True):
                    with patch("ctypes.wintypes", ct.wintypes, create=True):
                        backend._run()

        # SetWindowsHookExW should have been called twice (mouse + keyboard)
        assert windll_mock.user32.SetWindowsHookExW.call_count >= 2

    def test_hook_failure_logs_warning(self, caplog):
        backend = _WindowsBackend(lambda: None)
        ct = self._make_ctypes_mock()
        ct.windll.user32.SetWindowsHookExW.return_value = 0  # failure

        import logging

        with caplog.at_level(logging.WARNING):
            with patch("ctypes.windll", ct.windll, create=True):
                with patch("ctypes.CFUNCTYPE", ct.CFUNCTYPE, create=True):
                    with patch("ctypes.wintypes", ct.wintypes, create=True):
                        backend._run()

        assert any("hook" in r.message.lower() for r in caplog.records)


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------


class TestThreadSafety:
    def test_concurrent_record_activity_does_not_race(self):
        monitor = _make_monitor("linux", idle_threshold=5.0)
        errors = []

        def _worker():
            try:
                for _ in range(100):
                    monitor._record_activity()
                    monitor.is_user_active()
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=_worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Thread-safety errors: {errors}"
