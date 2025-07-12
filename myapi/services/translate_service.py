import datetime
import re
from typing import List, Any
import boto3
from botocore.exceptions import ClientError
import logging

from myapi.domain.signal.signal_schema import GetSignalRequest, SignalBaseResponse
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

    def _translate_signal(self, signal: SignalBaseResponse) -> SignalBaseResponse:
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

        return translated_signal

    def _translate_json_recursive(self, data: Any) -> Any:
        if isinstance(data, dict):
            return {k: self._translate_json_recursive(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._translate_json_recursive(elem) for elem in data]
        elif isinstance(data, str):
            return self._translate_text_with_aws(data)
        else:
            return data

    def translate_by_date(self, target_date: datetime.date) -> List[SignalBaseResponse]:
        next_target_date = target_date + datetime.timedelta(days=1)
        request = GetSignalRequest(
            start_date=target_date.strftime("%Y-%m-%d"),
            end_date=next_target_date.strftime("%Y-%m-%d"),
        )

        try:
            signals = self.signals_repository.get_signals(request)
        except Exception as e:
            logger.error(f"시그널 조회 중 오류 발생: {e}")
            return []

        translated: List[SignalBaseResponse] = []

        for s in signals:
            try:
                translated.append(self._translate_signal(s))
            except Exception as e:
                logger.error(f"시그널 번역 중 오류 발생 (ticker: {s.ticker}): {e}")
                # 번역 실패 시 원본 시그널 추가
                translated.append(s)

        try:
            # SignalBaseResponse 객체들을 딕셔너리로 변환하여 JSON 직렬화 가능하게 만듦
            translated_dicts = [signal.model_dump(mode="json") for signal in translated]

            self.analysis_repository.create_analysis(
                analysis_date=target_date,
                analysis=translated_dicts,
                name="signals",
            )
        except Exception as e:
            logger.error(f"분석 결과 저장 중 오류 발생: {e}")

        return translated

    def get_translated(
        self, target_date: datetime.date
    ) -> List[SignalBaseResponse] | None:
        try:
            result = self.analysis_repository.get_analysis_by_date(
                target_date, name="signals", schema=None
            )

            if not result or not result.value:
                return None

            return [SignalBaseResponse.model_validate(r) for r in result.value]
        except Exception as e:
            logger.error(f"번역된 시그널 조회 중 오류 발생: {e}")
            return None

    def translate_and_markdown(self, target_date: datetime.date) -> dict:
        existing = self.get_translated(target_date)

        if existing and len(existing) > 0:
            markdown = self._to_markdown(existing)
            return {"signals": existing, "markdown": markdown}

        signals = self.translate_by_date(target_date)

        markdown = self._to_markdown(signals)
        return {"signals": signals, "markdown": markdown}

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
