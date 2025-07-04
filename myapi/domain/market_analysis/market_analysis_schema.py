from pydantic import BaseModel, Field
from typing import List, Optional


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
    value: dict  # JSON object containing the analysis data

    class Config:
        orm_mode = True  # Enable ORM mode for compatibility with SQLAlchemy models
