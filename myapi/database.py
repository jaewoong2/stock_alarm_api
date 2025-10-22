import contextlib
import logging
from dotenv import load_dotenv


from urllib.parse import quote
from sqlalchemy import URL, MetaData, create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base

from myapi.utils.config import get_settings


load_dotenv(dotenv_path="myapi/.env")  # Load variables from .env
logger = logging.getLogger(__name__)


settings = get_settings()

password = quote(settings.database_password)
url = URL.create(
    drivername=settings.database_engine,
    username=settings.database_username,
    password=settings.database_password,
    host=settings.database_host,
    port=int(settings.database_port),
    database=settings.database_dbname,
)


# SQLALCHEMY_DATABASE_URL = f"{settings.database_engine}://{settings.database_username}:{password}@{settings.database_host}:{settings.database_port}/{settings.database_dbname}"
SQLALCHEMY_DATABASE_URL = url.render_as_string(hide_password=False)
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_size=20,  # Increased from 5 to 20 for better concurrency
    max_overflow=10,  # Increased from 2 to 10 for additional connections
    pool_pre_ping=True,
    pool_recycle=1800,
    echo=False,
    pool_timeout=60,  # Increased from 30 to 60 seconds
    connect_args={"connect_timeout": 60, "application_name": "tqqq_api"},
)

SessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine, expire_on_commit=False
)

Base = declarative_base(metadata=MetaData(schema=settings.database_schema))


def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        db.rollback()
        raise e
    finally:
        try:
            db.close()
        except Exception:
            logger.warning("Failed to close database session gracefully.")
            # 연결 종료 시 예외가 발생해도 무시
            pass


@contextlib.contextmanager
def get_db_contextlib():
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        db.rollback()
        raise e
    finally:
        try:
            db.close()
        except Exception:
            logger.warning("Failed to close database session gracefully.")
            # 연결 종료 시 예외가 발생해도 무시
            pass
