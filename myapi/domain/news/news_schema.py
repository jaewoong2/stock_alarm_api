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
    sort_by: Optional[
        Literal["recommendation_score", "final_assessment", "stock_name"]
    ] = "stock_name"
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
    ticker: str = Field(
        default="", description="ETF ticker for JSON filtering"
    )  # JSON 필터링용 필드 추가
    date: str
    total_portfolio_value: Optional[float] = None
    changes: List[ETFPortfolioChange]
    summary: str
    source_url: Optional[str] = None

    def model_post_init(self, __context):
        """ETF ticker 값을 ticker 필드에도 복사"""
        if not self.ticker and self.etf_ticker:
            self.ticker = self.etf_ticker.upper()


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


# ---------------------- Weekly Insider Trend ----------------------
class SourceRef(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    date: Optional[str] = None
    confidence: Optional[float] = None  # 0.0~1.0


class InsiderTradeItem(BaseModel):
    ticker: str
    insider_name: Optional[str] = None
    insider_role: Optional[str] = None
    action: Literal["BUY", "SELL"]
    shares: Optional[float] = None
    est_value: Optional[float] = None
    rationale: Optional[str] = None
    sources: List[str] = []
    source_details: List[SourceRef] = []
    source_confidence: Optional[float] = None
    filing_url: Optional[str] = None
    cik: Optional[str] = None
    date: Optional[str] = None


class InsiderTrendResponse(BaseModel):
    items: List[InsiderTradeItem]
    window: str


class InsiderTrendGetRequest(BaseModel):
    target_date: Optional[dt.date] = dt.date.today()
    tickers: Optional[List[str]] = None
    action: Optional[Literal["BUY", "SELL"]] = None
    limit: Optional[int] = None
    sort_by: Optional[Literal["date", "value"]] = None
    sort_order: Optional[Literal["asc", "desc"]] = "desc"


class InsiderTrendGetResponse(BaseModel):
    items: List[InsiderTradeItem]
    total_count: int
    filtered_count: int
    actual_date: Optional[dt.date] = None
    is_exact_date_match: bool = True
    request_params: InsiderTrendGetRequest


# ---------------------- Analyst Price Target Weekly ----------------------
class AnalystPTItem(BaseModel):
    ticker: str
    action: Literal["UP", "DOWN", "INIT", "DROP"]
    broker: Optional[str] = None
    broker_rating: Optional[str] = None  # Buy/Hold/Sell 등
    old_pt: Optional[float] = None
    new_pt: Optional[float] = None
    consensus: Optional[float] = None
    upside_pct: Optional[float] = None
    rationale: Optional[str] = None
    sources: List[str] = []
    source_details: List[SourceRef] = []
    impact_score: Optional[float] = None
    date: Optional[str] = None
    published_at: Optional[str] = None


class AnalystPTResponse(BaseModel):
    items: List[AnalystPTItem]
    window: str


class AnalystPTGetRequest(BaseModel):
    target_date: Optional[dt.date] = dt.date.today()
    tickers: Optional[List[str]] = None
    action: Optional[Literal["UP", "DOWN", "INIT", "DROP"]] = None
    limit: Optional[int] = None
    sort_by: Optional[Literal["impact", "date"]] = None
    sort_order: Optional[Literal["asc", "desc"]] = "desc"


class AnalystPTGetResponse(BaseModel):
    items: List[AnalystPTItem]
    total_count: int
    filtered_count: int
    actual_date: Optional[dt.date] = None
    is_exact_date_match: bool = True
    request_params: AnalystPTGetRequest


# ---------------------- ETF Weekly Flows ----------------------
class ETFFlowItem(BaseModel):
    ticker: str
    name: Optional[str] = None
    net_flow: Optional[float] = None
    flow_1w: Optional[float] = None
    volume_change: Optional[float] = None
    sector: Optional[str] = None
    themes: List[str] = []
    sector_inferred: Optional[bool] = None
    evidence: Optional[str] = None
    source: Optional[str] = None
    source_details: List[SourceRef] = []


class ETFWeeklyFlowResponse(BaseModel):
    items: List[ETFFlowItem]
    window: str


class ETFWeeklyFlowGetRequest(BaseModel):
    target_date: Optional[dt.date] = dt.date.today()
    provider: Optional[str] = None
    sector_only: Optional[bool] = False
    tickers: Optional[List[str]] = None


class ETFWeeklyFlowGetResponse(BaseModel):
    items: List[ETFFlowItem]
    total_count: int
    filtered_count: int
    actual_date: Optional[dt.date] = None
    is_exact_date_match: bool = True
    request_params: ETFWeeklyFlowGetRequest


# ---------------------- US Liquidity Weekly ----------------------
class LiquidityPoint(BaseModel):
    date: str
    m2: Optional[float] = None
    rrp: Optional[float] = None


class LiquidityWeeklyResponse(BaseModel):
    series_m2: List[LiquidityPoint] = []
    series_rrp: List[LiquidityPoint] = []
    commentary: Optional[str] = None
    window: Optional[str] = None
    sources: List[SourceRef] = []


# ---------------------- Market Breadth Daily ----------------------
class BreadthDailyPoint(BaseModel):
    date: str
    vix: Optional[float] = None
    advancers: Optional[int] = None
    decliners: Optional[int] = None
    new_highs: Optional[int] = None
    new_lows: Optional[int] = None
    trin: Optional[float] = None


class MarketBreadthResponse(BaseModel):
    series: List[BreadthDailyPoint] = []
    commentary: Optional[str] = None
    sources: List[SourceRef] = []
