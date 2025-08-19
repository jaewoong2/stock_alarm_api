from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import inspect
import logging

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="myapi/.env",
        env_file_encoding="utf-8",
        extra="allow",
    )

    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_DEFAULT_REGION: str = "ap-northeast-2"
    AWS_S3_ACCESS_KEY_ID: str = ""
    AWS_S3_SECRET_ACCESS_KEY: str = ""
    AWS_S3_DEFAULT_REGION: str = "ap-northeast-2"

    DATABASE_URL: str = (
        "postgresql+psycopg2://postgres:postgres@localhost:5432/postgres"
    )
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60

@lru_cache
def get_settings() -> Settings:
    return Settings()

def row_to_dict(row) -> dict:
    return {key: getattr(row, key) for key in inspect(row).attrs.keys()}

def init_logging() -> None:
    logger = logging.getLogger()
    if logger.hasHandlers():
        logger.handlers.clear()
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s in %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger.setLevel(logging.INFO)
    logger.info("✅ Logging initialized!")
