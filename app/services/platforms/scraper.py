"""Browser-based adapters for review platforms without an open API."""

import logging
from datetime import datetime

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from app.schemas.parser import RawReview
from app.services.platforms.base import BasePlatformAdapter

logger = logging.getLogger(__name__)

_PAGE_TIMEOUT_MS = 15_000


class OtzovikScraperAdapter(BasePlatformAdapter):
    async def fetch_reviews(self, since: datetime) -> list[RawReview]:
        raise NotImplementedError("Otzovik review fetching is not implemented")

    async def publish_reply(self, review_id: str, text: str) -> bool:
        async with async_playwright() as playwright:
            browser = None
            context = None
            page = None
            try:
                browser = await playwright.chromium.launch(
                    headless=True,
                    timeout=_PAGE_TIMEOUT_MS,
                )
                context = await browser.new_context()
                page = await context.new_page()
                page.set_default_timeout(_PAGE_TIMEOUT_MS)
                await page.goto(
                    f"https://otzovik.com/review_{review_id}.html",
                    wait_until="domcontentloaded",
                    timeout=_PAGE_TIMEOUT_MS,
                )
                reply_field = page.locator('textarea[name="reply"]')
                await reply_field.wait_for(
                    state="visible",
                    timeout=_PAGE_TIMEOUT_MS,
                )
                await reply_field.fill(text)
                await page.locator('button[type="submit"]').click()
                return True
            except PlaywrightTimeoutError:
                logger.warning(
                    "Timed out while publishing an Otzovik reply",
                    extra={"review_id": review_id},
                )
                return False
            finally:
                try:
                    if page is not None:
                        await page.close()
                finally:
                    try:
                        if context is not None:
                            await context.close()
                    finally:
                        if browser is not None:
                            await browser.close()
