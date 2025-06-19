import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, case

from myapi.domain.news.news_models import MarketForecast, WebSearchResult
from myapi.domain.news.news_schema import MarketForecastSchema


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
            query = query.filter(WebSearchResult.created_at < end_date)

        query = query.order_by(WebSearchResult.date_yyyymmdd.desc())

        return query.all()

    def get_ticker_counts_by_recommendation(
        self, recommendation: str, limit: int, date: Optional[datetime.date]
    ):
        """
        추천(recommendation) 유형에 따라 티커별 점수를 계산하여 순위를 매깁니다.
        - recommendation='buy': Buy +1, Sell -1, Hold 0 점으로 계산
        - recommendation='sell': Sell +1, Buy -1, Hold 0 점으로 계산
        """
        current_date = datetime.date.today() if date is None else date

        if recommendation.lower() == "buy":
            score_expression = case(
                (WebSearchResult.recommendation == "Buy", 1),
                (WebSearchResult.recommendation == "Sell", -1),
                else_=0,
            )
        elif recommendation.lower() == "sell":
            score_expression = case(
                (WebSearchResult.recommendation == "Sell", 1),
                (WebSearchResult.recommendation == "Buy", -1),
                else_=0,
            )
        else:
            # 'buy' 또는 'sell'이 아닌 경우 빈 리스트를 반환합니다.
            return []

        score = func.sum(score_expression).label("score")

        query = (
            self.db_session.query(
                WebSearchResult.ticker,
                score,
            )
            .filter(WebSearchResult.result_type == "ticker")
            .filter(WebSearchResult.created_at >= current_date.strftime("%Y-%m-%d"))
            .group_by(WebSearchResult.ticker)
            .order_by(score.desc())
            .limit(limit)
        )

        return query.all()

    def create(self, forecast: MarketForecast):
        self.db_session.add(forecast)
        self.db_session.commit()
        self.db_session.refresh(forecast)

        return MarketForecastSchema.model_validate(forecast) if forecast else None

    def get_by_date(self, date_yyyymmdd: str):
        result = (
            self.db_session.query(MarketForecast)
            .filter(MarketForecast.date_yyyymmdd == date_yyyymmdd)
            .first()
        )

        return MarketForecastSchema.model_validate(result) if result else None
