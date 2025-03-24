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
    def __init__(
        self,
        db_session: Session,
    ):
        self.db_session = db_session

    def get_all_futures(self, symbol: str = "BTCUSDT"):
        futures = self.db_session.query(Futures).filter(Futures.symbol == symbol).all()
        return [FuturesVO.model_validate(f) for f in futures]

    def create_futures(
        self,
        futures: FuturesVO,
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
                order_id=futures.order_id,
                parent_order_id=futures.parent_order_id,
                stop_loss=stop_loss,
            )
            self.db_session.add(db_futures)
            self.db_session.commit()
            self.db_session.refresh(db_futures)
            return FuturesResponse.model_validate(db_futures)
        except Exception as e:
            self.db_session.rollback()
            logging.error(f"DB futures creation failed: {e}")
            raise

    def get_futures_by_symbol(self, symbol: str) -> List[FuturesResponse]:
        futures = self.db_session.query(Futures).filter(Futures.symbol == symbol).all()
        return [FuturesResponse.model_validate(f) for f in futures]

    def get_open_futures(self, symbol: str):
        row = (
            self.db_session.query(Futures)
            .filter(Futures.symbol == symbol, Futures.status == "open")
            .first()
        )
        return FuturesVO(**row_to_dict(row)), row

    def update_futures_status(self, order_id: str, status: str) -> FuturesResponse:
        try:
            futures = (
                self.db_session.query(Futures)
                .filter(Futures.order_id == order_id)
                .first()
            )
            if futures is None:
                raise ValueError(f"No futures found with order_id: {order_id}")

            futures.status = status

            self.db_session.add(futures)
            self.db_session.commit()
            self.db_session.refresh(futures)
            return FuturesResponse.from_orm(futures)
        except Exception as e:
            self.db_session.rollback()
            logging.error(f"DB futures update failed: {e}")
            raise
