import aiohttp
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import html
import logging
import re
from typing import List
import requests

from myapi.domain.news.news_schema import Article
from myapi.domain.signal.signal_schema import NewsHeadline
from myapi.services.translate_service import TranslateService
from myapi.utils.config import Settings

logger = logging.getLogger(__name__)


class NewsService:
    """뉴스 관련 서비스"""

    def __init__(self, settings: Settings, translate_service: TranslateService):
        self.settings = settings
        self.translate_service = translate_service
        self.logger = logging.getLogger(__name__)

    def fetch_news(
        self, ticker: str, days_back: int = 5, max_items: int = 5
    ) -> List[NewsHeadline]:
        """특정 티커의 뉴스 헤드라인 조회"""
        try:
            url = "https://newsapi.org/v2/everything"
            params = {
                "q": ticker,
                "language": "en",
                "from": (date.today() - timedelta(days=days_back)).isoformat(),
                "sortBy": "relevancy",
                "pageSize": max_items,
                "apiKey": self.settings.NEWS_API_KEY,
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            articles = response.json().get("articles", [])

            headlines = [
                NewsHeadline(
                    title=article["title"],
                    url=article["url"],
                    sentiment=None,
                )
                for article in articles
            ]

            # 번역 서비스가 있으면 번역 수행
            if self.translate_service:
                return self._translate_headlines(headlines)

            return headlines

        except Exception as e:
            self.logger.warning(f"Failed to fetch news for {ticker}: {e}")
            return []

    def _translate_headlines(self, headlines: List[NewsHeadline]) -> List[NewsHeadline]:
        """헤드라인 번역"""
        translated_headlines = []
        for headline in headlines:
            try:
                translated = self.translate_service.translate_schema(headline)
                translated_headlines.append(translated)
            except Exception as e:
                self.logger.warning(f"Failed to translate headline: {e}")
                translated_headlines.append(headline)
        return translated_headlines

    async def get_today_market_articles(self) -> List[Article]:
        """오늘 시장 관련 기사 조회"""
        items = await self._fetch_naver_news_page(start=1)

        three_days_ago = datetime.now(timezone.utc).astimezone().date() - timedelta(
            days=3
        )
        today = datetime.now(timezone.utc).astimezone().date()

        articles = [
            Article(
                id=item["link"],
                title=html.unescape(re.sub(r"</?b>", "", item["title"])),
                summary=html.unescape(re.sub(r"</?b>", "", item["description"])),
                url=item["originallink"] or item["link"],
                published=parsedate_to_datetime(item["pubDate"]),
                category="naver",
            )
            for item in items
            if (
                parsedate_to_datetime(item["pubDate"]).date() >= three_days_ago
                and parsedate_to_datetime(item["pubDate"]).date() <= today
            )
        ]

        # 번역 서비스가 있으면 번역 수행
        if self.translate_service:
            return self._translate_articles(articles)

        return articles

    def _translate_articles(self, articles: List[Article]) -> List[Article]:
        """기사 번역"""
        translated_articles = []
        for article in articles:
            try:
                translated = self.translate_service.translate_schema(article)
                translated_articles.append(translated)
            except Exception as e:
                self.logger.warning(f"Failed to translate article: {e}")
                translated_articles.append(article)
        return translated_articles

    async def _fetch_naver_news_page(self, start: int = 1) -> List[dict]:
        """네이버 뉴스 API로 시장 뉴스 조회"""
        naver_base = "https://openapi.naver.com/v1/search/news.json"
        queries = ["nasdaq", "s&p500"]
        items = []

        for query in queries:
            params = {"query": query, "display": 100, "start": start, "sort": "date"}

            async with aiohttp.ClientSession(
                headers={
                    "X-Naver-Client-Id": self.settings.NAVER_CLIENT_ID,
                    "X-Naver-Client-Secret": self.settings.NAVER_CLIENT_SECRET,
                }
            ) as session:
                async with session.get(naver_base, params=params) as response:
                    response.raise_for_status()
                    data = await response.json()
                    items.extend(data["items"])

        if not items:
            return []

        # 날짜순 정렬 후 최대 100개만 반환
        items.sort(key=lambda x: x["pubDate"], reverse=True)
        return items[:100]
