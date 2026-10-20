from unittest.mock import AsyncMock, Mock

import pytest
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from app.services.platforms import scraper


@pytest.mark.asyncio
@pytest.mark.parametrize("timeout", [False, True])
async def test_otzovik_publish_reply_handles_timeout_and_closes_resources(
    monkeypatch: pytest.MonkeyPatch,
    timeout: bool,
) -> None:
    playwright = Mock()
    browser = Mock()
    context = Mock()
    page = Mock()
    reply_field = Mock()
    submit_button = Mock()
    playwright_context = Mock()
    playwright_context.__aenter__ = AsyncMock(return_value=playwright)
    playwright_context.__aexit__ = AsyncMock()

    playwright.chromium.launch = AsyncMock(return_value=browser)
    browser.new_context = AsyncMock(return_value=context)
    browser.close = AsyncMock()
    context.new_page = AsyncMock(return_value=page)
    context.close = AsyncMock()
    page.set_default_timeout = Mock()
    page.goto = AsyncMock()
    page.locator = Mock(side_effect=[reply_field, submit_button])
    page.close = AsyncMock()
    reply_field.wait_for = AsyncMock(
        side_effect=PlaywrightTimeoutError("selector timed out") if timeout else None
    )
    reply_field.fill = AsyncMock()
    submit_button.click = AsyncMock()
    monkeypatch.setattr(
        scraper,
        "async_playwright",
        Mock(return_value=playwright_context),
    )
    adapter = scraper.OtzovikScraperAdapter("unused", {})

    result = await adapter.publish_reply("123", "Thanks for your feedback")

    assert result is (not timeout)
    playwright.chromium.launch.assert_awaited_once_with(
        headless=True,
        timeout=15_000,
    )
    page.goto.assert_awaited_once_with(
        "https://otzovik.com/review_123.html",
        wait_until="domcontentloaded",
        timeout=15_000,
    )
    page.set_default_timeout.assert_called_once_with(15_000)
    page.locator.assert_any_call('textarea[name="reply"]')
    reply_field.wait_for.assert_awaited_once_with(
        state="visible",
        timeout=15_000,
    )
    if timeout:
        reply_field.fill.assert_not_awaited()
        submit_button.click.assert_not_awaited()
    else:
        reply_field.fill.assert_awaited_once_with("Thanks for your feedback")
        submit_button.click.assert_awaited_once()
    page.close.assert_awaited_once()
    context.close.assert_awaited_once()
    browser.close.assert_awaited_once()
    playwright_context.__aexit__.assert_awaited_once_with(None, None, None)
