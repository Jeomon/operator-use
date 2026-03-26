import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from operator_use.web.browser.views import BrowserState
from operator_use.web.watchdog.state import StateWatchdog


@pytest.mark.asyncio
async def test_state_watchdog_returns_cached_state_when_clean():
    session = MagicMock()
    session._client = MagicMock()
    session._get_current_session_id = MagicMock(return_value="session-1")
    watchdog = StateWatchdog(session)
    cached = BrowserState()
    watchdog._cached_state = cached
    watchdog._dirty = False

    result = await watchdog.get_state()

    assert result is cached


@pytest.mark.asyncio
async def test_state_watchdog_dedupes_inflight_capture():
    session = MagicMock()
    session._client = MagicMock()
    session._get_current_session_id = MagicMock(return_value="session-1")
    watchdog = StateWatchdog(session)
    state = BrowserState()
    watchdog._capture_state = AsyncMock(return_value=state)

    result1, result2 = await asyncio.gather(
        watchdog.get_state(),
        watchdog.get_state(),
    )

    assert result1 is state
    assert result2 is state
    watchdog._capture_state.assert_awaited_once_with(use_vision=False)


@pytest.mark.asyncio
async def test_state_watchdog_invalidates_cache_on_state_change():
    session = MagicMock()
    watchdog = StateWatchdog(session)
    watchdog._cached_state = BrowserState()
    watchdog._dirty = False

    from operator_use.web.browser.events import StateInvalidatedEvent

    watchdog._on_state_invalidated(StateInvalidatedEvent(session_id="session-1", reason="click"))

    assert watchdog._dirty is True
