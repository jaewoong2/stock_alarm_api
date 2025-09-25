from typing import List, Optional, Dict, Union
from datetime import date, timedelta
from sqlalchemy import desc, func, select, and_
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from myapi.domain.ticker.ticker_model import Ticker
from myapi.domain.ticker.ticker_schema import (
    TickerChangeResponse,
    TickerCreate,
    TickerOrderBy,
    TickerUpdate,
    TickerVO,
)
from myapi.utils.utils import get_prev_date


class TickerRepository:
    def __init__(self, db_session: Union[Session, AsyncSession]):
        self.db_session = db_session

    def create(self, ticker: TickerCreate) -> Ticker:
        db_ticker = Ticker(**ticker.model_dump())
        self.db_session.add(db_ticker)
        self.db_session.commit()
        self.db_session.refresh(db_ticker)
        return db_ticker

    def bulk_create(self, tickers: List[TickerCreate]) -> List[Ticker]:
        if isinstance(self.db_session, AsyncSession):
            # AsyncSession에서는 bulk_save_objects가 지원되지 않으므로 개별 추가
            db_tickers = [Ticker(**ticker.model_dump()) for ticker in tickers]
            for db_ticker in db_tickers:
                self.db_session.add(db_ticker)
            # 비동기에서는 commit을 직접 호출할 수 없으므로 동기 모드에서만 실행
            return db_tickers
        else:
            db_tickers = [Ticker(**ticker.model_dump()) for ticker in tickers]
            self.db_session.bulk_save_objects(db_tickers)
            self.db_session.commit()
            return db_tickers

    def get(self, ticker_id: int) -> Optional[Ticker]:
        if isinstance(self.db_session, AsyncSession):
            # AsyncSession에서는 동기 메서드를 호출할 수 없으므로 None 반환
            return None
        else:
            return (
                self.db_session.query(Ticker)
                .filter(Ticker.id == ticker_id)
                .one_or_none()
            )

    def get_by_symbol(self, symbol: str):
        if isinstance(self.db_session, AsyncSession):
            # AsyncSession에서는 동기 메서드를 호출할 수 없으므로 빈 결과 반환
            return []
        else:
            return self.db_session.query(Ticker).filter(Ticker.symbol == symbol)

    # 날짜와 심볼로 티커 정보 조회
    def get_by_symbol_and_date(self, symbol: str, date_value: date):
        if isinstance(self.db_session, AsyncSession):
            # AsyncSession에서는 동기 메서드를 호출할 수 없으므로 None 반환
            return None
        else:
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
        if isinstance(self.db_session, AsyncSession):
            # AsyncSession에서는 동기 메서드를 호출할 수 없으므로 빈 리스트 반환
            return []
        else:
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
        모든 티커의 고유 심볼 목록을 반환합니다.
        중복 심볼은 제거됩니다.
        """
        if isinstance(self.db_session, AsyncSession):
            # AsyncSession에서는 동기 메서드를 호출할 수 없으므로 빈 리스트 반환
            return []
        else:
            results = (
                self.db_session.query(Ticker.symbol)
                .distinct(Ticker.symbol)
                .order_by(Ticker.symbol)
                .all()
            )
            return [str(result[0]) for result in results]

    def list(self) -> List[Ticker]:
        if isinstance(self.db_session, AsyncSession):
            # AsyncSession에서는 동기 메서드를 호출할 수 없으므로 빈 리스트 반환
            return []
        else:
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
        if isinstance(self.db_session, AsyncSession):
            # AsyncSession에서는 동기 메서드를 호출할 수 없으므로 빈 리스트 반환
            return []
        else:
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
        if isinstance(self.db_session, AsyncSession):
            # AsyncSession에서는 동기 메서드를 호출할 수 없으므로 None 반환
            return None
        else:
            return (
                self.db_session.query(Ticker)
                .filter(Ticker.symbol == symbol)
                .order_by(desc(Ticker.date))
                .first()
            )

    def get_next_day_ticker(self, symbol: str, reference_date: date):
        """특정 날짜 이후의 가장 가까운 거래일 데이터 조회"""
        if isinstance(self.db_session, AsyncSession):
            # AsyncSession에서는 동기 메서드를 호출할 수 없으므로 None 반환
            return None
        else:
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
        if isinstance(self.db_session, AsyncSession):
            # AsyncSession에서는 동기 메서드를 호출할 수 없으므로 빈 리스트 반환
            return []

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
        if isinstance(self.db_session, AsyncSession):
            # AsyncSession에서는 동기 메서드를 호출할 수 없으므로 빈 리스트 반환
            return []

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
            .filter(Ticker.date == date_value.strftime("%Y-%m-%d"))
            .subquery("current_day")
        )

        # 실제 이전 거래일 데이터를 찾는 서브쿼리
        # 각 심볼별로 현재 날짜보다 이전인 날짜 중 가장 최근 날짜를 찾음
        prev_trading_date_subquery = (
            self.db_session.query(
                Ticker.symbol, func.max(Ticker.date).label("prev_date")
            )
            .filter(Ticker.date < date_value.strftime("%Y-%m-%d"))
            .group_by(Ticker.symbol)
            .subquery("prev_trading_dates")
        )

        # 이전 거래일의 실제 데이터를 가져오는 서브쿼리
        prev_day = (
            self.db_session.query(
                Ticker.symbol.label("symbol"),
                Ticker.open_price.label("prev_open_price"),
                Ticker.close_price.label("prev_close_price"),
                Ticker.volume.label("prev_volume"),
            )
            .join(
                prev_trading_date_subquery,
                (Ticker.symbol == prev_trading_date_subquery.c.symbol)
                & (Ticker.date == prev_trading_date_subquery.c.prev_date),
            )
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
        )

        # 정렬 적용 (NULL 값 처리)
        if order_by.field == "close_change":
            if order_by.direction == "desc":
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

    # 비동기 메서드들 추가
    async def create_async(self, ticker: TickerCreate) -> Ticker:
        """비동기 티커 생성"""
        if isinstance(self.db_session, AsyncSession):
            db_ticker = Ticker(**ticker.model_dump())
            self.db_session.add(db_ticker)
            await self.db_session.commit()
            await self.db_session.refresh(db_ticker)
            return db_ticker
        else:
            return self.create(ticker)

    async def get_async(self, ticker_id: int) -> Optional[Ticker]:
        """비동기 티커 조회"""
        if isinstance(self.db_session, AsyncSession):
            result = await self.db_session.get(Ticker, ticker_id)
            return result
        else:
            return self.get(ticker_id)

    async def get_by_symbol_async(self, symbol: str) -> List[Ticker]:
        """비동기 심볼로 티커 조회"""
        if isinstance(self.db_session, AsyncSession):
            from sqlalchemy import select

            stmt = select(Ticker).where(Ticker.symbol == symbol)
            result = await self.db_session.execute(stmt)
            return list(result.scalars().all())
        else:
            query_result = self.get_by_symbol(symbol)
            if isinstance(query_result, list):
                # AsyncSession 모드에서는 빈 리스트가 반환됨
                return query_result
            else:
                # 동기 Session 모드에서는 Query 객체가 반환됨
                return query_result.all()

    async def get_latest_for_all_symbols_async(self) -> List[TickerVO]:
        """비동기로 각 심볼별 가장 최신 데이터 조회 - 최적화된 단일 쿼리"""
        if isinstance(self.db_session, AsyncSession):
            from sqlalchemy import select

            # 각 심볼별 최신 날짜를 찾는 서브쿼리
            subquery = (
                select(Ticker.symbol, func.max(Ticker.date).label("max_date"))
                .group_by(Ticker.symbol)
                .subquery()
            )

            # 메인 쿼리: 서브쿼리와 조인하여 최신 데이터만 가져오기
            stmt = (
                select(Ticker)
                .join(
                    subquery,
                    (Ticker.symbol == subquery.c.symbol)
                    & (Ticker.date == subquery.c.max_date),
                )
                .order_by(Ticker.symbol)  # 일관된 순서 보장
            )

            result = await self.db_session.execute(stmt)
            tickers = result.scalars().all()
            return [TickerVO.model_validate(ticker) for ticker in tickers]
        else:
            return self.get_latest_for_all_symbols()

    async def get_previous_day_tickers_batch_async(
        self, symbols: List[str], dates: List[date]
    ) -> Dict[str, TickerVO]:
        """
        배치로 여러 심볼의 이전 거래일 데이터 조회 (N+1 쿼리 방지)
        """
        if isinstance(self.db_session, AsyncSession):
            from sqlalchemy import select, and_

            # 각 심볼-날짜 조합에 대해 이전 거래일을 찾는 서브쿼리
            prev_date_conditions = []
            for symbol, date_val in zip(symbols, dates):
                prev_date_conditions.append(
                    and_(Ticker.symbol == symbol, Ticker.date < date_val)
                )

            if not prev_date_conditions:
                return {}

            # 각 심볼별로 가장 최근의 이전 거래일 찾기
            subquery = (
                select(Ticker.symbol, func.max(Ticker.date).label("prev_date"))
                .where(func.or_(*prev_date_conditions))
                .group_by(Ticker.symbol)
                .subquery()
            )

            # 실제 이전 거래일 데이터 가져오기
            stmt = select(Ticker).join(
                subquery,
                and_(
                    Ticker.symbol == subquery.c.symbol,
                    Ticker.date == subquery.c.prev_date,
                ),
            )

            result = await self.db_session.execute(stmt)
            prev_tickers = result.scalars().all()

            # 심볼을 키로 하는 딕셔너리로 변환
            return {
                str(ticker.symbol): TickerVO.model_validate(ticker)
                for ticker in prev_tickers
            }
        else:
            # 동기 버전 fallback
            result = {}
            for symbol, date_val in zip(symbols, dates):
                prev_ticker = self.get_previous_day_ticker(symbol, date_val)
                if prev_ticker:
                    result[symbol] = prev_ticker
            return result

    async def get_by_symbol_and_dates_async(
        self, symbol: str, dates: List[date]
    ) -> List[TickerVO]:
        """비동기로 특정 심볼의 여러 날짜 데이터 배치 조회"""
        if isinstance(self.db_session, AsyncSession):
            from sqlalchemy import select

            stmt = (
                select(Ticker)
                .where(and_(Ticker.symbol == symbol, Ticker.date.in_(dates)))
                .order_by(Ticker.date)
            )

            result = await self.db_session.execute(stmt)
            tickers = result.scalars().all()
            return [TickerVO.model_validate(ticker) for ticker in tickers]
        else:
            return self.get_by_symbol_and_dates(symbol, dates)

    async def get_previous_day_tickers_for_dates_async(
        self, symbol: str, dates: List[date]
    ) -> Dict[date, TickerVO]:
        """특정 심볼의 여러 날짜에 대한 이전 거래일 데이터를 배치로 조회"""
        if isinstance(self.db_session, AsyncSession):
            from sqlalchemy import select, and_

            result = {}

            # 각 날짜별로 이전 거래일 찾기
            for date_val in dates:
                stmt = (
                    select(Ticker)
                    .where(and_(Ticker.symbol == symbol, Ticker.date < date_val))
                    .order_by(Ticker.date.desc())
                    .limit(1)
                )

                query_result = await self.db_session.execute(stmt)
                ticker = query_result.scalar_one_or_none()

                if ticker:
                    result[date_val] = TickerVO.model_validate(ticker)

            return result
        else:
            # 동기 버전 fallback
            result = {}
            for date_val in dates:
                prev_ticker = self.get_previous_day_ticker(symbol, date_val)
                if prev_ticker:
                    result[date_val] = prev_ticker
            return result
