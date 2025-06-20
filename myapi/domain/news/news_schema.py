from typing import List, Literal, Optional
from pydantic import BaseModel


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
