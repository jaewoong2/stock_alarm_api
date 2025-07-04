from datetime import date, timedelta
from typing import Literal


from myapi.domain.news.news_models import MarketForecast
from myapi.domain.news.news_schema import (
    MarketForecastResponse,
    MarketForecastSchema,
    SectorMomentumResponse,
)
from myapi.repositories.web_search_repository import WebSearchResultRepository
from myapi.services.ai_service import AIService


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
            {"2. Cite at least three independent, reputable sources (major financial news outlets, Analyst Reports, or primary data providers)." if source == "Major" else ""}
            {"2. Cite at least three independent Community Source (like 'X[Tweet]', 'Reddit', 'Facebook[Threads]', 'Youtube') " if source == "Minor" else ""}
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
        #  2주간 움직임
        start_date = (today - timedelta(days=6)).strftime("%Y-%m-%d")
        end_date = (today).strftime("%Y-%m-%d")

        cached = self.websearch_repository.get_by_date(
            start_date_yyyymmdd=start_date, end_date_yyyymmdd=end_date, source=source
        )

        if cached:
            cached_latest = cached[-1]

            if isinstance(cached_latest, MarketForecastSchema):
                if cached_latest.date_yyyymmdd == end_date:
                    return cached

        prompt = self._build_prompt(end_date, source)

        response = self.ai_service.perplexity_completion(
            prompt=prompt,
            schema=MarketForecastResponse,
        )

        if not isinstance(response, MarketForecastResponse):
            raise ValueError("Invalid response format from AI service")

        created = self.websearch_repository.create(
            MarketForecast(
                date_yyyymmdd=end_date,
                outlook=response.outlook,
                reason=response.reason,
                up_percentage=response.up_percentage,
                source=source,
            )
        )

        cached = self.websearch_repository.get_by_date(
            start_date_yyyymmdd=start_date,
            end_date_yyyymmdd=end_date,
            source=source,
        )

        if cached:
            return cached

        return [created]

    def _build_sector_prompt(self, today: str) -> str:
        return f"""
미국 동부 시간(EST) 기준 오늘 ({today}) 증시 개장 전에, 단기(1~3일) 트레이딩 관점에서 가장 강력한 모멘텀이 예상되는 상위 3개 섹터를 분석하고, 그 핵심 배경을 구체적으로 설명해 줘.

각 섹터별로 가장 주목해야 할 핵심 테마와 해당 테마의 주도주들을 아래의 JSON 형식에 맞춰 제공해 줘.

{SectorMomentumResponse.model_json_schema()}
"""

    def analyze_sector_momentum(self, today: date) -> SectorMomentumResponse:
        prompt = self._build_sector_prompt(today.strftime("%Y-%m-%d"))
        response = self.ai_service.perplexity_completion(
            prompt=prompt,
            schema=SectorMomentumResponse,
        )

        if not isinstance(response, SectorMomentumResponse):
            raise ValueError("Invalid response format from AI service")

        return response
