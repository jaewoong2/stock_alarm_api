from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from myapi.domain.futures.futures_model import Futures
from myapi.domain.futures.futures_schema import (
    FuturesCreate,
    FuturesResponse,
    FuturesVO,
)
from myapi.utils.config import row_to_dict


class FuturesRepository:
    def create_futures(
        self,
        db: Session,
        futures: FuturesCreate,
        position_type: Optional[str] = None,
        take_profit: Optional[float] = None,
        stop_loss: Optional[float] = None,
    ) -> FuturesResponse:
        try:
            db_futures = Futures(
                symbol=futures.symbol,
                price=futures.price,
                quantity=futures.quantity,
                side=futures.side,
                position_type=position_type,
                take_profit=take_profit,
                stop_loss=stop_loss,
            )
            db.add(db_futures)
            db.commit()
            db.refresh(db_futures)
            return FuturesResponse.model_validate(db_futures)
        except Exception as e:
            db.rollback()
            logging.error(f"DB futures creation failed: {e}")
            raise

    def get_futures_by_symbol(self, db: Session, symbol: str) -> List[FuturesResponse]:
        futures = db.query(Futures).filter(Futures.symbol == symbol).all()
        return [FuturesResponse.model_validate(f) for f in futures]

    def get_open_futures(self, db: Session, symbol: str):
        row = (
            db.query(Futures)
            .filter(Futures.symbol == symbol, Futures.status == "open")
            .first()
        )
        return FuturesVO(**row_to_dict(row)), row

    def update_futures_status(
        self, db: Session, futures: Futures, status: str
    ) -> FuturesResponse:
        try:
            futures.status = status
            db.add(futures)
            db.commit()
            db.refresh(futures)
            return FuturesResponse.from_orm(futures)
        except Exception as e:
            db.rollback()
            logging.error(f"DB futures update failed: {e}")
            raise
