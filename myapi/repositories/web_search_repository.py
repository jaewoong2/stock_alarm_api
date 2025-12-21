import datetime
import logging
from typing import List, Literal, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, case, text, cast, String
from sqlalchemy.exc import OperationalError

from myapi.domain.news.news_models import (
    MarketForecast,
    WebSearchResult,
    AiAnalysisModel,
)
from myapi.domain.news.news_schema import (
    MahaneyStockAnalysis,
    MarketForecastSchema,
    MarketAnalysis,
    AiAnalysisVO,
)

logger = logging.getLogger(__name__)


class WebSearchResultRepository:
    def __init__(self, db_session: Session):
        self.db_session = db_session

    def bulk_create(self, records: List[WebSearchResult]) -> List[WebSearchResult]:
        try:
            self.db_session.bulk_save_objects(records)
            self.db_session.commit()
            return records
        except Exception as e:
            self.db_session.rollback()
            raise e

    def get_search_results(
        self,
        result_type: str,
        ticker: Optional[str] = None,
        start_date: Optional[datetime.datetime] = None,
        end_date: Optional[datetime.datetime] = None,
    ) -> List[WebSearchResult]:
        import time

        max_retries = 3
        retry_delay = 1

        tickers: Optional[List[str]] = None

        for attempt in range(max_retries):
            try:
                query = self.db_session.query(WebSearchResult).filter(
                    WebSearchResult.result_type == result_type
                )

                if ticker != "" and ticker is not None:

                    tickers = ticker.split(",")

                    if tickers and len(tickers) > 1:
                        query = query.filter(WebSearchResult.ticker.in_(tickers))
                    elif isinstance(ticker, str) and ticker.strip() != "":
                        ticker = ticker.strip().upper()
                        query = query.filter(WebSearchResult.ticker == ticker)

                if start_date is not None:
                    if isinstance(start_date, datetime.date) and not isinstance(
                        start_date, datetime.datetime
                    ):
                        start_boundary = datetime.datetime.combine(
                            start_date,
                            datetime.time.min,
                        )
                    else:
                        start_boundary = start_date

                    if start_boundary.tzinfo is None:
                        start_boundary = start_boundary.replace(
                            tzinfo=datetime.timezone.utc
                        )

                    query = query.filter(
                        WebSearchResult.created_at >= start_boundary
                    )

                if end_date is not None:
                    if isinstance(end_date, datetime.date) and not isinstance(
                        end_date, datetime.datetime
                    ):
                        end_boundary = datetime.datetime.combine(
                            end_date,
                            datetime.time.min,
                        )
                    else:
                        end_boundary = end_date

                    if end_boundary.tzinfo is None:
                        end_boundary = end_boundary.replace(tzinfo=datetime.timezone.utc)

                    query = query.filter(WebSearchResult.created_at < end_boundary)

                query = query.distinct(WebSearchResult.id).order_by(
                    WebSearchResult.id.desc(), WebSearchResult.date_yyyymmdd.desc()
                )

                result = query.all()

                if len(result) == 0:
                    if result_type == "ticker" and ticker:
                        query = self.db_session.query(WebSearchResult).filter(
                            WebSearchResult.result_type == result_type
                        )

                        if tickers and len(tickers) > 0:
                            query = query.filter(WebSearchResult.ticker.in_(tickers))
                        else:
                            ticker = ticker.strip().upper()
                            query = query.filter(WebSearchResult.ticker == ticker)

                        query = (
                            query.distinct(WebSearchResult.id)
                            .order_by(
                                WebSearchResult.id.desc(),
                                WebSearchResult.created_at.desc(),
                            )
                            .limit(30)
                        )

                        result = query.all()

                logger.info(
                    f"Successfully retrieved search results (attempt {attempt + 1}/{max_retries})"
                )
                return result

            except OperationalError as e:
                self.db_session.rollback()

                if attempt < max_retries - 1:
                    logger.warning(
                        f"Failed to get search results (attempt {attempt + 1}/{max_retries}): {e}. "
                        f"Retrying in {retry_delay}s..."
                    )
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    logger.error(
                        f"Failed to get search results after {max_retries} attempts: {e}"
                    )
                    raise e
            except Exception:
                self.db_session.rollback()
                raise

        # This line should never be reached due to raise e above, but satisfies type checker
        return []

    def get_ticker_counts_by_recommendation(
        self, recommendation: str, limit: int, date: Optional[datetime.date]
    ):
        """
        추천(recommendation) 유형에 따라 티커별 점수를 계산하여 순위를 매깁니다.
        - recommendation='buy': Buy +1, Sell -1, Hold 0 점으로 계산
        - recommendation='sell': Sell +1, Buy -1, Hold 0 점으로 계산
        """
        try:
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

            if isinstance(current_date, datetime.datetime):
                start_of_day = current_date
            else:
                start_of_day = datetime.datetime.combine(
                    current_date,
                    datetime.time.min,
                )

            if start_of_day.tzinfo is None:
                start_of_day = start_of_day.replace(tzinfo=datetime.timezone.utc)

            query = (
                self.db_session.query(
                    WebSearchResult.ticker,
                    score,
                )
                .filter(WebSearchResult.result_type == "ticker")
                .filter(WebSearchResult.created_at >= start_of_day)
                .group_by(WebSearchResult.ticker)
                .order_by(score.desc())
                .limit(limit)
            )

            return query.all()
        except Exception as e:
            self.db_session.rollback()
            raise e

    def create(self, forecast: MarketForecast):
        try:
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
        except Exception as e:
            self.db_session.rollback()
            raise e

    def get_by_date(
        self,
        start_date_yyyymmdd: str,
        end_date_yyyymmdd: str,
        source: Literal["Major", "Minor"],
    ):
        import time

        max_retries = 3
        retry_delay = 1  # seconds

        for attempt in range(max_retries):
            try:
                response = (
                    self.db_session.query(MarketForecast)
                    .filter(MarketForecast.date_yyyymmdd >= start_date_yyyymmdd)
                    .filter(MarketForecast.date_yyyymmdd <= end_date_yyyymmdd)
                    .filter(cast(MarketForecast.source, String) == source)
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

                logger.info(
                    f"Successfully retrieved market forecast data (attempt {attempt + 1}/{max_retries})"
                )
                return results

            except OperationalError as e:
                self.db_session.rollback()

                if attempt < max_retries - 1:
                    logger.warning(
                        f"Failed to get market forecast (attempt {attempt + 1}/{max_retries}): {e}. "
                        f"Retrying in {retry_delay}s..."
                    )
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    logger.error(
                        f"Failed to get market forecast after {max_retries} attempts: {e}"
                    )
                    raise e
            except Exception:
                self.db_session.rollback()
                raise

        # This line should never be reached due to raise e above, but satisfies type checker
        return None

    def safe_convert(self, value: Any, target_type: type = int):
        """SQLAlchemy Column이나 다른 객체에서 안전하게 원하는 타입으로 변환합니다.

        Args:
            value: 변환할 값
            target_type: 변환할 타입 (기본값: int)

        Returns:
            변환된 값 또는 None (변환 실패 시)
        """
        if value is None:
            return None
        try:
            return target_type(value)
        except (TypeError, ValueError):
            return None

    def get_all_analyses(
        self,
        name: str = "market_analysis",
        item_schema: type | None = MarketAnalysis,
        target_date: datetime.date = datetime.date.today(),
        tickers: Optional[List[str]] = None,
        models: Optional[str] = None,
        strategy_filter: Optional[str] = None,
    ) -> List[AiAnalysisVO]:
        """Fetch all analysis data of a given type.

        Parameters
        ----------
        name: str
            Identifier of the analysis type. Defaults to ``"market_analysis"``.
        schema: Optional[type]
            Pydantic schema used to validate the stored value. If ``None`` the
            raw JSON value is returned.
        target_date: Optional[datetime.date]
            If provided, only analyses for this date will be returned.
        tickers: Optional[List[str]]
            If provided, only analyses for these tickers will be returned.
        """

        try:
            from sqlalchemy import text, or_

            query = self.db_session.query(AiAnalysisModel).filter(
                AiAnalysisModel.name == name
            )

            # tickers 파라미터가 있으면 JSON 필드에서 ticker로 필터링
            if tickers and len(tickers) > 0:
                # ETF 분석의 경우 etf_ticker 또는 ticker 필드로 필터링
                if name == "etf_portfolio_analysis":
                    ticker_filters = []
                    for i, ticker in enumerate(tickers):
                        ticker_filters.extend(
                            [
                                text(f"value->>'etf_ticker' = :ticker_{i}").params(
                                    **{f"ticker_{i}": ticker}
                                ),
                            ]
                        )
                    query = query.filter(or_(*ticker_filters))
                else:
                    # 일반 분석의 경우 ticker 필드로 필터링
                    ticker_filters = [
                        text(f"value->>'ticker' = :ticker_{i}").params(
                            **{f"ticker_{i}": ticker}
                        )
                        for i, ticker in enumerate(tickers)
                    ]
                    query = query.filter(or_(*ticker_filters))

            if name == "signals":
                if models:
                    query = query.filter(
                        text("value->>'ai_model' = :ai_model").params(ai_model=models)
                    )

                if strategy_filter == "AI_GENERATED":
                    query = query.filter(text("value->>'strategy' = :strategy")).params(
                        strategy="AI_GENERATED"
                    )

                elif strategy_filter != "AI_GENERATED":
                    query = query.filter(
                        text("value->>'strategy' != :strategy")
                    ).params(strategy="AI_GENERATED")

            if target_date:
                if isinstance(target_date, datetime.datetime):
                    normalized_target = target_date.date()
                else:
                    normalized_target = target_date

                query = query.filter(and_(AiAnalysisModel.date == normalized_target))

            results = query.all()

            analyses = []
            for result in results:
                value = result.value
                if item_schema is not None:
                    try:
                        value = item_schema.model_validate(value)
                    except Exception:
                        # Fall back to raw value if validation fails
                        value = result.value

                analyses.append(
                    AiAnalysisVO(
                        id=self.safe_convert(result.id),
                        date=str(result.date),
                        name=str(result.name),
                        value=value,
                    )
                )

            return analyses
        except Exception as e:
            self.db_session.rollback()
            raise e

    def _build_base_query(self):
        """Build the base query for Mahaney analyses.

        Returns
        -------
        Query
            SQLAlchemy query object filtered by Mahaney analysis type.
        """
        return self.db_session.query(AiAnalysisModel).filter(
            AiAnalysisModel.name == "mahaney_analysis"
        )

    def _find_closest_available_date(
        self, target_date: datetime.date
    ) -> Optional[datetime.date]:
        """Find the closest available date to the target date.

        Parameters
        ----------
        target_date: datetime.date
            Target date to find closest match for.

        Returns
        -------
        Optional[datetime.date]
            Closest available date, or None if no data exists.
        """
        available_dates = (
            self.db_session.query(AiAnalysisModel.date)
            .filter(AiAnalysisModel.name == "mahaney_analysis")
            .distinct()
            .all()
        )

        if not available_dates:
            return None

        closest_date_str = None
        min_diff = float("inf")

        for date_tuple in available_dates:
            date_str = date_tuple[0]
            try:
                # Convert database date to date object
                if isinstance(date_str, datetime.date):
                    date_obj = date_str
                else:
                    date_obj = datetime.datetime.strptime(
                        str(date_str), "%Y-%m-%d"
                    ).date()

                diff = abs((date_obj - target_date).days)
                if diff < min_diff:
                    min_diff = diff
                    closest_date_str = date_str
            except (ValueError, TypeError):
                continue

        if closest_date_str:
            if isinstance(closest_date_str, datetime.date):
                return closest_date_str
            return datetime.datetime.strptime(str(closest_date_str), "%Y-%m-%d").date()

        return None

    def _resolve_target_date(
        self, base_query, target_date: datetime.date
    ) -> tuple[Optional[datetime.date], bool]:
        """Resolve the target date to an actual date with exact match flag.

        Checks if target_date exists in database. If not, finds closest available date.

        Parameters
        ----------
        base_query: Query
            Base query object for Mahaney analyses.
        target_date: datetime.date
            Target date to resolve.

        Returns
        -------
        tuple[Optional[datetime.date], bool]
            Tuple containing:
            - Actual date to use (None if no data exists)
            - Whether it's an exact match to target_date
        """
        # Check if exact date exists
        if isinstance(target_date, datetime.datetime):
            normalized_target = target_date.date()
        else:
            normalized_target = target_date

        exact_date_query = base_query.filter(
            AiAnalysisModel.date == normalized_target
        )
        exact_date_exists = exact_date_query.first() is not None

        if exact_date_exists:
            return normalized_target, True

        # Find closest date
        closest_date = self._find_closest_available_date(normalized_target)
        if closest_date:
            return closest_date, False

        return None, False

    def _apply_filters(
        self, query, tickers: Optional[List[str]], recommendation: Optional[str]
    ):
        """Apply ticker and recommendation filters to query.

        Parameters
        ----------
        query: Query
            Query object to apply filters to.
        tickers: Optional[List[str]]
            List of tickers to filter by.
        recommendation: Optional[str]
            Recommendation type to filter by (e.g., "Buy", "Sell", "Hold").

        Returns
        -------
        Query
            Filtered query object.
        """
        from sqlalchemy import text, or_, and_

        filters = []

        # Filter by tickers if provided
        if tickers and len(tickers) > 0:
            ticker_filters = [
                text("value->>'stock_name' = :ticker").params(ticker=ticker)
                for ticker in tickers
            ]
            filters.append(or_(*ticker_filters))

        # Filter by recommendation if provided
        if recommendation:
            filters.append(
                text("value->>'recommendation' = :recommendation").params(
                    recommendation=recommendation
                )
            )

        # Apply filters if any
        if filters:
            query = query.filter(and_(*filters))

        return query

    def _parse_query_results(self, results) -> List[MahaneyStockAnalysis]:
        """Parse and validate database query results.

        Parameters
        ----------
        results: List[AiAnalysisModel]
            Raw database query results.

        Returns
        -------
        List[MahaneyStockAnalysis]
            List of validated Mahaney stock analyses.
        """
        from myapi.domain.news.news_schema import MahaneyStockAnalysis

        analyses = []
        for result in results:
            try:
                stock_analysis = MahaneyStockAnalysis.model_validate(result.value)
                analyses.append(stock_analysis)
            except Exception as e:
                # Skip invalid data
                print(f"Failed to validate Mahaney analysis: {e}")
                continue

        return analyses

    def get_mahaney_analyses(
        self,
        target_date: datetime.date = datetime.date.today(),
        tickers: Optional[List[str]] = None,
        recommendation: Optional[str] = None,
    ) -> tuple[List[MahaneyStockAnalysis], datetime.date, bool]:
        """Fetch Mahaney analysis data with filtering options.

        If no exact match for target_date is found, returns data from the closest available date.

        Parameters
        ----------
        target_date: datetime.date
            Target date for analysis. Defaults to today.
        tickers: Optional[List[str]]
            If provided, only analyses for these tickers will be returned.
        recommendation: Optional[str]
            If provided, only analyses with this recommendation will be returned.

        Returns
        -------
        tuple[List[MahaneyStockAnalysis], datetime.date, bool]
            Tuple containing:
            - List of Mahaney stock analyses
            - Actual date used for the data
            - Whether the date is an exact match
        """
        try:
            # Build base query
            base_query = self._build_base_query()

            # Handle date matching (exact or closest)
            actual_date, is_exact_match = self._resolve_target_date(
                base_query, target_date
            )

            if actual_date is None:
                return [], target_date, False

            # Apply date filter
            query = base_query.filter(AiAnalysisModel.date == actual_date)

            # Apply ticker/recommendation filters
            query = self._apply_filters(query, tickers, recommendation)

            # Execute and parse results
            results = query.all()
            analyses = self._parse_query_results(results)

            return analyses, actual_date, is_exact_match

        except Exception as e:
            self.db_session.rollback()
            raise e

    def get_analyses_by_ticker(
        self,
        ticker: str,
        strategy_filter: Optional[str] = None,
        name: str = "signals",
        item_schema: type | None = None,
        ai_model: Optional[str] = None,
        target_date: datetime.date = datetime.date.today(),
    ) -> AiAnalysisVO | None:
        """Fetch analysis data for a given ticker and type.

        Note: The value field in the returned AiAnalysisVO contains JSON data that,
        when parsed, corresponds to the SignalBase type structure.

        Parameters
        ----------
        ticker: str
            Ticker symbol to filter the analysis.
        name: str
            Identifier of the analysis type. Defaults to ``"signals"``.
        item_schema: Optional[type]
            Pydantic schema used to validate the stored value. If ``None`` the
            raw JSON value is returned.
        target_date: Optional[datetime.date]
            If provided, only analyses for this date will be returned.
        """
        try:
            from sqlalchemy import text

            query = self.db_session.query(AiAnalysisModel).filter(
                AiAnalysisModel.name == name
            )

            if target_date:
                if isinstance(target_date, datetime.datetime):
                    normalized_target = target_date.date()
                else:
                    normalized_target = target_date
                query = query.filter(AiAnalysisModel.date == normalized_target)

            # JSON 필드에서 ticker로 필터링 (PostgreSQL의 경우)
            query = query.filter(text("value->>'ticker' = :ticker")).params(
                ticker=ticker
            )

            if ai_model:
                # value ai_model 필드로 필터링
                query = query.filter(text("value->>'ai_model' = :ai_model")).params(
                    ai_model=ai_model
                )

            if strategy_filter == "AI_GENERATED":
                query = query.filter(text("value->>'strategy' = :strategy")).params(
                    strategy="AI_GENERATED"
                )
            elif strategy_filter is not None:
                query = query.filter(text("value->>'strategy' != :strategy")).params(
                    strategy="AI_GENERATED"
                )

            result = query.first()

            if not result:
                return None

            value = result.value
            if item_schema is not None:
                try:
                    result.value = item_schema.model_validate(value)
                except Exception:
                    result.value = value

            return AiAnalysisVO(
                id=self.safe_convert(result.id),
                date=str(result.date),
                name=str(result.name),
                value=value,
            )
        except Exception as e:
            self.db_session.rollback()
            raise e

    def get_analysis_by_date(
        self,
        analysis_date: datetime.date,
        name: str = "market_analysis",
        schema: type | None = MarketAnalysis,
    ) -> AiAnalysisVO | None:
        """Fetch analysis data for a given date and type.

        Parameters
        ----------
        analysis_date: datetime.date
            Date of the analysis to retrieve.
        name: str
            Identifier of the analysis type. Defaults to ``"market_analysis"``.
        schema: Optional[type]
            Pydantic schema used to validate the stored value. If ``None`` the
            raw JSON value is returned.
        """
        import time

        max_retries = 3
        retry_delay = 1

        for attempt in range(max_retries):
            try:
                normalized_date = (
                    analysis_date.date()
                    if isinstance(analysis_date, datetime.datetime)
                    else analysis_date
                )
                result = (
                    self.db_session.query(AiAnalysisModel)
                    .filter(
                        AiAnalysisModel.date == normalized_date,
                        AiAnalysisModel.name == name,
                    )
                    .first()
                )

                if not result:
                    return None

                value = result.value
                if schema is not None:
                    try:
                        value = schema.model_validate(value)
                    except Exception:
                        # Fall back to raw value if validation fails
                        value = result.value

                logger.info(
                    f"Successfully retrieved analysis by date (attempt {attempt + 1}/{max_retries})"
                )
                return AiAnalysisVO(
                    id=self.safe_convert(result.id),
                    date=str(result.date),
                    name=str(result.name),
                    value=value,
                )

            except OperationalError as e:
                self.db_session.rollback()

                if attempt < max_retries - 1:
                    logger.warning(
                        f"Failed to get analysis by date (attempt {attempt + 1}/{max_retries}): {e}. "
                        f"Retrying in {retry_delay}s..."
                    )
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    logger.error(
                        f"Failed to get analysis by date after {max_retries} attempts: {e}"
                    )
                    raise e
            except Exception:
                self.db_session.rollback()
                raise

        # This line should never be reached due to raise e above, but satisfies type checker
        return None

    def get_anaylsis_by_name_latest(
        self,
        name: str,
        schema: type | None = None,
    ):
        """Fetch analysis data for a given name.

        Parameters
        ----------
        name: str
            Identifier of the analysis type.
        schema: Optional[type]
            Pydantic schema used to validate the stored value. If ``None`` the
            raw JSON value is returned.
        """
        try:
            result = (
                self.db_session.query(AiAnalysisModel)
                .filter(
                    AiAnalysisModel.name == name,
                )
                .order_by(AiAnalysisModel.created_at.desc())
                .first()
            )

            if not result:
                return None

            value = result.value
            if schema is not None:
                try:
                    value = schema.model_validate(value)
                except Exception:
                    value = result.value

            logger.info(f"Successfully retrieved analysis by name")
            return AiAnalysisVO(
                id=self.safe_convert(result.id),
                date=str(result.date),
                name=str(result.name),
                value=value,
            )

        except OperationalError as e:
            self.db_session.rollback()

        except Exception:
            self.db_session.rollback()
            raise

        # This line should never be reached due to raise e above, but satisfies type checker
        return None

    def get_analysis_by_date_and_ticker(
        self,
        analysis_date: datetime.date,
        ticker: str,
        name: str = "fundamental_analysis",
        schema: type | None = None,
    ) -> AiAnalysisVO | None:
        """Fetch analysis data filtered by date, name, AND ticker from JSON field.

        Parameters
        ----------
        analysis_date: datetime.date
            Date of the analysis to retrieve.
        ticker: str
            Ticker symbol to filter from JSON value field (value->>'ticker').
        name: str
            Identifier of the analysis type. Defaults to ``"fundamental_analysis"``.
        schema: Optional[type]
            Pydantic schema used to validate the stored value. If ``None`` the
            raw JSON value is returned.
        """
        import time
        from sqlalchemy import text

        max_retries = 3
        retry_delay = 1

        for attempt in range(max_retries):
            try:
                normalized_date = (
                    analysis_date.date()
                    if isinstance(analysis_date, datetime.datetime)
                    else analysis_date
                )
                result = (
                    self.db_session.query(AiAnalysisModel)
                    .filter(
                        AiAnalysisModel.date == normalized_date,
                        AiAnalysisModel.name == name,
                        text("value->>'ticker' = :ticker").params(
                            ticker=ticker.upper()
                        ),
                    )
                    .first()
                )

                if not result:
                    return None

                value = result.value
                if schema is not None:
                    try:
                        value = schema.model_validate(value)
                    except Exception:
                        # Fall back to raw value if validation fails
                        value = result.value

                logger.info(
                    f"Successfully retrieved analysis by date and ticker (attempt {attempt + 1}/{max_retries})"
                )
                return AiAnalysisVO(
                    id=self.safe_convert(result.id),
                    date=str(result.date),
                    name=str(result.name),
                    value=value,
                )

            except OperationalError as e:
                self.db_session.rollback()

                if attempt < max_retries - 1:
                    logger.warning(
                        f"Failed to get analysis by date and ticker (attempt {attempt + 1}/{max_retries}): {e}. "
                        f"Retrying in {retry_delay}s..."
                    )
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    logger.error(
                        f"Failed to get analysis by date and ticker after {max_retries} attempts: {e}"
                    )
                    raise e
            except Exception:
                self.db_session.rollback()
                raise

        # This line should never be reached due to raise e above, but satisfies type checker
        return None

    def create_analysis(
        self,
        analysis_date: datetime.date,
        analysis: Any,
        name: str = "market_analysis",
    ) -> AiAnalysisVO:
        """Store analysis data for a given date and type."""
        import time

        max_retries = 3
        retry_delay = 1  # seconds

        for attempt in range(max_retries):
            try:
                normalized_date = (
                    analysis_date.date()
                    if isinstance(analysis_date, datetime.datetime)
                    else analysis_date
                )
                db_obj = AiAnalysisModel(
                    date=normalized_date,
                    name=name,
                    value=analysis,
                )

                self.db_session.add(db_obj)
                self.db_session.commit()
                self.db_session.refresh(db_obj)

                logger.info(
                    f"Successfully stored {name} analysis (attempt {attempt + 1}/{max_retries})"
                )

                return AiAnalysisVO(
                    id=self.safe_convert(db_obj.id),
                    date=str(db_obj.date),
                    name=str(db_obj.name),
                    value=analysis,
                )
            except OperationalError as e:
                self.db_session.rollback()

                if attempt < max_retries - 1:
                    logger.warning(
                        f"Failed to store analysis (attempt {attempt + 1}/{max_retries}): {e}. "
                        f"Retrying in {retry_delay}s..."
                    )
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    logger.error(
                        f"Failed to store analysis after {max_retries} attempts: {e}"
                    )
                    raise e
            except Exception:
                self.db_session.rollback()
                raise

        # This line should never be reached due to raise e above, but satisfies type checker
        raise RuntimeError("Failed to create analysis after all retries")
