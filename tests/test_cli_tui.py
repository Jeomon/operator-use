from operator_use.cli import tui


class _FakePrompt:
    def __init__(self, result):
        self.result = result
        self.bound = []
        self.application = type("App", (), {"ttimeoutlen": 0.5})()

    def register_kb(self, *keys, **kwargs):
        self.bound.append((keys, kwargs))

        def decorator(func):
            return func

        return decorator

    def execute(self):
        return self.result


def test_execute_prompt_raises_navigate_back_on_back_signal():
    prompt = _FakePrompt(tui.BACK_SIGNAL)

    try:
        tui._execute_prompt(prompt)
    except tui.NavigateBack:
        pass
    else:
        raise AssertionError("Expected NavigateBack to be raised")

    assert prompt.bound
    assert prompt.bound[0][0] == ("escape",)


def test_execute_prompt_returns_normal_result():
    prompt = _FakePrompt("ok")
    assert tui._execute_prompt(prompt) == "ok"
    assert prompt.application.ttimeoutlen == tui.ESCAPE_FLUSH_TIMEOUT_SECONDS
