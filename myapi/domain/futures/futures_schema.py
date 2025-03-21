from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List, Dict


class FuturesVO(BaseModel):
    id: int
    #  = Column(Integer, primary_key=True, index=True)
    symbol: str
    #  = Column(String, index=True)
    price: float | int
    #  = Column(Float)
    quantity: float | int
    #  = Column(Float)
    side: str
    #  = Column(String)  # "buy" or "sell"
    timestamp: str | datetime
    #  = Column(DateTime, default=datetime.utcnow)
    position_type: str
    #  = Column(String, nullable=True)  # "long" or "short"
    take_profit: float | int
    #  = Column(Float, nullable=True)
    stop_loss: float | int
    #  = Column(Float, nullable=True)
    status: str
    #  = Column(String, default="open")  # "open", "closed", "canceled"


class FuturesBase(BaseModel):
    symbol: str
    price: float
    quantity: float
    side: str


class FuturesCreate(FuturesBase):
    pass


class FuturesResponse(FuturesBase):
    id: int
    timestamp: datetime
    position_type: Optional[str]
    take_profit: Optional[float]
    stop_loss: Optional[float]
    status: Optional[str]

    class Config:
        from_attributes = True


class PivotPoints(BaseModel):
    pivot: float
    support1: float
    resistance1: float
    support2: float
    resistance2: float


class BollingerBands(BaseModel):
    middle_band: float
    upper_band: float
    lower_band: float


class MACDResult(BaseModel):
    macd: float
    signal: float
    histogram: float
    crossover: bool
    crossunder: bool


class Ticker(BaseModel):
    last: float
    bid: Optional[float]
    ask: Optional[float]
    high: Optional[float]
    low: Optional[float]


class TechnicalAnalysis(BaseModel):
    support: Optional[float]
    resistance: Optional[float]
    pivot: Optional[float]
    support2: Optional[float]
    resistance2: Optional[float]
    bollinger_bands: Optional[BollingerBands]
    fibonacci_levels: Dict[str, float]  # 동적 키로 인해 Dict 유지
    macd_divergence: Optional[bool]
    macd_crossover: Optional[bool]
    macd_crossunder: Optional[bool]
    rsi_divergence: Optional[bool]
    volume_trend: Optional[str]


class OpenAISuggestion(BaseModel):
    decision: str
    reasoning: str
    tp: Optional[float]
    sl: Optional[float]
