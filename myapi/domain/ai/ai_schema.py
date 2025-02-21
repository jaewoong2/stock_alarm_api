from typing import List, Optional
from pydantic import BaseModel, Field


class OrderRequest(BaseModel):
    side: str  # "BUY" or "SELL"
    quote_currency: str  # e.g., "KRW"
    target_currency: str  # e.g., "BTC"
    type: str  # "LIMIT", "MARKET", "STOP_LIMIT"
    price: Optional[str] = None  # required for LIMIT or STOP_LIMIT
    qty: Optional[str] = None  # required for LIMIT, STOP_LIMIT, or MARKET SELL
    amount: Optional[str] = None  # required for MARKET BUY
    post_only: Optional[bool] = None  # applies to LIMIT orders
    limit_price: Optional[str] = None  # applies to MARKET orders
    trigger_price: Optional[str] = None  # required for STOP_LIMIT orders


class Action(BaseModel):
    order: OrderRequest
    reason: str  # e.g., "Bollinger breakout with overbought signal"
    priority: int  # 1-5 (1 = highest)
    action: str  # "SELL" | "BUY" | "HOLD"


class SixHOutlook(BaseModel):
    outlook: str  # "BULLISH", "BEARISH", or "MIXED"
    confidence: float  # confidence level between 0 and 1


class TradingResponse(BaseModel):
    # Using alias for "6h_outlook" to match JSON key requirement.
    six_h_outlook: SixHOutlook = Field(..., alias="6h_outlook")
    actions: List[Action]
    time_window: str  # e.g., "6h" or "15m"
    learned_insight: str  # e.g., "Reduced qty due to past overbought losses"
