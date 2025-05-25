from sqlalchemy.orm import Session
from typing import Dict, List, Optional, Tuple
import logging
from sqlalchemy.exc import PendingRollbackError
from sqlalchemy import text, desc, func, between, and_
from datetime import datetime, timedelta

from myapi.domain.signal.signal_models import Signals
from myapi.domain.signal.signal_schema import SignalBaseResponse
from myapi.utils.config import row_to_dict


class SignalsRepository:
    def __init__(
        self,
        db_session: Session,
    ):
        self.db_session = db_session

    def _ensure_valid_session(self):
        """
        세션이 유효한 상태인지 확인하고, 필요한 경우 복구합니다.
        """
        try:
            # 간단한 쿼리를 실행하여 세션 상태 확인
            self.db_session.execute(text("SELECT 1"))
        except PendingRollbackError:
            # 롤백이 필요한 경우 롤백 수행
            logging.warning("PendingRollbackError detected. Rolling back transaction.")
            self.db_session.rollback()
        except Exception as e:
            # 기타 예외 처리
            logging.error(f"Session error: {e}")
            self.db_session.rollback()

    def create_signal(
        self,
        ticker: str,
        entry_price: float,
        action: str,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        probability: Optional[str] = None,
        result_description: Optional[str] = None,
        strategy: Optional[str] = None,  # 신호가 발생한 전략 추가
        report_summary: Optional[str] = None,
    ) -> SignalBaseResponse:
        """
        새로운 신호를 생성합니다.
        """
        self._ensure_valid_session()
        try:
            signal = Signals(
                ticker=ticker,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                action=action,
                timestamp=datetime.utcnow(),
                probability=probability,
                result_description=result_description,
                strategy=strategy,  # 전략 정보 추가
                report_summary=report_summary,
            )
            self.db_session.add(signal)
            self.db_session.commit()
            self.db_session.refresh(signal)
            return SignalBaseResponse.model_validate(signal)
        except Exception as e:
            self.db_session.rollback()
            logging.error(f"DB signal creation failed: {e}")
            raise

    def get_ticker(self) -> List[str]:
        """ """
        self._ensure_valid_session()
        signals = self.db_session.query(Signals).filter(
            Signals.timestamp == datetime.utcnow().date()
        )
        return [str(signal.ticker) for signal in signals]

    def get_today_tickers(self) -> List[str]:
        """
        오늘의 티커를 가져옵니다.
        """
        self._ensure_valid_session()
        today = datetime.utcnow().date()
        signals = (
            self.db_session.query(Signals)
            .filter(func.date(Signals.timestamp) == today)
            .all()
        )

        return [str(signal.ticker) for signal in signals]

    def get_signals(self) -> List[SignalBaseResponse]:
        """
        모든 신호를 가져옵니다.
        """
        self._ensure_valid_session()
        signals = self.db_session.query(Signals).order_by(desc(Signals.timestamp)).all()
        return [SignalBaseResponse.model_validate(s) for s in signals]

    def get_signals_by_ticker(self, ticker: str) -> List[SignalBaseResponse]:
        """
        특정 티커에 대한 신호를 가져옵니다.
        """
        self._ensure_valid_session()
        signals = (
            self.db_session.query(Signals)
            .filter(Signals.ticker == ticker)
            .order_by(desc(Signals.timestamp))
            .all()
        )
        return [SignalBaseResponse.model_validate(s) for s in signals]

    def get_recent_signals(self, limit: int = 10) -> List[SignalBaseResponse]:
        """
        최근 신호를 가져옵니다.
        """
        self._ensure_valid_session()
        signals = (
            self.db_session.query(Signals)
            .order_by(desc(Signals.timestamp))
            .limit(limit)
            .all()
        )
        return [SignalBaseResponse.model_validate(s) for s in signals]

    def get_signal_by_id(self, signal_id: int) -> Optional[SignalBaseResponse]:
        """
        ID로 신호를 가져옵니다.
        """
        self._ensure_valid_session()
        signal = self.db_session.query(Signals).filter(Signals.id == signal_id).first()
        if signal:
            return SignalBaseResponse.model_validate(signal)
        return None

    def update_signal(self, signal_id: int, **kwargs) -> Optional[SignalBaseResponse]:
        """
        기존 신호를 업데이트합니다.
        """
        self._ensure_valid_session()
        try:
            signal = (
                self.db_session.query(Signals).filter(Signals.id == signal_id).first()
            )
            if signal is None:
                return None

            # 제공된 키워드 인자로 속성 업데이트
            for key, value in kwargs.items():
                if hasattr(signal, key):
                    setattr(signal, key, value)

            self.db_session.commit()
            self.db_session.refresh(signal)
            return SignalBaseResponse.model_validate(signal)
        except Exception as e:
            self.db_session.rollback()
            logging.error(f"DB signal update failed: {e}")
            raise

    def delete_signal(self, signal_id: int) -> bool:
        """
        신호를 삭제합니다.
        """
        self._ensure_valid_session()
        try:
            signal = (
                self.db_session.query(Signals).filter(Signals.id == signal_id).first()
            )
            if signal is None:
                return False

            self.db_session.delete(signal)
            self.db_session.commit()
            return True
        except Exception as e:
            self.db_session.rollback()
            logging.error(f"DB signal deletion failed: {e}")
            raise

    def get_signals_by_action(self, action: str) -> List[SignalBaseResponse]:
        """
        특정 액션(buy/sell)에 대한 신호를 가져옵니다.
        """
        self._ensure_valid_session()
        signals = (
            self.db_session.query(Signals)
            .filter(Signals.action == action)
            .order_by(desc(Signals.timestamp))
            .all()
        )
        return [SignalBaseResponse.model_validate(s) for s in signals]

    # ------ 추가된 메서드 ------

    def get_signals_by_strategy(self, strategy: str) -> List[SignalBaseResponse]:
        """
        특정 전략에 대한 신호를 가져옵니다.
        """
        self._ensure_valid_session()
        signals = (
            self.db_session.query(Signals)
            .filter(Signals.strategy == strategy)
            .order_by(desc(Signals.timestamp))
            .all()
        )
        return [SignalBaseResponse.model_validate(s) for s in signals]

    def get_signals_by_date_range(
        self,
        start_date: datetime,
        end_date: Optional[datetime] = None,
        action: Optional[str] = None,
    ) -> List[SignalBaseResponse]:
        """
        특정 날짜 범위 내의 신호를 가져옵니다.
        """
        self._ensure_valid_session()
        if end_date is None:
            end_date = datetime.utcnow()

        signals = (
            self.db_session.query(Signals)
            .filter(Signals.timestamp.between(start_date, end_date))
            .order_by(desc(Signals.timestamp))
        )

        if action == "buy" or action == "sell" or action == "hold":
            signals = signals.filter(Signals.action == action)

        return [SignalBaseResponse.model_validate(s) for s in signals.all()]

    def get_signals_by_probability(
        self, min_probability: float, max_probability: Optional[float] = None
    ) -> List[SignalBaseResponse]:
        """
        특정 확률 범위의 신호를 가져옵니다.
        """
        self._ensure_valid_session()
        if max_probability is None:
            max_probability = 100.0

        signals = (
            self.db_session.query(Signals)
            .filter(
                Signals.probability.isnot(None),
                Signals.probability >= min_probability,
                Signals.probability <= max_probability,
            )
            .order_by(desc(Signals.timestamp))
            .all()
        )
        return [SignalBaseResponse.model_validate(s) for s in signals]

    def get_signals_with_result(self, result_keyword: str) -> List[SignalBaseResponse]:
        """
        특정 결과 설명을 포함하는 신호를 가져옵니다.
        """
        self._ensure_valid_session()
        signals = (
            self.db_session.query(Signals)
            .filter(Signals.result_description.ilike(f"%{result_keyword}%"))
            .order_by(desc(Signals.timestamp))
            .all()
        )
        return [SignalBaseResponse.model_validate(s) for s in signals]

    def get_successful_signals(self) -> List[SignalBaseResponse]:
        """
        성공한 신호를 가져옵니다. (result_description에 'success' 또는 'profitable' 포함)
        """
        self._ensure_valid_session()
        signals = (
            self.db_session.query(Signals)
            .filter(
                Signals.result_description.ilike("%success%")
                | Signals.result_description.ilike("%profitable%")
            )
            .order_by(desc(Signals.timestamp))
            .all()
        )
        return [SignalBaseResponse.model_validate(s) for s in signals]

    def get_failed_signals(self) -> List[SignalBaseResponse]:
        """
        실패한 신호를 가져옵니다. (result_description에 'fail' 또는 'loss' 포함)
        """
        self._ensure_valid_session()
        signals = (
            self.db_session.query(Signals)
            .filter(
                Signals.result_description.ilike("%fail%")
                | Signals.result_description.ilike("%loss%")
            )
            .order_by(desc(Signals.timestamp))
            .all()
        )
        return [SignalBaseResponse.model_validate(s) for s in signals]

    def get_signals_stats_by_ticker(self) -> Dict[str, Dict[str, int]]:
        """
        티커별 신호 통계를 가져옵니다.
        """
        self._ensure_valid_session()
        results = {}

        # 티커별 총 신호 수
        signals_count = (
            self.db_session.query(Signals.ticker, func.count(Signals.id))
            .group_by(Signals.ticker)
            .all()
        )

        # 티커별 성공 신호 수
        success_count = (
            self.db_session.query(Signals.ticker, func.count(Signals.id))
            .filter(
                Signals.result_description.ilike("%success%")
                | Signals.result_description.ilike("%profitable%")
            )
            .group_by(Signals.ticker)
            .all()
        )

        # 티커별 실패 신호 수
        fail_count = (
            self.db_session.query(Signals.ticker, func.count(Signals.id))
            .filter(
                Signals.result_description.ilike("%fail%")
                | Signals.result_description.ilike("%loss%")
            )
            .group_by(Signals.ticker)
            .all()
        )

        # 결과 조합
        for ticker, count in signals_count:
            if ticker not in results:
                results[ticker] = {"total": 0, "success": 0, "fail": 0}
            results[ticker]["total"] = count

        for ticker, count in success_count:
            if ticker in results:
                results[ticker]["success"] = count

        for ticker, count in fail_count:
            if ticker in results:
                results[ticker]["fail"] = count

        return results

    def get_signals_stats_by_strategy(self) -> Dict[str, Dict[str, int]]:
        """
        전략별 신호 통계를 가져옵니다.
        """
        self._ensure_valid_session()
        results = {}

        # 전략별 총 신호 수
        signals_count = (
            self.db_session.query(Signals.strategy, func.count(Signals.id))
            .filter(Signals.strategy.isnot(None))
            .group_by(Signals.strategy)
            .all()
        )

        # 전략별 성공 신호 수
        success_count = (
            self.db_session.query(Signals.strategy, func.count(Signals.id))
            .filter(
                Signals.strategy.isnot(None),
                Signals.result_description.ilike("%success%")
                | Signals.result_description.ilike("%profitable%"),
            )
            .group_by(Signals.strategy)
            .all()
        )

        # 전략별 실패 신호 수
        fail_count = (
            self.db_session.query(Signals.strategy, func.count(Signals.id))
            .filter(
                Signals.strategy.isnot(None),
                Signals.result_description.ilike("%fail%")
                | Signals.result_description.ilike("%loss%"),
            )
            .group_by(Signals.strategy)
            .all()
        )

        # 결과 조합
        for strategy, count in signals_count:
            if strategy not in results:
                results[strategy] = {"total": 0, "success": 0, "fail": 0}
            results[strategy]["total"] = count

        for strategy, count in success_count:
            if strategy in results:
                results[strategy]["success"] = count

        for strategy, count in fail_count:
            if strategy in results:
                results[strategy]["fail"] = count

        return results

    def get_recent_signals_by_days(self, days: int = 7) -> List[SignalBaseResponse]:
        """
        최근 n일 동안의 신호를 가져옵니다.
        """
        self._ensure_valid_session()
        start_date = datetime.utcnow() - timedelta(days=days)

        signals = (
            self.db_session.query(Signals)
            .filter(Signals.timestamp >= start_date)
            .order_by(desc(Signals.timestamp))
            .all()
        )
        return [SignalBaseResponse.model_validate(s) for s in signals]

    def get_high_probability_signals(
        self, threshold: float = 70.0
    ) -> List[SignalBaseResponse]:
        """
        높은 확률의 신호를 가져옵니다.
        """
        self._ensure_valid_session()
        signals = (
            self.db_session.query(Signals)
            .filter(Signals.probability.isnot(None), Signals.probability >= threshold)
            .order_by(desc(Signals.timestamp))
            .all()
        )
        return [SignalBaseResponse.model_validate(s) for s in signals]
