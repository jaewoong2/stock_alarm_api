from datetime import date, timedelta
from typing import Literal
from fastapi import HTTPException


from myapi.domain.news.news_models import MarketForecast
from myapi.domain.news.news_schema import (
    MahaneyAnalysisResponse,
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

    async def create_market_forecast(
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

        await self.websearch_repository.create(
            MarketForecast(
                date_yyyymmdd=end_date,
                outlook=response.outlook,
                reason=response.reason,
                up_percentage=response.up_percentage,
                source=source,
            )
        )

        cached = await self.websearch_repository.get_by_date(
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
            today, analysis.model_dump(), name="market_analysis"
        )
        return analysis

    def generate_mahaney_prompt(self, tickers: list[str], target_date: str) -> str:
        if not isinstance(tickers, list) or not tickers:
            raise ValueError("Tickers must be a non-empty list of stock tickers.")

        if not isinstance(tickers, list) or not tickers:
            raise ValueError("Tickers must be a non-empty list of stock tickers.")
        tickers = sorted(
            set([t.upper() for t in tickers])
        )  # dedupe & sort for reproducibility
        ticker_list = ", ".join(tickers)

        prompt = f"""
            Today is **{target_date}**.

            You are **Gemini Pro Portfolio** – a finance-specialised AI with Google Search grounding.  
            Your job is to evaluate the following U.S.-listed tech tickers:

            [{ticker_list}]
            against **Mark Mahaney’s 7-step checklist** (see below).  
            Return **two clearly separated sections**:

            1. **Reasoning (Log)** – your step-by-step thoughts *for each ticker & criterion*  
            2. **Result (JSON)** – a machine-readable summary that downstream code can parse

            ---

            ### Mahaney 7-Step Checklist  *(from “Nothing But Net”)*

            | # | Criterion |
            |---|----------------------|
            | 1 | **Revenue Growth – 20 % Rule**: YoY revenue (or core KPI) ≥ 20 % for the last 5–6 quarters |
            | 2 | **Valuation – 2 % Rule**: PEG ≤ 1 **OR** P/E or P/S looks cheap vs growth (PEG≈1) |
            | 3 | **Product Innovation**: faster release cadence & rising R&D intensity |
            | 4 | **Total Addressable Market (TAM)** ≥ $1 T **OR** single-digit share with credible expansion |
            | 5 | **Customer Value Proposition**: high NPS / retention / usage growth |
            | 6 | **Management Quality**: visionary CEO/CFO, solid execution, material insider ownership |
            | 7 | **Timing**: price ≥ 20 % below 52-week high **OR** PEG < 1 |
            ---

            ### Data-gathering rules (use Google Search)

            * Prefer **2024–2025** company filings, earnings calls, Investor Relations decks  
            * Cross-check with reputable aggregators (Yahoo Finance, Morningstar, FactSet)  
            * Cite **at least 3 independent sources per ticker**; include publication date in the citation  
            * Ignore rumours or unverified blogs
            ---

            ### Output requirements

            #### 1) Reasoning (Log)
            Write a concise chain-of-thought for every *(ticker, criterion)* pair.  
            Prefix each ticker with `### TICKER: <symbol>` to keep logs readable.

            #### 2) Result (JSON)
            Return exactly one JSON object with this schema:

            ```json
            {{
                "as_of": "{target_date}",
                "stocks": {{
                    "XYZ": {{
                    "revenue_growth": {{
                        "pass": true,
                        "metric": "50,45,40,55,60",
                        "comment": "5 straight qtrs ≥ 40 %",
                        "sources": ["source-id-1", "source-id-2"]
                    }},
                    "valuation": {{ "pass": true, "peg": 0.8, "sources": [...] }},
                    "product_innovation": {{ "score": 5, "comment": "...", "sources": [...] }},
                    ...
                    "timing": {{ "pass": false, "price_vs_high": "-8 %", "sources": [...] }},
                    "final_assessment": "Watch"  // "Pass" if ≥6 YES else "Watch"
                    "recommendation": "Buy" | "Sell" | "Hold" // "Buy", "Sell", "Hold", or "Watch"
                    "recommendation_score": "..."  // Why this recommendation
                    }},
                    "...": {{}}
                }}
            }}
            Use snake_case keys exactly as shown
            For YES/NO criteria set "pass": true/false. For qualitative ones include "score": 1–5.
            If missing data, set the value to null and explain in "comment".
            """

        return prompt

    async def create_mahaney_analysis(
        self, tickers: list[str], target_date: date = date.today()
    ):
        """Create Mahaney analysis for the given tickers using the AI service."""
        if not tickers:
            raise ValueError("Tickers list cannot be empty")

        prompt = self.generate_mahaney_prompt(tickers, target_date.strftime("%Y-%m-%d"))

        response = self.ai_service.gemini_search_grounding(
            prompt=prompt,
            schema=MahaneyAnalysisResponse,
        )

        if not isinstance(response, MahaneyAnalysisResponse):
            raise ValueError("Invalid response format from AI service")

        self.websearch_repository.create_analysis(
            analysis_date=target_date,
            analysis=response.response.model_dump(),
            name="mahaney_analysis",
        )

        return response.response

    async def get_mahaney_analysis(self, target_date: date = date.today()):
        """Fetch Mahaney analysis for the given tickers."""

        response = self.websearch_repository.get_analysis_by_date(
            analysis_date=target_date,
            name="mahaney_analysis",
            schema=MahaneyAnalysisResponse,
        )

        if not isinstance(response, MahaneyAnalysisResponse):
            raise ValueError("Invalid response format from AI service")

        return response
