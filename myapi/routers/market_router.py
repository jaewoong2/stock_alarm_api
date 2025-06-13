from datetime import date
from fastapi import APIRouter, Depends
from dependency_injector.wiring import inject, Provide

from myapi.containers import Container
from myapi.domain.market.market_schema import WebSearchMarketResponse
from myapi.services.signal_service import SignalService
from myapi.services.ai_service import AIService

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/news-summary", response_model=WebSearchMarketResponse)
@inject
def market_news_summary(
    signal_service: SignalService = Depends(Provide[Container.services.signal_service]),
    ai_service: AIService = Depends(Provide[Container.services.ai_service]),
) -> WebSearchMarketResponse | str:
    today_str = date.today().strftime("%Y-%m-%d")
    return signal_service.get_us_market_info(today_str, ai_service=ai_service)
