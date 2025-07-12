from datetime import date as date_, datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel


class TickerVO(BaseModel):
    id: int
    symbol: str
    name: str
    price: float
    open_price: Optional[float] = None
    high_price: Optional[float] = None
    low_price: Optional[float] = None
    close_price: Optional[float] = None
    volume: Optional[int] = None
    date: Optional[date_] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

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
    date: Optional[date_] = None


class TickerUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[float] = None
    open_price: Optional[float] = None
    high_price: Optional[float] = None
    low_price: Optional[float] = None
    close_price: Optional[float] = None
    volume: Optional[int] = None
    date: Optional[date_] = None


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
    date: Optional[date_] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# 날짜 기반 요청을 위한 스키마
class TickerDateQuery(BaseModel):
    symbol: str
    date: date_


# 다중 날짜 비교 요청을 위한 스키마
class TickerMultiDateQuery(BaseModel):
    symbol: str
    dates: List[date_]


# 날짜별 변화율 응답을 위한 스키마
class TickerChangeResponse(BaseModel):
    date: date_
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


class SignalAccuracyResponse(BaseModel):
    """시그널 예측 정확도 평가 응답 스키마"""

    ticker: str
    action: Optional[str] = None  # buy, sell, hold
    entry_price: float = 0
    prediction_date: Optional[date_] = None
    check_date: Optional[date_] = None
    initial_price: Optional[float] = None
    final_price: Optional[float] = None
    actual_result: Optional[str] = None  # 상승, 하락, 유지
    is_accurate: bool = False
    accuracy_details: str = ""


class TickerLatestWithChangeResponse(BaseModel):
    symbol: str
    date: Optional[date_]
    open_price: Optional[float] = None
    high_price: Optional[float] = None
    low_price: Optional[float] = None
    close_price: Optional[float] = None
    volume: Optional[int] = None
    name: Optional[str] = None
    close_change: Optional[float] = None
    volume_change: Optional[float] = None
    signal: Optional[Dict] = None


class UpdateTickerRequest(BaseModel):
    """티커 업데이트 요청 스키마"""

    start_date: Optional[str]  # 시작 날짜 (YYYY-MM-DD 형식)
    end_date: Optional[str]  # 종료 날짜 (YYYY-MM-DD 형식)


class TickerOrderBy(BaseModel):
    """티커 정렬 기준 스키마"""

    field: Literal["close_change", "volume_change"] = (
        "close_change"  # 정렬할 필드 이름 (예: 'price', 'date')
    )
    direction: Literal["asc", "desc"] = "desc"  # 정렬 방향 ('asc' 또는 'desc')
