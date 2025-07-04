from pyparsing import C
import sqlalchemy
from sqlalchemy.orm import Session
from typing import Dict, List, Literal, Optional
import logging
from sqlalchemy.exc import PendingRollbackError
from sqlalchemy import text, desc, func, and_
from datetime import date, datetime, timedelta

from myapi.domain.signal.signal_models import Signals
from myapi.domain.signal.signal_schema import (
    ChartPattern,
    GetSignalRequest,
    SignalBaseResponse,
    SignalJoinTickerResponse,
    SignalValueObject,
)
from myapi.domain.ticker.ticker_model import Ticker


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

    def create_signal_bulk(
        self, signals_vo_list: List[SignalValueObject]
    ) -> List[SignalBaseResponse]:
        """
        여러 신호를 한 번에 생성합니다.

        Args:
            signals_vo_list: SignalValueObject 리스트

        Returns:
            생성된 신호 리스트
        """
        self._ensure_valid_session()
        try:
            # SignalValueObject 리스트를 Signals 객체로 변환
            signals_models = []
            for signal_vo in signals_vo_list:
                # SignalValueObject를 Signals 모델로 변환
                signal_model = signal_vo.to_orm(Signals)
                signals_models.append(signal_model)

            # DB에 한 번에 저장
            self.db_session.add_all(signals_models)
            self.db_session.commit()

            # 응답 생성
            results = []
            for signal in signals_models:
                self.db_session.refresh(signal)
                results.append(SignalBaseResponse.model_validate(signal))

            return results
        except Exception as e:
            self.db_session.rollback()
            logging.error(f"DB bulk signal creation failed: {e}")
            raise

    def create_signal(
        self,
        ticker: str,
        entry_price: float,
        action: str,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        close_price: Optional[float] = None,
        probability: Optional[str] = None,
        result_description: Optional[str] = None,
        strategy: Optional[str] = None,  # 신호가 발생한 전략 추가
        report_summary: Optional[str] = None,
        ai_model: str = "OPENAI_O4MINI",
        senario: Optional[str] = None,  # 시나리오 설명
        good_things: Optional[str] = None,  # 좋은 점
        bad_things: Optional[str] = None,  # 나쁜 점
        chart_pattern: Optional[ChartPattern] = None,  # 차트 패턴 정보
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
                close_price=close_price,
                action=action,
                timestamp=datetime.utcnow(),
                probability=probability,
                result_description=result_description,
                strategy=strategy,  # 전략 정보 추가
                report_summary=report_summary,
                ai_model=ai_model,  # AI 모델 정보 추가
                senario=senario,  # 시나리오 설명 추가
                good_things=good_things,  # 좋은 점 추가
                bad_things=bad_things,  # 나쁜 점 추가
                chart_pattern=(
                    chart_pattern.model_dump() if chart_pattern else None
                ),  # 차트 패턴 정보 추가
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

    def get_signals(self, request: GetSignalRequest):
        """
        모든 신호를 가져옵니다.
        """
        self._ensure_valid_session()
        signals_query = self.db_session.query(Signals)

        if request.tickers:
            # 티커 목록이 제공된 경우 해당 티커들로 필터링
            signals_query = signals_query.filter(Signals.ticker.in_(request.tickers))

        if request.actions:
            signals_query = signals_query.filter(Signals.action.in_(request.actions))

        if request.start_date and request.end_date:
            start_date = datetime.strptime(request.start_date, "%Y-%m-%d")
            end_date = datetime.strptime(request.end_date, "%Y-%m-%d")
            signals_query = signals_query.filter(
                Signals.timestamp.between(start_date, end_date)
            )

        if not request.start_date and request.end_date:
            end_date = datetime.strptime(request.end_date, "%Y-%m-%d")
            signals_query = signals_query.filter(Signals.timestamp <= end_date)

        if request.start_date and not request.end_date:
            start_date = datetime.strptime(request.start_date, "%Y-%m-%d")
            signals_query = signals_query.filter(Signals.timestamp >= start_date)

        signals = signals_query.order_by(desc(Signals.timestamp)).all()
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

    def count_signals_by_action(
        self,
        tickers: Optional[List[str]],
        start_date: datetime,
        end_date: datetime,
        action: Literal["Buy", "Sell", "Hold"],
    ):
        """
        주어진 기간 동안 티커별로 날짜별 액션 시그널 개수 배열을 반환합니다.
        배열의 각 요소는 해당 날짜의 시그널 개수를 나타냅니다.
        주말(토요일, 일요일)은 제외됩니다.
        """
        self._ensure_valid_session()

        # 주말을 제외한 날짜 범위 계산
        date_range = [
            (start_date + timedelta(days=i)).date()
            for i in range((end_date.date() - start_date.date()).days + 1)
            if (start_date + timedelta(days=i)).weekday() < 5  # 0-4: 월-금, 5-6: 토-일
        ]

        # 날짜 컬럼 추출 (시간 부분 제외)
        date_column = func.date(Signals.timestamp)

        # 주말을 제외한 쿼리 작성
        query = self.db_session.query(
            Signals.ticker,
            date_column.label("date"),
            func.count(Signals.id).label("count"),
        ).filter(
            Signals.timestamp >= start_date,
            Signals.timestamp <= end_date,
            Signals.action == action.lower(),
            # 주말 제외 필터 추가 (0=월요일, 6=일요일)
            func.extract("dow", Signals.timestamp).notin_([0, 6]),
        )

        if tickers:
            query = query.filter(Signals.ticker.in_(tickers))

        results = query.group_by(Signals.ticker, date_column).all()

        # 결과를 티커별로 그룹화 (딕셔너리 컴프리헨션 사용)
        count_by_ticker_date = {}
        for ticker, date, count in results:
            if ticker not in count_by_ticker_date:
                count_by_ticker_date[ticker] = {}
            count_by_ticker_date[ticker][date] = count

        # 요청된 티커와 결과에서 얻은 티커를 모두 포함
        all_tickers = set(ticker for ticker, _, _ in results) if results else set()
        if tickers:
            all_tickers = all_tickers.union(set(tickers))

        # 결과 생성 - 각 티커별로 날짜 범위에 대한 시그널 개수 배열 생성
        final_results = []
        formatted_dates = [d.strftime("%Y-%m-%d") for d in date_range]

        for ticker in all_tickers:
            ticker_counts = [
                count_by_ticker_date.get(ticker, {}).get(d, 0) for d in date_range
            ]

            final_results.append(
                {
                    "ticker": ticker,
                    "count": ticker_counts,
                    "date": formatted_dates,
                }
            )

        return final_results

    def get_by_ticker_and_date(self, ticker: str, date_value: date):
        """특정 날짜와 티커의 시그널을 조회"""
        # 해당 날짜의 시작과 끝 시간 계산
        start_of_day = datetime.combine(date_value, datetime.min.time())
        end_of_day = datetime.combine(date_value, datetime.max.time())

        results = (
            self.db_session.query(Signals)
            .filter(
                Signals.ticker == ticker,
                Signals.created_at >= start_of_day,
                Signals.created_at <= end_of_day,
            )
            .order_by(Signals.created_at.desc())
            .all()
        )

        return (
            [SignalBaseResponse.model_validate(s) for s in results] if results else []
        )

    # get_by_ticker 메서드 수정
    def get_by_ticker(self, ticker: str):
        """특정 티커의 모든 시그널을 최신순으로 조회"""
        try:
            # timestamp 필드를 기준으로 정렬 시도
            results = (
                self.db_session.query(Signals)
                .filter(Signals.ticker == ticker)
                .order_by(Signals.timestamp.desc())
                .all()
            )

            return (
                [SignalBaseResponse.model_validate(s) for s in results]
                if results
                else []
            )
        except Exception:
            # timestamp가 없다면 created_at 필드로 정렬 시도
            return (
                self.db_session.query(Signals)
                .filter(Signals.ticker == ticker)
                .order_by(Signals.created_at.desc())
                .all()
            )

    def get_signal_by_symbol(self, symbol: str, timestamp: Optional[datetime] = None):
        """
        특정 심볼(티커)에 대한 신호를 가져옵니다.
        ticker_service의 evaluate_signal_accuracy 메서드에서 사용됩니다.

        Args:
            symbol (str): 조회할 심볼(티커)

        Returns:
            List[Signals]: 해당 심볼의 시그널 객체 목록
        """
        self._ensure_valid_session()
        try:
            signal = (
                self.db_session.query(Signals)
                .filter(Signals.ticker == symbol)
                .where(
                    and_(
                        Signals.timestamp == timestamp
                        if timestamp is not None
                        else True
                    )
                )
                .order_by(Signals.timestamp.desc())
                .one_or_none()
            )

            return signal

        except Exception as e:
            logging.error(f"Error fetching signals by symbol: {e}")
            # timestamp가 없다면 created_at 필드로 정렬 시도
            return None

    def get_signals_with_ticker(
        self,
        date_value: date,
        symbols: Optional[List[str]] = None,
        strategy_filter: Optional[str] = None,
    ) -> List[SignalJoinTickerResponse]:
        """
        특정 날짜 및 선택적 티커와 전략에 대한 시그널과 티커 정보를 조인하여 가져옵니다.

        Args:
            date_value: 조회할 날짜(시그널 날짜 기준)
            symbols: 조회할 티커 심볼 목록 (None일 경우 모든 심볼)
            strategy_filter: 전략 필터링 ('AI_GENERATED', 'NOT_AI_GENERATED', None=모든 전략)

        Returns:
            List[SignalJoinTickerResponse]: 시그널과 티커 정보가 결합된 응답 모델의 리스트
        """
        self._ensure_valid_session()
        try:
            # 기본 쿼리 설정
            query = self.db_session.query(Signals, Ticker).outerjoin(
                Ticker,
                and_(
                    Signals.ticker == Ticker.symbol,
                    Signals.action != "hold",
                    Ticker.date >= func.cast(Signals.timestamp, sqlalchemy.Date),
                    Ticker.date
                    <= func.cast(
                        Signals.timestamp + timedelta(days=5), sqlalchemy.Date
                    ),
                ),
            )

            # 날짜 필터링
            query = query.filter(func.date(Signals.timestamp) == date_value)

            # 심볼 필터링
            if symbols:
                query = query.filter(Signals.ticker.in_(symbols))

            # 전략 필터링
            if strategy_filter == "AI_GENERATED":
                query = query.filter(Signals.strategy == "AI_GENERATED")
            else:
                query = query.filter(Signals.strategy != "AI_GENERATED")

            # 정렬
            query = query.order_by(Signals.timestamp.desc(), Ticker.date.asc())

            # 쿼리 실행
            results = query.all()

            # 결과를 응답 모델로 변환
            response_list = []
            for signal, ticker in results:
                response = {"signal": {}, "ticker": None}

                if signal is not None:
                    response["signal"] = {
                        "ticker": signal.ticker,
                        "strategy": signal.strategy,
                        "entry_price": signal.entry_price,
                        "stop_loss": signal.stop_loss,
                        "take_profit": signal.take_profit,
                        "action": signal.action,
                        "timestamp": signal.timestamp,
                        "probability": signal.probability,
                        "result_description": signal.result_description,
                        "report_summary": signal.report_summary,
                        "ai_model": signal.ai_model,
                        "senario": signal.senario,
                        "good_things": signal.good_things,
                        "bad_things": signal.bad_things,
                        "close_price": signal.close_price,
                        "chart_pattern": signal.chart_pattern,
                    }

                if ticker is not None:
                    response["ticker"] = {
                        "symbol": ticker.symbol,
                        "name": ticker.name,
                        "price": ticker.price,
                        "open_price": ticker.open_price,
                        "high_price": ticker.high_price,
                        "low_price": ticker.low_price,
                        "close_price": ticker.close_price,
                        "volume": ticker.volume,
                        "ticker_date": ticker.date,
                        "created_at": ticker.created_at,
                        "updated_at": ticker.updated_at,
                    }

                response["result"] = None
                response_list.append(SignalJoinTickerResponse.model_validate(response))

            return response_list

        except Exception as e:
            logging.error(f"Error fetching signals with ticker join: {e}")
            return []
