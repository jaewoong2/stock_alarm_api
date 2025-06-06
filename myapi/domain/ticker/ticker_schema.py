from typing import Optional
from pydantic import BaseModel


class TickerBase(BaseModel):
    symbol: str
    name: Optional[str] = None
    description: Optional[str] = None


class TickerCreate(TickerBase):
    pass


class TickerUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class TickerResponse(TickerBase):
    id: int

    class Config:
        from_attributes = True
