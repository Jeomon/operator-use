from operator_use.web.browser.session import Session


def test_register_target_sets_current_target_once():
    manager = Session()

    manager.register_target("t1", "s1", "https://example.com", "Example")
    manager.register_target("t2", "s2", "https://openai.com", "OpenAI")

    assert manager.current_target_id == "t1"
    assert manager.current_session_id() == "s1"
    assert manager.targets["t2"]["title"] == "OpenAI"


def test_update_target_changes_stored_metadata():
    manager = Session()
    manager.register_target("t1", "s1", "https://example.com", "Example")

    manager.update_target("t1", url="https://example.org", title="Example Org")

    assert manager.targets["t1"]["url"] == "https://example.org"
    assert manager.targets["t1"]["title"] == "Example Org"


def test_remove_by_target_promotes_next_current_target():
    manager = Session()
    manager.register_target("t1", "s1")
    manager.register_target("t2", "s2")
    manager.current_target_id = "t1"

    removed_session = manager.remove_by_target("t1")

    assert removed_session == "s1"
    assert manager.current_target_id == "t2"
    assert manager.current_session_id() == "s2"


def test_find_target_by_session_returns_matching_target():
    manager = Session()
    manager.register_target("t1", "s1")

    assert manager.find_target_by_session("s1") == "t1"
    assert manager.find_target_by_session("missing") is None
