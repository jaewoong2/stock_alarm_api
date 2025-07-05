from typing import List, Literal, Optional
from pydantic import BaseModel, Field


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

    # id = Column(Integer, primary_key=True, index=True)
    # date_yyyymmdd = Column(String, nullable=False, index=True)
    # outlook = Column(String, nullable=False)
    # reason = Column(String, nullable=False)
    # up_percentage = Column(Float, nullable=True)  # e.g., '70'
    # created_at = Column(DateTime(timezone=True), server_default=func.now())

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
    value: MarketAnalysis  # JSON object containing the analysis data
