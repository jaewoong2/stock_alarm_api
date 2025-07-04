from datetime import date, timedelta
from typing import Literal
from fastapi import HTTPException


from myapi.domain.news.news_models import MarketForecast
from myapi.domain.news.news_schema import (
    MarketForecastResponse,
    MarketForecastSchema,
    SectorMomentumResponse,
    MarketAnalysis,
    MarketAnalysisResponse,
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

    def _build_market_analysis_prompt(self, today: str) -> str:
        return f"""
        ## Advanced Prompt (copy & paste)

        > **“As of U.S. Eastern Time *prior to today’s cash-market open* (EST), analyze the top *three* sectors with the strongest expected **1-to-3-day momentum** for short-term trading.”**
        >
        > 1. Begin with a **one-paragraph market overview** that summarizes the overnight macro backdrop and lists up to three *major catalysts* (time-stamped in EST).
        > 2. Rank the three sectors by momentum strength (1 = highest).
        > 3. For each sector, provide the details below in **valid JSON** that the system can parse.
        > 4. Your analysis must explain not only **what** is happening but also **why** it matters and **how** traders might act.
        > 5. Support every key point with a concrete **news or data source** (include publication name and time).
        > 6. Use concise, punchy language; avoid generic statements.”**

        ### JSON schema & field guidelines
        ```json
        {{
        "analysis_date_est": "{today}",
        "market_overview": {{
            "summary": "<75-word snapshot of the overnight session>",
            "major_catalysts": [
            "EST HH:MM - <event one>",
            "EST HH:MM - <event two>",
            "EST HH:MM - <event three>"
            ]
        }},
        "top_momentum_sectors": [
            {{
            "sector_ranking": 1,
            "sector": "<name>",
            "reason": "<2-3 sentences on why momentum is strongest>",
            "risk_factor": "<specific near-term threat that could stall the move>",
            "themes": [
                {{
                "key_theme": "<dominant intra-sector theme>",
                "stocks": [
                    {{
                    "ticker": "<symbol>",
                    "name": "<company name>",
                    "pre_market_change": "<price % and relative volume versus 30-day avg>",
                    "key_news": {{
                        "headline": "<single most impactful headline>",
                        "source": "<publication>",
                        "summary": "<1-sentence essence>"
                    }},
                    "short_term_strategy": "If <technical or news condition>, consider <actionable trade idea with entry/exit levels or triggers>."
                    }}
                ]
                }}
            ]
            }},
            {{ /* repeat for sector_ranking 2 */ }},
            {{ /* repeat for sector_ranking 3 */ }}
        ]
        }}
        """

    def get_market_analysis(self, today: date) -> MarketAnalysis:
        cached = self.websearch_repository.get_analysis_by_date(today)
        if cached:
            return MarketAnalysis.model_validate(cached.value)

        prompt = self._build_market_analysis_prompt(today.strftime("%Y-%m-%d"))
        try:
            response = self.ai_service.perplexity_completion(
                prompt=prompt,
                schema=MarketAnalysisResponse,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

        if not isinstance(response, MarketAnalysisResponse):
            raise ValueError("Invalid response format from AI service")

        analysis = response.analysis
        self.websearch_repository.create_analysis(today, analysis)
        return analysis
