from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

from myapi.domain.trading.coinone_schema import OrderRequest


class OrderSide(str, Enum):
    BUY = "BUY"
    CANCLE = "CANCLE"


class OrderType(str, Enum):
    LIMIT = "LIMIT"
    MARKET = "MARKET"
    STOP_LIMIT = "STOP_LIMIT"


class ActionType(str, Enum):
    SELL = "SELL"
    BUY = "BUY"
    HOLD = "HOLD"
    CANCEL = "CANCEL"


class OutlookEnum(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    MIXED = "MIXED"


class Action(BaseModel):
    order: Optional[OrderRequest] = Field(..., description="The order request details")
    reason: str = Field(
        ...,
        description="Reason for the order (e.g., 'Bollinger breakout with overbought signal')",
    )
    # - "prediction": "UP" | "DOWN" (If the price will be up, "UP" else the price will be down, "DOWN")
    # - "market_outlook": string describing your best guess if price will rise or fall in the next few hours
    prediction: str = Field(
        ...,
        description="UP | DOWN (If the price will be up, 'UP' else the price will be down, 'DOWN'",
    )
    market_outlook: str = Field(
        ...,
        description="string describing your best guess if price will rise or fall in the next few hours",
    )
    priority: int = Field(..., description="Priority level (1 highest to 5 lowest)")

    action: ActionType = Field(
        ..., description="Action type: SELL, BUY, CANCEL, or HOLD"
    )

    model_config = ConfigDict(extra="ignore")


class SixHOutlook(BaseModel):
    outlook: OutlookEnum = Field(
        ..., description="Market outlook: BULLISH, BEARISH, or MIXED"
    )
    confidence: float = Field(
        ..., ge=0, le=1, description="Confidence level between 0 and 1"
    )


class TradingResponse(BaseModel):
    action: Action
