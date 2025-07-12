from datetime import date, timedelta
from typing import Literal
from fastapi import HTTPException


from myapi.domain.news.news_models import MarketForecast
from myapi.domain.news.news_schema import (
    MarketForecastResponse,
    MarketForecastSchema,
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

    async def get_market_forecast(
        self, today: date, source: Literal["Major", "Minor"] = "Major"
    ):
        """Return cached market forecast if available."""

        start_date = (today - timedelta(days=6)).strftime("%Y-%m-%d")
        end_date = today.strftime("%Y-%m-%d")

        cached = await self.websearch_repository.get_by_date(
            start_date_yyyymmdd=start_date, end_date_yyyymmdd=end_date, source=source
        )

        if cached:
            return cached

        raise HTTPException(status_code=404, detail="Forecast not found")

    def create_market_forecast(
        self, today: date, source: Literal["Major", "Minor"] = "Major"
    ):
        """Create a new market forecast using the AI service."""

        start_date = (today - timedelta(days=6)).strftime("%Y-%m-%d")
        end_date = today.strftime("%Y-%m-%d")

        prompt = self._build_prompt(end_date, source)

        response = self.ai_service.perplexity_completion(
            prompt=prompt,
            schema=MarketForecastResponse,
        )

        if not isinstance(response, MarketForecastResponse):
            raise ValueError("Invalid response format from AI service")

        self.websearch_repository.create(
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

        return cached if cached else []

    def _build_market_analysis_prompt(self, today: str) -> str:
        return f"""
        ## Advanced Prompt (copy & paste)

        > **“As of U.S. Eastern Time *prior to today’s cash-market open* (EST), analyze the top *three* sectors with the strongest expected **1-to-3-day momentum** for short-term trading.”**
        >
        > 1. Begin with a **one-paragraph market overview** that summarizes the today`s macro backdrop and lists up to three *major catalysts* (time-stamped in EST).
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
            "summary": "<75-word summary of today`s macro conditions and predict market direction>",
            "major_catalysts": [
                "<Today`s key catalyst 1 with timestamp in EST> And Senario",
                "<Today`s key catalyst 2 with timestamp in EST> And Senario",
                "<Today`s key catalyst 3 with timestamp in EST> And Senario"
            ]
        }},
        "top_momentum_sectors": [
            {{
            "sector_ranking": 1,
            "sector": "<name>",
            "reason": "<why momentum is strongest with rationale and how to move the prices>",
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
                    "short_term_strategy": "If <technical or news condition>, consider <actionable trade idea with entry/exit levels or triggers>. forcast: <short-term price target with rationale>"
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

    def get_market_analysis(self, today: date):
        """Return cached market analysis if available."""
        cached = self.websearch_repository.get_analysis_by_date(
            today, name="market_analysis"
        )
        if cached:
            return MarketAnalysis.model_validate(cached.value)

        raise HTTPException(status_code=404, detail="Analysis not found")

    def create_market_analysis(self, today: date):
        """Generate and store market analysis using the AI service."""

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
        self.websearch_repository.create_analysis(
            today, analysis, name="market_analysis"
        )
        return analysis
