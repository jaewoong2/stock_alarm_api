# config.py
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

from sqlalchemy import inspect

import logging
import logging.config


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="myapi/.env",
        env_file_encoding="utf-8",
        extra="allow",
    )

    BINANCE_API_KEY: str = ""
    BINANCE_API_SECRET: str = ""
    BINANCE_FUTURES_API_KEY: str = ""
    BINANCE_FUTURES_API_SECRET: str = ""

    NAVER_CLIENT_ID: str = ""
    NAVER_CLIENT_SECRET: str = ""

    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_DEFAULT_REGION: str = ""
    AWS_S3_ACCESS_KEY_ID: str = ""
    AWS_S3_SECRET_ACCESS_KEY: str = ""
    AWS_S3_DEFAULT_REGION: str = ""
    KAKAO_NATIVE_APP_KEY: str = ""
    KAKAO_REST_API_KEY: str = ""
    KAKAO_JAVASCRIPT_KEY: str = ""
    KAKAO_ADMIN_KEY: str = ""
    KAKAO_REDIRECT_URI: str = ""
    KAKAO_MY_AUTH_TOKEN: str = ""
    KAKAO_MY_ACCESS_TOKEN: str = ""
    KAKAO_MY_REFRESH_TOKEN: str = ""
    OPENAI_API_KEY: str = ""
    COIN_ACCESS_TOKEN: str = ""
    COIN_SECRET_KEY: str = ""
    HYPERBOLIC_API_KEY: str = ""
    NEWS_API_KEY: str = ""
    FRED_API_KEY: str = ""
    DISCORD_WEBHOOK_URL: str = ""

    database_engine: str = ""
    database_username: str = ""
    database_password: str = ""
    database_host: str = ""
    database_port: str = ""
    database_dbname: str = ""
    database_port: str = ""
    database_schema: str = ""

    GEMINI_API_KEY: str = ""


@lru_cache
def get_settings():
    return Settings()


def row_to_dict(row) -> dict:
    return {key: getattr(row, key) for key in inspect(row).attrs.keys()}


def init_logging():
    # 루트 로거 가져오기
    logger = logging.getLogger()

    # 기존 핸들러가 있으면 제거 (중복 방지)
    if logger.hasHandlers():
        logger.handlers.clear()

    # 로거 설정
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s in %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # AWS Lambda에서 로그가 찍히도록 로그 레벨 설정
    logger.setLevel(logging.INFO)

    logger.info("✅ Logging initialized!")  # 로그 확인용
