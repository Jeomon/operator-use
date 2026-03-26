import pytest
from unittest.mock import AsyncMock, MagicMock

from operator_use.web.browser.config import BrowserConfig
from operator_use.web.browser.page import Page
from operator_use.web.browser.service import Browser


def test_current_page_returns_page_wrapper():
    browser = Browser(BrowserConfig())

    page = browser.current_page()

    assert isinstance(page, Page)


@pytest.mark.asyncio
async def test_page_execute_script_uses_browser_transport():
    browser = Browser(BrowserConfig())
    browser._get_current_session_id = MagicMock(return_value="session-1")
    browser.send = AsyncMock(return_value={"result": {"value": 123}})

    result = await browser.current_page().execute_script("1+2")

    assert result == 123
    browser.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_page_click_at_uses_browser_transport():
    browser = Browser(BrowserConfig())
    browser._get_current_session_id = MagicMock(return_value="session-1")
    browser.send = AsyncMock()
    browser._move_mouse = AsyncMock()

    await browser.current_page().click_at(10, 20)

    browser._move_mouse.assert_awaited_once()
    assert browser.send.await_count == 2
