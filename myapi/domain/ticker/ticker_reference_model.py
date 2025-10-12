from sqlalchemy import Boolean, Column, DateTime, String

from myapi.database import Base


class TickerReference(Base):
    __tablename__ = "tickers_reference"
    __table_args__ = {"schema": "crypto"}

    symbol = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    market_category = Column(String, nullable=True)
    is_etf = Column(Boolean, nullable=False, default=False)
    exchange = Column(String, nullable=True)
    ingested_at_utc = Column(DateTime(timezone=True), nullable=False)
