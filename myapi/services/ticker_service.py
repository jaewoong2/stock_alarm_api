from typing import List, Optional

from myapi.domain.ticker.ticker_schema import (
    TickerCreate,
    TickerResponse,
    TickerUpdate,
)
from myapi.repositories.ticker_repository import TickerRepository


class TickerService:
    def __init__(self, ticker_repository: TickerRepository):
        self.ticker_repository = ticker_repository

    def create_ticker(self, data: TickerCreate) -> TickerResponse:
        ticker = self.ticker_repository.create(data)
        return TickerResponse.model_validate(ticker)

    def get_ticker(self, ticker_id: int) -> Optional[TickerResponse]:
        ticker = self.ticker_repository.get(ticker_id)
        return TickerResponse.model_validate(ticker) if ticker else None

    def get_all_tickers(self) -> List[TickerResponse]:
        tickers = self.ticker_repository.list()
        return [TickerResponse.model_validate(t) for t in tickers]

    def update_ticker(self, ticker_id: int, data: TickerUpdate) -> Optional[TickerResponse]:
        ticker = self.ticker_repository.update(ticker_id, data)
        return TickerResponse.model_validate(ticker) if ticker else None

    def delete_ticker(self, ticker_id: int) -> bool:
        return self.ticker_repository.delete(ticker_id)
