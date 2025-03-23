from sqlalchemy import Column, Integer, Float, String, DateTime
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from myapi.database import Base


class Futures(Base):
    __tablename__ = "futures"
    __table_args__ = {"schema": "crypto"}  # 스키마 지정

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True)
    price = Column(Float)
    quantity = Column(Float)
    side = Column(String)  # "buy" or "sell"
    timestamp = Column(DateTime, default=datetime.utcnow)
    position_type = Column(String, nullable=True)  # "long" or "short"
    take_profit = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=True)
    # status = Column(String, default="open")  # "open", "closed", "canceled"
    status: Mapped[str] = mapped_column(String(50), default="open")
    order_id = Column(String, nullable=True, index=True, unique=True)
    parent_order_id = Column(String, nullable=True)
