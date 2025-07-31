from pydantic import BaseModel, Field
from typing import List, Literal, Optional, Any, Dict
import datetime as dt
from myapi.domain.signal.signal_schema import DefaultTickers


class MahaneySourceItem(BaseModel):
    id: str
    name: Optional[str] = None
    url: Optional[str] = None
    date: Optional[str] = None


class MahaneyCriterionEvaluation(BaseModel):
    pass_criterion: bool
    score: int
    metric: str
    comment: str


class MahaneyStockAnalysis(BaseModel):
    stock_name: str
    revenue_growth: MahaneyCriterionEvaluation
    valuation: MahaneyCriterionEvaluation
    product_innovation: MahaneyCriterionEvaluation
    tam: MahaneyCriterionEvaluation
    customer_value: MahaneyCriterionEvaluation
    management_quality: MahaneyCriterionEvaluation
    timing: MahaneyCriterionEvaluation
    final_assessment: str
    recommendation: Literal["Buy", "Sell", "Hold"]
    recommendation_score: str
    summary: str
    detail_summary: str


class MahaneyAnalysisData(BaseModel):
    stocks: List[MahaneyStockAnalysis]


class MahaneyAnalysisResponse(BaseModel):
    response: MahaneyAnalysisData


class WebSearchMarketItem(BaseModel):
    issued_YYYYMMDD: str
    headline: str
    summary: str
    full_description: str
    recommendation: Literal["Buy", "Hold", "Sell"]


class WebSearchMarketResponse(BaseModel):
    search_results: List[WebSearchMarketItem]


class MarketForecastResponse(BaseModel):
    outlook: Literal["UP", "DOWN"]
    reason: str
    up_percentage: Optional[float]


class MarketForecastSchema(BaseModel):
    """Table to store daily US market forecasts."""

    date_yyyymmdd: str
    outlook: Literal["UP", "DOWN"]
    reason: str
    up_percentage: Optional[float] = None  # e.g., '70'
    created_at: Optional[str] = None  # ISO format string for datetime


class WebSearchResultSchema(BaseModel):
    id: Optional[int] = None
    result_type: str
    ticker: Optional[str] = None
    date_yyyymmdd: str
    headline: Optional[str] = None
    summary: Optional[str] = None
    detail_description: Optional[str] = None
    recommendation: Optional[str] = None
    created_at: Optional[str] = None


class KeyNewsSchema(BaseModel):
    headline: str
    source: str
    summary: str


class StockMomentumSchema(BaseModel):
    ticker: str
    name: str
    pre_market_change: str
    key_news: KeyNewsSchema
    short_term_strategy: str


class SectorThemeSchema(BaseModel):
    key_theme: str
    stocks: List[StockMomentumSchema]


class MomentumSectorSchema(BaseModel):
    sector_ranking: int
    sector: str
    reason: str
    risk_factor: str
    themes: List[SectorThemeSchema]


class MarketOverviewSchema(BaseModel):
    summary: str
    major_catalysts: List[str]


class SectorMomentumResponse(BaseModel):
    analysis_date_est: str
    market_overview: MarketOverviewSchema
    top_momentum_sectors: List[MomentumSectorSchema]


class KeyNews(BaseModel):
    headline: str
    source: str
    summary: str


class Stock(BaseModel):
    ticker: str
    name: str
    pre_market_change: str
    key_news: KeyNews
    short_term_strategy: str


class Theme(BaseModel):
    key_theme: str
    stocks: List[Stock]


class TopMomentumSector(BaseModel):
    sector_ranking: int
    sector: str
    reason: str
    risk_factor: str
    themes: List[Theme]


class MarketOverview(BaseModel):
    summary: str
    major_catalysts: List[str]


class MarketAnalysis(BaseModel):
    analysis_date_est: str = Field(..., alias="analysis_date_est")
    market_overview: MarketOverview
    top_momentum_sectors: List[TopMomentumSector]


class MarketAnalysisResponse(BaseModel):
    analysis: MarketAnalysis


class AiAnalysisVO(BaseModel):
    id: Optional[int]
    date: str  # ISO format string for date
    name: str
    value: Any  # JSON object containing the analysis data


class MahaneyAnalysisRequest(BaseModel):
    tickers: List[str] = DefaultTickers
    target_date: Optional[dt.date] = dt.date.today()


class MahaneyAnalysisGetRequest(BaseModel):
    target_date: Optional[dt.date] = dt.date.today()
    tickers: Optional[List[str]] = None
    recommendation: Optional[Literal["Buy", "Sell", "Hold"]] = None
    limit: Optional[int] = None
    sort_by: Optional[Literal["recommendation_score", "final_assessment", "stock_name"]] = "stock_name"
    sort_order: Optional[Literal["asc", "desc"]] = "asc"


class MahaneyAnalysisGetResponse(BaseModel):
    stocks: List[MahaneyStockAnalysis]
    total_count: int
    filtered_count: int
    actual_date: Optional[dt.date] = None  # 실제 사용된 데이터의 날짜
    is_exact_date_match: bool = True  # 요청한 날짜와 정확히 일치하는지
    request_params: MahaneyAnalysisGetRequest
