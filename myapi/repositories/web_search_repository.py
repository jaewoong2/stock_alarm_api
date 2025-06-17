from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from myapi.domain.news.news_models import WebSearchResult


class WebSearchResultRepository:
    def __init__(self, db_session: Session):
        self.db_session = db_session

    def bulk_create(self, records: List[WebSearchResult]) -> List[WebSearchResult]:
        self.db_session.bulk_save_objects(records)
        self.db_session.commit()
        return records

    def get_search_results(
        self,
        result_type: str,
        ticker: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[WebSearchResult]:
        query = self.db_session.query(WebSearchResult).filter(
            WebSearchResult.result_type == result_type
        )
        if ticker != "" and ticker is not None:
            query = query.filter(WebSearchResult.ticker == ticker)

        if start_date:
            query = query.filter(WebSearchResult.created_at >= start_date)

        if end_date:
            query = query.filter(WebSearchResult.created_at <= end_date)

        query = query.order_by(WebSearchResult.date_yyyymmdd.desc())

        return query.all()

    def get_ticker_counts_by_recommendation(
        self, recommendation: str, limit: int
    ) -> List[tuple[str, int]]:
        query = (
            self.db_session.query(
                WebSearchResult.ticker,
                func.count(WebSearchResult.id).label("cnt"),
            )
            .filter(WebSearchResult.result_type == "ticker")
            .filter(WebSearchResult.recommendation.ilike(recommendation))
            .group_by(WebSearchResult.ticker)
            .order_by(func.count(WebSearchResult.id).desc())
            .limit(limit)
        )
        return query.all()
