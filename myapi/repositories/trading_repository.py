import logging

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

    def insert_transaction(self, transaction: TransactionCreate):
        """
        거래 정보를 DB에 추가합니다.
        """
        try:
            with self.db_session.begin():
                self.db_session.add(transaction)
                self.db_session.flush()
            return transaction
        except Exception as e:
            logger.error("Error inserting trading information: %s", e)
            self.db_session.rollback()
            raise HTTPException(status_code=500)
        finally:
            self.db_session.close()

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
