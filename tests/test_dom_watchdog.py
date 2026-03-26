from unittest.mock import MagicMock

from operator_use.web.browser.events import StateInvalidatedEvent
from operator_use.web.watchdog.dom import DOMWatchdog


def test_dom_watchdog_emits_invalidated_on_document_update():
    session = MagicMock()
    watchdog = DOMWatchdog(session)

    watchdog._on_dom_updated({}, session_id="session-1")

    emitted = session.emit_browser_event.call_args.args[0]
    assert isinstance(emitted, StateInvalidatedEvent)
    assert emitted.reason == "dom_document_updated"


def test_dom_watchdog_emits_invalidated_on_dom_mutation():
    session = MagicMock()
    watchdog = DOMWatchdog(session)

    watchdog._on_dom_changed({}, session_id="session-1")

    emitted = session.emit_browser_event.call_args.args[0]
    assert isinstance(emitted, StateInvalidatedEvent)
    assert emitted.reason == "dom_mutation"
