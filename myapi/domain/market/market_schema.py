from typing import List
from pydantic import BaseModel


class WebSearchMarketItem(BaseModel):
    date_YYYYMMDD: str
    headline: str
    summary: str
    detail_description: str


class WebSearchMarketResponse(BaseModel):
    search_results: List[WebSearchMarketItem]
