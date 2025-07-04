import datetime
from typing import List, Literal, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, case

from myapi.domain.news.news_models import MarketForecast, WebSearchResult
from myapi.domain.news.news_schema import (
    MarketForecastSchema,
    WebSearchResultSchema,
)


class WebSearchResultRepository:
    def __init__(self, db_session: Session):
        self.db_session = db_session

    def _to_schema(self, obj: WebSearchResult) -> WebSearchResultSchema:
        return WebSearchResultSchema(
            id=obj.id,
            result_type=obj.result_type,
            ticker=obj.ticker,
            date_yyyymmdd=obj.date_yyyymmdd,
            headline=obj.headline,
            summary=obj.summary,
            detail_description=obj.detail_description,
            recommendation=obj.recommendation,
            created_at=obj.created_at.isoformat() if obj.created_at else None,
        )

    def bulk_create(self, records: List[WebSearchResult]) -> List[WebSearchResultSchema]:
        self.db_session.bulk_save_objects(records)
        self.db_session.commit()
        return [self._to_schema(r) for r in records]

    def get_search_results(
        self,
        result_type: str,
        ticker: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[WebSearchResultSchema]:
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

        return [self._to_schema(r) for r in query.all()]

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

        up_percentage = None
        if forecast.up_percentage is not None:
            up_percentage = float(str(forecast.up_percentage))

        return MarketForecastSchema(
            created_at=forecast.created_at.isoformat(),
            date_yyyymmdd=str(forecast.date_yyyymmdd),
            outlook="UP" if str(forecast.outlook) == "UP" else "DOWN",
            reason=str(forecast.reason),
            up_percentage=up_percentage,
        )

    def get_by_date(
        self,
        start_date_yyyymmdd: str,
        end_date_yyyymmdd: str,
        source: Literal["Major", "Minor"],
    ):
        # result = (
        #     self.db_session.query(MarketForecast)
        #     .filter(MarketForecast.date_yyyymmdd == date_yyyymmdd)
        #     .filter(MarketForecast.source == source)
        #     .first()
        # )

        response = (
            self.db_session.query(MarketForecast)
            .filter(MarketForecast.date_yyyymmdd >= start_date_yyyymmdd)
            .filter(MarketForecast.date_yyyymmdd <= end_date_yyyymmdd)
            .filter(MarketForecast.source == source)
            .order_by(MarketForecast.date_yyyymmdd.asc())
            .all()
        )

        if not response:
            return None

        results = []

        for result in response:
            up_percentage = None

            if result.up_percentage is not None:
                up_percentage = float(str(result.up_percentage))

            results.append(
                MarketForecastSchema(
                    created_at=result.created_at.isoformat(),
                    date_yyyymmdd=str(result.date_yyyymmdd),
                    outlook="UP" if str(result.outlook) == "UP" else "DOWN",
                    reason=str(result.reason),
                    up_percentage=up_percentage,
                )
            )

        return results
