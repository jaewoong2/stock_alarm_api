import logging
from typing import List, Union

from fastapi import HTTPException
from sqlalchemy.orm import Session

from myapi.domain.trading.coinone_schema import GetTradingInformationResponseModel
from myapi.domain.trading.trading_model import Trade, Transaction
from myapi.domain.trading.trading_schema import TransactionCreate
from myapi.utils.config import row_to_dict

logger = logging.getLogger(__name__)


class TradingRepository:
    def __init__(
        self,
        db_session: Session,
    ):
        self.db_session = db_session

    def insert_transactions_if_not_exist(
        self, transactions: Union[TransactionCreate, List[TransactionCreate]]
    ) -> Union[TransactionCreate, List[TransactionCreate]]:
        """
        하나 또는 여러 거래 정보를 받아, 기존에 존재하지 않는 경우에만 DB에 삽입합니다.
        고유 식별자(trade_id)를 기준으로 존재 여부를 판단하며, 이미 존재하면 삽입하지 않습니다.

        주의:
        - TransactionCreate는 Pydantic 모델로, .dict() 또는 .model_dump() 등을 통해 데이터를 추출할 수 있어야 합니다.
        - Transaction은 SQLAlchemy 모델입니다.
        - add_all()을 사용하므로, PK가 자동 생성되는 경우 새 값이 즉시 반영되려면 session.flush() 또는 refresh()가 필요할 수 있습니다.
        """
        try:
            # 입력이 단일 객체인 경우 리스트로 변환
            if not isinstance(transactions, list):
                transactions = [transactions]

            # trade_id가 존재하는 거래의 id만 추출
            transaction_ids = [
                tx.trade_id for tx in transactions if getattr(tx, "trade_id", None)
            ]

            existing_ids = set()
            if transaction_ids:
                # 이미 존재하는 trade_id 조회
                existing_transactions = (
                    self.db_session.query(Transaction)
                    .filter(Transaction.trade_id.in_(transaction_ids))
                    .all()
                )
                existing_ids = {etx.trade_id for etx in existing_transactions}

            # 삽입할 객체 생성: (DB에 없는 trade_id만)
            new_objects = []
            for tx in transactions:
                tx_data = tx.model_dump()  # Pydantic 모델 → dict 추출
                if not getattr(tx, "trade_id", None) or tx.trade_id not in existing_ids:
                    new_objects.append(Transaction(**tx_data))

            # add_all() 사용
            if new_objects:
                self.db_session.add_all(new_objects)
                # 필요한 경우, 새로 생성된 PK를 사용하려면 flush()나 refresh()를 호출
            self.db_session.commit()

            # 입력이 단일 객체였다면 단일 객체, 아니면 리스트 반환
            if len(transactions) == 1:
                # 새로 삽입된 게 있다면 그 객체 반환, 아니면 원본 반환
                return new_objects[0] if new_objects else transactions[0]
            else:
                return new_objects if new_objects else transactions

        except Exception as exc:
            logger.exception("Error in insert_transactions_if_not_exist")
            self.db_session.rollback()
            raise HTTPException(
                status_code=500, detail="Internal Server Error"
            ) from exc

    def insert_transaction(
        self, transaction: Union[TransactionCreate, List[TransactionCreate]]
    ) -> Union[TransactionCreate, List[TransactionCreate]]:
        """
        하나 또는 여러 거래 정보를 데이터베이스에 추가합니다.
        """
        try:
            # 컨텍스트 매니저를 통해 트랜잭션 범위 내에서 작업
            if isinstance(transaction, list):
                self.db_session.add_all(transaction)
            else:
                self.db_session.add(transaction)

            # flush를 통해 DB에 반영(새로운 ID 할당 등을 위해 필요)
            self.db_session.commit()

            # 새로 생성된 데이터(예: ID)를 반영하기 위해 refresh 호출
            if isinstance(transaction, list):
                for tx in transaction:
                    self.db_session.refresh(tx)
            else:
                self.db_session.refresh(transaction)

            return transaction
        except Exception as exc:
            # 예외 발생 시 스택 트레이스까지 로깅
            logger.exception("Error inserting trading information")
            raise HTTPException(
                status_code=500, detail="Internal Server Error"
            ) from exc

    def insert_trading_information(self, trading: Trade):
        """
        AI 트레이딩 정보를 DB에 추가합니다.
        """
        try:
            self.db_session.add(trading)
            self.db_session.commit()
            return trading
        except Exception as e:
            logger.error("Error inserting trading information: %s", e)
            self.db_session.rollback()
            raise HTTPException(status_code=500)

    def get_trading_information(
        self,
    ):
        """
        DB에서 모든 거래 정보를 조회합니다.
        """
        try:
            trade = (
                self.db_session.query(Trade).order_by(Trade.timestamp.desc()).first()
            )

            return GetTradingInformationResponseModel(**row_to_dict(trade))
        except Exception as e:
            logger.error("Error inserting trading information: %s", e)
            self.db_session.rollback()
            raise HTTPException(status_code=500)
