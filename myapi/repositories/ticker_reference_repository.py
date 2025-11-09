from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from myapi.domain.ticker.ticker_reference_model import TickerReference


class TickerReferenceRepository:
    def __init__(self, db_session: Session):
        self.db_session = db_session

    def find_by_symbol(self, symbol: str) -> Optional[TickerReference]:
        if not symbol:
            return None
        normalized = symbol.strip().upper()
        return (
            self.db_session.query(TickerReference)
            .filter(func.upper(TickerReference.symbol) == normalized)
            .one_or_none()
        )

    def search_by_symbol_prefix(self, prefix: str, limit: int) -> List[TickerReference]:
        if not prefix:
            return []
        normalized = prefix.strip().upper()
        return (
            self.db_session.query(TickerReference)
            .filter(func.upper(TickerReference.symbol).like(f"{normalized}%"))
            .order_by(TickerReference.symbol.asc())
            .limit(limit)
            .all()
        )

    def search_by_name(self, name: str, limit: int) -> List[TickerReference]:
        if not name:
            return []
        pattern = f"%{name.strip()}%"
        return (
            self.db_session.query(TickerReference)
            .filter(TickerReference.name.ilike(pattern))
            .order_by(TickerReference.name.asc())
            .limit(limit)
            .all()
        )
