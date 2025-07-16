from typing import Dict, List, Literal, Optional
from datetime import date, datetime, timedelta
import logging
from unittest import result
from fastapi import HTTPException

from myapi.repositories.signals_repository import SignalsRepository
from myapi.domain.signal.signal_schema import (
    GetSignalRequest,
    SignalBaseResponse,
    SignalCreate,
    SignalJoinTickerResponse,
    SignalUpdate,
)
from myapi.services.translate_service import TranslateService


class DBSignalService:
    def __init__(
        self, repository: SignalsRepository, translate_service: TranslateService
    ):
        self.repository = repository
        self.logger = logging.getLogger(__name__)
        self.translate_service = translate_service

    async def create_signal(self, signal_data: SignalCreate) -> SignalBaseResponse:
        """
        새로운 신호를 생성합니다.
        """
        try:
            signal = self.repository.create_signal(
                ticker=signal_data.ticker,
                entry_price=signal_data.entry_price,
                action=signal_data.action,
                stop_loss=signal_data.stop_loss,
                take_profit=signal_data.take_profit,
                probability=signal_data.probability,
                result_description=signal_data.result_description,
                strategy=signal_data.strategy,
                report_summary=signal_data.report_summary,
            )
            return signal
        except Exception as e:
            self.logger.error(f"Error creating signal: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Failed to create signal: {str(e)}"
            )

    async def get_all_signals(
        self, request: GetSignalRequest
    ) -> List[SignalBaseResponse]:
        """
        모든 신호를 조회합니다.
        """
        try:
            # 신호 데이터 조회
            signals = self.repository.get_signals(request=request)
            return signals
        except Exception as e:
            self.logger.error(f"Error fetching all signals: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Failed to fetch signals: {str(e)}"
            )

    async def get_signals_result(
        self,
        date: date,
        symbols: Optional[List[str]] = None,
        strategy_type: Optional[str] = None,
    ) -> List[SignalJoinTickerResponse]:
        """
        특정 날짜의 시그널 결과를 조회합니다.

        Args:
            date: 조회할 날짜
            symbols: 조회할 티커 심볼 목록 (None이면 모든 심볼)
            strategy_type: 조회할 전략 유형 ('AI_GENERATED', 'NOT_AI_GENERATED', None=모든 전략)
        """
        try:
            # 통합된 리포지토리 메서드 사용
            signals = self.repository.get_signals_with_ticker(
                date_value=date, symbols=symbols, strategy_filter=strategy_type
            )

            if not signals or len(signals) == 0:
                raise HTTPException(
                    status_code=404, detail=f"No signals found for date {date}"
                )

            # 결과 처리
            for row in signals:

                translated_signal = self.translate_service.get_translated_by_ticker(
                    target_date=date, ticker=row.signal.ticker
                )
                if translated_signal:
                    row.signal = SignalJoinTickerResponse.Signal.model_validate(
                        translated_signal.model_dump()
                    )

                signal, ticker = row.signal, row.ticker

                if not signal or not ticker:
                    continue

                price_change, result_action, is_correct = 0.0, "unknown", False

                # 매수 시그널 가격 차이 계산
                if (
                    signal.action
                    and signal.action.lower() == "buy"
                    and signal.close_price
                    and ticker.close_price
                ):
                    price_change = signal.close_price - ticker.close_price

                # 매도 시그널 가격 차이 계산
                if (
                    signal.action
                    and signal.action.lower() == "sell"
                    and signal.close_price
                    and ticker.close_price
                ):
                    price_change = signal.close_price - ticker.close_price

                # 실제 가격 변동 결과 확인
                if ticker.close_price and ticker.open_price:
                    if ticker.close_price > ticker.open_price:
                        result_action = "up"
                    elif ticker.close_price < ticker.open_price:
                        result_action = "down"
                    else:
                        result_action = "unchanged"

                # 예측 정확도 확인
                if signal.action:
                    if result_action == "up" and signal.action.lower() == "buy":
                        is_correct = True
                    elif result_action == "down" and signal.action.lower() == "sell":
                        is_correct = True
                    elif (
                        result_action == "unchanged" and signal.action.lower() == "hold"
                    ):
                        is_correct = True

                # 결과 데이터 설정
                row.result = SignalJoinTickerResponse.Result(
                    action=result_action,
                    price_diff=price_change,
                    is_correct=is_correct,
                )

            return signals

        except HTTPException as e:
            raise e
        except Exception as e:
            self.logger.error(f"Error fetching signals for date {date}: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Failed to fetch signals: {str(e)}"
            )

    async def get_signal_by_id(self, signal_id: int) -> SignalBaseResponse:
        """
        ID로 신호를 조회합니다.
        """
        signal = self.repository.get_signal_by_id(signal_id)
        if not signal:
            raise HTTPException(
                status_code=404, detail=f"Signal with ID {signal_id} not found"
            )
        return signal

    async def update_signal(
        self, signal_id: int, signal_data: SignalUpdate
    ) -> SignalBaseResponse:
        """
        신호를 업데이트합니다.
        """
        try:
            # SignalUpdate를 딕셔너리로 변환하고 None이 아닌 값만 필터링
            update_data = {
                k: v for k, v in signal_data.model_dump().items() if v is not None
            }

            if not update_data:
                raise HTTPException(
                    status_code=400, detail="No valid update data provided"
                )

            updated_signal = self.repository.update_signal(signal_id, **update_data)
            if not updated_signal:
                raise HTTPException(
                    status_code=404, detail=f"Signal with ID {signal_id} not found"
                )

            return updated_signal
        except HTTPException as e:
            raise e
        except Exception as e:
            self.logger.error(f"Error updating signal {signal_id}: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Failed to update signal: {str(e)}"
            )

    async def delete_signal(self, signal_id: int) -> bool:
        """
        신호를 삭제합니다.
        """
        try:
            result = self.repository.delete_signal(signal_id)
            if not result:
                raise HTTPException(
                    status_code=404, detail=f"Signal with ID {signal_id} not found"
                )
            return True
        except HTTPException as e:
            raise e
        except Exception as e:
            self.logger.error(f"Error deleting signal {signal_id}: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Failed to delete signal: {str(e)}"
            )

    async def get_signals_by_ticker(self, ticker: str) -> List[SignalBaseResponse]:
        """
        티커별 신호를 조회합니다.
        """
        try:
            return self.repository.get_signals_by_ticker(ticker)
        except Exception as e:
            self.logger.error(f"Error fetching signals for ticker {ticker}: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Failed to fetch signals: {str(e)}"
            )

    async def get_recent_signals(self, limit: int = 10) -> List[SignalBaseResponse]:
        """
        최근 신호를 조회합니다.
        """
        try:
            return self.repository.get_recent_signals(limit)
        except Exception as e:
            self.logger.error(f"Error fetching recent signals: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Failed to fetch recent signals: {str(e)}"
            )

    async def get_signals_by_action(self, action: str) -> List[SignalBaseResponse]:
        """
        액션별 신호를 조회합니다.
        """
        try:
            if action not in ["buy", "sell"]:
                raise HTTPException(
                    status_code=400, detail="Action must be 'buy' or 'sell'"
                )
            return self.repository.get_signals_by_action(action)
        except HTTPException as e:
            raise e
        except Exception as e:
            self.logger.error(f"Error fetching signals for action {action}: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Failed to fetch signals: {str(e)}"
            )

    async def get_signals_by_strategy(self, strategy: str) -> List[SignalBaseResponse]:
        """
        전략별 신호를 조회합니다.
        """
        try:
            return self.repository.get_signals_by_strategy(strategy)
        except Exception as e:
            self.logger.error(
                f"Error fetching signals for strategy {strategy}: {str(e)}"
            )
            raise HTTPException(
                status_code=500, detail=f"Failed to fetch signals: {str(e)}"
            )

    async def get_signals_by_date_range(
        self, start_date: datetime, end_date: Optional[datetime] = None
    ) -> List[SignalBaseResponse]:
        """
        날짜 범위별 신호를 조회합니다.
        """
        try:
            return self.repository.get_signals_by_date_range(start_date, end_date)
        except Exception as e:
            self.logger.error(f"Error fetching signals by date range: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Failed to fetch signals: {str(e)}"
            )

    async def get_signals_stats(
        self, by_type: str = "ticker"
    ) -> Dict[str, Dict[str, int]]:
        """
        신호 통계를 조회합니다. (ticker 또는 strategy별 통계)
        """
        try:
            if by_type == "ticker":
                return self.repository.get_signals_stats_by_ticker()
            elif by_type == "strategy":
                return self.repository.get_signals_stats_by_strategy()
            else:
                raise HTTPException(
                    status_code=400, detail="Type must be 'ticker' or 'strategy'"
                )
        except HTTPException as e:
            raise e
        except Exception as e:
            self.logger.error(f"Error fetching signals stats by {by_type}: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Failed to fetch signals stats: {str(e)}"
            )

    async def get_recent_signals_by_days(
        self, days: int = 7
    ) -> List[SignalBaseResponse]:
        """
        최근 n일간 신호를 조회합니다.
        """
        try:
            if days <= 0:
                raise HTTPException(
                    status_code=400, detail="Days must be a positive integer"
                )
            return self.repository.get_recent_signals_by_days(days)
        except HTTPException as e:
            raise e
        except Exception as e:
            self.logger.error(
                f"Error fetching recent signals for {days} days: {str(e)}"
            )
            raise HTTPException(
                status_code=500, detail=f"Failed to fetch signals: {str(e)}"
            )

    async def get_high_probability_signals(
        self, threshold: float = 70.0
    ) -> List[SignalBaseResponse]:
        """
        높은 확률의 신호를 조회합니다.
        """
        try:
            if threshold < 0 or threshold > 100:
                raise HTTPException(
                    status_code=400, detail="Threshold must be between 0 and 100"
                )
            return self.repository.get_high_probability_signals(threshold)
        except HTTPException as e:
            raise e
        except Exception as e:
            self.logger.error(f"Error fetching high probability signals: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Failed to fetch signals: {str(e)}"
            )

    async def get_successful_signals(self) -> List[SignalBaseResponse]:
        """
        성공한 신호를 조회합니다.
        """
        try:
            return self.repository.get_successful_signals()
        except Exception as e:
            self.logger.error(f"Error fetching successful signals: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Failed to fetch signals: {str(e)}"
            )

    async def get_failed_signals(self) -> List[SignalBaseResponse]:
        """
        실패한 신호를 조회합니다.
        """
        try:
            return self.repository.get_failed_signals()
        except Exception as e:
            self.logger.error(f"Error fetching failed signals: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Failed to fetch signals: {str(e)}"
            )

    async def get_signals_with_result(
        self, result_keyword: str
    ) -> List[SignalBaseResponse]:
        """
        특정 결과를 포함하는 신호를 조회합니다.
        """
        try:
            return self.repository.get_signals_with_result(result_keyword)
        except Exception as e:
            self.logger.error(
                f"Error fetching signals with result keyword '{result_keyword}': {str(e)}"
            )
            raise HTTPException(
                status_code=500, detail=f"Failed to fetch signals: {str(e)}"
            )

    async def get_today_signals(self, action: str = "all") -> List[SignalBaseResponse]:
        """
        오늘 생성된 신호들을 조회합니다.
        """
        try:
            today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            tomorrow = today + timedelta(days=1)
            return self.repository.get_signals_by_date_range(
                start_date=today, end_date=tomorrow, action=action
            )
        except Exception as e:
            self.logger.error(f"Error fetching today's signals: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Failed to fetch today's signals: {str(e)}"
            )

    async def get_signals_by_date_and_ticker(self, ticker: str, date_value: date):
        """특정 날짜와 티커의 시그널을 조회합니다."""
        try:
            # 해당 날짜에 생성된 특정 티커의 시그널 조회
            signals = self.repository.get_by_ticker_and_date(ticker, date_value)
            return signals
        except Exception as e:
            self.logger.error(
                f"Error getting signals for {ticker} on {date_value}: {e}"
            )
            return []

    async def get_weekly_action_counts(
        self,
        tickers: Optional[List[str]],
        reference_date: date,
        action: Literal["Buy", "Sell"] = "Buy",
        order_by: Optional[Literal["counts"]] = None,
        limit: int = 10,
    ):
        """지정한 날짜를 기준으로 일주일간 액션별 시그널 개수를 조회합니다."""

        try:
            if action not in ["Buy", "Sell"]:
                raise HTTPException(
                    status_code=400, detail="Action must be 'Buy' or 'Sell'"
                )

            end_dt = datetime.combine(reference_date, datetime.max.time())
            start_dt = end_dt - timedelta(days=6)

            result = await self.repository.count_signals_by_action(
                tickers, start_dt, end_dt, action, order_by, limit
            )

            return result
        except HTTPException as e:
            raise e
        except Exception as e:
            self.logger.error(f"Error fetching weekly action counts: {e}")
            raise HTTPException(
                status_code=500, detail=f"Failed to fetch action counts: {e}"
            )
