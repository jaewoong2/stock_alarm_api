from __future__ import annotations

from typing import List

from myapi.domain.ticker.ticker_reference_model import TickerReference
from myapi.domain.ticker.ticker_reference_schema import (
    TickerReferenceLookupResponse,
    TickerReferenceMatch,
)
from myapi.repositories.ticker_reference_repository import (
    TickerReferenceRepository,
)


class TickerReferenceService:
    def __init__(self, repository: TickerReferenceRepository):
        self.repository = repository

    def lookup(self, raw_query: str, limit: int = 10) -> TickerReferenceLookupResponse:
        query = (raw_query or "").strip()
        if not query:
            return TickerReferenceLookupResponse(
                query=query, has_exact_symbol=False, matches=[]
            )

        matches: List[TickerReferenceMatch] = []
        has_exact_symbol = False

        symbol_record = self.repository.find_by_symbol(query)
        if symbol_record:
            has_exact_symbol = True
            matches.append(
                self._to_match(symbol_record, match_type="symbol")
            )

        remaining = max(limit - len(matches), 0)
        if remaining > 0:
            # Prefer symbol-prefix matches before wider name search for speed.
            prefix_candidates = self.repository.search_by_symbol_prefix(
                query, remaining
            )
            matches.extend(
                self._unique_matches(
                    matches,
                    prefix_candidates,
                    match_type="symbol_prefix",
                    limit=remaining,
                )
            )

        remaining = max(limit - len(matches), 0)
        if remaining > 0:
            name_candidates = self.repository.search_by_name(query, remaining)
            matches.extend(
                self._unique_matches(
                    matches,
                    name_candidates,
                    match_type="name",
                    limit=remaining,
                )
            )

        return TickerReferenceLookupResponse(
            query=query,
            has_exact_symbol=has_exact_symbol,
            matches=matches,
        )

    def _unique_matches(
        self,
        existing: List[TickerReferenceMatch],
        candidates: List[TickerReference],
        match_type: str,
        limit: int,
    ) -> List[TickerReferenceMatch]:
        seen_symbols = {match.symbol for match in existing}
        new_matches: List[TickerReferenceMatch] = []

        for candidate in candidates:
            if candidate.symbol in seen_symbols:
                continue
            new_matches.append(self._to_match(candidate, match_type))
            seen_symbols.add(candidate.symbol)
            if len(new_matches) >= limit:
                break

        return new_matches

    @staticmethod
    def _to_match(
        ticker: TickerReference, match_type: str
    ) -> TickerReferenceMatch:
        return TickerReferenceMatch(
            symbol=ticker.symbol,
            name=ticker.name,
            exchange=ticker.exchange,
            market_category=ticker.market_category,
            is_etf=bool(ticker.is_etf),
            match_type=match_type,  # type: ignore[arg-type]
        )
