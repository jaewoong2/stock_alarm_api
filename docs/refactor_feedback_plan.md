# 리팩터링 피드백 및 계획 (초안)

## 범위
- 목표: 라우터 → 서비스 → 레포지토리 흐름의 구조 개선
- 관점: 코드 가독성, 테스트 용이성, 관심사 분리
- 비목표: 기능 추가나 동작 변경

## 현재 설계 스냅샷
- FastAPI 라우터가 서비스를 직접 호출하고, 서비스가 LLM 호출/번역/DB 저장을 모두 담당.
- 레포지토리가 쿼리, 재시도, 데이터 변환까지 섞어 처리.
- async 라우터인데 내부에서 sync I/O를 많이 호출.

## 핵심 피드백 (영향 중심)
1. 서비스가 너무 많은 도메인을 동시에 처리.
   - 예: `myapi/services/web_search_service.py`는 시장예측/마켓분석/ETF/유동성/브레드스 등 다 섞여 있음.
   - 영향: 변경 영향 범위가 커지고 테스트가 어려움.
2. HTTP 계층 책임이 서비스에 섞임.
   - 서비스가 `HTTPException`을 직접 던짐.
   - 영향: 서비스 재사용이 어려워지고 테스트가 복잡해짐.
3. async 경계가 불명확.
   - async 라우터 안에서 sync DB/네트워크 호출이 혼재.
   - 영향: 이벤트 루프 블로킹 가능성.
4. 레포지토리 책임 혼합.
   - 재시도/파싱/스키마 검증까지 포함.
   - 영향: 결합도 상승, 중복 로직 증가.
5. LLM 오케스트레이션이 중복/문자열 기반.
   - 정책 문자열이 흩어져 있고 병합 로직도 분산.
   - 영향: 확장/변경 시 버그 위험.
6. 테스트 부족.
   - `tests/` 비어 있음.
   - 영향: 리팩터링 안정성 낮음.

## 결정 반영
- 점진적 변경 가능 (기존 API 유지하면서 단계적으로 개선).
- async DB는 에러가 잦았던 경험이 있음 → 당장은 sync 유지 + 경계 정리부터 진행.
- 기능별 작은 서비스 선호.
- 문서는 한국어 유지.

## 리팩터링 단계 (권장)

### 1단계: 공통 LLM 파이프라인 분리
- `myapi/llm/` 폴더 신설:
  - `LLMPolicy` enum (AUTO, GEMINI, PERPLEXITY, BOTH, FALLBACK, HYBRID)
  - `LLMRunner` (정책 해석, provenance 기록, 결과 병합)
- 프롬프트는 `myapi/prompts/`로 모으고, 서비스는 프롬프트 + LLMRunner만 사용.

### 2단계: 서비스 분리 (기능별)
- `WebSearchService`를 기능별로 쪼개기:
  - MarketForecastService
  - MarketAnalysisService
  - MahaneyAnalysisService
  - ETFAnalysisService
  - InsiderTrendService
  - LiquidityService
  - MarketBreadthService
- 각 서비스의 의존성은 최소화:
  - Repository 1개
  - LLMRunner
  - TranslateService (필요시)

### 3단계: 레포지토리 단순화
- 레포지토리는 CRUD + 쿼리만.
- 스키마 검증/번역/응답 shaping은 서비스로 이동.
- `AiAnalysisRepository`를 별도 도입:
  - `create_analysis(name, date, payload, metadata)`
  - `get_by_date(name, date)`
  - `get_by_date_and_ticker(name, date, ticker)`

### 4단계: 에러 핸들링 정리
- 서비스에서는 도메인 예외만 발생.
- 라우터에서 도메인 예외 → `HTTPException`으로 매핑.

### 5단계: 테스트 최소 세트 구축
- 프롬프트 빌더 테스트
- LLM 정책/병합 로직 테스트
- 레포지토리 필터 쿼리 테스트

## DB async 관련 제안 (학습 관점)
- 당장은 sync 유지 + 경계 분리로 안정성 확보.
- 나중에 async로 옮길 경우:
  - SQLAlchemy 2.0 async engine + async session
  - 테스트 및 재시도 전략을 먼저 설계
  - 단계적으로 교체 (새로운 repository만 async로 시작)

## 제안 구조 (스케치)
- `myapi/llm/` : `client.py`, `runner.py`, `policy.py`, `merge.py`
- `myapi/prompts/` : `market.py`, `mahaney.py`, `etf.py`, `insider.py`
- `myapi/services/market/` : `forecast_service.py`, `analysis_service.py`, `breadth_service.py`
- `myapi/services/analysis/` : `mahaney_service.py`, `etf_service.py`, `insider_service.py`
- `myapi/repositories/ai_analysis_repository.py`

## 다음 질문
1. 첫 번째로 분리해볼 기능을 선택할까요? (예: 시장예측, ETF, Insider)
2. LLM 파이프라인부터 분리 vs 서비스 분리부터 시작 중 어떤 흐름이 더 좋을까요?
