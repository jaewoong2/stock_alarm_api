from typing import List, Optional, Dict
from datetime import date, timedelta
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from myapi.domain.ticker.ticker_model import Ticker
from myapi.domain.ticker.ticker_schema import (
    TickerChangeResponse,
    TickerCreate,
    TickerOrderBy,
    TickerUpdate,
    TickerVO,
)


class TickerRepository:
    def __init__(self, db_session: Session):
        self.db_session = db_session

    def create(self, ticker: TickerCreate) -> Ticker:
        db_ticker = Ticker(**ticker.model_dump())
        self.db_session.add(db_ticker)
        self.db_session.commit()
        self.db_session.refresh(db_ticker)
        return db_ticker

    def bulk_create(self, tickers: List[TickerCreate]) -> List[Ticker]:
        db_tickers = [Ticker(**ticker.model_dump()) for ticker in tickers]
        self.db_session.bulk_save_objects(db_tickers)
        self.db_session.commit()
        return db_tickers

    def get(self, ticker_id: int) -> Optional[Ticker]:
        return (
            self.db_session.query(Ticker).filter(Ticker.id == ticker_id).one_or_none()
        )

    def get_by_symbol(self, symbol: str):
        return self.db_session.query(Ticker).filter(Ticker.symbol == symbol)

    # 날짜와 심볼로 티커 정보 조회
    def get_by_symbol_and_date(self, symbol: str, date_value: date):
        results = (
            self.db_session.query(Ticker)
            .filter(Ticker.symbol == symbol, Ticker.date == date_value)
            .one_or_none()
        )
        if results:
            return TickerVO.model_validate(results)
        return None

    # 여러 날짜에 대한 티커 정보 조회 (순서대로 반환)
    def get_by_symbol_and_dates(self, symbol: str, dates: List[date]):
        results = (
            self.db_session.query(Ticker)
            .filter(Ticker.symbol == symbol, Ticker.date.in_(dates))
            .order_by(Ticker.date)
            .all()
        )

        tickers = [TickerVO.model_validate(t) for t in results] if results else []

        return tickers

    # 특정 날짜의 전일 데이터 조회
    def get_previous_day_ticker(self, symbol: str, date_value: Optional[date]):
        if not date_value:
            return None
        prev_date = date_value - timedelta(days=1)
        return self.get_by_symbol_and_date(symbol, prev_date)

    def get_all_ticker_name(self):
        """
        모든 티커의 심볼과 이름 조회
        중복 네임 제외
        """
        results = self.db_session.query(Ticker).distinct(Ticker.name).all()

        return [str(result.name) for result in results]

    def list(self) -> List[Ticker]:
        return self.db_session.query(Ticker).all()

    def update(self, ticker_id: int, ticker: TickerUpdate) -> Optional[Ticker]:
        db_ticker = self.get(ticker_id)
        if not db_ticker:
            return None
        for field, value in ticker.model_dump(exclude_unset=True).items():
            setattr(db_ticker, field, value)
        self.db_session.commit()
        self.db_session.refresh(db_ticker)
        return db_ticker

    def delete(self, ticker_id: int) -> bool:
        db_ticker = self.get(ticker_id)
        if not db_ticker:
            return False
        self.db_session.delete(db_ticker)
        self.db_session.commit()
        return True

    def get_latest_for_all_symbols(self):
        """각 심볼별 가장 최신 데이터 조회"""
        subquery = (
            self.db_session.query(
                Ticker.symbol, func.max(Ticker.date).label("max_date")
            )
            .group_by(Ticker.symbol)
            .subquery()
        )

        results = (
            self.db_session.query(Ticker)
            .join(
                subquery,
                (Ticker.symbol == subquery.c.symbol)
                & (Ticker.date == subquery.c.max_date),
            )
            .all()
        )

        return [TickerVO.model_validate(ticker) for ticker in results]

    def get_latest_by_symbol(self, symbol: str):
        """특정 심볼의 가장 최신 데이터 조회"""
        return (
            self.db_session.query(Ticker)
            .filter(Ticker.symbol == symbol)
            .order_by(desc(Ticker.date))
            .first()
        )

    def get_next_day_ticker(self, symbol: str, reference_date: date):
        """특정 날짜 이후의 가장 가까운 거래일 데이터 조회"""
        return (
            self.db_session.query(Ticker)
            .filter(Ticker.symbol == symbol, Ticker.date > reference_date)
            .order_by(Ticker.date)
            .first()
        )

    def count_price_movements(
        self,
        symbols: Optional[List[str]],
        start_date: date,
        end_date: date,
        direction: str,
    ):
        """
        기간 동안 티커별로 날짜별 가격 변동(상승/하락) 배열을 반환합니다.
        배열의 각 요소는 해당 날짜의 가격이 지정된 방향으로 움직였는지 여부(1 또는 0)입니다.
        주말(토요일, 일요일)은 제외됩니다.
        """
        # 주말을 제외한 날짜 범위 계산
        date_range = [
            start_date + timedelta(days=i)
            for i in range((end_date - start_date).days + 1)
            if (start_date + timedelta(days=i)).weekday() < 5  # 0-4: 월-금, 5-6: 토-일
        ]

        # 티커별, 날짜별 쿼리 (주말 제외)
        query = self.db_session.query(Ticker.symbol, Ticker.date).filter(
            Ticker.date >= start_date,
            Ticker.date <= end_date,
            # 주말 제외 필터 추가 (0=월요일, 6=일요일)
            func.extract("dow", Ticker.date).notin_([0, 6]),
        )

        if symbols:
            query = query.filter(Ticker.symbol.in_(symbols))

        if direction == "up":
            query = query.filter(Ticker.close_price > Ticker.open_price)
        elif direction == "down":
            query = query.filter(Ticker.close_price < Ticker.open_price)

        results = query.all()

        # 결과를 티커별, 날짜별로 그룹화 (dict 사용)
        movements_by_ticker_date = {}
        for symbol, date_val in results:
            if symbol not in movements_by_ticker_date:
                movements_by_ticker_date[symbol] = set()
            movements_by_ticker_date[symbol].add(date_val)

        # 요청된 심볼과 결과에서 얻은 심볼을 모두 포함
        all_symbols = set(symbol for symbol, _ in results) if results else set()
        if symbols:
            all_symbols = all_symbols.union(set(symbols))

        # 결과 생성 - 각 심볼별로 날짜 범위에 대한 변동 배열 생성
        final_results = []
        formatted_dates = [d.strftime("%Y-%m-%d") for d in date_range]

        for symbol in all_symbols:
            # 각 날짜별로 변동 여부 확인 (1: 변동 있음, 0: 변동 없음)
            counts = [
                1 if d in movements_by_ticker_date.get(symbol, set()) else 0
                for d in date_range
            ]

            # 변동이 하나도 없는 심볼은 결과에서 제외
            if sum(counts) == 0:
                continue

            final_results.append(
                {
                    "ticker": symbol,
                    "count": counts,
                    "date": formatted_dates,
                }
            )

        return final_results

    def get_ticker_order_by(
        self, date_value: date, order_by: TickerOrderBy, limit=10
    ) -> List[TickerChangeResponse]:
        """
        특정 날짜의 티커를 close_change 또는 volume_change 기준으로 정렬하여 조회합니다.
        전날 데이터와 비교하여 변화율을 계산하고 TickerChangeResponse 형태로 반환합니다.
        ORM을 활용한 단일 쿼리 최적화 버전.
        """
        # 전날 날짜 계산
        prev_date = date_value - timedelta(days=1)

        # 현재 날짜의 티커 데이터를 위한 서브쿼리
        current_day = (
            self.db_session.query(
                Ticker.symbol.label("symbol"),
                Ticker.date.label("date"),
                Ticker.open_price.label("open_price"),
                Ticker.high_price.label("high_price"),
                Ticker.low_price.label("low_price"),
                Ticker.close_price.label("close_price"),
                Ticker.volume.label("volume"),
            )
            .filter(Ticker.date == date_value)
            .subquery("current_day")
        )

        # 전날의 티커 데이터를 위한 서브쿼리
        prev_day = (
            self.db_session.query(
                Ticker.symbol.label("symbol"),
                Ticker.open_price.label("prev_open_price"),
                Ticker.close_price.label("prev_close_price"),
                Ticker.volume.label("prev_volume"),
            )
            .filter(Ticker.date == prev_date)
            .subquery("prev_day")
        )

        # 두 서브쿼리를 조인하고 변화율 계산
        close_change = (
            (current_day.c.close_price - prev_day.c.prev_close_price)
            / func.nullif(prev_day.c.prev_close_price, 0)
            * 100
        ).label("close_change")

        open_change = (
            (current_day.c.open_price - prev_day.c.prev_open_price)
            / func.nullif(prev_day.c.prev_open_price, 0)
            * 100
        ).label("open_change")

        price_change = (
            (current_day.c.close_price - prev_day.c.prev_close_price)
            / func.nullif(prev_day.c.prev_close_price, 0)
            * 100
        ).label("price_change")

        volume_change = (
            (current_day.c.volume - prev_day.c.prev_volume)
            / func.nullif(prev_day.c.prev_volume, 0)
            * 100
        ).label("volume_change")

        query = self.db_session.query(
            current_day.c.symbol,
            current_day.c.date,
            current_day.c.open_price,
            current_day.c.high_price,
            current_day.c.low_price,
            current_day.c.close_price,
            current_day.c.volume,
            close_change,
            open_change,
            price_change,
            volume_change,
        ).join(
            prev_day,
            current_day.c.symbol == prev_day.c.symbol,
            # isouter=True,  # LEFT OUTER JOIN으로 전일 데이터가 없는 경우도 포함
        )

        # 정렬 적용 (NULL 값 처리)
        if order_by.field == "close_change":
            if order_by.direction == "desc":
                # NULL을 마지막으로 정렬 (IS NULL은 True/False 반환)
                query = query.order_by(close_change.is_(None), close_change.desc())
            else:
                query = query.order_by(close_change.is_(None), close_change)
        elif order_by.field == "volume_change":
            if order_by.direction == "desc":
                query = query.order_by(volume_change.is_(None), volume_change.desc())
            else:
                query = query.order_by(volume_change.is_(None), volume_change)

        # 결과 제한
        query = query.limit(limit)

        # 쿼리 실행 및 결과 변환
        results = query.all()

        # 결과를 TickerChangeResponse 객체로 변환
        ticker_changes = []
        for row in results:
            ticker_change = TickerChangeResponse(
                symbol=row.symbol or "",
                date=row.date or date_value,
                open_price=row.open_price,
                high_price=row.high_price,
                low_price=row.low_price,
                close_price=row.close_price,
                volume=row.volume,
                close_change=row.close_change,
                open_change=row.open_change,
                price_change=row.price_change,
                volume_change=row.volume_change,
            )
            ticker_changes.append(ticker_change)

        return ticker_changes
