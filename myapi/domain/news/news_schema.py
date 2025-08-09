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


# ETF Portfolio Analysis Schemas
class ETFPortfolioChange(BaseModel):
    ticker: str
    action: Literal["BUY", "SELL", "HOLD"]
    shares_traded: Optional[float] = None
    price_per_share: Optional[float] = None
    total_value: Optional[float] = None
    percentage_of_portfolio: Optional[float] = None
    reason: Optional[str] = None


class ETFPortfolioData(BaseModel):
    etf_name: str
    etf_ticker: str
    date: str
    total_portfolio_value: Optional[float] = None
    changes: List[ETFPortfolioChange]
    summary: str
    source_url: Optional[str] = None


class ETFAnalysisRequest(BaseModel):
    etf_tickers: List[str] = ["ARKK", "QQQ", "VTI", "SPY"]
    target_date: Optional[dt.date] = dt.date.today()


class ETFAnalysisResponse(BaseModel):
    etf_portfolios: List[ETFPortfolioData]


class ETFAnalysisGetRequest(BaseModel):
    etf_tickers: Optional[List[str]] = None
    target_date: Optional[dt.date] = dt.date.today()
    limit: Optional[int] = None
    sort_by: Optional[Literal["date", "etf_name", "total_value"]] = "date"
    sort_order: Optional[Literal["asc", "desc"]] = "desc"


class ETFAnalysisGetResponse(BaseModel):
    etf_analyses: List[ETFPortfolioData]
    total_count: int
    filtered_count: int
    actual_date: Optional[dt.date] = None
    is_exact_date_match: bool = True
    request_params: ETFAnalysisGetRequest


# ETF Analyst Summary Schemas
class ETFMarketContext(BaseModel):
    key_catalysts: List[str]
    sector_rotation_trend: str
    macro_backdrop: str


class ETFIndividualStockAnalysis(BaseModel):
    ticker: str
    action_taken: Literal["BUY", "SELL", "HOLD"]
    fundamental_rationale: str
    technical_rationale: str
    news_catalysts: List[str]
    analyst_sentiment: str
    valuation_assessment: str


class ETFPortfolioStrategyInsights(BaseModel):
    manager_thesis: str
    risk_positioning: str
    time_horizon: str
    peer_comparison: str


class ETFForwardLookingImplications(BaseModel):
    sector_implications: str
    stock_opportunities: List[str]
    risk_factors: List[str]
    retail_investor_takeaways: str


class ETFAnalystSummaryResponse(BaseModel):
    etf_ticker: str
    analysis_date: str
    market_context: ETFMarketContext
    individual_stock_analysis: List[ETFIndividualStockAnalysis]
    portfolio_strategy_insights: ETFPortfolioStrategyInsights
    forward_looking_implications: ETFForwardLookingImplications
    confidence_level: Literal["High", "Medium", "Low"]
    data_sources: List[str]
