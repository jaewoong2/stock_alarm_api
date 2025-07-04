from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import os

os.environ.setdefault("DATABASE_ENGINE", "postgresql+psycopg2")
os.environ.setdefault("DATABASE_USERNAME", "")
os.environ.setdefault("DATABASE_PASSWORD", "")
os.environ.setdefault("DATABASE_HOST", "localhost")
os.environ.setdefault("DATABASE_PORT", "5432")
os.environ.setdefault("DATABASE_DBNAME", "test")
os.environ.setdefault("DATABASE_SCHEMA", "crypto")

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    String,
    func,
    MetaData,
)
from sqlalchemy.orm import declarative_base
from myapi.repositories import web_search_repository
from myapi.repositories.web_search_repository import WebSearchResultRepository

TestBase = declarative_base(metadata=MetaData(schema="crypto"))


class TestWebSearchResult(TestBase):
    __tablename__ = "web_search_results"
    __table_args__ = {"schema": "crypto"}

    id = Column(Integer, primary_key=True, index=True)
    result_type = Column(String, nullable=False)
    ticker = Column(String, nullable=True)
    date_yyyymmdd = Column(String, nullable=False)
    headline = Column(String, nullable=True)
    summary = Column(String, nullable=True)
    detail_description = Column(String, nullable=True)
    recommendation = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


web_search_repository.WebSearchResult = TestWebSearchResult


def setup_session():
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("ATTACH DATABASE ':memory:' AS crypto"))
    TestBase.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


def test_get_search_results():
    session = setup_session()
    repo = WebSearchResultRepository(session)
    repo.bulk_create([
        TestWebSearchResult(
            result_type="ticker",
            ticker="AAPL",
            date_yyyymmdd="2024-01-01",
            headline="headline",
            summary="summary",
            detail_description="detail",
            recommendation="Buy",
        )
    ])

    results = repo.get_search_results(result_type="ticker", ticker="AAPL")
    assert len(results) == 1
    assert results[0].ticker == "AAPL"
