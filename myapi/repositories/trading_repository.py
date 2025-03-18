import logging
from typing import List, Union

from fastapi import HTTPException
from sqlalchemy.orm import Session

from myapi.domain.trading.coinone_schema import GetTradingInformationResponseModel
from myapi.domain.trading.trading_model import Trade
from myapi.domain.trading.trading_schema import TransactionCreate
from myapi.utils.config import row_to_dict

logger = logging.getLogger(__name__)


class TradingRepository:
    def __init__(
        self,
        db_session: Session,
    ):
        self.db_session = db_session

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
