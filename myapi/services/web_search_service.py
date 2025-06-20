from datetime import date
from typing import Literal

import openai

from myapi.domain.news.news_models import MarketForecast
from myapi.domain.news.news_schema import MarketForecastResponse, MarketForecastSchema
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

    def _build_prompt(
        self, today: str, source: Literal["Major", "Minor"] = "Major"
    ) -> str:
        return f"""
        ### Role
        You are a veteran U.S. equity strategist with a strong macro-economic background.

        ### Task
            Using **only** information published on {today} On Internet, determine whether the
            S&P 500 and Nasdaq Composite are *most likely* to **close higher or lower**
            than yesterday’s close. Explain the key drivers succinctly.

        ### Rules
            1. Do **not** rely on any source not dated {today}.
            {"2. Cite at least three independent, reputable sources (major financial news outlets, government releases, or primary data providers)." if source == "Major" else ""}
            {"2. Cite at least three independent Community Source (like 'X[Tweet]', 'Reddit', 'Facebook[Threads]') " if source == "Minor" else ""}
            3. Be concise – three to five bullet points of reasoning maximum.

        ### Response
        {{
            \n 
                \"outlook\": \"UP or DOWN (required)\"\n 
                \"reason\": \"Why Today {today} Up or Down With Refrences (required) \"\n,
                \"up_percentage\": "int"% eg. "70" (required)\n
            \n
        }}
        \n
        """

    def forecast_market(self, today: date, source: Literal["Major", "Minor"] = "Major"):
        today_str = today.strftime("%Y-%m-%d")
        # cached = self.websearch_repository.get_by_date(today_str)

        # if cached:
        #     return cached

        prompt = self._build_prompt(today_str, source)

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
                up_percentage=response.up_percentage,
            )
        )

        return response
