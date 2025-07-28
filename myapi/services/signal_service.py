import datetime as dt
from datetime import date
from io import BytesIO
import logging
from typing import Literal, Optional, Sequence
import cloudscraper
import pdfplumber
import yfinance as yf

from myapi.repositories.signals_repository import SignalsRepository
from myapi.repositories.web_search_repository import WebSearchResultRepository
from myapi.services.technical_analysis_service import TechnicalAnalysisService
from myapi.services.news_service import NewsService
from myapi.services.translate_service import TranslateService
from myapi.utils.config import Settings
from myapi.domain.signal.signal_schema import (
    SignalPromptData,
    Strategy,
    TickerReport,
    SignalRequest,
    SignalResponse,
    WebSearchTickerResult,
)
from myapi.domain.news.news_schema import (
    WebSearchMarketItem,
)
from myapi.domain.news.news_models import WebSearchResult

logger = logging.getLogger(__name__)


class SignalService:
    """통합 시그널 생성 서비스

    기술적 분석, 뉴스, 웹 검색 등을 통합하여 매매 시그널을 생성합니다.
    복잡한 로직은 각각의 전용 서비스로 위임합니다.
    """

    def __init__(
        self,
        settings: Settings,
        signals_repository: SignalsRepository,
        web_search_repository: WebSearchResultRepository,
        translate_service: TranslateService,
    ):
        self.settings = settings
        self.signals_repository = signals_repository
        self.web_search_repository = web_search_repository
        self.translate_service = translate_service

        # 전용 서비스들
        self.technical_service = TechnicalAnalysisService()
        self.news_service = NewsService(settings, translate_service)

        self.logger = logging.getLogger(__name__)

    def generate_signals(self, request: SignalRequest) -> SignalResponse:
        """시그널 생성 메인 메서드"""
        reports = []

        # 시장 상태 확인
        market_condition = "bullish" if self.market_ok() else "neutral"

        for ticker in request.tickers or []:
            try:
                # OHLCV 데이터 수집
                df = self.technical_service.fetch_ohlcv(ticker)
                if df.empty:
                    continue

                # SPY 데이터 수집 (상대강도 계산용)
                spy_df = self.technical_service.fetch_ohlcv("SPY")

                # 기술적 지표 추가
                df = self.technical_service.add_indicators(df, spy_df)

                # 시그널 평가
                signals = self.technical_service.evaluate_signals(
                    df, request.strategies
                )

                # 기본적 지표 수집
                fundamentals = None
                if request.with_fundamental:
                    fundamentals = self.technical_service.fetch_fundamentals(ticker)

                # 뉴스 수집
                news = []
                if request.with_news:
                    news = self.news_service.fetch_news(ticker)

                # 리포트 생성
                report = TickerReport(
                    ticker=ticker,
                    last_price=df["Close"].iloc[-1] if not df.empty else None,
                    price_change_pct=(
                        df["Close"].pct_change().iloc[-1] * 100 if len(df) > 1 else None
                    ),
                    signals=signals,
                    fundamentals=fundamentals,
                    news=news,
                    dataframe=df.tail(10).to_csv() if not df.empty else None,
                )

                reports.append(report)

            except Exception as e:
                self.logger.error(f"Error generating signals for {ticker}: {e}")
                continue

        return SignalResponse(
            run_date=date.today(), reports=reports, market_condition=market_condition
        )

    def save_web_search_results(
        self,
        result_type: str,
        results: Sequence[WebSearchMarketItem | WebSearchTickerResult],
        ticker: str | None = None,
    ) -> None:
        """웹 검색 결과를 데이터베이스에 저장"""
        db_items = [
            WebSearchResult(
                result_type=result_type,
                ticker=ticker,
                date_yyyymmdd=item.issued_YYYYMMDD,
                headline=getattr(item, "headline", None),
                summary=getattr(item, "summary", None),
                detail_description=getattr(item, "full_description", None),
                recommendation=getattr(item, "recommendation", None),
            )
            for item in results
        ]
        if db_items:
            self.web_search_repository.bulk_create(db_items)

    def market_ok(self, index_ticker="SPY") -> bool:
        """시장 상태 확인: 지수가 20일 SMA 위에 있으면 True"""
        try:
            df = yf.download(
                index_ticker, period="6mo", auto_adjust=True, progress=False
            )
            if df is None or df.empty:
                return False

            df = self.technical_service.add_indicators(df)
            return bool(df["Close"].iloc[-1] > df["SMA20"].iloc[-1])
        except Exception as e:
            self.logger.error(f"Error checking market condition: {e}")
            return False

    def rs_ok(self, ticker: str, benchmark="SPY", lookback_weeks=13) -> bool:
        """상대강도 필터: 벤치마크 대비 상위 30% 성과면 True"""
        try:
            lookback_days = lookback_weeks * 5
            t_df = yf.download(
                ticker, period=f"{lookback_days+5}d", auto_adjust=True, progress=False
            )
            b_df = yf.download(
                benchmark,
                period=f"{lookback_days+5}d",
                auto_adjust=True,
                progress=False,
            )

            if t_df is None or b_df is None or t_df.empty or b_df.empty:
                return False

            rel = (t_df["Close"] / b_df["Close"]).dropna()
            rs_rank = rel.pct_change(lookback_days).rank(pct=True).iloc[-1]
            return bool(rs_rank > 0.70)
        except Exception as e:
            self.logger.error(f"Error checking relative strength for {ticker}: {e}")
            return False

    def generate_prompt(
        self,
        data: SignalPromptData,
        report_summary: str | None = "",
        today: str = dt.date.today().strftime("%Y-%m-%d"),
    ) -> str:
        """AI 모델용 프롬프트 생성"""
        prompt = f"""
        You are a professional day-swing trader with deep knowledge.
        Ensure recommendations are realistic and aligned with short-term trading (1-2 days).
        
        Date: {today}
        
        ### Analysis Instructions
        1. Extract all bullish/bearish signals from the data
        2. Stress-test signals against historical patterns
        3. Consider fundamental data for stock quality
        4. Think about Relative Strength vs S&P 500
        5. Analyze chart patterns using OHLCV data
        
        ### Provide Recommendations
        For each stock/ETF, recommend: BUY, SELL, or HOLD
        - Entry Price: Suggested entry price
        - Stop-Loss Price: Risk management level
        - Take-Profit Price: Profit target
        
        ### Input Data
        - Ticker: {data.ticker}
        - Last Price: {data.last_price}
        - Price Change %: {data.price_change_pct}
        - Triggered Strategies: {data.triggered_strategies}
        - Technical Details: {data.technical_details}
        - Fundamentals: {data.fundamentals}
        - Report Summary: {report_summary}
        - S&P 500 Status: {data.spy_description}
        - Additional Info: {data.additional_info}
        - OHLCV DataFrame: {data.dataframe}
        """
        return prompt

    def report_summary_prompt(self, ticker: str, report_text: str):
        """기술적 분석 리포트 요약용 프롬프트"""
        system_prompt = f"""
        You are a financial analyst. Summarize a {ticker} technical report.
        
        The summary must include:
        1) Price Action (1-3 sentences)
        2) Volume (1-3 sentences)
        3) Trend & Pattern (1-3 sentences)
        4) Technical Signals (1-3 sentences)
        5) Support & Resistance (1-3 sentences)
        6) Expected Volatility & Risk (1-3 sentences)
        7) Overall Assessment (1-3 sentences)
        """

        prompt = f"""
        Please summarize the following report:
        
        # Report
        {report_text}
        """

        return system_prompt, prompt

    def extract_text_only(self, pdf_bytes: bytes) -> str:
        """PDF에서 텍스트만 추출"""
        full_text: list[str] = []

        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    full_text.append(text)

        return "\n\n".join(full_text)

    def fetch_pdf_stock_investment(self, ticker: str) -> bytes:
        """주식 투자 PDF 리포트 다운로드"""
        url = f"https://stockinvest.us/pdf/technical-analysis/{ticker}"
        scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "mobile": False},
        )

        # 페이지 먼저 열기
        scraper.get(f"https://stockinvest.us/stock/{ticker}", timeout=20)
        response = scraper.get(
            url=url,
            timeout=20,
            headers={
                "Accept": "application/pdf",
                "Referer": f"https://stockinvest.us/stock/{ticker}",
            },
            stream=True,
        )

        response.raise_for_status()
        if not response.headers.get("Content-Type", "").startswith("application/pdf"):
            return b"None"

        return response.content

    def generate_web_search_prompt(self, ticker: str, date: dt.date | str) -> str:
        """웹 검색용 프롬프트 생성"""
        ticker = ticker.upper()
        prompt = f"""
        Today is {date} and you are an AI assistant for stock analysis.
        You are a sell-side equity-research assistant with real-time web and market-data access.
        
        Find the latest news, press releases, SEC filings, analyst reports, and market chatter for {ticker}.
        
        TASK:
        1. Search for company-specific news, press releases, SEC filings (8-K, 6-K) from last 7 days
        2. Look for sell-side research notes, rating changes, price target updates from last 7 days
        3. Find market chatter: unusual options activity, block trades, rumors from last 3 days
        4. Classify each item as: "+" (Bullish), "−" (Bearish), or "0" (Neutral)
        5. Get latest 30 trading days of price & volume for {ticker}
        6. Label short-term price state: Uptrend / Downtrend / Range-bound
        
        Return structured data with:
        - issued_YYYYMMDD: str (yyyymmdd)
        - headline: str
        - summary: str
        - full_description: str (with reference links)
        - recommendation: Literal["Buy", "Hold", "Sell"]
        """
        return prompt

    def generate_us_market_prompt(self, date: str) -> str:
        """미국 시장 분석용 프롬프트 생성"""
        prompt = f"""
        Today is {date} and you are analyzing U.S. market catalysts.
        
        TASK:
        1. Search for the most important U.S. market catalysts
        2. Find economic releases (CPI, jobs, FOMC, etc.) around {date}
        3. Identify headlines impacting market sentiment
        4. Note movements in major indexes (S&P 500, NASDAQ, Dow) and sectors
        5. Provide 3-5 concise bullet points summarizing findings
        
        Return structured data format:
        - issued_YYYYMMDD: str (yyyymmdd)
        - headline: str
        - summary: str
        - full_description: str (with reference links)
        - recommendation: Literal["Buy", "Hold", "Sell"]
        """
        return prompt

    def get_web_search_summary(
        self,
        date: dt.date,
        type: Literal["ticker", "market"],
        ticker: Optional[str] = "",
    ):
        """웹 검색 결과 요약 조회"""
        start_date = (date - dt.timedelta(days=1)).strftime("%Y-%m-%d")
        end_date = (date + dt.timedelta(days=2)).strftime("%Y-%m-%d")

        results = self.web_search_repository.get_search_results(
            result_type=type,
            ticker=ticker,
            start_date=start_date,
            end_date=end_date,
        )

        return results

    def get_ticker_news_by_recommendation(
        self, recommendation: str, limit: int, date: Optional[dt.date] = None
    ) -> list[dict]:
        """추천 등급별 티커 뉴스 조회"""
        ticker_counts = self.web_search_repository.get_ticker_counts_by_recommendation(
            recommendation=recommendation,
            limit=limit,
            date=date,
        )

        result = []
        for ticker, _ in ticker_counts:
            items = self.web_search_repository.get_search_results(
                result_type="ticker",
                ticker=ticker,
            )

            result.append(
                {
                    "ticker": ticker,
                    "news": [
                        {
                            "date": item.date_yyyymmdd,
                            "headline": item.headline,
                            "summary": item.summary,
                            "detail_description": item.detail_description,
                            "recommendation": item.recommendation,
                        }
                        for item in items
                    ],
                }
            )
        return result
