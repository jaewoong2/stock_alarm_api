from datetime import date as d, datetime
from typing import Any, Optional

from sqlalchemy import Date, DateTime, Float, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from myapi.database import Base


class WebSearchResult(Base):
    """Universal table for storing web search results for tickers and market."""

    __tablename__ = "web_search_results"
    __table_args__ = {"schema": "crypto"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    result_type: Mapped[str] = mapped_column(String, nullable=False)
    ticker: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    date_yyyymmdd: Mapped[str] = mapped_column(String, nullable=False)
    headline: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    detail_description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    recommendation: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class MarketForecast(Base):
    """Table to store daily US market forecasts."""

    __tablename__ = "market_forecasts"
    __table_args__ = {"schema": "crypto"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    date_yyyymmdd: Mapped[str] = mapped_column(String, nullable=False, index=True)
    outlook: Mapped[str] = mapped_column(String, nullable=False)
    reason: Mapped[str] = mapped_column(String, nullable=False)
    up_percentage: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    source: Mapped[str] = mapped_column(String, nullable=False)


class AiAnalysisModel(Base):
    __tablename__ = "ai_analysis"
    __table_args__ = {"schema": "crypto"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    date: Mapped[d] = mapped_column(Date, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False, default="market_analysis")
    value: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
