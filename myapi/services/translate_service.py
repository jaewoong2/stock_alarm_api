import datetime
import json
from typing import List
from google.cloud import translate_v3 as translate
import os

from myapi.domain.signal.signal_schema import GetSignalRequest, SignalBaseResponse
from myapi.repositories.signals_repository import SignalsRepository
from myapi.repositories.web_search_repository import WebSearchResultRepository


class TranslateService:
    def __init__(
        self,
        signals_repository: SignalsRepository,
        analysis_repository: WebSearchResultRepository,
    ) -> None:
        self.signals_repository = signals_repository
        self.analysis_repository = analysis_repository
        self.project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID")
        self.translate_client = translate.TranslationServiceClient()
        self.parent = f"projects/{self.project_id}"

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
                lines.append(f"- 차트 패턴: {s.chart_pattern}")
            lines.append("")
        return "\n".join(lines)

    def _translate_text_with_google(
        self, text: str, target_language: str = "ko"
    ) -> str:
        if not text:
            return text
        try:
            response = self.translate_client.translate_text(
                request={
                    "parent": self.parent,
                    "contents": [text],
                    "mime_type": "text/plain",
                    "source_language_code": "en",
                    "target_language_code": target_language,
                }
            )
            return response.translations[0].translated_text
        except Exception as e:
            print(f"Error translating text with Google Cloud Translation: {e}")
            return text

    def _translate_signal(self, signal: SignalBaseResponse) -> SignalBaseResponse:
        translated_signal = signal.model_copy(deep=True)

        if translated_signal.result_description:
            translated_signal.result_description = self._translate_text_with_google(
                translated_signal.result_description
            )
        if translated_signal.report_summary:
            translated_signal.report_summary = self._translate_text_with_google(
                translated_signal.report_summary
            )
        if translated_signal.senario:
            translated_signal.senario = self._translate_text_with_google(
                translated_signal.senario
            )
        if translated_signal.good_things:
            translated_signal.good_things = self._translate_text_with_google(
                translated_signal.good_things
            )
        if translated_signal.bad_things:
            translated_signal.bad_things = self._translate_text_with_google(
                translated_signal.bad_things
            )
        if (
            translated_signal.chart_pattern
            and translated_signal.chart_pattern.description
        ):
            translated_signal.chart_pattern.description = (
                self._translate_text_with_google(
                    translated_signal.chart_pattern.description
                )
            )

        return translated_signal

    def _translate_json_recursive(self, data: any, target_language: str) -> any:
        if isinstance(data, dict):
            return {
                k: self._translate_json_recursive(v, target_language)
                for k, v in data.items()
            }
        elif isinstance(data, list):
            return [
                self._translate_json_recursive(elem, target_language) for elem in data
            ]
        elif isinstance(data, str):
            return self._translate_text_with_google(data, target_language)
        else:
            return data

    def translate_by_date(self, target_date: datetime.date) -> List[SignalBaseResponse]:
        next_target_date = target_date + datetime.timedelta(days=1)
        request = GetSignalRequest(
            start_date=target_date.strftime("%Y-%m-%d"),
            end_date=next_target_date.strftime("%Y-%m-%d"),
        )

        signals = self.signals_repository.get_signals(request)

        translated: List[SignalBaseResponse] = []

        for s in signals:
            translated.append(self._translate_signal(s))

        self.analysis_repository.create_analysis(
            analysis_date=target_date,
            analysis=translated,
            name="signals",
        )

        return translated

    def get_translated(
        self, target_date: datetime.date
    ) -> List[SignalBaseResponse] | None:
        result = self.analysis_repository.get_analysis_by_date(
            target_date, name="signals", schema=None
        )

        if not result:
            return None

        return [SignalBaseResponse.model_validate(r) for r in result.value]

    def translate_and_markdown(self, target_date: datetime.date) -> dict:
        existing = self.get_translated(target_date)

        if existing and len(existing) > 0:
            markdown = self._to_markdown(existing)

            return {"signals": existing, "markdown": markdown}

        signals = self.translate_by_date(target_date)
        markdown = self._to_markdown(signals)
        return {"signals": signals, "markdown": markdown}

    def translate_text(self, text: str, target_language: str = "ko") -> str:
        """
        주어진 텍스트를 대상 언어로 번역합니다.
        """
        return self._translate_text_with_google(text, target_language)

    def translate_json(self, json_data: dict, target_language: str = "ko") -> dict:
        """
        주어진 JSON 데이터를 대상 언어로 번역합니다.
        """
        return self._translate_json_recursive(json_data, target_language)
