import datetime
from typing import Dict, List, Optional
from datetime import date, timedelta

from numpy import rec, record
from pandas import Timestamp

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
from myapi.services.signal_service import SignalService


class TickerService:
    def __init__(
        self,
        ticker_repository: TickerRepository,
        signals_repository: SignalsRepository,
        signals_service: SignalService,
    ):
        self.ticker_repository = ticker_repository
        self.signals_repository = signals_repository
        self.signals_service = signals_service

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

    # 가장 최신의 모든 티커를 가져와.
    # 해당 티커에 대한 정보를 가져와
    # 티커에 대한 시그널 정보를 Join 해서 가져와
    # 없으면 없는대로 있으면 있는대로 보여줘
    # Response [Ticker, Signal`s Prediction Action, Reality Action, Prediction Price, Prediction Change %, Reality Price, Reality Change USD, Reality Change %]

    def update_ticker_informations(
        self, ticker: str, start: Optional[date], end: Optional[date]
    ):
        """
        특정 티커의 OHLCV 데이터를 가져와서 데이터베이스에 저장합니다.

        Args:
            ticker: 티커 심볼 (예: "TQQQ")
            start: 데이터 시작 날짜 (None인 경우 기본값 사용)
            end: 데이터 종료 날짜 (None인 경우 오늘 날짜 사용)

        Returns:
            Dictionary containing statistics about the operation:
            - 'total': 처리된 총 레코드 수
            - 'created': 새로 생성된 레코드 수
            - 'updated': 업데이트된 레코드 수
            - 'skipped': 변경 없이 건너뛴 레코드 수
        """
        try:
            # 데이터 가져오기
            dataframe = self.signals_service.fetch_ohlcv(
                ticker=ticker, start=start, end=end
            )

            if dataframe.empty:
                raise ValueError(
                    f"No data found for ticker {ticker} in the specified date range."
                )

            # 통계 추적을 위한 카운터 초기화
            stats = {"total": len(dataframe), "created": 0, "updated": 0, "skipped": 0}

            # 데이터 벌크 처리를 위한 배치 크기 설정
            BATCH_SIZE = 100
            batch = []

            df_reset = dataframe.reset_index()
            # 데이터프레임의 Date 별로 Ticker 정보 생성
            for _, row in df_reset.iterrows():
                date = row["Date"]

                if isinstance(date, Timestamp):
                    record_date = date.to_pydatetime().date()

                if record_date is None:
                    print(f"Skipping row with missing date for ticker {ticker}")
                    stats["skipped"] += 1
                    continue

                try:
                    existing_ticker = self.ticker_repository.get_by_symbol_and_date(
                        ticker, record_date
                    )
                    try:
                        ticker_data = TickerCreate(
                            symbol=ticker,
                            name=ticker,  # 향후 회사명 추가 필요 시 수정
                            price=float(row["Close"]),
                            open_price=float(row["Open"]),
                            high_price=float(row["High"]),
                            low_price=float(row["Low"]),
                            close_price=float(row["Close"]),
                            volume=int(row["Volume"]),
                            date=record_date,
                        )
                    except (ValueError, KeyError) as e:
                        print(
                            f"Error processing data for {ticker} on {record_date}: {e}"
                        )
                        stats["skipped"] += 1
                        continue

                    # 이미 존재하는 레코드는 업데이트, 아니면 생성
                    if existing_ticker:
                        stats["skipped"] += 1
                        continue
                    else:
                        # 생성 작업을 배치에 추가
                        batch.append(ticker_data)
                        stats["created"] += 1

                        # 배치 크기에 도달하면 벌크 생성 수행
                        if len(batch) >= BATCH_SIZE:
                            self.ticker_repository.bulk_create(batch)
                            batch = []

                except Exception as e:
                    print(f"Error processing ticker {ticker} for date {date}: {e}")
                    stats["skipped"] += 1
                    continue

            # 남은 배치 처리
            if batch:
                self.ticker_repository.bulk_create(batch)

            return stats

        except Exception as e:
            print(f"Failed to update ticker information for {ticker}: {e}")
            raise

    def get_all_ticker_name(self):
        """
        모든 티커의 이름을 가져옵니다.
        """
        tickers = self.ticker_repository.get_all_ticker_name()
        return tickers

    def count_price_movements(
        self,
        symbols: Optional[List[str]],
        start_date: date,
        end_date: date,
        direction: str,
    ) -> List[Dict[str, int]]:
        """기간 동안 가격 상승/하락 횟수를 반환합니다."""
        return self.ticker_repository.count_price_movements(symbols, start_date, end_date, direction)
