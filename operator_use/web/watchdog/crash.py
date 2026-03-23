from __future__ import annotations
import logging
from operator_use.web.watchdog.base import BaseWatchdog

logger = logging.getLogger(__name__)


class CrashWatchdog(BaseWatchdog):
    """Detects tab crashes and cleans up session state.

    Chrome sends Inspector.targetCrashed in the context of the crashed
    page's session. Without this the agent hangs indefinitely waiting
    for a response from a dead renderer.
    """

    async def attach(self) -> None:
        self.session.on('Inspector.targetCrashed', self._on_crash)

    def _on_crash(self, event, session_id=None) -> None:
        if not session_id:
            return

        # Find which target this session belongs to
        target_id = next(
            (tid for tid, sid in self.session._sessions.items() if sid == session_id),
            None,
        )

        # Always clean up session state to unblock any waiters and avoid leaks.
        # This handles both tracked tabs and untracked sub-frames / service workers.
        self.session._lifecycle.pop(session_id, None)
        self.session._page_loading.pop(session_id, None)
        ready = self.session._page_ready.pop(session_id, None)
        if ready:
            ready.set()

        if target_id:
            # Tracked tab crashed — clean up target/session maps
            logger.warning('Tab crashed (target=%s, session=%s)', target_id, session_id)
            self.session._targets.pop(target_id, None)
            self.session._sessions.pop(target_id, None)

            # Switch current target to another tab if possible
            if self.session._current_target_id == target_id:
                self.session._current_target_id = (
                    next(iter(self.session._sessions), None)
                )

            # If no tabs remain, mark session as crashed so the agent can abort
            if not self.session._sessions:
                self.session.crashed = True
        else:
            # Untracked session (sub-frame, service worker, etc.) — log quietly
            logger.debug('Sub-frame/worker crashed (session=%s) — ignored', session_id)
