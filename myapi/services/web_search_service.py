from datetime import date, timedelta
from typing import Literal, Optional, List, Tuple, Any, Type
from fastapi import HTTPException
import logging
import hashlib
import json

from myapi.services.translate_service import TranslateService

logger = logging.getLogger(__name__)


from myapi.domain.news.news_models import MarketForecast
from myapi.domain.news.news_schema import (
    MahaneyAnalysisResponse,
    MahaneyAnalysisGetRequest,
    MahaneyAnalysisGetResponse,
    MahaneyStockAnalysis,
    MarketAnalysis,
    MarketAnalysisResponse,
    MarketForecastResponse,
    MarketOverview,
    ETFAnalysisResponse,
    ETFAnalysisGetRequest,
    ETFAnalysisGetResponse,
    ETFPortfolioData,
    ETFAnalystSummaryResponse,
    InsiderTrendResponse,
    InsiderTradeItem,
    InsiderTrendGetRequest,
    InsiderTrendGetResponse,
    AnalystPTResponse,
    AnalystPTItem,
    AnalystPTGetRequest,
    AnalystPTGetResponse,
    ETFWeeklyFlowResponse,
    ETFFlowItem,
    ETFWeeklyFlowGetRequest,
    ETFWeeklyFlowGetResponse,
    LiquidityWeeklyResponse,
    LiquidityPoint,
    MarketBreadthResponse,
    BreadthDailyPoint,
    FundamentalAnalysisResponse,
    FundamentalAnalysisGetRequest,
    FundamentalAnalysisGetResponse,
)
from myapi.repositories.web_search_repository import WebSearchResultRepository
from myapi.services.ai_service import AIService


