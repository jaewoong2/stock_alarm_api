from datetime import date
from typing import Literal, Optional

from myapi.utils.date_utils import validate_date
from fastapi import APIRouter, Depends

from myapi.utils.auth import verify_bearer_token
from dependency_injector.wiring import inject, Provide

from myapi.containers import Container
from myapi.domain.news.news_schema import (
    WebSearchMarketResponse,
    WebSearchResultSchema,
    SectorMomentumResponse,
    MarketAnalysis,
)
from myapi.services.signal_service import SignalService
from myapi.services.ai_service import AIService
from myapi.services.web_search_service import WebSearchService

router = APIRouter(prefix="/news", tags=["news"])


@router.get("/", response_model=dict)
@inject
def get_news(
    ticker: Optional[str] = "",
    news_type: Literal["ticker", "market"] = "market",
    news_date: Optional[date] = date.today(),
    signal_service: SignalService = Depends(Provide[Container.services.signal_service]),
):
    today_str = validate_date(news_date if news_date else date.today())
    result = signal_service.get_web_search_summary(
        type=news_type,
        ticker=ticker,
        date=today_str,
    )
    return {"result": [r.model_dump() for r in result]}


@router.get("/recommendations")
@inject
def news_recommendations(
    recommendation: Literal["Buy", "Hold", "Sell"] = "Buy",
    limit: int = 5,
    request_date: Optional[date] = date.today(),
    signal_service: SignalService = Depends(Provide[Container.services.signal_service]),
):
    valid_date = validate_date(
        request_date if request_date is not None else date.today()
    )
    results = signal_service.get_ticker_news_by_recommendation(
        recommendation=recommendation,
        limit=limit,
        date=valid_date,
    )
    return {"results": results}


@router.get(
    "/summary",
    dependencies=[Depends(verify_bearer_token)],
)
@inject
def news_summary(
    signal_service: SignalService = Depends(Provide[Container.services.signal_service]),
    ai_service: AIService = Depends(Provide[Container.services.ai_service]),
):
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


@router.get("/market-forecast")
@inject
def market_forecast(
    forecast_date: date = date.today(),
    source: Literal["Major", "Minor"] = "Major",
    websearch_service: WebSearchService = Depends(
        Provide[Container.services.websearch_service]
    ),
):
    forecast_date = validate_date(forecast_date)

    return websearch_service.forecast_market(forecast_date, source=source)


@router.get("/sector-momentum")
@inject
def sector_momentum(
    request_date: date = date.today(),
    websearch_service: WebSearchService = Depends(
        Provide[Container.services.websearch_service]
    ),
):
    request_date = validate_date(request_date)
    result = websearch_service.analyze_sector_momentum(request_date)
    return result


@router.get("/market-analysis", response_model=MarketAnalysis)
@inject
def market_analysis(
    today: date,
    websearch_service: WebSearchService = Depends(
        Provide[Container.services.websearch_service]
    ),
):
    today = validate_date(today)
    return websearch_service.get_market_analysis(today)
