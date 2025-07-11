from __future__ import annotations

import datetime
import json
from typing import List

from myapi.domain.signal.signal_schema import GetSignalRequest, SignalBaseResponse
from myapi.repositories.signals_repository import SignalsRepository
from myapi.repositories.web_search_repository import WebSearchResultRepository
from myapi.services.ai_service import AIService


class TranslateService:
    def __init__(
        self,
        signals_repository: SignalsRepository,
        analysis_repository: WebSearchResultRepository,
        ai_service: AIService,
    ) -> None:
        self.signals_repository = signals_repository
        self.analysis_repository = analysis_repository
        self.ai_service = ai_service

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

    def _translate_signal(self, signal: SignalBaseResponse) -> SignalBaseResponse:
        prompt = (
            "Translate the following JSON to Korean. Keep the JSON format and do not change keys.\n"\
            + json.dumps(signal.model_dump(), ensure_ascii=False)
        )
        result = self.ai_service.nova_lite_completion(prompt=prompt, schema=SignalBaseResponse)
        return result if isinstance(result, SignalBaseResponse) else signal

    def translate_by_date(self, target_date: datetime.date) -> List[SignalBaseResponse]:
        request = GetSignalRequest(
            tickers=None,
            start_date=target_date.strftime("%Y-%m-%d"),
            end_date=target_date.strftime("%Y-%m-%d"),
            actions=None,
        )
        signals = self.signals_repository.get_signals(request)

        translated: List[SignalBaseResponse] = []
        for s in signals:
            translated.append(self._translate_signal(s))

        self.analysis_repository.create_analysis(
            analysis_date=target_date,
            analysis=[t.model_dump() for t in translated],
            name="signals",
        )
        return translated

    def get_translated(self, target_date: datetime.date) -> List[SignalBaseResponse] | None:
        result = self.analysis_repository.get_analysis_by_date(
            target_date, name="signals", schema=None
        )
        if not result:
            return None
        return [SignalBaseResponse.model_validate(r) for r in result.value]

    def translate_and_markdown(self, target_date: datetime.date) -> dict:
        existing = self.get_translated(target_date)
        if existing:
            markdown = self._to_markdown(existing)
            return {"signals": existing, "markdown": markdown}

        signals = self.translate_by_date(target_date)
        markdown = self._to_markdown(signals)
        return {"signals": signals, "markdown": markdown}

