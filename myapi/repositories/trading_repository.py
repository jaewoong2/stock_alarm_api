import logging

from fastapi import HTTPException
from sqlalchemy.orm import Session

from myapi.domain.trading.coinone_schema import GetTradingInformationResponseModel
from myapi.domain.trading.trading_model import Trade
from myapi.utils.config import row_to_dict

logger = logging.getLogger(__name__)


class TradingRepository:
    def __init__(
        self,
        db_session: Session,
    ):
        self.db_session = db_session

    def insert_trading_information(self, trading: Trade) -> Trade:
        """
        거래 정보를 DB에 추가합니다.
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

    # def save(self, user: UserVo):
    #     new_user = User(
    #         id=user.id,
    #         memo=user.memo,
    #         name=user.name,
    #         email=user.email,
    #         password=user.password,
    #         created_at=user.created_at,
    #         updated_at=user.updated_at,
    #     )

    #     with SessionLocal() as db:
    #         try:
    #             db = SessionLocal()
    #             db.add(new_user)
    #             db.commit()
    #         finally:
    #             db.close()

    # def find_by_email(self, email: str) -> UserVo:
    #     with SessionLocal() as db:
    #         user = db.query(User).filter(User.email == email).first()

    #     if not user:
    #         raise HTTPException(status_code=422)

    #     return UserVo(**row_to_dict(user))

    # def find_by_id(self, id: str):
    #     with SessionLocal() as db:
    #         user = db.query(User).filter(User.id == id).first()

    #     if not user:
    #         raise HTTPException(status_code=404)

    #     return UserVo(**row_to_dict(user))

    # def update(self, user_vo: UserVo):
    #     with SessionLocal() as db:
    #         try:
    #             user = db.query(User).filter(User.id == user_vo.id).first()

    #             if not user:
    #                 raise HTTPException(status_code=422)

    #             user.name = user_vo.name
    #             user.password = user_vo.password
    #             user.memo = user_vo.memo

    #             db.add(user)
    #             db.commit()

    #             return user
    #         except Exception as e:
    #             print(e)
    #             raise HTTPException(status_code=500)

    # def find_all(self, page: int = 1, items_per_page: int = 10):
    #     with SessionLocal() as db:
    #         query = db.query(User)
    #         total_count = query.count()

    #         # offset => 얼마나 건너 뛸 것 인가.
    #         offset = (page - 1) * items_per_page
    #         users = query.limit(items_per_page).offset(offset).all()

    #     return total_count, [UserVo(**row_to_dict(user)) for user in users]

    # def make_fake_users(self):
    #     with SessionLocal() as db:
    #         for i in range(50):
    #             user = User(
    #                 id=f"userid-{str(i).zfill(2)}",
    #                 name=f"TestUser{i}",
    #                 email=f"TestUser{i}@email.com",
    #                 password=Crypto().encrypt(secret="XXXXXXXX"),
    #                 memo=None,
    #                 created_at=datetime.now(),
    #                 updated_at=datetime.now(),
    #             )
    #             db.add(user)
    #         db.commit()

    # def delete(self, id: str):
    #     with SessionLocal() as db:
    #         try:
    #             user = db.query(User).filter(User.id == id).first()

    #             if not user:
    #                 raise HTTPException(status_code=422)

    #             db.delete(user)
    #             db.commit()
    #         except Exception as e:
    #             print(e)
    #             raise HTTPException(status_code=500)
