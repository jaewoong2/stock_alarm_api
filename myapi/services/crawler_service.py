import asyncio, os
import time
from typing import Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, HttpUrl
from playwright.async_api import async_playwright, TimeoutError as PwTimeoutError
from mangum import Mangum

from playwright.async_api import async_playwright, Browser, Page, Playwright


# ---------- Pydantic models ---------- #
class CrawlerRequest(BaseModel):
    url: HttpUrl
    selector: Optional[str] = Field(
        None, description="가져올 DOM 영역 CSS 셀렉터(없으면 <main>/<body>)"
    )
    wait_ms: int = Field(2000, ge=0, description="스크롤 후 추가 대기(ms)")


class CrawlerResponse(BaseModel):
    url: HttpUrl
    title: Optional[str]
    html: str


class CrawlerService:
    """SPA 페이지 전용 크롤러 서비스 (Playwright 싱글턴 재사용)."""

    # ───── 클래스(전역) 리소스 ──────────────────────────
    _playwright: Optional[Playwright] = None
    _browser: Optional[Browser] = None
    _lock = asyncio.Lock()  # 동시 콜드스타트 방지

    # ───── 인스턴스 설정 ──────────────────────────────
    def __init__(self, default_wait_ms: int = 2000) -> None:
        """
        :param default_wait_ms: 스크롤 완료 후 추가 대기 시간(ms)
        """
        self.default_wait_ms = default_wait_ms

    # ───── 내부 유틸 ───────────────────────────────────
    async def _ensure_browser(self) -> Browser:
        """
        싱글턴 브라우저를 생성·캐시. Cold Start 시에만 launch.
        """
        async with self._lock:
            if self.__class__._browser is None:
                self.__class__._playwright = await async_playwright().start()
                self.__class__._browser = (
                    await self.__class__._playwright.chromium.launch(
                        headless=True,
                        args=["--no-sandbox", "--disable-gpu"],
                    )
                )
        return self.__class__._browser

    async def _auto_scroll(self, page: Page) -> None:
        """lazy‑load·무한스크롤 대응 전역 스크롤."""
        await page.evaluate(
            """
            async () => {
                const distance = 1024;
                while (document.scrollingElement.scrollTop + innerHeight <
                       document.scrollingElement.scrollHeight) {
                    document.scrollingElement.scrollBy(0, distance);
                    await new Promise(r => setTimeout(r, 100));
                }
            }
            """
        )

    async def fetch_html(
        self,
        url: str,
        selector: Optional[str] = None,
        wait_ms: Optional[int] = None,
    ):
        browser = await self._ensure_browser()
        context = await browser.new_context()
        page = await context.new_page()

        try:
            await page.goto(url, wait_until="networkidle")
            await self._auto_scroll(page)
            await page.wait_for_load_state("networkidle")

            # 추가 지연
            await page.wait_for_timeout(wait_ms or self.default_wait_ms)

            # ② fallback: DOM 안정화 heuristics
            # await self._wait_until_dom_stable(page)

            # 대상 영역 추출
            element = (
                await page.query_selector(selector)
                if selector
                else await page.query_selector("main")
                or await page.query_selector("body")
            )

            if not element:
                raise RuntimeError("지정 selector를 찾지 못했습니다.")

            html = await element.inner_html()
            title = await page.title()
            return html, title

        finally:
            await context.close()  # 컨텍스트만 닫고 브라우저는 재사용
            await self.close()

    async def close(self) -> None:
        """Lambda 종료 전 자원 해제(옵션)."""
        if self.__class__._browser:
            await self.__class__._browser.close()
            self.__class__._browser = None
        if isinstance(self.__class__._playwright, Playwright):
            await self.__class__._playwright.stop()  # Not awaitable
            self.__class__._playwright = None

    # ───── DOM 안정화 헬퍼 ────────────────────────────
    async def _wait_until_dom_stable(
        self,
        page: Page,
        check_interval: float = 0.5,  # 초
        stable_duration: float = 1.0,  # 변동 없이 유지돼야 하는 시간
        timeout: float = 10.0,  # 총 대기 한도
    ) -> None:
        """
        DOM 크기 및 텍스트 길이가 일정 시간 변하지 않으면 반환.
        (네트워크 idle 이후 추가 로딩·애니메이션 대응)
        """
        start_time = time.time()
        last_change = time.time()
        prev_len, prev_height = None, None

        while time.time() - start_time < timeout:
            # 현재 메트릭 측정
            curr_len, curr_height = await page.evaluate(
                """() => [document.body.innerText.length,
                          document.scrollingElement.scrollHeight]"""
            )
            if (curr_len, curr_height) != (prev_len, prev_height):
                # 변화 감지 → 타이머 리셋
                prev_len, prev_height = curr_len, curr_height
                last_change = time.time()
            else:
                # 변화가 없는데 stable_duration 충족?
                if time.time() - last_change >= stable_duration:
                    return
            await asyncio.sleep(check_interval)
        # timeout 초과 시 경고만 남기고 진행
        print("[WARN] DOM 안정화 시간 초과")
