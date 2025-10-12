from typing import List, Literal, Optional

from pydantic import BaseModel


class TickerReferenceMatch(BaseModel):
    symbol: str
    name: str
    exchange: Optional[str] = None
    market_category: Optional[str] = None
    is_etf: bool
    match_type: Literal["symbol", "name", "symbol_prefix"]

    class Config:
        from_attributes = True


class TickerReferenceLookupResponse(BaseModel):
    query: str
    has_exact_symbol: bool
    matches: List[TickerReferenceMatch]