class WebSearchService:
    def __init__(
        self,
        websearch_repository: WebSearchResultRepository,
        ai_service: AIService,
        translate_service: TranslateService,
    ):
        self.websearch_repository = websearch_repository
        self.ai_service = ai_service
        self.translate_service = translate_service

    def _hash_prompt(self, prompt: str) -> str:
        return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12]

    def _pair_results_with_models(self, results: List[Any], provenance: List[dict]) -> List[tuple[Any, str | None]]:
        models = [p.get("model") for p in provenance if p.get("used")]
        paired: List[tuple[Any, str | None]] = []
        for idx, r in enumerate(results):
            m = models[idx] if idx < len(models) else None
            paired.append((r, m))
        return paired

    def run_llm(
        self,
        policy: Literal["AUTO", "GEMINI", "PERPLEXITY", "BOTH", "FALLBACK", "HYBRID"] = "AUTO",
        prompt: str = "",
        schema: Type[Any] | None = None,
    ) -> Tuple[List[Any], str, List[dict]]:
        resolved = policy
        provenance: List[dict] = []
        results: List[Any] = []

        if policy == "AUTO":
            resolved = "FALLBACK"

        prompt_hash = self._hash_prompt(prompt)

        def call_perplexity() -> Any:
            if schema is None:
                raise ValueError("schema is required for perplexity_completion")
            r = self.ai_service.perplexity_completion(prompt=prompt, schema=schema)
            provenance.append({"model": "PERPLEXITY", "prompt_hash": prompt_hash, "used": r is not None})
            return r

        def call_gemini() -> Any:
            if schema is None:
                raise ValueError("schema is required for gemini_search_grounding")
            r = self.ai_service.gemini_search_grounding(prompt=prompt, schema=schema)
            provenance.append({"model": "GEMINI", "prompt_hash": prompt_hash, "used": r is not None})
            return r

        try:
            if resolved == "GEMINI":
                r = call_gemini()
                if r is not None:
                    results.append(r)
            elif resolved == "PERPLEXITY":
                r = call_perplexity()
                if r is not None:
                    results.append(r)
            elif resolved == "BOTH":
                r1 = call_perplexity()
                r2 = call_gemini()
                if r1 is not None:
                    results.append(r1)
                if r2 is not None:
                    results.append(r2)
            elif resolved == "FALLBACK":
                try:
                    r = call_perplexity()
                    if r is not None:
                        results.append(r)
                    else:
                        raise ValueError("Empty response")
                except Exception:
                    r2 = call_gemini()
                    if r2 is not None:
                        results.append(r2)
            elif resolved == "HYBRID":
                r1 = None
                try:
                    r1 = call_perplexity()
                except Exception:
                    pass
                r2 = None
                try:
                    r2 = call_gemini()
                except Exception:
                    pass
                if r1 is not None:
                    results.append(r1)
                if r2 is not None:
                    results.append(r2)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"LLM invocation failed: {e}")

        return results, resolved, provenance

    def _merge_results(self, schema: Any, results: List[Any]) -> Any:
        if not results:
            return None
        # If results are same type and have 'items', union items by JSON string
        try:
            first = results[0]
            if hasattr(first, "items"):
                seen = set()
                merged_items = []
                for r in results:
                    try:
                        for it in getattr(r, "items", []) or []:
                            key = json.dumps(it.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)
                            if key not in seen:
                                seen.add(key)
                                merged_items.append(it)
                    except Exception:
                        continue
                window = getattr(first, "window", None)
                try:
                    return schema(items=merged_items, window=window)
                except Exception:
                    return first
            # LiquidityWeeklyResponse: merge series
            if hasattr(first, "series_m2") and hasattr(first, "series_rrp"):
                def merge_series(attr):
                    seen_dates = set()
                    out = []
                    for r in results:
                        for p in getattr(r, attr, []) or []:
                            d = getattr(p, "date", None)
                            if d and d not in seen_dates:
                                seen_dates.add(d)
                                out.append(p)
                    out.sort(key=lambda x: getattr(x, "date", ""))
                    return out

                return schema(
                    series_m2=merge_series("series_m2"),
                    series_rrp=merge_series("series_rrp"),
                    commentary=getattr(first, "commentary", None),
                    window=getattr(first, "window", None),
                )
            # MarketBreadthResponse: merge series
            if hasattr(first, "series"):
                seen_dates = set()
                out = []
                for r in results:
                    for p in getattr(r, "series", []) or []:
                        d = getattr(p, "date", None)
                        if d and d not in seen_dates:
                            seen_dates.add(d)
                            out.append(p)
                out.sort(key=lambda x: getattr(x, "date", ""))
                return schema(series=out, commentary=getattr(first, "commentary", None))
        except Exception:
            return results[0]
        return results[0]

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

        try:
            start_date = (today - timedelta(days=6)).strftime("%Y-%m-%d")
            end_date = today.strftime("%Y-%m-%d")

            cached = self.websearch_repository.get_by_date(
                start_date_yyyymmdd=start_date,
                end_date_yyyymmdd=end_date,
                source=source,
            )

            if cached:
                return cached

            raise HTTPException(status_code=404, detail="Forecast not found")
        except HTTPException:
            # HTTPException은 다시 raise
            raise
        except Exception as e:
            # 다른 모든 예외는 500 에러로 변환
            raise HTTPException(
                status_code=500,
                detail=f"Internal server error while fetching market forecast: {str(e)}",
            )

    async def create_market_forecast(
        self, today: date, source: Literal["Major", "Minor"] = "Major"
    ):
        """Create a new market forecast using the AI service."""

        try:
            start_date = (today - timedelta(days=6)).strftime("%Y-%m-%d")
            end_date = today.strftime("%Y-%m-%d")

            prompt = self._build_prompt(end_date, source)

            response = self.ai_service.perplexity_completion(
                prompt=prompt,
                schema=MarketForecastResponse,
            )

            response = self.translate_service.translate_schema(response)

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
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Internal server error while creating market forecast: {str(e)}",
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

        return MarketAnalysis(
            analysis_date_est=today.strftime("%Y-%m-%d"),
            market_overview=MarketOverview(
                summary="",
                major_catalysts=[],
            ),
            top_momentum_sectors=[],
        )

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

        # Translate analysis if translate_service is available
        try:
            analysis = self.translate_service.translate_schema(analysis)
        except Exception as e:
            logger.warning(f"Failed to translate market analysis: {e}")

        self.websearch_repository.create_analysis(
            today, analysis.model_dump(), name="market_analysis"
        )
        return analysis

    def generate_mahaney_prompt(self, tickers: list[str], target_date: str) -> str:
        if not isinstance(tickers, list) or not tickers:
            raise ValueError("Tickers must be a non-empty list of stock tickers.")

        tickers = sorted(
            set([t.upper() for t in tickers])
        )  # dedupe & sort for reproducibility

        ticker_list = ", ".join(tickers)

        prompt = f"""
            Today is **{target_date}**.

            You are a finance-specialised AI with Google Search grounding.  
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
            | 1 | **Revenue Growth – 20 % Rule**: YoY revenue (or core KPI) ≥ 20 % for the last 4 quarters |
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
            * Forecast **short-term price targets** based on the Analysis
            * And Then, Find The Social Media Sentiment (X, Reddit, etc.) for each ticker
            * Today is {target_date} search and think ALL Recent of {target_date}ㅑ
            ---

            ### Output requirements

            #### 1) Reasoning (Log)
            Write a concise chain-of-thought for every *(ticker, criterion)* pair.  
            Prefix each ticker with `### TICKER: <symbol>` to keep logs readable.

            #### 2) Result (JSON)
            * score is 1-5 for qualitative criteria, true/false for YES/NO
            Return exactly one JSON object with this schema:

            ```json
            {{
                "as_of": " Today is {target_date}",
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
                    "summary": "..."  // Detail summary of the analysis
                    }},
                    "...": {{}}
                }}
            }}
            Use snake_case keys exactly as shown
            For YES/NO criteria set "pass": true/false. For qualitative ones include "score": 1–5.
            If missing data, set the value to null and explain in "comment".
            """

        return prompt

    def generate_insider_trend_prompt(self, tickers: list[str] | None, target_date: str) -> str:
        ticker_list = ", ".join(sorted(set([t.upper() for t in tickers])) ) if tickers else "ALL"
        return f"""
        Today is {target_date}.
        Task: Summarize insider transactions (SEC Form 4 or equivalent) in the last 7 days for tickers [{ticker_list}].
        RULES:
        - STRICT JSON ONLY (no prose). Use the exact keys below.
        - Include ≥2 credible sources per item with confidence 0.0~1.0.
        - Uppercase tickers. Use null when unknown.
        SCHEMA:
        {{
          "items": [{{
            "ticker": "AAPL",
            "insider_name": "John Doe",
            "insider_role": "CEO",
            "action": "BUY",
            "shares": 15000,
            "est_value": 2550000.0,
            "rationale": "Open market purchase after earnings beat",
            "sources": ["SEC Form 4", "Bloomberg"],
            "source_details": [{{"name": "SEC Form 4", "url": "https://...", "date": "{target_date}", "confidence": 0.95}}],
            "source_confidence": 0.9,
            "filing_url": "https://sec.gov/...",
            "cik": "0000320193",
            "date": "{target_date}"
          }}],
          "window": "YYYY-MM-DD~YYYY-MM-DD"
        }}
        """

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

        for stock in response.response.stocks:
            if not isinstance(stock, MahaneyStockAnalysis):
                raise ValueError("Invalid stock data format in response")

            # Translate stock analysis if translate_service is available
            translated_stock = stock
            if self.translate_service:
                try:
                    translated_stock = self.translate_service.translate_schema(stock)
                    translated_stock.stock_name = stock.stock_name.upper()
                except Exception as e:
                    logger.warning(
                        f"Failed to translate Mahaney analysis for {stock.stock_name}: {e}"
                    )

            self.websearch_repository.create_analysis(
                analysis_date=target_date,
                analysis=translated_stock.model_dump(),
                name="mahaney_analysis",
            )

        return response.response

    async def get_mahaney_analysis(
        self, target_date: date = date.today(), tickers: Optional[list[str]] = None
    ):
        """Fetch Mahaney analysis for the given tickers."""

        responses = self.websearch_repository.get_all_analyses(
            target_date=target_date,
            name="mahaney_analysis",
            item_schema=MahaneyStockAnalysis,
            tickers=tickers,
        )

        for response in responses:
            if not isinstance(response.value, MahaneyStockAnalysis):
                raise ValueError("Invalid stock data format in response")

        return responses

    async def get_mahaney_analysis_with_filters(
        self, request: MahaneyAnalysisGetRequest
    ) -> MahaneyAnalysisGetResponse:
        """Fetch Mahaney analysis with filtering, sorting, and pagination."""

        # Ensure target_date is not None
        target_date = request.target_date if request.target_date else date.today()

        # Use the specialized repository method for Mahaney analysis
        stocks, actual_date, is_exact_match = (
            self.websearch_repository.get_mahaney_analyses(
                target_date=target_date,
                tickers=request.tickers,
                recommendation=request.recommendation,
            )
        )

        total_count = len(stocks)
        filtered_count = total_count  # Already filtered in repository

        # Apply sorting
        if request.sort_by:
            reverse = request.sort_order == "desc"
            if request.sort_by == "stock_name":
                stocks.sort(key=lambda x: x.stock_name, reverse=reverse)
            elif request.sort_by == "recommendation_score":
                stocks.sort(key=lambda x: x.recommendation_score, reverse=reverse)
            elif request.sort_by == "final_assessment":
                stocks.sort(key=lambda x: x.final_assessment, reverse=reverse)

        # Apply limit
        if request.limit and request.limit > 0:
            stocks = stocks[: request.limit]

        return MahaneyAnalysisGetResponse(
            stocks=stocks,
            total_count=total_count,
            filtered_count=filtered_count,
            actual_date=actual_date,
            is_exact_date_match=is_exact_match,
            request_params=request,
        )

    def generate_etf_portfolio_prompt(
        self, etf_tickers: list[str], target_date: str
    ) -> str:
        """Generate prompt for ETF portfolio analysis."""
        if not isinstance(etf_tickers, list) or not etf_tickers:
            raise ValueError("ETF tickers must be a non-empty list.")

        etf_tickers = sorted(set([t.upper() for t in etf_tickers]))
        ticker_list = ", ".join(etf_tickers)

        prompt = f"""
            Today is **{target_date}**.
            
            You are a specialized ETF research analyst with deep knowledge of active ETF portfolio management.
            
            **TASK**: Analyze the recent portfolio changes for these Active ETFs: [{ticker_list}]
            
            **REQUIREMENTS**:
            1. Search for the **most recent portfolio holdings changes** for each ETF as of {target_date}
            - If Target date is not available, use the most Recent data
            2. Focus on **ACTIVE ETFs** that frequently adjust their holdings (like ARK funds, active management strategies)
            3. Identify **BUY/SELL transactions** made by the fund managers in the past 1-7 days
            4. For each transaction, explain **WHY** the fund managers made these decisions
            
            **DATA TO COLLECT**:
            For each ETF, find:
            - Recent stock purchases (BUY actions)
            - Recent stock sales (SELL actions) 
            - Number of shares traded (if available)
            - Approximate trade value
            - Portfolio weight changes
            - Fund manager's rationale or market commentary
            
            **ANALYSIS FOCUS**:
            - What sectors are they rotating INTO and OUT OF?
            - What specific catalysts drove these decisions?
            - How do these moves align with current market trends?
            - What does this suggest about the fund's investment thesis?
            
            **OUTPUT FORMAT**:
            Return a JSON object with this exact structure:
            ```json
            {{
                "etf_portfolios": [
                    {{
                        "etf_name": "ARK Innovation ETF",
                        "etf_ticker": "ARKK",
                        "date": "{target_date}",
                        "total_portfolio_value": 8500000000.0,
                        "changes": [
                            {{
                                "ticker": "TSLA",
                                "action": "SELL",
                                "shares_traded": 100000.0,
                                "price_per_share": 185.50,
                                "total_value": 18550000.0,
                                "percentage_of_portfolio": 2.1,
                                "reason": "Profit taking after strong Q4 earnings, rebalancing overweight position"
                            }},
                            {{
                                "ticker": "PLTR",
                                "action": "BUY",
                                "shares_traded": 500000.0,
                                "price_per_share": 45.20,
                                "total_value": 22600000.0,
                                "percentage_of_portfolio": 2.7,
                                "reason": "AI government contracts acceleration, undervalued relative to peers"
                            }}
                        ],
                        "summary": "ARK continued its AI theme focus by rotating out of overvalued EV positions into undervalued AI plays. Fund appears to be preparing for Q1 AI earnings season.",
                        "source_url": "https://ark-funds.com/ark-innovation-etf"
                    }}
                ]
            }}
            ```
            
            **IMPORTANT NOTES**:
            - Only include ETFs with **actual recent portfolio changes**
            - If no recent changes found for an ETF, exclude it from results
            - Use **real, current data** from {target_date} or the most recent available
            - Cite sources where possible in the summary
            - Focus on **actionable insights** about fund manager strategy
        """

        return prompt

    async def create_etf_analysis(
        self, etf_tickers: list[str], target_date: date = date.today()
    ):
        """Create ETF portfolio analysis using AI service with web search grounding."""
        if not etf_tickers:
            raise ValueError("ETF tickers list cannot be empty")

        prompt = self.generate_etf_portfolio_prompt(
            etf_tickers, target_date.strftime("%Y-%m-%d")
        )

        response = self.ai_service.perplexity_completion(
            prompt=prompt,
            schema=ETFAnalysisResponse,
        )

        if not isinstance(response, ETFAnalysisResponse):
            raise ValueError("Invalid response format from AI service")

        # Store each ETF portfolio analysis in ai_analysis table
        for etf_data in response.etf_portfolios:
            if not isinstance(etf_data, ETFPortfolioData):
                raise ValueError("Invalid ETF data format in response")

            # ticker 필드 설정 (JSON 필터링용)
            etf_data.ticker = etf_data.etf_ticker.upper()

            # Translate ETF analysis if translate_service is available
            translated_etf = etf_data
            if self.translate_service:
                try:
                    translated_etf = self.translate_service.translate_schema(etf_data)
                    translated_etf.etf_ticker = etf_data.etf_ticker.upper()
                    translated_etf.ticker = (
                        etf_data.etf_ticker.upper()
                    )  # ticker 필드도 설정
                except Exception as e:
                    logger.warning(
                        f"Failed to translate ETF analysis for {etf_data.etf_ticker}: {e}"
                    )

            # Store in ai_analysis table with name "etf_portfolio_analysis"
            self.websearch_repository.create_analysis(
                analysis_date=target_date,
                analysis=translated_etf.model_dump(),
                name="etf_portfolio_analysis",
            )

        return response

    async def create_insider_trend(
        self,
        tickers: list[str] | None,
        target_date: date = date.today(),
        llm_policy: Literal["AUTO", "GEMINI", "PERPLEXITY", "BOTH", "FALLBACK", "HYBRID"] = "AUTO",
    ) -> InsiderTrendResponse:
        prompt = self.generate_insider_trend_prompt(tickers, target_date.strftime("%Y-%m-%d"))
        results, resolved_policy, provenance = self.run_llm(llm_policy, prompt, InsiderTrendResponse)

        if not results or not isinstance(results[0], InsiderTrendResponse):
            raise ValueError("Invalid response format from AI service")

        if llm_policy == "BOTH" and len(results) > 1:
            # Store each model's items separately
            window = getattr(results[0], "window", None)
            for res, model in self._pair_results_with_models(results, provenance):
                for item in res.items:
                    payload = {
                        "ai_model": model,
                        "llm_policy": resolved_policy,
                        "prompt_hash": self._hash_prompt(prompt),
                        "provenance": provenance,
                        "window": window,
                        "ticker": item.ticker.upper() if item.ticker else None,
                        "item": item.model_dump(),
                    }
                    self.websearch_repository.create_analysis(
                        analysis_date=target_date,
                        analysis=payload,
                        name="insider_trend_weekly",
                    )
            # Return first for response
            return results[0]

        response: InsiderTrendResponse = (
            self._merge_results(InsiderTrendResponse, results)
            if llm_policy == "HYBRID" and len(results) >= 1
            else results[0]
        )

        if self.translate_service:
            try:
                response = self.translate_service.translate_schema(response)
            except Exception as e:
                logger.warning(f"Failed to translate insider trend: {e}")

        window = response.window

        for item in response.items:
            payload = {
                "ai_model": "HYBRID" if llm_policy == "HYBRID" and len(results) > 1 else ("PERPLEXITY" if resolved_policy in ("PERPLEXITY", "FALLBACK") else "GEMINI"),
                "llm_policy": resolved_policy,
                "prompt_hash": self._hash_prompt(prompt),
                "provenance": provenance,
                "window": window,
                "ticker": item.ticker.upper() if item.ticker else None,
                "item": item.model_dump(),
            }
            self.websearch_repository.create_analysis(
                analysis_date=target_date,
                analysis=payload,
                name="insider_trend_weekly",
            )

        return response

    async def get_insider_trend_with_filters(
        self, request: InsiderTrendGetRequest
    ) -> InsiderTrendGetResponse:
        target_date = request.target_date if request.target_date else date.today()

        analyses = self.websearch_repository.get_all_analyses(
            target_date=target_date,
            name="insider_trend_weekly",
            item_schema=None,
            tickers=request.tickers,
        )

        items: List[InsiderTradeItem] = []
        for a in analyses:
            v = a.value
            item = v.get("item") if isinstance(v, dict) else None
            if not item:
                continue
            try:
                it = InsiderTradeItem.model_validate(item)
            except Exception:
                continue
            if request.action and it.action != request.action:
                continue
            items.append(it)

        # sorting
        if request.sort_by == "value":
            items.sort(key=lambda x: (x.est_value or 0), reverse=(request.sort_order == "desc"))
        elif request.sort_by == "date":
            items.sort(key=lambda x: (x.date or ""), reverse=(request.sort_order == "desc"))

        # limit
        if request.limit is not None:
            items = items[: max(0, int(request.limit))]

        filtered_count = len(items)
        total_count = filtered_count

        return InsiderTrendGetResponse(
            items=items,
            total_count=total_count,
            filtered_count=filtered_count,
            actual_date=target_date,
            is_exact_date_match=True,
            request_params=request,
        )

    # ---------------------- Analyst Price Targets (Weekly) ----------------------
    def generate_analyst_pt_prompt(self, tickers: list[str] | None, target_date: str) -> str:
        ticker_list = ", ".join(sorted(set([t.upper() for t in tickers])) ) if tickers else "ALL"
        return f"""
        Today is {target_date}.
        Task: For [{ticker_list}], summarize last 7 days analyst PT changes (UP/DOWN/INIT/DROP) with broker, rating, old/new PT, consensus, rationale and publish dates.
        RULES:
        - STRICT JSON ONLY. Use exact keys as below. Uppercase tickers.
        - Include upside_pct = (new_pt/current_price - 1) if available; otherwise null.
        - Provide ≥2 sources with confidence.
        SCHEMA:
        {{
          "items": [{{
            "ticker": "MSFT",
            "action": "UP",
            "broker": "Morgan Stanley",
            "broker_rating": "Overweight",
            "old_pt": 400.0,
            "new_pt": 450.0,
            "consensus": 430.0,
            "upside_pct": 0.05,
            "rationale": "AI revenue acceleration, Copilot monetization",
            "sources": ["Morgan Stanley note", "WSJ"],
            "source_details": [{{"name": "MS note", "url": "https://...", "date": "{target_date}", "confidence": 0.9}}],
            "impact_score": 0.12,
            "date": "{target_date}",
            "published_at": "{target_date}"
          }}],
          "window": "YYYY-MM-DD~YYYY-MM-DD"
        }}
        """

    async def create_analyst_price_targets(
        self,
        tickers: list[str] | None,
        target_date: date = date.today(),
        llm_policy: Literal["AUTO", "GEMINI", "PERPLEXITY", "BOTH", "FALLBACK", "HYBRID"] = "AUTO",
    ) -> AnalystPTResponse:
        prompt = self.generate_analyst_pt_prompt(tickers, target_date.strftime("%Y-%m-%d"))
        results, resolved_policy, provenance = self.run_llm(llm_policy, prompt, AnalystPTResponse)

        if not results or not isinstance(results[0], AnalystPTResponse):
            raise ValueError("Invalid response format from AI service")

        if llm_policy == "BOTH" and len(results) > 1:
            window = getattr(results[0], "window", None)
            for res, model in self._pair_results_with_models(results, provenance):
                for item in res.items:
                    payload = {
                        "ai_model": model,
                        "llm_policy": resolved_policy,
                        "prompt_hash": self._hash_prompt(prompt),
                        "provenance": provenance,
                        "window": window,
                        "ticker": item.ticker.upper() if item.ticker else None,
                        "item": item.model_dump(),
                    }
                    self.websearch_repository.create_analysis(
                        analysis_date=target_date,
                        analysis=payload,
                        name="analyst_price_targets_weekly",
                    )
            return results[0]

        response: AnalystPTResponse = (
            self._merge_results(AnalystPTResponse, results)
            if llm_policy == "HYBRID" and len(results) >= 1
            else results[0]
        )

        if self.translate_service:
            try:
                response = self.translate_service.translate_schema(response)
            except Exception as e:
                logger.warning(f"Failed to translate analyst PT: {e}")

        window = response.window

        for item in response.items:
            payload = {
                "ai_model": "HYBRID" if llm_policy == "HYBRID" and len(results) > 1 else ("PERPLEXITY" if resolved_policy in ("PERPLEXITY", "FALLBACK") else "GEMINI"),
                "llm_policy": resolved_policy,
                "prompt_hash": self._hash_prompt(prompt),
                "provenance": provenance,
                "window": window,
                "ticker": item.ticker.upper() if item.ticker else None,
                "item": item.model_dump(),
            }
            self.websearch_repository.create_analysis(
                analysis_date=target_date,
                analysis=payload,
                name="analyst_price_targets_weekly",
            )

        return response

    async def get_analyst_price_targets_with_filters(
        self, request: AnalystPTGetRequest
    ) -> AnalystPTGetResponse:
        target_date = request.target_date if request.target_date else date.today()

        analyses = self.websearch_repository.get_all_analyses(
            target_date=target_date,
            name="analyst_price_targets_weekly",
            item_schema=None,
            tickers=request.tickers,
        )

        items: List[AnalystPTItem] = []
        for a in analyses:
            v = a.value
            item = v.get("item") if isinstance(v, dict) else None
            if not item:
                continue
            try:
                it = AnalystPTItem.model_validate(item)
            except Exception:
                continue
            if request.action and it.action != request.action:
                continue
            items.append(it)

        # sorting
        def impact(it: AnalystPTItem) -> float:
            try:
                if getattr(it, "impact_score", None) is not None:
                    return float(it.impact_score or 0.0)
                if it.action in ("UP", "DOWN") and it.old_pt and it.new_pt and it.old_pt != 0:
                    return abs((it.new_pt - it.old_pt) / it.old_pt)
                if it.action in ("INIT", "DROP"):
                    base = 0.3
                    if it.consensus and it.new_pt and it.consensus != 0:
                        base += abs((it.new_pt - it.consensus) / it.consensus)
                    return base
            except Exception:
                return 0.0
            return 0.0

        if request.sort_by == "impact":
            items.sort(key=lambda x: impact(x), reverse=(request.sort_order == "desc"))
        elif request.sort_by == "date":
            items.sort(key=lambda x: (x.date or ""), reverse=(request.sort_order == "desc"))

        # limit
        if request.limit is not None:
            items = items[: max(0, int(request.limit))]

        filtered_count = len(items)
        total_count = filtered_count

        return AnalystPTGetResponse(
            items=items,
            total_count=total_count,
            filtered_count=filtered_count,
            actual_date=target_date,
            is_exact_date_match=True,
            request_params=request,
        )

    # ---------------------- ETF Weekly Flows ----------------------
    def generate_etf_weekly_flows_prompt(self, universe: list[str] | None, target_date: str, provider: str | None = None) -> str:
        uni = ", ".join(sorted(set([t.upper() for t in universe])) ) if universe else "ALL"
        return f"""
        Today is {target_date}.
        Task: Provide weekly ETF flows summary for [{uni}] including top net inflow/outflow, volume change leaders, and sector/theme grouping.
        If data provider is specified use it as primary reference: {provider or "AUTO"}.
        RULES:
        - STRICT JSON ONLY. Use exact keys as below.
        - Include sector_inferred/evidence when sector is inferred by LLM.
        - Provide source_details with confidence for each item.
        JSON format:
        {{
          "items": [{{
            "ticker": "QQQ",
            "name": "Invesco QQQ Trust",
            "net_flow": 1500000000.0,
            "flow_1w": 2200000000.0,
            "volume_change": 0.35,
            "sector": "Technology",
            "themes": ["AI", "Megacap Growth"],
            "sector_inferred": false,
            "evidence": null,
            "source": "ProviderX",
            "source_details": [{{"name": "ProviderX", "url": "https://...", "date": "{target_date}", "confidence": 0.9}}]
          }}],
          "window": "YYYY-MM-DD~YYYY-MM-DD"
        }}
        """

    async def create_etf_weekly_flows(
        self,
        universe: list[str] | None,
        target_date: date = date.today(),
        provider: str | None = None,
        llm_policy: Literal["AUTO", "GEMINI", "PERPLEXITY", "BOTH", "FALLBACK", "HYBRID"] = "AUTO",
    ) -> ETFWeeklyFlowResponse:
        prompt = self.generate_etf_weekly_flows_prompt(universe, target_date.strftime("%Y-%m-%d"), provider)
        results, resolved_policy, provenance = self.run_llm(llm_policy, prompt, ETFWeeklyFlowResponse)

        if not results or not isinstance(results[0], ETFWeeklyFlowResponse):
            raise ValueError("Invalid response format from AI service")

        if llm_policy == "BOTH" and len(results) > 1:
            window = getattr(results[0], "window", None)
            for res, model in self._pair_results_with_models(results, provenance):
                for item in res.items:
                    payload = {
                        "ai_model": model,
                        "llm_policy": resolved_policy,
                        "prompt_hash": self._hash_prompt(prompt),
                        "provenance": provenance,
                        "window": window,
                        "provider": provider,
                        "ticker": item.ticker.upper() if item.ticker else None,
                        "item": item.model_dump(),
                    }
                    self.websearch_repository.create_analysis(
                        analysis_date=target_date,
                        analysis=payload,
                        name="etf_flows_weekly",
                    )
            return results[0]

        response: ETFWeeklyFlowResponse = (
            self._merge_results(ETFWeeklyFlowResponse, results)
            if llm_policy == "HYBRID" and len(results) >= 1
            else results[0]
        )

        if self.translate_service:
            try:
                response = self.translate_service.translate_schema(response)
            except Exception as e:
                logger.warning(f"Failed to translate ETF flows: {e}")

        window = response.window

        for item in response.items:
            payload = {
                "ai_model": "HYBRID" if len(results) > 1 and llm_policy in ("BOTH", "HYBRID") else ("PERPLEXITY" if resolved_policy in ("PERPLEXITY", "FALLBACK") else "GEMINI"),
                "llm_policy": resolved_policy,
                "prompt_hash": self._hash_prompt(prompt),
                "provenance": provenance,
                "window": window,
                "provider": provider,
                "ticker": item.ticker.upper() if item.ticker else None,
                "item": item.model_dump(),
            }
            self.websearch_repository.create_analysis(
                analysis_date=target_date,
                analysis=payload,
                name="etf_flows_weekly",
            )

        return response

    async def get_etf_weekly_flows_with_filters(
        self, request: ETFWeeklyFlowGetRequest
    ) -> ETFWeeklyFlowGetResponse:
        target_date = request.target_date if request.target_date else date.today()

        analyses = self.websearch_repository.get_all_analyses(
            target_date=target_date,
            name="etf_flows_weekly",
            item_schema=None,
            tickers=request.tickers,
        )

        items: List[ETFFlowItem] = []
        for a in analyses:
            v = a.value
            item = v.get("item") if isinstance(v, dict) else None
            if not item:
                continue
            try:
                it = ETFFlowItem.model_validate(item)
            except Exception:
                continue
            if request.provider and isinstance(v, dict) and v.get("provider") and v.get("provider") != request.provider:
                continue
            if request.sector_only and not (it.sector or (it.themes and len(it.themes) > 0)):
                continue
            items.append(it)

        filtered_count = len(items)
        total_count = filtered_count

        return ETFWeeklyFlowGetResponse(
            items=items,
            total_count=total_count,
            filtered_count=filtered_count,
            actual_date=target_date,
            is_exact_date_match=True,
            request_params=request,
        )

    # ---------------------- Liquidity Weekly ----------------------
    def generate_liquidity_weekly_prompt(self, target_date: str) -> str:
        return f"""
        Today is {target_date}.
        Summarize US liquidity weekly with M2 and Reverse Repo (RRP) time series for recent 4-8 weeks and concise commentary.
        RULES: STRICT JSON ONLY. Use primary sources (FRED/NYFRB) and include sources list with confidence.
        JSON:
        {{
          "series_m2": [{{"date": "YYYY-MM-DD", "m2": 0}}],
          "series_rrp": [{{"date": "YYYY-MM-DD", "rrp": 0}}],
          "commentary": "",
          "window": "YYYY-MM-DD~YYYY-MM-DD",
          "sources": [{{"name": "FRED", "url": "https://fred.stlouisfed.org/...", "date": "{target_date}", "confidence": 0.95}}]
        }}
        """

    async def create_liquidity_weekly(
        self,
        target_date: date = date.today(),
        llm_policy: Literal["AUTO", "GEMINI", "PERPLEXITY", "BOTH", "FALLBACK", "HYBRID"] = "AUTO",
    ) -> LiquidityWeeklyResponse:
        prompt = self.generate_liquidity_weekly_prompt(target_date.strftime("%Y-%m-%d"))
        results, resolved_policy, provenance = self.run_llm(llm_policy, prompt, LiquidityWeeklyResponse)

        if not results or not isinstance(results[0], LiquidityWeeklyResponse):
            raise ValueError("Invalid response format from AI service")

        response: LiquidityWeeklyResponse = (
            self._merge_results(LiquidityWeeklyResponse, results)
            if llm_policy == "HYBRID" and len(results) >= 1
            else results[0]
        )
        if self.translate_service:
            try:
                response = self.translate_service.translate_schema(response)
            except Exception as e:
                logger.warning(f"Failed to translate liquidity weekly: {e}")

        # Store as a single snapshot for the day
        self.websearch_repository.create_analysis(
            analysis_date=target_date,
            analysis=response.model_dump(),
            name="us_liquidity_weekly",
        )

        return response

    def get_liquidity_weekly(self, target_date: date = date.today()) -> LiquidityWeeklyResponse:
        cached = self.websearch_repository.get_analysis_by_date(
            target_date, name="us_liquidity_weekly", schema=None
        )
        if cached and cached.value:
            try:
                return LiquidityWeeklyResponse.model_validate(cached.value)
            except Exception:
                pass
        return LiquidityWeeklyResponse(series_m2=[], series_rrp=[], commentary=None)

    # ---------------------- Market Breadth Daily ----------------------
    def generate_market_breadth_prompt(self, target_date: str) -> str:
        return f"""
        Today is {target_date}.
        Provide daily market breadth core metrics (VIX, advancers/decliners, new highs/lows, TRIN) and short commentary.
        RULES: STRICT JSON ONLY. Include sources with confidence.
        JSON:
        {{
          "series": [{{
             "date": "YYYY-MM-DD", "vix": 0, "advancers": 0, "decliners": 0, "new_highs": 0, "new_lows": 0, "trin": 0
          }}],
          "commentary": "",
          "sources": [{{"name": "CBOE", "url": "https://...", "date": "{target_date}", "confidence": 0.9}}]
        }}
        """

    async def create_market_breadth_daily(
        self,
        target_date: date = date.today(),
        llm_policy: Literal["AUTO", "GEMINI", "PERPLEXITY", "BOTH", "FALLBACK", "HYBRID"] = "AUTO",
    ) -> MarketBreadthResponse:
        prompt = self.generate_market_breadth_prompt(target_date.strftime("%Y-%m-%d"))
        results, resolved_policy, provenance = self.run_llm(llm_policy, prompt, MarketBreadthResponse)

        if not results or not isinstance(results[0], MarketBreadthResponse):
            raise ValueError("Invalid response format from AI service")

        response: MarketBreadthResponse = (
            self._merge_results(MarketBreadthResponse, results)
            if llm_policy == "HYBRID" and len(results) >= 1
            else results[0]
        )

        if self.translate_service:
            try:
                response = self.translate_service.translate_schema(response)
            except Exception as e:
                logger.warning(f"Failed to translate market breadth: {e}")

        self.websearch_repository.create_analysis(
            analysis_date=target_date,
            analysis=response.model_dump(),
            name="market_breadth_daily",
        )

        return response

    def get_market_breadth(self, target_date: date = date.today()) -> MarketBreadthResponse:
        cached = self.websearch_repository.get_analysis_by_date(
            target_date, name="market_breadth_daily", schema=None
        )
        if cached and cached.value:
            try:
                return MarketBreadthResponse.model_validate(cached.value)
            except Exception:
                pass
        return MarketBreadthResponse(series=[], commentary=None)

    async def get_etf_analysis(
        self, target_date: date = date.today(), etf_tickers: Optional[list[str]] = None
    ):
        """Fetch ETF portfolio analysis for the given tickers."""

        responses = self.websearch_repository.get_all_analyses(
            target_date=target_date,
            name="etf_portfolio_analysis",
            item_schema=ETFPortfolioData,
            tickers=etf_tickers,
        )

        for response in responses:
            if not isinstance(response.value, ETFPortfolioData):
                raise ValueError("Invalid ETF data format in response")

        return responses

    async def get_etf_analysis_with_filters(
        self, request: ETFAnalysisGetRequest
    ) -> ETFAnalysisGetResponse:
        """Fetch ETF analysis with filtering, sorting, and pagination."""

        # Ensure target_date is not None
        target_date = request.target_date if request.target_date else date.today()

        # Get all ETF analyses for the date
        all_analyses = await self.get_etf_analysis(
            target_date=target_date, etf_tickers=request.etf_tickers
        )

        # Convert to ETFPortfolioData objects
        etf_analyses = [
            analysis.value
            for analysis in all_analyses
            if isinstance(analysis.value, ETFPortfolioData)
        ]

        # Filter by ETF tickers if specified
        if request.etf_tickers:
            etf_tickers_upper = [ticker.upper() for ticker in request.etf_tickers]
            etf_analyses = [
                etf
                for etf in etf_analyses
                if etf.etf_ticker.upper() in etf_tickers_upper
            ]

        total_count = len(etf_analyses)
        filtered_count = total_count

        # Apply sorting
        if request.sort_by:
            reverse = request.sort_order == "desc"
            if request.sort_by == "etf_name":
                etf_analyses.sort(key=lambda x: x.etf_name, reverse=reverse)
            elif request.sort_by == "date":
                etf_analyses.sort(key=lambda x: x.date, reverse=reverse)
            elif request.sort_by == "total_value":
                etf_analyses.sort(
                    key=lambda x: x.total_portfolio_value or 0, reverse=reverse
                )

        return ETFAnalysisGetResponse(
            etf_analyses=etf_analyses,
            total_count=total_count,
            filtered_count=filtered_count,
            actual_date=target_date,
            is_exact_date_match=True,
            request_params=request,
        )

    def generate_etf_analyst_summary_prompt(
        self, etf_portfolio_data: ETFPortfolioData, target_date: str
    ) -> str:
        """Generate prompt for deep analyst analysis of ETF portfolio changes."""

        changes_summary = []
        for change in etf_portfolio_data.changes:
            changes_summary.append(
                f"- {change.action} {change.ticker}: {change.shares_traded} shares "
                f"at ${change.price_per_share} (${change.total_value:,.0f} total value, "
                f"{change.percentage_of_portfolio}% of portfolio)"
            )

        changes_text = "\n".join(changes_summary)

        prompt = f"""
            Today is **{target_date}**.
            
            You are a senior equity research analyst specializing in institutional portfolio analysis and market strategy.
            
            **CONTEXT**: 
            The {etf_portfolio_data.etf_name} ({etf_portfolio_data.etf_ticker}) recently made the following portfolio changes:
            
            {changes_text}
            
            **CURRENT PORTFOLIO SUMMARY**:
            {etf_portfolio_data.summary}
            
            **YOUR TASK**:
            Conduct a **comprehensive analyst-level investigation** to understand WHY these specific trades were made:
            
            1. **Market Context Analysis**:
               - What major market events/catalysts occurred around {target_date}?
               - How did sector rotation trends influence these decisions?
               - What macroeconomic factors (Fed policy, earnings, geopolitics) drove this strategy?
            
            2. **Company-Specific Research** (for each ticker traded):
               - Recent earnings/guidance changes
               - Analyst upgrades/downgrades
               - Major news events or product launches
               - Technical chart patterns and momentum
               - Valuation changes vs. peers
            
            3. **Fund Manager Strategy Analysis**:
               - How do these trades align with the fund's stated investment thesis?
               - What does this suggest about the manager's market outlook?
               - Are they rotating between sectors, growth vs. value, or risk-on vs. risk-off?
               - How do these moves compare to peer funds' actions?
            
            4. **Market Impact & Forward-Looking Insights**:
               - What do these trades signal about upcoming market themes?
               - Which sectors/stocks might benefit from this rotation?
               - What risks or opportunities does this create for retail investors?
            
            **OUTPUT REQUIREMENTS**:
            Provide a structured analysis in JSON format:
            
            ```json
            {{
                "etf_ticker": "{etf_portfolio_data.etf_ticker}",
                "analysis_date": "{target_date}",
                "market_context": {{
                    "key_catalysts": ["List 3-5 major market events driving decisions"],
                    "sector_rotation_trend": "Description of current sector rotation dynamics",
                    "macro_backdrop": "Fed policy, economic indicators, geopolitical factors"
                }},
                "individual_stock_analysis": [
                    {{
                        "ticker": "STOCK_SYMBOL",
                        "action_taken": "BUY/SELL",
                        "fundamental_rationale": "Why fundamentally attractive/unattractive",
                        "technical_rationale": "Chart patterns, momentum, technical triggers",
                        "news_catalysts": ["Recent news events affecting stock"],
                        "analyst_sentiment": "Current Wall Street analyst consensus",
                        "valuation_assessment": "Expensive/Fair/Cheap vs peers and history"
                    }}
                ],
                "portfolio_strategy_insights": {{
                    "manager_thesis": "What investment theme/strategy is driving these moves",
                    "risk_positioning": "Risk-on, risk-off, or neutral positioning",
                    "time_horizon": "Short-term tactical vs long-term strategic moves",
                    "peer_comparison": "How these moves compare to similar funds"
                }},
                "forward_looking_implications": {{
                    "sector_implications": "Which sectors likely to benefit/suffer next",
                    "stock_opportunities": ["Specific tickers that might benefit from this rotation"],
                    "risk_factors": ["Key risks to monitor based on these moves"],
                    "retail_investor_takeaways": "Actionable insights for individual investors"
                }},
                "confidence_level": "High/Medium/Low - based on data availability and clarity of signals",
                "data_sources": ["List of key sources used for analysis"]
            }}
            ```
            
            **IMPORTANT**: 
            - Use **real, current data** from {target_date} and recent days
            - Cite specific sources (earnings reports, analyst notes, news articles)
            - Focus on **actionable insights** rather than generic commentary
            - Explain complex institutional strategies in accessible terms
        """

        return prompt

    async def create_etf_analyst_summary(
        self, etf_portfolio_data: ETFPortfolioData, target_date: date = date.today()
    ):
        """Generate comprehensive analyst summary for ETF portfolio changes."""

        prompt = self.generate_etf_analyst_summary_prompt(
            etf_portfolio_data, target_date.strftime("%Y-%m-%d")
        )

        # Use Perplexity for research-backed analysis with structured schema
        response = self.ai_service.perplexity_completion(
            prompt=prompt,
            schema=ETFAnalystSummaryResponse,
        )

        if not isinstance(response, ETFAnalystSummaryResponse):
            raise ValueError("Invalid response format from AI service")

        # Translate the response if translate_service is available
        translated_response = response
        if self.translate_service:
            try:
                translated_response = self.translate_service.translate_schema(response)
                # Keep the original ETF ticker uppercase
                translated_response.etf_ticker = etf_portfolio_data.etf_ticker.upper()
            except Exception as e:
                logger.warning(f"Failed to translate ETF analyst summary: {e}")

        # Store the analyst summary in ai_analysis table
        analyst_summary = {
            "etf_ticker": etf_portfolio_data.etf_ticker,
            "original_portfolio_data": etf_portfolio_data.model_dump(),
            "analyst_summary": translated_response.model_dump(),
            "analysis_type": "etf_analyst_summary",
        }

        self.websearch_repository.create_analysis(
            analysis_date=target_date,
            analysis=analyst_summary,
            name="etf_analyst_summary",
        )

        return translated_response

    # ---------------------- Fundamental Analysis ----------------------
    def generate_fundamental_analysis_prompt(self, ticker: str, target_date: str) -> str:
        """Generate comprehensive institutional-grade fundamental analysis prompt"""
        return f"""Today is {target_date}. You are a veteran equity research analyst from Goldman Sachs with 15+ years experience.

Conduct a comprehensive fundamental analysis for {ticker}. Use REAL, CURRENT data (most recent quarterly/annual filings).

ANALYSIS SECTIONS:

1. NARRATIVE & VISION
- Dominant market narrative driving {ticker}
- Vision status: Strong/Moderate/Weak/Dead
- 3-7 key narrative drivers
- Market sentiment: Very Bullish/Bullish/Neutral/Bearish/Very Bearish
- Sentiment reasoning & narrative shift risks

2. SECTOR & COMPETITIVE POSITION
- Sector name, YTD return vs S&P 500
- 3-5 key sector catalysts & headwinds
- Market share (%) & trend
- Top 3-5 competitors
- Competitive advantages & threats
- Moat rating: Wide/Narrow/None
- Peer comparison vs top 3-5 competitors

3. PRODUCT & INNOVATION
- Recent product launches (6-12 months)
- Pipeline strength: Strong/Moderate/Weak
- R&D spending (% of revenue)
- Innovation score: Leader/Fast Follower/Laggard
- Key patents/tech

4. MARKET OPPORTUNITY
- TAM & SAM (in billions USD)
- Market growth rate (CAGR %)
- Company penetration (%)
- Expansion opportunities
- Geographic breakdown

5. FINANCIALS (Use Q4 2024/FY 2024 data)
GROWTH: Revenue YoY/QoQ/3yr CAGR, EPS YoY/3yr CAGR, guidance, earnings surprises
PROFITABILITY: Gross/Operating/Net margins, margin trend, ROE/ROIC/ROA
BALANCE SHEET: Debt-to-Equity, Net Debt, Current/Quick ratios, Cash, Debt maturity
CASH FLOW: FCF, FCF yield, Operating CF, CapEx, FCF conversion rate
VALUATION: P/E, Forward P/E, PEG, P/S, P/B, EV/EBITDA, vs peers, vs historical, fair value

6. MANAGEMENT
- CEO name, tenure, background
- Quality score: Excellent/Good/Average/Poor
- Key strengths (3-5) & concerns (3-5)
- Execution track record
- Capital allocation score: Excellent/Good/Average/Poor
- Insider ownership (%) & recent activity

7. RISKS
- Regulatory, competitive, execution, macro, financial risks (3-5 each)
- Overall risk score: Low/Medium/High/Very High
- 2-3 black swan scenarios

8. CATALYSTS
- Near-term (0-3mo), medium-term (3-12mo), long-term (12mo+) catalysts
- Earnings date, product launches, regulatory milestones

9. RECOMMENDATION
- Rating: Strong Buy/Buy/Hold/Sell/Strong Sell
- Target price, current price, upside/downside %
- Conviction: Very High/High/Medium/Low
- Time horizon: Short/Medium/Long-term
- 5-7 bullish & bearish factors
- Base/Bull/Bear case scenarios
- Ideal entry point, stop-loss

10. SUMMARY
- Executive summary (5-7 sentences)
- Investment thesis (3-4 paragraphs)
- 5-7 key takeaways

OUTPUT: Return JSON matching FundamentalAnalysisResponse schema with ALL fields populated. Use specific numbers, dates, names. Cite 2-3 sources per section. If data unavailable, use null.
"""

    async def create_fundamental_analysis(
        self, ticker: str, target_date: date = date.today()
    ) -> FundamentalAnalysisResponse:
        """Create comprehensive fundamental analysis for a ticker using OpenAI"""
        ticker = ticker.upper()

        prompt = self.generate_fundamental_analysis_prompt(
            ticker, target_date.strftime("%Y-%m-%d")
        )

        try:
            # Use OpenAI for analysis (can also use Perplexity for research-backed analysis)
            response = self.ai_service.perplexity_completion(
                prompt=prompt,
                schema=FundamentalAnalysisResponse,
            )

            if not isinstance(response, FundamentalAnalysisResponse):
                raise ValueError("Invalid response format from AI service")

            # Translate if translate_service is available
            translated_response = response
            if self.translate_service:
                try:
                    translated_response = self.translate_service.translate_schema(response)
                    # Keep ticker uppercase
                    translated_response.ticker = ticker
                except Exception as e:
                    logger.warning(f"Failed to translate fundamental analysis for {ticker}: {e}")

            # Store in ai_analysis table with proper JSON encoding
            try:
                # model_dump_json()으로 직렬화하여 ensure_ascii=False 적용
                analysis_json_str = translated_response.model_dump_json(exclude_none=True)
                # JSON 문자열을 다시 dict로 변환하여 저장
                analysis_dict = json.loads(analysis_json_str)

                # 데이터 크기 체크
                data_size = len(analysis_json_str)
                logger.info(f"Fundamental analysis data size: {data_size} bytes ({data_size/1024:.2f} KB)")

                if data_size > 1000000:  # 1MB 이상이면 경고
                    logger.warning(f"Large analysis data detected: {data_size/1024:.2f} KB")

                self.websearch_repository.create_analysis(
                    analysis_date=target_date,
                    analysis=analysis_dict,
                    name="fundamental_analysis",
                )

                logger.info(f"Successfully stored fundamental analysis for {ticker}")
            except Exception as db_error:
                logger.error(f"Failed to store analysis in database: {db_error}")
                # DB 저장 실패해도 응답은 반환
                logger.warning(f"Returning analysis without database storage for {ticker}")

            return translated_response

        except Exception as e:
            logger.error(f"Failed to create fundamental analysis for {ticker}: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create fundamental analysis: {str(e)}"
            )

    async def get_fundamental_analysis(
        self,
        ticker: str,
        target_date: date = date.today(),
        force_refresh: bool = False,
        analysis_request: bool = True,
    ) -> FundamentalAnalysisGetResponse:
        """
        Get fundamental analysis for a ticker with 1-month caching

        Cache Logic:
        - If analysis exists and is less than 30 days old: return cached
        - If analysis is older than 30 days or force_refresh=True: create new analysis
        - If no analysis exists: create new analysis

        Parameters
        ----------
        analysis_request: bool
            When False, skip generating new analysis and read from cache only.
        """
        ticker = ticker.upper()

        cached_response: FundamentalAnalysisGetResponse | None = None
        cached_days_old: int | None = None

        cached_analysis = self.websearch_repository.get_analysis_by_date(
            target_date, name="fundamental_analysis", schema=None
        )

        if cached_analysis and cached_analysis.value:
            try:
                cached_value = cached_analysis.value
                cached_ticker = ""

                if isinstance(cached_value, dict):
                    cached_ticker = cached_value.get("ticker", "").upper()

                if cached_ticker == ticker:
                    try:
                        cached_date = date.fromisoformat(str(cached_analysis.date))
                    except Exception:
                        cached_date = target_date

                    try:
                        analysis_model = FundamentalAnalysisResponse.model_validate(
                            cached_value
                        )
                        days_old = (target_date - cached_date).days
                        if days_old < 0:
                            days_old = 0

                        cached_days_old = days_old
                        cached_response = FundamentalAnalysisGetResponse(
                            analysis=analysis_model,
                            is_cached=True,
                            cache_date=cached_date,
                            days_until_expiry=max(0, 30 - days_old),
                        )
                    except Exception as parse_error:
                        logger.warning(
                            f"Failed to validate cached fundamental analysis for {ticker}: {parse_error}"
                        )
            except Exception as e:
                logger.warning(f"Failed to parse cached fundamental analysis: {e}")

        if not analysis_request:
            if cached_response:
                return cached_response
            raise HTTPException(
                status_code=404,
                detail=f"Fundamental analysis for {ticker} not found in cache",
            )

        if (
            not force_refresh
            and cached_response
            and cached_days_old is not None
            and cached_days_old < 30
        ):
            return cached_response

        # No valid cache found or force_refresh - create new analysis
        logger.info(f"Creating new fundamental analysis for {ticker}")
        analysis = await self.create_fundamental_analysis(ticker, target_date)

        return FundamentalAnalysisGetResponse(
            analysis=analysis,
            is_cached=False,
            cache_date=target_date,
            days_until_expiry=30,
        )
