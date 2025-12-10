from datetime import datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo

from sqlalchemy import DateTime, Float, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from myapi.database import Base


KST = ZoneInfo("Asia/Seoul")


def _now_kst_naive() -> datetime:
    """Return current time in Asia/Seoul without tzinfo for DB storage."""

    return datetime.now(KST).replace(tzinfo=None)


class Signals(Base):
    __tablename__ = "signals"
    __table_args__ = {"schema": "crypto"}  # 스키마 지정

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    ticker: Mapped[str] = mapped_column(String, index=True)
    strategy: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    entry_price: Mapped[float] = mapped_column(Float)
    stop_loss: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    take_profit: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    close_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    action: Mapped[str] = mapped_column(String)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=_now_kst_naive)
    probability: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    result_description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    report_summary: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    ai_model: Mapped[Optional[str]] = mapped_column(
        String, nullable=True, default="OPENAI_O4MINI"
    )
    senario: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    good_things: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    bad_things: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    chart_pattern: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
