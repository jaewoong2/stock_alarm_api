from datetime import date
from typing import Literal, Optional
from fastapi import APIRouter, Depends
from dependency_injector.wiring import inject, Provide

from myapi.containers import Container
from myapi.domain.news.news_schema import WebSearchMarketResponse
from myapi.services.signal_service import SignalService
from myapi.services.ai_service import AIService

router = APIRouter(prefix="/news", tags=["news"])


@router.get("/")
@inject
def get_news(
    ticker: Optional[str] = "",
    news_type: Literal["ticker", "market"] = "market",
    news_date: Optional[date] = date.today(),
    signal_service: SignalService = Depends(Provide[Container.services.signal_service]),
):
    today_str = date.today() if news_date is None else news_date
    result = signal_service.get_web_search_summary(
        type=news_type,
        ticker=ticker,
        date=today_str,
    )
    return {"result": result}


@router.get("/recommendations")
@inject
def news_recommendations(
    recommendation: Literal["Buy", "Hold", "Sell"] = "Buy",
    limit: int = 5,
    date: Optional[date] = date.today(),
    signal_service: SignalService = Depends(Provide[Container.services.signal_service]),
):
    return {
        "results": signal_service.get_ticker_news_by_recommendation(
            recommendation=recommendation,
            limit=limit,
            date=date,
        )
    }


@router.get("/summary", response_model=WebSearchMarketResponse)
@inject
def news_summary(
    signal_service: SignalService = Depends(Provide[Container.services.signal_service]),
    ai_service: AIService = Depends(Provide[Container.services.ai_service]),
) -> WebSearchMarketResponse | str:
    today_str = date.today().strftime("%Y-%m-%d")
    prompt = signal_service.generate_us_market_prompt(today_str)
    result = ai_service.gemini_search_grounding(
        prompt=prompt,
        schema=WebSearchMarketResponse,
    )
    if isinstance(result, WebSearchMarketResponse):
        signal_service.save_web_search_results(
            result_type="market",
            results=result.search_results,
        )
    return result
