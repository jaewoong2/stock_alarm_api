from datetime import date
from typing import List, TypeVar
import logging

from myapi.domain.research.research_schema import (
    ResearchRequest,
    ResearchResponse,
    SectorAnalysisRequest,
    SectorAnalysisResponse,
    LeadingStockRequest,
    LeadingStockResponse,
    ComprehensiveResearchResponse,
    ComprehensiveResearchData,
    CreateResearchAnalysisRequest,
    GetResearchAnalysisRequest,
    GetResearchAnalysisResponse,
    ResearchAnalysisVO,
)
from myapi.repositories.web_search_repository import WebSearchResultRepository
from myapi.services.ai_service import AIService
from myapi.services.translate_service import TranslateService
from myapi.domain.ai.ai_schema import ChatModel

T = TypeVar("T")

logger = logging.getLogger(__name__)


class ResearchService:
    def __init__(
        self,
        websearch_repository: WebSearchResultRepository,
        ai_service: AIService,
        translate_service: TranslateService,
    ):
        self.websearch_repository = websearch_repository
        self.ai_service = ai_service
        self.translate_service = translate_service

    def _build_research_prompt(self, request: ResearchRequest) -> str:
        """Build Perplexity research prompt based on user requirements."""
        return f"""
            Role: You are an evidence-based research assistant focusing on US stock market impact analysis.
            Task: Search for recent issues/policies/press releases that could impact US stocks/companies based on the parameters below and return each item as a JSON array.
            Focus: Only include events that have potential impact on US publicly traded companies and their stock prices.
            Required: (1) Source link, (2) Initial announcement 'date', (3) Summary in 1-2 sentences focusing on stock market implications, (4) Key US companies/stocks that could be affected, (5) Event type (policy/budget/tech announcement/regulation/sanctions/Capex/RFP, etc.).
            Quality requirements: Remove duplicate articles of the same event, prioritize official documents/press releases that affect US stock market.
            
            Find at least Five recent issues/policies/press releases that could impact US stocks/companies based on the parameters below and return each item as a JSON array.

            Parameters:
            - Region: {request.region}
            - Topic: {request.topic}
            - Period: Last {request.period_days} days

            Output format (JSON):
            {{
            "research_items": [
                {{
                    "title": "...",
                    "date": "YYYY-MM-DD",
                    "source": "URL",
                    "summary": "Summary with focus on US stock market impact...",
                    "entities": ["US Company/Stock ticker 1", "US Company/Stock ticker 2", "..."],
                    "event_type": "policy|budget|tech|regulation|sanction|capex|rfp"
                }}
            ]
            }}
        """

    def _build_sector_analysis_prompt(self, news_content: str) -> str:
        """Build o4-mini sector analysis prompt."""
        return f"""
        # Role Assignment
        You are a top-tier US stock market analyst with 20 years of experience. You specialize in analyzing macroeconomic and industry trends to predict cascading ripple effects on US publicly traded companies, and through this, you discover hidden beneficiary sectors and US stocks.

        # Latest News or Policy to Analyze
        {news_content}

        # Analysis Instructions
        Based on the content above, please analyze the US industry sectors expected to benefit at each stage according to the 4-stage cascade analysis model below, along with their reasons and representative US publicly traded companies (focus on NYSE/NASDAQ listed stocks).

        ## Analysis Result JSON Format:
        {{
        "analysis": {{
            "primary_beneficiaries": [
            {{
                "sector": "Direct beneficiary US sector name",
                "reason": "Reason and basis for benefits to US companies",
            }}
            ],
            "supply_chain_beneficiaries": [
            {{
                "sector": "Supply chain beneficiary US sector name",
                "reason": "Reason for benefits from upstream industry growth to US companies",
            }}
            ],
            "bottleneck_solution_beneficiaries": [
            {{
                "sector": "Bottleneck solution beneficiary US sector name",
                "reason": "Potential problems and solution approaches by US companies",
            }}
            ],
            "infrastructure_beneficiaries": [
            {{
                "sector": "Infrastructure/ecosystem expansion beneficiary US sector name", 
                "reason": "Reason for providing essential infrastructure for ecosystem expansion by US companies",
            }}
            ]
        }}
        }}

        ### Primary Beneficiary Sectors (Direct Benefits)
        * **Analysis Question:** Which US sectors and publicly traded companies will receive the most direct and immediate benefits from the above news/policy?

        ### Secondary Beneficiary Sectors (Supply Chain/Upstream Benefits)
        * **Analysis Question:** Following the growth of primary beneficiary sectors, which US sectors among the 'supply chain' or 'upstream industries' that provide components, equipment, materials, and services to those sectors will benefit?

        ### Tertiary Beneficiary Sectors (Problem Solving/Bottleneck Benefits)
        * **Analysis Question:** What 'bottlenecks' or 'new problems' will inevitably arise from the rapid growth of primary and secondary sectors, and which US sectors and companies can benefit by solving these issues?

        ### Quaternary Beneficiary Sectors (Infrastructure/Ecosystem Expansion Benefits)
        * **Analysis Question:** Which US sectors provide essential 'core infrastructure' or 'platforms' necessary for this new industrial ecosystem to be stably maintained and further expanded?

        # Result Reporting Format
        * Focus exclusively on US publicly traded companies (NYSE, NASDAQ).
        * Please clearly distinguish and present the analysis content for each stage.
        * Logically connect the analysis rationale to the news content and explain.
        * Briefly comment on the potential from short-term and medium-to-long-term perspectives for each US sector.
        """

    def _build_leading_stocks_prompt(self, sectors: List[str]) -> str:
        """Build Perplexity leading stocks analysis prompt."""
        sectors_text = ", ".join(sectors)
        return f"""
        You are a US stock market specialist analyst. Please find and analyze leading US publicly traded stocks in the following sectors:

        **Target Sectors for Analysis:** {sectors_text}

        **Selection Criteria:**
        1. US publicly traded companies (NYSE, NASDAQ only)
        2. Revenue growth rate averaging 10% or higher over the last 4 quarters
        3. Relative Strength (RS) index higher compared to S&P500
        4. Focus on diverse sectors - technology, healthcare, energy, consumer goods, financials, industrials, materials, utilities, real estate
        5. Market capitalization of $1 billion or more
        6. Recent trading volume showing an increasing trend compared to average
        7. at least 7 stocks in each sector

        **Analysis Items:**
        - Financial performance (revenue/profit growth rates)
        - Technical indicators (RS strength, chart patterns)
        - Business momentum (new products, partnerships, market share)
        - Risk factors

        Output Format (JSON):
        {{
        "leading_stocks": [
            {{
            "stock_metrics": {{
                "ticker": "JPM",
                "company_name": "JPMorgan Chase & Co.",
                "revenue_growth_rate": 22.0,
                "rs_strength": 78.0,
                "market_cap": 485000.0,
                "sector": "Financials",
                "current_price": 165.50,
                "volume_trend": "Increasing"
            }},
            "analysis_summary": "Leading US bank with strong lending growth and digital transformation",
            "growth_potential": "Continued growth through 2025 with rising interest rates and digital banking expansion",
            "risk_factors": ["Credit risk in economic downturn", "Regulatory changes", "Competition from fintech"],
            "target_price": 180.0,
            "recommendation": "Buy"
            }}
        ]
        }}

        **Important:** 
        - Only include US stocks traded on NYSE or NASDAQ
        - Diversify across different sectors beyond just technology
        - Include stocks from healthcare, energy, consumer goods, financials, industrials, materials, utilities, real estate sectors
        - Provide comprehensive analysis incorporating the latest financial data, analyst consensus, and technical indicators.
        """

    async def perplexity_research(self, request: ResearchRequest) -> ResearchResponse:
        """Execute Perplexity search for research topics."""
        prompt = self._build_research_prompt(request)

        try:
            response = self.ai_service.perplexity_completion(
                prompt=prompt,
                schema=ResearchResponse,
            )

            if not isinstance(response, ResearchResponse):
                raise ValueError("Invalid response format from Perplexity API")

            return response

        except Exception as e:
            logger.error(f"Perplexity research failed: {e}")
            raise

    async def o4_mini_sector_analysis(
        self, request: SectorAnalysisRequest
    ) -> SectorAnalysisResponse:
        """Execute o4-mini sector analysis."""
        prompt = self._build_sector_analysis_prompt(request.news_content)

        try:
            response = self.ai_service.completions_parse(
                prompt=prompt,
                schema=SectorAnalysisResponse,
                system_prompt="You are an expert financial analyst. Analyze sector impacts and return results in JSON format.",
                chat_model=ChatModel.O4_MINI,
                image_url=None,
            )

            if not isinstance(response, SectorAnalysisResponse):
                raise ValueError("Invalid response format from o4-mini")

            return response

        except Exception as e:
            logger.error(f"o4-mini sector analysis failed: {e}")
            raise

    async def perplexity_leading_stocks(
        self, request: LeadingStockRequest
    ) -> LeadingStockResponse:
        """Execute Perplexity leading stocks analysis."""
        prompt = self._build_leading_stocks_prompt(request.sectors)

        try:
            response = self.ai_service.perplexity_completion(
                prompt=prompt,
                schema=LeadingStockResponse,
            )

            if not isinstance(response, LeadingStockResponse):
                raise ValueError("Invalid response format from Perplexity API")

            # Filter stocks by criteria
            filtered_stocks = []
            for stock in response.leading_stocks:
                filtered_stocks.append(stock)

            response.leading_stocks = filtered_stocks

            return response

        except Exception as e:
            logger.error(f"Perplexity leading stocks analysis failed: {e}")
            raise

    async def comprehensive_research_analysis(self) -> ComprehensiveResearchResponse:
        """Execute comprehensive research analysis combining all services."""
        try:
            # Step 1: Perplexity Research with default values
            research_request = ResearchRequest(
                region="United States",
                topic="Economic Policy and Market Developments",
                period_days=14,
            )
            research_results = await self.perplexity_research(research_request)

            # Step 2: Combine research content for sector analysis
            news_content = "\n".join(
                [
                    f"title: {item.title}\n summary: {item.summary}\n sources: {item.source}\n"
                    for item in research_results.research_items
                ]
            )

            sector_analysis_request = SectorAnalysisRequest(news_content=news_content)
            sector_analysis = await self.o4_mini_sector_analysis(
                sector_analysis_request
            )

            # Step 3: Extract sectors for leading stocks analysis
            all_sectors = []
            for sector_list in [
                sector_analysis.analysis.primary_beneficiaries,
                sector_analysis.analysis.supply_chain_beneficiaries,
                sector_analysis.analysis.bottleneck_solution_beneficiaries,
                sector_analysis.analysis.infrastructure_beneficiaries,
            ]:
                all_sectors.extend([item.sector for item in sector_list])

            # Remove duplicates
            unique_sectors = list(set(all_sectors))

            leading_stock_request = LeadingStockRequest(
                sectors=unique_sectors,
            )

            leading_stocks = await self.perplexity_leading_stocks(leading_stock_request)

            # Step 4: Combine all results
            comprehensive_data = ComprehensiveResearchData(
                research_date=date.today().strftime("%Y-%m-%d"),
                research_results=research_results,
                sector_analysis=sector_analysis,
                leading_stocks=leading_stocks,
            )

            return ComprehensiveResearchResponse(analysis=comprehensive_data)

        except Exception as e:
            logger.error(f"Comprehensive research analysis failed: {e}")
            raise

    async def save_research_analysis(
        self, request: CreateResearchAnalysisRequest
    ) -> ResearchAnalysisVO:
        """Create and save comprehensive research analysis."""
        try:
            # Execute comprehensive analysis with default parameters
            comprehensive_response = await self.comprehensive_research_analysis()

            # Save to database with enhanced metadata
            target_date = request.target_date if request.target_date else date.today()

            # Translate the comprehensive response first
            translated_analysis = self.translate_service.translate_schema(
                comprehensive_response.analysis
            )

            # Convert to dict (JSON serializable)
            analysis_data = translated_analysis.model_dump()

            # Add metadata for better searchability
            analysis_data["metadata"] = {
                "research_type": "comprehensive",
                "ai_models_used": ["perplexity-sonar-pro", "openai-o4-mini"],
                "total_research_items": len(
                    translated_analysis.research_results.research_items
                ),
                "total_sectors_analyzed": (
                    len(
                        translated_analysis.sector_analysis.analysis.primary_beneficiaries
                    )
                    + len(
                        translated_analysis.sector_analysis.analysis.supply_chain_beneficiaries
                    )
                    + len(
                        translated_analysis.sector_analysis.analysis.bottleneck_solution_beneficiaries
                    )
                    + len(
                        translated_analysis.sector_analysis.analysis.infrastructure_beneficiaries
                    )
                ),
                "total_stocks_identified": len(
                    translated_analysis.leading_stocks.leading_stocks
                ),
                "created_by": "research_service",
                "version": "1.0",
            }

            saved_analysis = self.websearch_repository.create_analysis(
                analysis_date=target_date,
                analysis=analysis_data,
                name="comprehensive_research",
            )

            # Also save individual components for separate analysis
            try:
                # Save research results separately (already translated and in dict format)
                self.websearch_repository.create_analysis(
                    analysis_date=target_date,
                    analysis=analysis_data["research_results"],
                    name="research_results",
                )

                # Save sector analysis separately (already translated and in dict format)
                self.websearch_repository.create_analysis(
                    analysis_date=target_date,
                    analysis=analysis_data["sector_analysis"],
                    name="sector_analysis",
                )

                # Save leading stocks separately (already translated and in dict format)
                self.websearch_repository.create_analysis(
                    analysis_date=target_date,
                    analysis=analysis_data["leading_stocks"],
                    name="leading_stocks",
                )

                logger.info(
                    f"Saved comprehensive research and individual components for {target_date}"
                )

            except Exception as e:
                logger.warning(f"Failed to save individual components: {e}")
                # Continue with main analysis even if individual saves fail

            return ResearchAnalysisVO(
                id=saved_analysis.id,
                date=saved_analysis.date,
                name=saved_analysis.name,
                value=translated_analysis,  # Use the translated version
                created_at=None,  # Will be set by database
            )

        except Exception as e:
            logger.error(f"Save research analysis failed: {e}")
            raise

    async def get_research_analysis(
        self, request: GetResearchAnalysisRequest
    ) -> GetResearchAnalysisResponse:
        """Retrieve research analysis with filtering."""
        try:
            target_date = request.target_date if request.target_date else date.today()

            # Get all comprehensive research analyses
            analyses = self.websearch_repository.get_all_analyses(
                name="comprehensive_research",
                item_schema=None,  # We'll handle validation manually
                target_date=target_date,
            )

            # Convert to ResearchAnalysisVO objects
            research_analyses = []
            for analysis in analyses:
                try:
                    # Validate the comprehensive research data
                    comprehensive_data = ComprehensiveResearchData.model_validate(
                        analysis.value
                    )
                    research_analyses.append(
                        ResearchAnalysisVO(
                            id=analysis.id,
                            date=analysis.date,
                            name=analysis.name,
                            value=comprehensive_data,
                        )
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to validate research analysis {analysis.id}: {e}"
                    )
                    continue

            # Apply filters
            filtered_analyses = research_analyses

            # Note: region and topic filtering removed as they're no longer part of stored data
            # Only general filtering by date and other metadata is available

            total_count = len(research_analyses)
            filtered_count = len(filtered_analyses)

            # Apply sorting
            if request.sort_by == "date":
                filtered_analyses.sort(
                    key=lambda x: x.date, reverse=(request.sort_order == "desc")
                )

            # Apply limit
            if request.limit and request.limit > 0:
                filtered_analyses = filtered_analyses[: request.limit]

            return GetResearchAnalysisResponse(
                analyses=filtered_analyses,
                total_count=total_count,
                filtered_count=filtered_count,
                actual_date=target_date,
                is_exact_date_match=True,
                request_params=request,
            )

        except Exception as e:
            logger.error(f"Get research analysis failed: {e}")
            raise

    async def get_research_components_by_date(self, target_date: date) -> dict:
        """Retrieve individual research components by date."""
        try:
            components = {}

            # Get research results
            research_analyses = self.websearch_repository.get_all_analyses(
                name="research_results", target_date=target_date, item_schema=None
            )
            if research_analyses:
                components["research_results"] = research_analyses[0].value

            # Get sector analysis
            sector_analyses = self.websearch_repository.get_all_analyses(
                name="sector_analysis", target_date=target_date, item_schema=None
            )
            if sector_analyses:
                components["sector_analysis"] = sector_analyses[0].value

            # Get leading stocks
            stock_analyses = self.websearch_repository.get_all_analyses(
                name="leading_stocks", target_date=target_date, item_schema=None
            )
            if stock_analyses:
                components["leading_stocks"] = stock_analyses[0].value

            # Get comprehensive analysis
            comprehensive_analyses = self.websearch_repository.get_all_analyses(
                name="comprehensive_research", target_date=target_date, item_schema=None
            )
            if comprehensive_analyses:
                components["comprehensive_research"] = comprehensive_analyses[0].value

            return components

        except Exception as e:
            logger.error(f"Get research components failed: {e}")
            raise

    async def get_latest_analysis_summary(self) -> dict:
        """Get a summary of the latest comprehensive analysis."""
        try:
            today = date.today()
            components = await self.get_research_components_by_date(today)

            if not components:
                return {
                    "message": "No analysis found for today",
                    "date": today.strftime("%Y-%m-%d"),
                }

            summary = {
                "analysis_date": today.strftime("%Y-%m-%d"),
                "components_available": list(components.keys()),
                "summary": {},
            }

            # Add component summaries
            if "research_results" in components:
                research_data = components["research_results"]
                summary["summary"]["research"] = {
                    "total_items": len(research_data.get("research_items", [])),
                    "event_types": list(
                        set(
                            [
                                item.get("event_type")
                                for item in research_data.get("research_items", [])
                            ]
                        )
                    ),
                }

            if "sector_analysis" in components:
                sector_data = components["sector_analysis"]
                analysis = sector_data.get("analysis", {})
                summary["summary"]["sectors"] = {
                    "primary_beneficiaries": len(
                        analysis.get("primary_beneficiaries", [])
                    ),
                    "supply_chain_beneficiaries": len(
                        analysis.get("supply_chain_beneficiaries", [])
                    ),
                    "bottleneck_solution_beneficiaries": len(
                        analysis.get("bottleneck_solution_beneficiaries", [])
                    ),
                    "infrastructure_beneficiaries": len(
                        analysis.get("infrastructure_beneficiaries", [])
                    ),
                }

            if "leading_stocks" in components:
                stocks_data = components["leading_stocks"]
                summary["summary"]["stocks"] = {
                    "total_stocks": len(stocks_data.get("leading_stocks", [])),
                    "recommendations": {},
                }

                # Count recommendations
                for stock in stocks_data.get("leading_stocks", []):
                    rec = stock.get("recommendation", "Unknown")
                    summary["summary"]["stocks"]["recommendations"][rec] = (
                        summary["summary"]["stocks"]["recommendations"].get(rec, 0) + 1
                    )

            return summary

        except Exception as e:
            logger.error(f"Get latest analysis summary failed: {e}")
            raise
