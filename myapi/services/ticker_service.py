from typing import Dict, List, Optional
from datetime import date, timedelta

from myapi.domain.ticker.ticker_schema import (
    SignalAccuracyResponse,
    TickerCreate,
    TickerLatestWithChangeResponse,
    TickerResponse,
    TickerUpdate,
    TickerChangeResponse,
)
from myapi.repositories.signals_repository import SignalsRepository
from myapi.repositories.ticker_repository import TickerRepository


class TickerService:
    def __init__(
        self,
        ticker_repository: TickerRepository,
        signals_repository: SignalsRepository,
    ):
        self.ticker_repository = ticker_repository
        self.signals_repository = signals_repository  # 시그널 레포지토리 추가

    def create_ticker(self, data: TickerCreate) -> TickerResponse:
        ticker = self.ticker_repository.create(data)
        return TickerResponse.model_validate(ticker)

    def get_ticker(self, ticker_id: int) -> Optional[TickerResponse]:
        ticker = self.ticker_repository.get(ticker_id)
        return TickerResponse.model_validate(ticker) if ticker else None

    def get_ticker_by_symbol(self, symbol: str) -> Optional[List[TickerResponse]]:
        ticker = self.ticker_repository.get_by_symbol(symbol).all()
        return [TickerResponse.model_validate(t) for t in ticker] if ticker else None

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
        return (
            TickerResponse(
                id=ticker.id,
                symbol=ticker.symbol,
                name=ticker.name,
                price=ticker.price,
                open_price=ticker.open_price,
                high_price=ticker.high_price,
                low_price=ticker.low_price,
                close_price=ticker.close_price,
                volume=ticker.volume,
                date=ticker.date,
            )
            if ticker
            else None
        )

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
        # 시그널 예측 정확성 평가 메서드

    def get_latest_tickers_with_changes(self) -> List[TickerLatestWithChangeResponse]:
        """
        모든 티커의 가장 최신 데이터와 전날 대비 변화율을 계산하여 반환합니다.
        """
        try:
            # 모든 심볼의 최신 데이터 가져오기
            latest_tickers = self.ticker_repository.get_latest_for_all_symbols()
            results = []

            for ticker in latest_tickers:
                try:
                    if not ticker:
                        continue

                    # 응답 객체 생성 - 변화율 필드는 기본값 None으로 초기화
                    # 각 필드에 명시적 타입 변환 적용
                    response = TickerLatestWithChangeResponse(
                        symbol=ticker.symbol,
                        date=ticker.date,
                        open_price=(
                            float(ticker.open_price)
                            if ticker.open_price is not None
                            else None
                        ),
                        high_price=(
                            float(ticker.high_price)
                            if ticker.high_price is not None
                            else None
                        ),
                        low_price=(
                            float(ticker.low_price)
                            if ticker.low_price is not None
                            else None
                        ),
                        close_price=(
                            float(ticker.close_price)
                            if ticker.close_price is not None
                            else None
                        ),
                        volume=(
                            int(ticker.volume) if ticker.volume is not None else None
                        ),
                        name=(
                            str(ticker.name)
                            if hasattr(ticker, "name") and ticker.name is not None
                            else None
                        ),
                        close_change=None,
                        volume_change=None,
                        signal=None,  # 시그널 정보 초기화
                    )

                    # 이전 날짜 데이터 가져오기
                    prev_ticker = self.ticker_repository.get_previous_day_ticker(
                        ticker.symbol, ticker.date
                    )

                    # 전일 데이터가 있으면 변화율 계산
                    if prev_ticker:
                        # 종가 변화율 - 0으로 나누는 오류 방지
                        if (
                            ticker.close_price is not None
                            and prev_ticker.close_price is not None
                            and prev_ticker.close_price != 0  # 0으로 나누기 방지
                        ):
                            current_close = float(ticker.close_price)
                            prev_close = float(prev_ticker.close_price)
                            response.close_change = (
                                (current_close - prev_close) / prev_close * 100
                            )

                        # 거래량 변화율 - 0으로 나누는 오류 방지
                        if (
                            ticker.volume is not None
                            and prev_ticker.volume is not None
                            and prev_ticker.volume != 0  # 0으로 나누기 방지
                        ):
                            current_volume = int(ticker.volume)
                            prev_volume = int(prev_ticker.volume)
                            response.volume_change = (
                                (current_volume - prev_volume) / prev_volume * 100
                            )

                    results.append(response)
                except Exception as e:
                    # 개별 티커 처리 중 오류가 발생해도 다른 티커는 계속 처리
                    print(f"티커 {ticker.symbol} 처리 중 오류 발생: {str(e)}")
                    continue

            return results
        except Exception as e:
            print(f"티커 데이터 조회 중 오류 발생: {str(e)}")
            return []

    # evaluate_signal_accuracy 메서드 수정 (created_at을 timestamp로 변경)
    def evaluate_signal_accuracy(
        self, ticker_symbol: str, signal_id: int, days_to_check: int = 5
    ):
        # 시그널 정보 가져오기 (특정 ID 또는 가장 최근 시그널)
        # 특정 티커의 가장 최근 시그널 가져오기
        signals = self.signals_repository.get_by_ticker(ticker_symbol)
        if signals:
            signal = signals[0]  # 가장 최근 시그널

        if not signal:
            return SignalAccuracyResponse(
                ticker=ticker_symbol,
                signal_id=signal_id,
                action=None,
                entry_price=0,
                actual_result=None,
                is_accurate=False,
                accuracy_details="시그널 정보를 찾을 수 없습니다.",
            )

        # 시그널 생성일 이후의 해당 티커 데이터 가져오기
        # created_at 대신 timestamp 사용
        signal_date = (
            signal.timestamp.date()
            if hasattr(signal, "timestamp")
            else signal.created_at.date()
        )
        check_date = signal_date + timedelta(days=days_to_check)
