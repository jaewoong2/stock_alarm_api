from sqlalchemy import Column, Integer, Float, String, DateTime
from datetime import datetime
from myapi.database import Base


class Signals(Base):
    __tablename__ = "signals"
    __table_args__ = {"schema": "crypto"}  # 스키마 지정

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, index=True)
    strategy = Column(String, nullable=True)  # JSON 형태로 저장할 수 있음
    entry_price = Column(Float)
    stop_loss = Column(Float, nullable=True)
    take_profit = Column(Float, nullable=True)
    action = Column(String)  # "buy" or "sell"
    timestamp = Column(DateTime, default=datetime.utcnow)
    probability = Column(String, nullable=True)  # 확률
    result_description = Column(String, nullable=True)  # 결과 설명
    report_summary = Column(String, nullable=True)  # 보고서 요약
