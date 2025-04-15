import datetime
from playwright.async_api import async_playwright, Playwright
from typing import List
import logging

from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Post(BaseModel):
    id: str = Field(..., description="Post ID")
    text: str = Field(..., description="Post content")
    username: str = Field(..., description="Author's username")
    created_at: str = Field(..., description="Post creation timestamp (string format)")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class CrawlerResponse(BaseModel):
    posts: List[Post] = Field(..., description="List of crawled posts")
    count: int = Field(..., description="Number of posts retrieved")
    keyword: str = Field(..., description="Search keyword used")


class CrawlerService:
    def __init__(
        self,
    ):
        print("Hello CralwerService")

    async def _launch_browser(self, playwright: Playwright):
        """Launch a headless browser optimized for Lambda."""
        browser = await playwright.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"],
        )
        return browser

    async def _create_page(self, browser):
        """Create a new browser page."""
        page = await browser.new_page()
        return page

    async def _navigate_to_search(self, page, keyword: str):
        """Navigate to X search page with the given keyword."""
        search_url = f"https://x.com/search?q={keyword}&src=typed_query"
        await page.goto(search_url, timeout=30000)
        await page.wait_for_load_state("networkidle", timeout=30000)

    async def _scroll_page(self, page, max_posts: int):
        """Scroll the page to load more posts."""
        posts_collected = 0
        while posts_collected < max_posts:
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(1000)
            posts_collected = len(await page.query_selector_all("article"))
            if posts_collected >= max_posts:
                break

    async def _parse_post(self, element):
        """Parse a single post element into a Post model."""
        try:
            tweet_id = await element.get_attribute("data-testid") or "unknown"
            text_element = await element.query_selector("div[lang]")
            text = await text_element.inner_text() if text_element else "No text"
            username_element = await element.query_selector("a[role='link']")
            username = (
                await username_element.inner_text() if username_element else "unknown"
            )
            time_element = await element.query_selector("time")
            created_at = (
                await time_element.get_attribute("datetime")
                if time_element
                else "unknown"
            )
            return Post(
                id=tweet_id, text=text, username=username, created_at=created_at
            )
        except Exception as e:
            logger.error(f"Error parsing post: {e}")
            return None

    async def crawl_x_posts(
        self, keyword: str = "bitcoin", max_posts: int = 5
    ) -> CrawlerResponse:
        """Crawl X for posts related to the given keyword."""
        posts = []
        async with async_playwright() as playwright:
            browser = await self._launch_browser(playwright)
            try:
                page = await self._create_page(browser)
                await self._navigate_to_search(page, keyword)
                await self._scroll_page(page, max_posts)

                post_elements = await page.query_selector_all("article")
                for element in post_elements[:max_posts]:
                    post = await self._parse_post(element)
                    if post:
                        posts.append(post)

            except Exception as e:
                logger.error(f"Error during crawling: {e}")
            finally:
                await browser.close()

        return CrawlerResponse(posts=posts, count=len(posts), keyword=keyword)
