import datetime
import json
import re
from typing import List, Any, Optional
import boto3
from botocore.exceptions import ClientError
import logging

from myapi.domain.signal.signal_schema import (
    GetSignalRequest,
    SignalBaseResponse,
    SignalValueObject,
)
from myapi.repositories.signals_repository import SignalsRepository
from myapi.repositories.web_search_repository import WebSearchResultRepository
from myapi.services.ai_service import AIService
from myapi.utils.config import Settings

# 로깅 설정
logger = logging.getLogger(__name__)


class TranslateService:
    def __init__(
        self,
        signals_repository: SignalsRepository,
        analysis_repository: WebSearchResultRepository,
        ai_service: AIService,  # AIService 인스턴스
        settings: Settings,
    ) -> None:
        self.signals_repository = signals_repository
        self.analysis_repository = analysis_repository
        self.ai_service = ai_service

        # AWS Translate 클라이언트 초기화
        try:
            self.translate_client = boto3.client(
                "translate",
                region_name="ap-northeast-2",  # 또는 원하는 리전
                aws_access_key_id=settings.AWS_S3_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_S3_SECRET_ACCESS_KEY,
            )
        except Exception as e:
            logger.warning(f"AWS Translate 클라이언트 초기화 실패: {e}")
            self.translate_client = None

    def _to_markdown(self, signals: List[SignalBaseResponse]) -> str:
        lines = []
        for s in signals:
            lines.append(f"### {s.ticker} ({s.action})")
            lines.append(f"- 진입 가격: {s.entry_price}")
            if s.probability:
                lines.append(f"- 상승 확률: {s.probability}")
            if s.result_description:
                lines.append(f"- 설명: {s.result_description}")
            if s.report_summary:
                lines.append(f"- 요약: {s.report_summary}")
            if s.senario:
                lines.append(f"- 시나리오: {s.senario}")
            if s.good_things:
                lines.append(f"- 좋은 점: {s.good_things}")
            if s.bad_things:
                lines.append(f"- 나쁜 점: {s.bad_things}")
            if s.chart_pattern:
                lines.append(
                    f"- 차트 패턴: {s.chart_pattern.name if hasattr(s.chart_pattern, 'name') else str(s.chart_pattern)}"
                )
                if (
                    hasattr(s.chart_pattern, "description")
                    and s.chart_pattern.description
                ):
                    lines.append(f"  - 설명: {s.chart_pattern.description}")
            lines.append("")
        return "\n".join(lines)

    def _extract_translation(self, response: str) -> str:
        """
        AI 응답에서 순수한 번역 결과만 추출합니다.
        """
        if not response or not response.strip():
            return response

        # 한국어 문장만 추출하는 정규식 패턴
        # 한글, 숫자, 기본 문장부호만 포함하는 패턴
        korean_pattern = (
            r"[가-힣0-9\s\.\,\!\?\:\;\-\(\)\[\]\{\}\'\"\/\%\$\&\*\+\=\<\>\~\`\|\\]+"
        )

        lines = response.split("\n")

        # 첫 번째로 한국어가 포함된 의미있는 문장 찾기
        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 따옴표나 인용구 안의 내용 추출
            quote_matches = re.findall(r"['\"]([^'\"]*)['\"]", line)
            for match in quote_matches:
                if re.search(r"[가-힣]", match) and len(match.strip()) > 1:
                    return match.strip()

            # 한국어가 포함된 문장 찾기 (설명 제외)
            if (
                re.search(r"[가-힣]", line)
                and len(line) > 5
                and not line.lower().startswith(
                    ("here", "to translate", "the translation", "breakdown")
                )
            ):

                # 문장 끝의 마침표나 따옴표 정리
                cleaned = re.sub(r"^['\"]|['\"]$", "", line)
                cleaned = cleaned.strip()
                if cleaned and len(cleaned) > 1:
                    return cleaned

        # 마지막 수단: 전체 응답에서 가장 긴 한국어 문장 추출
        korean_sentences = re.findall(korean_pattern, response)
        if korean_sentences:
            longest = max(korean_sentences, key=len)
            return longest.strip()

        return response.strip()

    def _translate_text_with_aws(self, text: str) -> str:
        if not text or not text.strip():
            return text

        # AWS Translate 클라이언트가 없으면 원본 텍스트 반환
        if not self.translate_client:
            logger.warning(
                "AWS Translate 클라이언트가 초기화되지 않음. 원본 텍스트 반환."
            )
            return text

        try:
            # 더 구체적이고 명확한 번역 프롬프트
            prompt = f"""
            ╭─ TRANSLATION TASK
            │ • Translate the following English text to natural Korean
            │ • Context: Financial/Investment analysis content
            │ • Target audience: Korean investors and traders
            │ • Maintain professional tone and accuracy
            ╰─ END TASK

            ╭─ TRANSLATION RULES
            │ • Keep financial terms and ticker symbols unchanged (e.g., S&P 500, NASDAQ, USD)
            │ • Use formal Korean language (존댓말)
            │ • Preserve numbers, percentages, and dates exactly as written
            │ • Do NOT add explanations, comments, or additional context
            │ • Do NOT include phrases like "번역:", "한국어:", "Korean translation:"
            │ • Output ONLY the translated Korean text
            │ • Do Not Summarize or simplify the content (keep all details) !! Very Important !!
            ╰─ END RULES

            ╭─ INPUT TEXT
            │ {text}
            ╰─ END INPUT

            Korean Translation:
            """

            response = self.ai_service.nova_lite(prompt)

            # 응답에서 순수한 번역 결과만 추출
            translated = self._extract_translation(response)

            # 로깅으로 번역 과정 확인
            logger.info(f"원문: {text[:50]}...")
            logger.info(f"AI 응답: {response[:100]}...")
            logger.info(f"추출된 번역: {translated[:50]}...")

            return response

        except ClientError as e:
            logger.error(f"AWS LLM 오류: {e}")
            return text
        except Exception as e:
            logger.error(f"텍스트 번역 중 오류 발생: {e}")
            return text

    def _translate_signal(self, signal: SignalValueObject) -> SignalValueObject:
        translated_signal = signal.model_copy(deep=True)

        if translated_signal.result_description:
            translated_signal.result_description = self._translate_text_with_aws(
                translated_signal.result_description
            )
        if translated_signal.report_summary:
            translated_signal.report_summary = self._translate_text_with_aws(
                translated_signal.report_summary
            )
        if translated_signal.senario:
            translated_signal.senario = self._translate_text_with_aws(
                translated_signal.senario
            )
        if translated_signal.good_things:
            translated_signal.good_things = self._translate_text_with_aws(
                translated_signal.good_things
            )
        if translated_signal.bad_things:
            translated_signal.bad_things = self._translate_text_with_aws(
                translated_signal.bad_things
            )

        # chart_pattern 안전하게 처리
        if translated_signal.chart_pattern:
            if (
                hasattr(translated_signal.chart_pattern, "description")
                and translated_signal.chart_pattern.description
            ):
                translated_signal.chart_pattern.description = (
                    self._translate_text_with_aws(
                        translated_signal.chart_pattern.description
                    )
                )

        return SignalValueObject(
            **translated_signal.model_dump(exclude_unset=True),
        )

    def _translate_json_recursive(self, data: Any) -> Any:
        if isinstance(data, dict):
            return {k: self._translate_json_recursive(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._translate_json_recursive(elem) for elem in data]
        elif isinstance(data, str):
            return self._translate_text_with_aws(data)
        else:
            return data

    def _save_translated_signals(
        self,
        translated_signals: List[SignalValueObject],
        target_date: datetime.date,
    ) -> None:
        """
        번역된 시그널들을 signals 테이블에 개별적으로 저장합니다.
        기존에 동일한 ticker + timestamp 조합이 있으면 덮어쓰기합니다.

        Args:
            translated_signals: 번역된 시그널 리스트
        """
        try:
            # SignalBaseResponse를 SignalValueObject로 변환
            for signal in translated_signals:
                # datetime 객체를 문자열로 변환하여 JSON 직렬화 가능하게 만듦
                signal_str = signal.model_dump_json(exclude={"id"})
                signal_dict = json.loads(signal_str)

                self.analysis_repository.create_analysis(
                    name="signals",
                    analysis=signal_dict,
                    analysis_date=target_date,
                )

            logger.info(f"번역된 시그널 {len(translated_signals)}개 개별 저장 완료")

        except Exception as e:
            logger.error(f"번역된 시그널 개별 저장 중 오류 발생: {e}")
            raise

    def translate_by_date(
        self, target_date: datetime.date, tickers: Optional[List[str]] = None
    ) -> List[SignalValueObject]:
        """
        특정 날짜의 모든 시그널을 번역하여 반환합니다.
        이미 번역된 시그널이 있으면 건너뛰고, 새로운 시그널만 번역합니다.
        """
        logger.info(f"{target_date} 날짜의 시그널 번역 시작 (티커: {tickers})")

        # 1. 먼저 이미 번역된 시그널들이 있는지 확인
        existing_translated = self.get_translated(target_date, tickers)
        if existing_translated:
            logger.info(f"이미 번역된 시그널 {len(existing_translated)}개 발견")
            return existing_translated

        # 2. 원본 시그널들을 페이지네이션으로 조회
        next_target_date = target_date + datetime.timedelta(days=1)
        all_translated_signals: List[SignalValueObject] = []
        processed_tickers = set()  # 중복 처리 방지

        request = GetSignalRequest(
            start_date=target_date.strftime("%Y-%m-%d"),
            end_date=next_target_date.strftime("%Y-%m-%d"),
        )

        try:
            signals = self.signals_repository.get_signals(request)

            # 3. 각 시그널에 대해 번역 처리
            for s in signals:
                # 특정 티커만 처리하도록 필터링
                if tickers and s.ticker not in tickers:
                    logger.debug(f"티커 {s.ticker} 필터링됨, 건너뛰기")
                    continue

                # 이미 처리한 티커는 건너뛰기
                if s.ticker in processed_tickers:
                    logger.debug(f"티커 {s.ticker} 이미 처리됨, 건너뛰기")
                    continue

                processed_tickers.add(s.ticker)

                # 개별 티커의 번역된 시그널이 이미 있는지 확인
                existing_ticker_signal = self.get_translated_by_ticker(
                    target_date, s.ticker
                )
                if existing_ticker_signal:
                    logger.debug(f"티커 {s.ticker}의 번역된 시그널이 이미 존재함")
                    all_translated_signals.append(existing_ticker_signal)
                    continue

                # 4. 번역 수행
                try:
                    logger.debug(f"티커 {s.ticker} 번역 시작")
                    translated_signal = self._translate_signal(s)
                    all_translated_signals.append(translated_signal)

                    # 5. 개별 저장 (즉시 저장으로 중복 방지)
                    try:
                        self._save_translated_signals([translated_signal], target_date)
                        logger.debug(f"티커 {s.ticker} 번역 및 저장 완료")
                    except Exception as save_error:
                        logger.error(f"티커 {s.ticker} 저장 중 오류: {save_error}")

                except Exception as translate_error:
                    logger.error(f"티커 {s.ticker} 번역 중 오류: {translate_error}")
                    # 번역 실패 시 원본 시그널을 SignalValueObject로 변환하여 저장
                    signal_vo = SignalValueObject(**s.model_dump(exclude_unset=True))
                    all_translated_signals.append(signal_vo)
                    try:
                        self._save_translated_signals([signal_vo], target_date)
                        logger.debug(f"티커 {s.ticker} 원본 시그널 저장 완료")
                    except Exception as save_error:
                        logger.error(f"티커 {s.ticker} 원본 저장 중 오류: {save_error}")

        except Exception as e:
            logger.error(f"{target_date} 날짜 시그널 조회 중 오류 발생: {e}")
            raise

        # 7. 최종 결과 반환
        logger.info(
            f"{target_date} 날짜 번역 완료: 총 {len(all_translated_signals)}개 시그널 처리됨"
        )
        return all_translated_signals

    def get_translated(
        self,
        target_date: datetime.date,
        tickers: Optional[List[str]] = None,
        models: Optional[str] = None,
    ) -> List[SignalValueObject]:
        try:
            response = self.analysis_repository.get_all_analyses(
                target_date=target_date,
                name="signals",
                item_schema=SignalValueObject,
                tickers=tickers,
                models=models,
            )

            results = []
            for r in response:
                if r.value:
                    try:
                        # r.value가 이미 SignalBaseResponse 인스턴스인지 확인
                        if isinstance(r.value, SignalValueObject):
                            results.append(r.value)
                        else:
                            # dict 형태라면 기본값으로 보완한 후 model_validate로 변환
                            signal_data = r.value if isinstance(r.value, dict) else {}

                            # 필수 필드들의 기본값 설정
                            defaults = {
                                "id": signal_data.get("id", 0),
                                "ticker": signal_data.get("ticker", ""),
                                "entry_price": signal_data.get("entry_price", 0.0),
                                "action": signal_data.get("action", "hold"),
                                "timestamp": signal_data.get(
                                    "timestamp",
                                    datetime.datetime.now(datetime.timezone.utc),
                                ),
                                "stop_loss": signal_data.get("stop_loss"),
                                "take_profit": signal_data.get("take_profit"),
                                "probability": signal_data.get("probability"),
                                "result_description": signal_data.get(
                                    "result_description"
                                ),
                                "report_summary": signal_data.get("report_summary"),
                                "strategy": signal_data.get("strategy"),
                                "close_price": signal_data.get("close_price"),
                                "ai_model": signal_data.get("ai_model", "OPENAI"),
                                "senario": signal_data.get("senario"),
                                "good_things": signal_data.get("good_things"),
                                "bad_things": signal_data.get("bad_things"),
                                "chart_pattern": signal_data.get("chart_pattern"),
                            }

                            signal = SignalBaseResponse.model_validate(defaults)
                            results.append(signal)
                    except Exception as validation_error:
                        logger.warning(
                            f"시그널 데이터 변환 실패: {validation_error}, 기본값으로 빈 시그널 생성"
                        )
                        # 최소한의 기본값으로 시그널 생성
                        try:
                            fallback_signal = SignalBaseResponse(
                                id=0,
                                ticker="UNKNOWN",
                                entry_price=0.0,
                                action="hold",
                                timestamp=datetime.datetime.now(datetime.timezone.utc),
                            )
                            results.append(fallback_signal)
                        except Exception:
                            # 완전히 실패한 경우에만 건너뛰기
                            continue

            # 특정 티커만 필터링
            if tickers:
                results = [r for r in results if r.ticker in tickers]

            return results
        except Exception as e:
            logger.error(f"번역된 시그널 조회 중 오류 발생: {e}")
            return []

    def get_translated_by_ticker(
        self,
        target_date: datetime.date,
        ticker: str,
        strategy_filter: str = "ALL",
        ai_model: str = "OPENAI",
    ) -> SignalValueObject | None:
        """
        특정 날짜와 티커의 번역된 시그널을 가져옵니다.

        Args:
            target_date: 조회할 날짜
            ticker: 조회할 티커 심볼

        Returns:
            해당 티커의 번역된 시그널 리스트
        """
        response = self.analysis_repository.get_analyses_by_ticker(
            ticker=ticker,
            target_date=target_date,
            name="signals",
            item_schema=SignalValueObject,
            strategy_filter=strategy_filter,
            ai_model=ai_model,
        )

        value = response.value if response else None
        # r.value가 이미 SignalBaseResponse 인스턴스인지 확인
        if isinstance(value, SignalValueObject):
            return value  # 이미 변환된 인스턴스라면 리스트로 감싸서 반환

        if value is not None:
            # dict 형태라면 기본값으로 보완한 후 model_validate로 변환
            signal_data = value if isinstance(value, dict) else {}

            # 필수 필드들의 기본값 설정
            defaults = {
                "id": signal_data.get("id", 0),
                "ticker": signal_data.get(
                    "ticker", ticker
                ),  # 파라미터로 받은 티커 사용
                "entry_price": signal_data.get("entry_price", 0.0),
                "action": signal_data.get("action", "hold"),
                "timestamp": signal_data.get(
                    "timestamp", datetime.datetime.now(datetime.timezone.utc)
                ),
                "stop_loss": signal_data.get("stop_loss"),
                "take_profit": signal_data.get("take_profit"),
                "probability": signal_data.get("probability"),
                "result_description": signal_data.get("result_description"),
                "report_summary": signal_data.get("report_summary"),
                "strategy": signal_data.get("strategy"),
                "close_price": signal_data.get("close_price"),
                "ai_model": signal_data.get("ai_model", "OPENAI"),
                "senario": signal_data.get("senario"),
                "good_things": signal_data.get("good_things"),
                "bad_things": signal_data.get("bad_things"),
                "chart_pattern": signal_data.get("chart_pattern"),
            }

            signal = SignalValueObject.model_validate(defaults)
            return signal  # 변환된 인스턴스 반환

        return None

    def get_translated_signals(
        self, target_date: datetime.date, tickers: Optional[List[str]] = None
    ) -> dict:
        """
        특정 날짜의 번역된 시그널을 가져와 마크다운 형식으로 변환합니다.
        """
        existing = self.get_translated(target_date, tickers)

        if existing and len(existing) > 0:
            return {"signals": existing}

        # 번역된 시그널이 없으면 빈 결과 반환
        logger.info(f"{target_date} 날짜의 번역된 시그널이 없습니다.")
        return {"signals": []}

    def translate_and_markdown(
        self,
        target_date: datetime.date,
        tickers: Optional[List[str]] = None,
        models: Optional[str] = None,
    ) -> dict:
        existing = self.get_translated(target_date, tickers, models=models)

        if existing and len(existing) > 0:
            return {"signals": existing}

        signals = self.translate_by_date(target_date, tickers)

        return {"signals": signals}

    def translate_text(self, text: str) -> str:
        """
        주어진 텍스트를 대상 언어로 번역합니다.
        """
        return self._translate_text_with_aws(text)

    def translate_json(self, json_data: dict) -> dict:
        """
        주어진 JSON 데이터를 대상 언어로 번역합니다.
        """
        try:
            return self._translate_json_recursive(json_data)
        except Exception as e:
            logger.error(f"JSON 번역 중 오류 발생: {e}")
            return json_data
