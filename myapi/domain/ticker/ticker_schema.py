import datetime
from typing import List, Optional

from pydantic import BaseModel


class TickerVO(BaseModel):
    symbol: str
    name: str
    price: float
    open_price: Optional[float] = None
    high_price: Optional[float] = None
    low_price: Optional[float] = None
    close_price: Optional[float] = None
    volume: Optional[int] = None
    date: Optional[datetime.date] = None
    created_at: Optional[datetime.datetime] = None
    updated_at: Optional[datetime.datetime] = None

    class Config:
        from_attributes = True


class TickerBase(BaseModel):
    symbol: str
    name: str
    price: float


class TickerCreate(TickerBase):
    open_price: Optional[float] = None
    high_price: Optional[float] = None
    low_price: Optional[float] = None
    close_price: Optional[float] = None
    volume: Optional[int] = None
    date: Optional[datetime.date] = None


class TickerUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[float] = None
    open_price: Optional[float] = None
    high_price: Optional[float] = None
    low_price: Optional[float] = None
    close_price: Optional[float] = None
    volume: Optional[int] = None
    date: Optional[datetime.date] = None


class TickerResponse(BaseModel):
    id: int
    symbol: str
    name: str
    price: float
    open_price: Optional[float] = None
    high_price: Optional[float] = None
    low_price: Optional[float] = None
    close_price: Optional[float] = None
    volume: Optional[int] = None
    date: Optional[datetime.date] = None
    created_at: Optional[datetime.datetime] = None
    updated_at: Optional[datetime.datetime] = None

    class Config:
        from_attributes = True


# 날짜 기반 요청을 위한 스키마
class TickerDateQuery(BaseModel):
    symbol: str
    date: datetime.date


# 다중 날짜 비교 요청을 위한 스키마
class TickerMultiDateQuery(BaseModel):
    symbol: str
    dates: List[datetime.date]


# 날짜별 변화율 응답을 위한 스키마
class TickerChangeResponse(BaseModel):
    date: datetime.date
    symbol: str
    open_price: Optional[float] = None
    high_price: Optional[float] = None
    low_price: Optional[float] = None
    close_price: Optional[float] = None
    volume: Optional[int] = None

    # 전일 대비 변화
    open_change: Optional[float] = None  # 시가 변화율
    close_change: Optional[float] = None  # 종가 변화율
    price_change: Optional[float] = None  # 가격 변화율
    volume_change: Optional[float] = None  # 거래량 변화율

    class Config:
        from_attributes = True
