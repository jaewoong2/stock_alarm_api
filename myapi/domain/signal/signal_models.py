from sqlalchemy import Column, Integer, Float, String, DateTime, JSON
from datetime import datetime
from zoneinfo import ZoneInfo
from myapi.database import Base


KST = ZoneInfo("Asia/Seoul")


def _now_kst_naive() -> datetime:
    """Return current time in Asia/Seoul without tzinfo for DB storage."""

    return datetime.now(KST).replace(tzinfo=None)


class Signals(Base):
    __tablename__ = "signals"
    __table_args__ = {"schema": "crypto"}  # 스키마 지정

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, index=True)
    strategy = Column(String, nullable=True)  # JSON 형태로 저장할 수 있음
    entry_price = Column(Float)
    stop_loss = Column(Float, nullable=True)
    take_profit = Column(Float, nullable=True)
    close_price = Column(Float, nullable=True)  # 거래 종료 가격
    action = Column(String)  # "buy" or "sell"
    timestamp = Column(DateTime, default=_now_kst_naive)
    probability = Column(String, nullable=True)  # 확률
    result_description = Column(String, nullable=True)  # 결과 설명
    report_summary = Column(String, nullable=True)  # 보고서 요약
    ai_model = Column(String, nullable=True, default="OPENAI_O4MINI")  # AI 모델 이름
    senario = Column(String, nullable=True)  # 시나리오 설명 250606 추가
    good_things = Column(String, nullable=True)  # 좋은 점 250606 추가
    bad_things = Column(String, nullable=True)  # 나쁜 점 250606 추가
    chart_pattern = Column(JSON, nullable=True)
