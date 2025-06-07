from typing import Dict, List, Optional
from datetime import date

from myapi.domain.ticker.ticker_schema import (
    TickerCreate,
    TickerResponse,
    TickerUpdate,
    TickerChangeResponse,
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

    def get_ticker_by_symbol(self, symbol: str) -> Optional[TickerResponse]:
        ticker = self.ticker_repository.get_by_symbol(symbol)
        return TickerResponse.model_validate(ticker) if ticker else None

    def get_all_tickers(self) -> List[TickerResponse]:
        tickers = self.ticker_repository.list()
        return [TickerResponse.model_validate(t) for t in tickers]

    def update_ticker(
        self, ticker_id: int, data: TickerUpdate
    ) -> Optional[TickerResponse]:
        ticker = self.ticker_repository.update(ticker_id, data)
        return TickerResponse.model_validate(ticker) if ticker else None

    def delete_ticker(self, ticker_id: int) -> bool:
        return self.ticker_repository.delete(ticker_id)

    # 새로 추가: 심볼과 날짜로 티커 정보 조회
    def get_ticker_by_date(
        self, symbol: str, date_value: date
    ) -> Optional[TickerResponse]:
        ticker = self.ticker_repository.get_by_symbol_and_date(symbol, date_value)
        return TickerResponse.model_validate(ticker) if ticker else None

    # 새로 추가: 날짜별 변화율 계산
    def get_ticker_changes(
        self, symbol: str, dates: List[date]
    ) -> List[TickerChangeResponse]:
        results = []

        # 날짜를 오름차순으로 정렬 (이전 날짜부터 최근 날짜 순으로)
        sorted_dates = sorted(dates)

        for date_value in sorted_dates:
            # 현재 날짜 데이터 조회
            current_ticker = self.ticker_repository.get_by_symbol_and_date(
                symbol, date_value
            )
            if not current_ticker:
                continue

            # 전일 데이터 조회
            prev_ticker = self.ticker_repository.get_previous_day_ticker(
                symbol, date_value
            )

            # SQLAlchemy model to dict conversion
            current_data = {
                "open_price": (
                    float(current_ticker.open_price)
                    if current_ticker.open_price is not None
                    else None
                ),
                "high_price": (
                    float(current_ticker.high_price)
                    if current_ticker.high_price is not None
                    else None
                ),
                "low_price": (
                    float(current_ticker.low_price)
                    if current_ticker.low_price is not None
                    else None
                ),
                "close_price": (
                    float(current_ticker.close_price)
                    if current_ticker.close_price is not None
                    else None
                ),
                "volume": (
                    int(current_ticker.volume)
                    if current_ticker.volume is not None
                    else None
                ),
                "price": (
                    float(current_ticker.price)
                    if hasattr(current_ticker, "price")
                    and current_ticker.price is not None
                    else None
                ),
            }

            # 변화율 계산을 위한 응답 객체 초기화
            change_response = TickerChangeResponse(
                date=date_value,
                symbol=symbol,
                open_price=current_data["open_price"],
                high_price=current_data["high_price"],
                low_price=current_data["low_price"],
                close_price=current_data["close_price"],
                volume=current_data["volume"],
            )

            # 전일 데이터가 있으면 변화율 계산
            if prev_ticker:
                # Convert previous ticker data to Python types
                prev_data = {
                    "open_price": (
                        float(prev_ticker.open_price)
                        if prev_ticker.open_price is not None
                        else None
                    ),
                    "close_price": (
                        float(prev_ticker.close_price)
                        if prev_ticker.close_price is not None
                        else None
                    ),
                    "volume": (
                        int(prev_ticker.volume)
                        if prev_ticker.volume is not None
                        else None
                    ),
                    "price": (
                        float(prev_ticker.price)
                        if hasattr(prev_ticker, "price")
                        and prev_ticker.price is not None
                        else None
                    ),
                }

                # 시가 변화율
                if (
                    prev_data["open_price"] is not None
                    and current_data["open_price"] is not None
                ):
                    change_response.open_change = (
                        (current_data["open_price"] - prev_data["open_price"])
                        / prev_data["open_price"]
                        * 100
                    )

                # 종가 변화율
                if (
                    prev_data["close_price"] is not None
                    and current_data["close_price"] is not None
                ):
                    change_response.close_change = (
                        (current_data["close_price"] - prev_data["close_price"])
                        / prev_data["close_price"]
                        * 100
                    )

                # 가격 변화율 (현재가 기준)
                if prev_data["price"] is not None and current_data["price"] is not None:
                    change_response.price_change = (
                        (current_data["price"] - prev_data["price"])
                        / prev_data["price"]
                        * 100
                    )

                # 거래량 변화율
                if (
                    prev_data["volume"] is not None
                    and current_data["volume"] is not None
                ):
                    change_response.volume_change = (
                        (current_data["volume"] - prev_data["volume"])
                        / prev_data["volume"]
                        * 100
                    )

            results.append(change_response)

        return results
