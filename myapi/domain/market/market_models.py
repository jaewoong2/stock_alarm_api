from sqlalchemy import Column, Integer, String, DateTime, func

from myapi.database import Base


class WebSearchResult(Base):
    """Universal table for storing web search results for tickers and market."""

    __tablename__ = "web_search_results"
    __table_args__ = {"schema": "crypto"}

    id = Column(Integer, primary_key=True, index=True)
    result_type = Column(String, nullable=False)  # e.g., 'market' or 'ticker'
    ticker = Column(String, nullable=True)
    date_YYYYMMDD = Column(String, nullable=False)
    headline = Column(String, nullable=True)
    summary = Column(String, nullable=True)
    detail_description = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
