from typing import List
from openai import BaseModel
from pandas import DataFrame
from sqlalchemy import Column, String, Integer, Float, DateTime, Text, Enum
from sqlalchemy.ext.declarative import declarative_base
import enum

from myapi.domain.backdata.backdata_schema import (
    ArticleResponseType,
    SentimentResponseType,
)
from myapi.domain.trading.coinone_schema import (
    ActiveOrdersResponse,
    Balance,
    GetTradingInformationResponseModel,
    OrderBookResponse,
)

Base = declarative_base()


class ActionEnum(enum.Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class ExecutionStatus(enum.Enum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"


class Trade(Base):
    __tablename__ = "trades"
    __table_args__ = {"schema": "crypto"}  # 스키마 지정

    id = Column(Integer, primary_key=True)
    # 결정/실행 시각
    timestamp = Column(DateTime, nullable=False)
    # 종목 (예: BTC, ETH 등)
    symbol = Column(String(10), nullable=False)
    # BUY, SELL, HOLD 중 하나
    action = Column(Enum(ActionEnum), nullable=False)
    # 매수/매도 수량
    amount = Column(Float, nullable=False)

    action_string = Column(Text, nullable=False)
    # 모델이 준 설명 또는 요약본
    reason = Column(Text, nullable=True)
    # 거래 내역에 대한 요약
    summary = Column(Text, nullable=True)
    # 입력된 데이터 (시세, 전략, 뉴스 등 중요한 데이터)
    openai_prompt = Column(Text, nullable=True)
    # 체결된 KRW 가격 (매매 완료 후)
    execution_krw = Column(Float, nullable=True)
    # 체결된 Crypto 가격 (매매 완료 후)
    execution_crypto = Column(Float, nullable=True)
    # 체결 성공/실패 여부
    status = Column(Enum(ExecutionStatus), nullable=False)

    # 입력된 데이터 (시세, 전략, 뉴스 등 중요한 데이터)
    action_string = Column(Text, nullable=True)


class BackdataInformations(BaseModel):
    trading_info: GetTradingInformationResponseModel
    market_data: dict
    candles_info: DataFrame
    orderbook: OrderBookResponse
    balances: List[Balance]
    news: ArticleResponseType
    sentiment: SentimentResponseType
    active_orders: ActiveOrdersResponse
    current_time: str
    technical_indicators: dict
