import contextlib
from dotenv import load_dotenv


from urllib.parse import quote
from sqlalchemy import URL, MetaData, create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base

from myapi.utils.config import get_settings


load_dotenv(dotenv_path="myapi/.env")  # Load variables from .env


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
engine = create_engine(SQLALCHEMY_DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base(metadata=MetaData(schema=settings.database_schema))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextlib.contextmanager
def get_db_contextlib():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
