from sqlalchemy import Column, Float, Integer, String, DateTime, Date, JSON, func

from myapi.database import Base


class WebSearchResult(Base):
    """Universal table for storing web search results for tickers and market."""

    __tablename__ = "web_search_results"
    __table_args__ = {"schema": "crypto"}

    id = Column(Integer, primary_key=True, index=True)
    result_type = Column(String, nullable=False)  # e.g., 'market' or 'ticker'
    ticker = Column(String, nullable=True)
    date_yyyymmdd = Column(String, nullable=False)
    headline = Column(String, nullable=True)
    summary = Column(String, nullable=True)
    detail_description = Column(String, nullable=True)
    recommendation = Column(String, nullable=True)  # e.g., 'buy', 'sell', 'hold'
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class MarketForecast(Base):
    """Table to store daily US market forecasts."""

    __tablename__ = "market_forecasts"
    __table_args__ = {"schema": "crypto"}

    id = Column(Integer, primary_key=True, index=True)
    date_yyyymmdd = Column(String, nullable=False, index=True)
    outlook = Column(String, nullable=False)
    reason = Column(String, nullable=False)
    up_percentage = Column(Float, nullable=True)  # e.g., '70'
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    source = Column(String, nullable=False)  # e.g., 'Major' or 'Minor'


class AiAnalysisModel(Base):
    __tablename__ = "ai_analysis"
    __table_args__ = {"schema": "crypto"}

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False, unique=True)
    name = Column(String, nullable=False, default="market_analysis")
    value = Column(JSON, nullable=False)
    name = Column(String, nullable=False)
