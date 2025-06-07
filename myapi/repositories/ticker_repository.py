from typing import List, Optional
from datetime import date, timedelta
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
    def get_previous_day_ticker(self, symbol: str, date_value: date):
        prev_date = date_value - timedelta(days=1)
        return self.get_by_symbol_and_date(symbol, prev_date)

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
