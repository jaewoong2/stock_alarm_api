from typing import List, Optional
from datetime import date, timedelta
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from myapi.domain.ticker.ticker_model import Ticker
from myapi.domain.ticker.ticker_schema import TickerCreate, TickerUpdate, TickerVO


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
