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
        하나 또는 여러 거래 정보를 받아, 기존에 존재하지 않는 경우에만 DB에 bulk 방식으로 삽입합니다.
        고유 식별자(id)를 기준으로 존재 여부를 판단하며, 이미 존재하면 삽입하지 않습니다.

        주의:
        - TransactionCreate는 Pydantic 모델로, .dict() 메서드를 통해 데이터를 추출할 수 있어야 합니다.
        - Transaction은 SQLAlchemy 모델입니다.
        - bulk_save_objects는 일반 ORM 작업보다 성능이 뛰어나지만, 자동으로 식별자(id) 등의 필드를 새로 반영하지 않을 수 있습니다.
        """
        try:
            # 입력이 단일 객체인 경우 리스트로 변환
            if not isinstance(transactions, list):
                transactions = [transactions]

            # id가 존재하는 거래의 id 추출 (업데이트나 삽입 대상 판별)
            transaction_ids = [
                tx.trade_id for tx in transactions if getattr(tx, "id", None)
            ]

            # 기존 레코드 조회: id가 있는 경우에 한해
            if transaction_ids:
                existing_transactions = (
                    self.db_session.query(Transaction)
                    .filter(Transaction.trade_id.in_(transaction_ids))
                    .all()
                )
                existing_ids = {tx.trade_id for tx in existing_transactions}
            else:
                existing_ids = set()

            # 삽입할 객체 준비: id가 없거나, DB에 없는 경우만
            new_objects = []
            for tx in transactions:
                # Pydantic 모델인 경우 dict()로 데이터를 추출
                tx_data = tx.model_dump() if hasattr(tx, "dict") else vars(tx)
                if not getattr(tx, "trade_id", None) or tx.trade_id not in existing_ids:
                    new_objects.append(Transaction(**tx_data))

            # bulk 방식으로 삽입
            with self.db_session.begin():
                if new_objects:
                    self.db_session.bulk_save_objects(new_objects)
                    self.db_session.flush()

            # 입력이 단일 객체인 경우 단일 객체, 복수면 리스트로 반환
            if len(transactions) == 1:
                return new_objects[0] if new_objects else transactions[0]
            else:
                return new_objects if new_objects else transactions

        except Exception as exc:
            logger.exception("Error in bulk insert transactions")
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
            with self.db_session.begin():
                if isinstance(transaction, list):
                    self.db_session.add_all(transaction)
                else:
                    self.db_session.add(transaction)

                # flush를 통해 DB에 반영(새로운 ID 할당 등을 위해 필요)
                self.db_session.flush()

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

    def insert_trading_information(self, trading: Trade) -> Trade:
        """
        AI 트레이딩 정보를 DB에 추가합니다.
        """
        try:
            with self.db_session.begin():
                self.db_session.add(trading)
                self.db_session.flush()  # Flush if you need to assign an ID or similar
            return trading
        except Exception as e:
            logger.error("Error inserting trading information: %s", e)
            self.db_session.rollback()
            raise HTTPException(status_code=500)
        finally:
            self.db_session.close()

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
        finally:
            self.db_session.close()
