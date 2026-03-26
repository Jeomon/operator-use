import pytest
from unittest.mock import AsyncMock, MagicMock

from operator_use.web.tools.browser import browser


@pytest.mark.asyncio
async def test_browser_tool_click_uses_current_page():
    page = MagicMock()
    page.click_at = AsyncMock()

    browser_instance = MagicMock()
    browser_instance._client = object()
    browser_instance.current_page = MagicMock(return_value=page)
    browser_instance._wait_for_page = AsyncMock()

    result = await browser.ainvoke(action="click", x=10, y=20, browser=browser_instance)

    assert result.success is True
    page.click_at.assert_awaited_once_with(10, 20)
    browser_instance._wait_for_page.assert_awaited_once_with(timeout=8.0)


@pytest.mark.asyncio
async def test_browser_tool_script_uses_current_page():
    page = MagicMock()
    page.execute_script = AsyncMock(return_value="ok")

    browser_instance = MagicMock()
    browser_instance._client = object()
    browser_instance.current_page = MagicMock(return_value=page)

    result = await browser.ainvoke(action="script", script="1+1", browser=browser_instance)

    assert result.success is True
    page.execute_script.assert_awaited_once_with("1+1", truncate=True, repair=True)
