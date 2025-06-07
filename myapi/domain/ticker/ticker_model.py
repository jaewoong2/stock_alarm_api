from sqlalchemy import Column, Float, Integer, String, DateTime, Date
from sqlalchemy.sql import func
from myapi.database import Base


class Ticker(Base):
    __tablename__ = "tickers"
    __table_args__ = {"schema": "crypto"}  # 스키마 지정

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True)
    name = Column(String)
    price = Column(Float)

    # OHLCV 데이터
    open_price = Column(Float, nullable=True)
    high_price = Column(Float, nullable=True)
    low_price = Column(Float, nullable=True)
    close_price = Column(Float, nullable=True)
    volume = Column(Integer, nullable=True)

    # 날짜 필드 추가
    date = Column(Date, nullable=True, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
