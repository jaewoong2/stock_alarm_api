from datetime import date
import logging
from fastapi import HTTPException
from myapi.domain.market_analysis.market_analysis_schema import (
    MarketAnalysis,
    MarketAnalysisResponse,
)
from myapi.repositories.market_analysis_repository import MarketAnalysisRepository
from myapi.services.ai_service import AIService

logger = logging.getLogger(__name__)


class MarketAnalysisService:
    def __init__(
        self,
        market_analysis_repository: MarketAnalysisRepository,
        ai_service: AIService,
    ):
        self.market_analysis_repository = market_analysis_repository
        self.ai_service = ai_service

    def _build_prompt(self, today: str) -> str:
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

    async def get_market_analysis(self, today: date) -> MarketAnalysis:
        logger.info(f"Fetching market analysis for {today}")
        cached_analysis = self.market_analysis_repository.get_by_date(today)
        if cached_analysis:
            logger.info(f"Cache hit for market analysis on {today}")
            return MarketAnalysis.model_validate(cached_analysis.value)

        logger.info(f"Cache miss for {today}. Fetching from Perplexity API.")
        prompt = self._build_prompt(today.strftime("%Y-%m-%d"))

        try:
            response = self.ai_service.perplexity_completion(
                prompt=prompt,
                schema=MarketAnalysisResponse,
            )
        except Exception as e:
            logger.error(f"Error fetching from Perplexity API: {e}")
            raise HTTPException(
                status_code=500, detail="Failed to fetch data from AI service."
            )

        if not isinstance(response, MarketAnalysisResponse):
            logger.error(f"Invalid response format from AI service: {type(response)}")
            raise HTTPException(
                status_code=500, detail="Invalid response format from AI service."
            )

        analysis_data = response.analysis
        self.market_analysis_repository.create(today, analysis_data)
        logger.info(f"Successfully fetched and cached market analysis for {today}")

        return analysis_data
