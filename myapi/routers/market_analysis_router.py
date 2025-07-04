from datetime import date
from fastapi import APIRouter, Depends
from myapi.domain.market_analysis.market_analysis_schema import MarketAnalysis
from myapi.services.market_analysis_service import MarketAnalysisService

router = APIRouter()

@router.get("/market-analysis", response_model=MarketAnalysis)
async def get_market_analysis(
    today: date,
    market_analysis_service: MarketAnalysisService = Depends(),
) -> MarketAnalysis:
    return await market_analysis_service.get_market_analysis(today)
