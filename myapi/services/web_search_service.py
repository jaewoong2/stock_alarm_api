from datetime import date, timedelta
from typing import Literal, Optional
from fastapi import HTTPException
import logging

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

            cached = await self.websearch_repository.get_by_date(
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

            await self.websearch_repository.create(
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

        response = self.ai_service.gemini_search_grounding(
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
