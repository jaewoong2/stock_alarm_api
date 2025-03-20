from sqlalchemy import ARRAY, Column, String, Integer, Float, DateTime, Text, Enum
from sqlalchemy.ext.declarative import declarative_base
import enum
from uuid import UUID

Base = declarative_base()


class ActionEnum(enum.Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    CANCLE = "CANCLE"


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
    action = Column(
        Enum(ActionEnum, name="actionenum", create_type=True), nullable=False
    )
    # 매수/매도 수량``
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


# SQLAlchemy 모델
class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = {"schema": "crypto"}  # 스키마 지정

    id = Column(Integer, primary_key=True, index=True)
    currency = Column(String, nullable=False)  # 필수
    qty = Column(Float, nullable=True)  # nullable
    avarage_price = Column(Float, nullable=True)  # nullable
    total_price = Column(Float, nullable=False)  # 필수
    fee = Column(Float, nullable=True)  # nullable
    timestamp = Column(DateTime, nullable=False)

    trade_id = Column(String, nullable=False)
    order_id = Column(String, nullable=False)
    action = Column(Enum(ActionEnum), nullable=False)


class ProfitLoss(Base):
    __tablename__ = "profit_loss"
    __table_args__ = {"schema": "crypto"}  # 스키마 지정
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=True, index=True)
    sell_trade_id = Column(Integer, nullable=False, index=True)
    buy_trade_ids = Column(ARRAY(Integer), nullable=False, index=True)
    realized_pl = Column(Float, nullable=False)
    cumulative_pl = Column(Float, nullable=False)
    calculated_at = Column(DateTime(timezone=True))
    last_processed_trade_id = Column(Integer, index=True)
