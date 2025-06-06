from typing import List, Optional
from sqlalchemy.orm import Session

from myapi.domain.ticker.ticker_model import Ticker
from myapi.domain.ticker.ticker_schema import TickerCreate, TickerUpdate


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
            self.db_session.query(Ticker)
            .filter(Ticker.id == ticker_id)
            .one_or_none()
        )

    def get_by_symbol(self, symbol: str) -> Optional[Ticker]:
        return (
            self.db_session.query(Ticker)
            .filter(Ticker.symbol == symbol)
            .one_or_none()
        )

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
