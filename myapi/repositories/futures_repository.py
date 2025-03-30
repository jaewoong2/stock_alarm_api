from sqlalchemy.orm import Session
from typing import Dict, List, Optional
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

    def get_children_orders(
        self, parent_order_id: Optional[str] = None
    ) -> List[FuturesResponse]:
        query = self.db_session.query(Futures)
        if parent_order_id is None:
            # parent_order_id가 None인 경우, 모든 자식 주문을 가져옵니다.
            futures = query.filter(Futures.parent_order_id != "").all()
        else:
            # 특정 parent_order_id에 해당하는 자식 주문을 가져옵니다.
            futures = query.filter(
                Futures.parent_order_id == parent_order_id,
            ).all()

        return [FuturesResponse.model_validate(f) for f in futures]

    def get_parents_orders(self, symbol: str) -> List[FuturesResponse]:
        _symbol = symbol

        if not symbol.endswith("USDT"):
            _symbol = f"{symbol}USDT"

        futures = (
            self.db_session.query(Futures)
            .filter(
                Futures.parent_order_id == "",
                Futures.status != "open",
                Futures.symbol == _symbol,
            )
            .all()
        )
        return [FuturesResponse.model_validate(f) for f in futures]

    def get_futures_siblings(
        self, parent_order_id: Optional[str] = None, symbol: Optional[str] = None
    ):
        """
        주어진 parent_order_id와 symbol을 가진 선물 거래의 형제 거래를 조회합니다.
        """
        query = self.db_session.query(Futures)

        if parent_order_id is not None:
            query = query.filter(Futures.parent_order_id == parent_order_id)
        if symbol is not None:
            query = query.filter(Futures.symbol == symbol)

        futures = [FuturesVO.model_validate(f) for f in query.all()]

        answers: Dict[str, List[FuturesVO]] = {}

        for future in futures:
            if future.parent_order_id not in answers:
                answers[future.parent_order_id] = []

            if future.parent_order_id != "":
                answers[future.parent_order_id].append(future)

        return answers

    def get_all_futures(self, symbol: Optional[str] = None):
        if symbol:
            futures = (
                self.db_session.query(Futures).filter(Futures.symbol == symbol).all()
            )
        else:
            futures = self.db_session.query(Futures).all()

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
                client_order_id=futures.client_order_id,
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
