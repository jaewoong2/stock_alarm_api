from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from myapi.database import Base


class TickerReference(Base):
    __tablename__ = "tickers_reference"
    __table_args__ = {"schema": "crypto"}

    symbol: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    market_category: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    is_etf: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    exchange: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    ingested_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
