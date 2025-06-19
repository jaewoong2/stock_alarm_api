from datetime import date

import openai

from myapi.domain.news.news_models import MarketForecast
from myapi.domain.news.news_schema import MarketForecastResponse
from myapi.repositories.web_search_repository import WebSearchResultRepository
from myapi.services.ai_service import AIService
from myapi.utils.config import Settings


class WebSearchService:
    def __init__(
        self,
        websearch_repository: WebSearchResultRepository,
        ai_service: AIService,
    ):
        self.websearch_repository = websearch_repository
        self.ai_service = ai_service

    def _build_prompt(self, today: str) -> str:
        return f"""
You are a market news assistant.
Your goal is to determine if the U.S. stock market (S&P 500 and Nasdaq) will rise or fall today ({today}).
Follow these steps:
1. Search the web for headlines, economic releases and futures movements published on {today} only.
2. Based on this information, decide whether the market is likely to go up or down today and explain why.
Respond in English using the JSON format:\n{{\n  \"outlook\": \"UP or DOWN\",\n  \"reason\": \"short justification\"\n}}"""

    def forecast_market(self, today: date) -> MarketForecastResponse:
        today_str = today.strftime("%Y-%m-%d")
        cached = self.websearch_repository.get_by_date(today_str)

        if cached:
            return MarketForecastResponse(outlook=cached.outlook, reason=cached.reason)

        prompt = self._build_prompt(today_str)

        response = self.ai_service.perplexity_completion(
            prompt=prompt,
            schema=MarketForecastResponse,
        )

        if not isinstance(response, MarketForecastResponse):
            raise ValueError("Invalid response format from AI service")

        self.websearch_repository.create(
            MarketForecast(
                date_yyyymmdd=today_str,
                outlook=response.outlook,
                reason=response.reason,
            )
        )

        return response
