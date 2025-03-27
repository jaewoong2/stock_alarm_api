from enum import Enum
from typing import Any, Dict, List, Literal, Optional, TypedDict, Union
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


class ChatModel(str, Enum):
    O3_MINI = "o3-mini"
    O3_MINI_2025_01_31 = "o3-mini-2025-01-31"
    O1 = "o1"
    O1_2024_12_17 = "o1-2024-12-17"
    O1_PREVIEW = "o1-preview"
    O1_PREVIEW_2024_09_12 = "o1-preview-2024-09-12"
    O1_MINI = "o1-mini"
    O1_MINI_2024_09_12 = "o1-mini-2024-09-12"
    GPT_4_5_PREVIEW = "gpt-4.5-preview"
    GPT_4_5_PREVIEW_2025_02_27 = "gpt-4.5-preview-2025-02-27"
    GPT_4O = "gpt-4o"
    GPT_4O_2024_11_20 = "gpt-4o-2024-11-20"
    GPT_4O_2024_08_06 = "gpt-4o-2024-08-06"
    GPT_4O_2024_05_13 = "gpt-4o-2024-05-13"
    GPT_4O_AUDIO_PREVIEW = "gpt-4o-audio-preview"
    GPT_4O_AUDIO_PREVIEW_2024_10_01 = "gpt-4o-audio-preview-2024-10-01"
    GPT_4O_AUDIO_PREVIEW_2024_12_17 = "gpt-4o-audio-preview-2024-12-17"
    GPT_4O_MINI_AUDIO_PREVIEW = "gpt-4o-mini-audio-preview"
    GPT_4O_MINI_AUDIO_PREVIEW_2024_12_17 = "gpt-4o-mini-audio-preview-2024-12-17"
    CHATGPT_4O_LATEST = "chatgpt-4o-latest"
    GPT_4O_MINI = "gpt-4o-mini"
    GPT_4O_MINI_2024_07_18 = "gpt-4o-mini-2024-07-18"
    GPT_4_TURBO = "gpt-4-turbo"
    GPT_4_TURBO_2024_04_09 = "gpt-4-turbo-2024-04-09"
    GPT_4_0125_PREVIEW = "gpt-4-0125-preview"
    GPT_4_TURBO_PREVIEW = "gpt-4-turbo-preview"
    GPT_4_1106_PREVIEW = "gpt-4-1106-preview"
    GPT_4_VISION_PREVIEW = "gpt-4-vision-preview"
    GPT_4 = "gpt-4"
    GPT_4_0314 = "gpt-4-0314"
    GPT_4_0613 = "gpt-4-0613"
    GPT_4_32K = "gpt-4-32k"
    GPT_4_32K_0314 = "gpt-4-32k-0314"
    GPT_4_32K_0613 = "gpt-4-32k-0613"
    GPT_3_5_TURBO = "gpt-3.5-turbo"
    GPT_3_5_TURBO_16K = "gpt-3.5-turbo-16k"
    GPT_3_5_TURBO_0301 = "gpt-3.5-turbo-0301"
    GPT_3_5_TURBO_0613 = "gpt-3.5-turbo-0613"
    GPT_3_5_TURBO_1106 = "gpt-3.5-turbo-1106"
    GPT_3_5_TURBO_0125 = "gpt-3.5-turbo-0125"
    GPT_3_5_TURBO_16K_0613 = "gpt-3.5-turbo-16k-0613"


class TextMessage(TypedDict):
    type: Literal["text"]
    text: str


class ImageUrlMessage(TypedDict):
    type: Literal["image_url"]
    image_url: Dict[str, str]


MessageContent = Dict[Any, Any]
