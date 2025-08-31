# 주간 AI 검색을 통한 예측/리서치 API 설계서

- 목적: 주간 단위로 웹검색+LLM을 활용해 시장/섹터/ETF/종목 관련 인사이트를 생성·저장·조회하는 일련의 API를 정의한다.
- 범위: `news_router` 중심. 생성(POST) 시 인증 필요, 조회(GET) 공개. 서비스 레이어는 `WebSearchService` 중심으로 작성한다.

## 아키텍처 개요

- Router: `myapi/routers/news_router.py` 에 엔드포인트 정의 (FastAPI + DI).
- Service: `myapi/services/web_search_service.py` 에 프롬프트·LLM 호출·번역·저장 로직 구현.
- Repository: `myapi/repositories/web_search_repository.py` 를 통해 `ai_analysis` 등 저장/조회.
- Schema: `myapi/domain/news/news_schema.py` 에 요청/응답 모델 정의.
- DI: `myapi/containers.py` 의 `Container.services.websearch_service` 주입.
- 공통 유틸: 날짜 검증 `validate_date`, 인증 `verify_bearer_token`, 번역 `TranslateService`.

## 공통 구현 규칙

- POST(생성) 엔드포인트는 `dependencies=[Depends(verify_bearer_token)]` 적용.
- 날짜 파라미터는 `dt.date` + `validate_date` 사용. 기본값은 `dt.date.today()`.
- Service는 생성 시 LLM 호출 → 스키마 검증 → 번역(옵션) → `web_search_repository.create_analysis(...)` 저장.
- 저장 규칙: `ai_analysis.name` 에 기능별 식별자 사용. JSON 내부에 필터를 위한 `ticker` 키 포함 권장.
- 조회는 Repository의 `get_all_analyses(...)`, `get_analysis_by_date(...)` 패턴 사용. 필요 시 정렬/필터 스펙 부여.
- 배치 실행은 `myapi/routers/batch_router.py` 패턴 참고하여 SQS Job으로 큐잉 가능.

## LLM 이중화 전략(gemini + perplexity)

- 목표: 동일 분석에서 `gemini_search_grounding`과 `perplexity_completion`을 활용해 신뢰성·복원력·품질을 향상.
- 공통 파라미터: `llm_policy`
  - `GEMINI`: Gemini만 사용
  - `PERPLEXITY`: Perplexity만 사용
  - `BOTH`: 두 모델 모두 호출하고 각각 저장(병렬 저장)
  - `FALLBACK`: 1차 Perplexity → 실패 시 Gemini(또는 반대)로 폴백
  - `HYBRID`: 두 결과를 합성하여 하나의 결과 생성(명확한 병합 규칙 필요)
  - `AUTO`: 서비스 기본값(권장 폴백 순서 적용)
- 저장(주간 배치 기준)
  - 실행일 = 저장일(`analysis_date`)
  - `BOTH`의 경우 옵션
    - A) 동일 `name`으로 저장하되 value.ai_model로 구분
    - B) `name`을 모델별로 분리: `<analysis>_gemini`, `<analysis>_perplexity`
  - `HYBRID`는 `name="<analysis>_hybrid"`로 저장하고 provenance에 원천 모델별 요약 포함
- 표준 메타데이터(저장 JSON 공통 필드)
  - `ai_model`: `GEMINI|PERPLEXITY|HYBRID`
  - `llm_policy`: 호출 정책
  - `prompt_hash`: 프롬프트 해시(SHA-256 축약)
  - `provenance`: `[ { model, prompt_hash, used, notes } ]`
  - `window`: `YYYY-MM-DD~YYYY-MM-DD` (사용 데이터 기간)

## 이미 구현된 레퍼런스: ETF 포트폴리오 변동 분석

- Router: `POST /news/etf/portfolio` → `news_router.create_etf_portfolio_analysis`
  - 내부에서 `websearch_service.create_etf_analysis(etf_tickers, target_date)` 호출.
  - 요청 스키마: `ETFAnalysisRequest { etf_tickers: List[str], target_date?: date }`
  - 응답 스키마: `ETFAnalysisResponse { etf_portfolios: List[ETFPortfolioData] }`
- Router: `GET /news/etf/portfolio` → `news_router.get_etf_portfolio_analysis`
  - 쿼리: `target_date?: date, etf_tickers?: comma-separated`
  - 응답: `ETFAnalysisGetResponse { etf_analyses, total_count, ... }`
- Service: `WebSearchService.create_etf_analysis`
  - 프롬프트: `generate_etf_portfolio_prompt`
  - LLM: `ai_service.perplexity_completion(..., schema=ETFAnalysisResponse)`
  - 번역: `translate_service.translate_schema` (실패 시 워닝 로그)
  - 저장: `name="etf_portfolio_analysis"`, JSON 내부 `ticker` 키에 `etf_ticker` 상향 저장
- Repository: 조회 시 `get_all_analyses(name="etf_portfolio_analysis", item_schema=ETFPortfolioData, tickers=[...])` 사용

#TODO: 위 레퍼런스 패턴을 신규 주간 분석 전반에 복제 적용할 것

## 신규 1) 내부자 매수/매도 동향 분석

- 목적: 최근 1주 내 SEC Form 4 / 신뢰 가능한 데이터소스 기반 내부자 거래 동향 요약과 티커별 시그널화.
- 제안 엔드포인트
  - GET `GET /news/insider-trend`
    - 쿼리: `target_date?: date`(기본 오늘), `tickers?: comma-separated`, `action?: BUY|SELL`, `limit?: int`, `sort_by?: date|value`, `sort_order?: asc|desc`
    - 응답: `InsiderTrendGetResponse`(신규 정의)
  - POST `POST /news/insider-trend`
    - 바디: `InsiderTrendCreateRequest { tickers?: List[str], target_date?: date, llm_policy?: 'AUTO'|'GEMINI'|'PERPLEXITY'|'BOTH'|'FALLBACK'|'HYBRID' }`
    - 동작: `WebSearchService.create_insider_trend(..., llm_policy)` 호출 후 저장
- Service 설계
  - 함수: `WebSearchService.create_insider_trend(tickers: list[str]|None, target_date: date)`
  - 프롬프트: “최근 7일 내부자 거래(SEC Form 4 등)에서 BUY/SELL, 수량·금액, 경영진 직책, 관련 뉴스와의 연관성, 신호 해석”을 포함한 JSON 스키마 요구
  - LLM: `run_llm(policy, prompt, schema=InsiderTrendResponse)` 사용(Gemini/Perplexity 이중화)
  - 번역: `translate_service.translate_schema` (HYBRID 시 합성 결과 번역)
  - 저장: `name="insider_trend_weekly"`; 각 항목에 `ticker` 필드 포함, value.ai_model/llm_policy/prompt_hash 기록
- Schema 설계
  - `InsiderTradeItem { ticker, insider_role, action: BUY|SELL, shares, est_value, rationale, sources[] }`
  - `InsiderTrendResponse { items: List[InsiderTradeItem], window: "YYYY-MM-DD~YYYY-MM-DD" }`
  - 조회용: `InsiderTrendGetRequest/Response` (정렬·필터·페이징 옵션 포함)
- Repository
  - 저장: `create_analysis(date=target_date, name="insider_trend_weekly", analysis=item)`
  - 조회: `get_all_analyses(name="insider_trend_weekly", tickers=[...])`
- Router 규칙
  - POST 에 `verify_bearer_token` 적용
  - 날짜 `validate_date`, 티커 문자열 파싱(대문자 트림)

#TODO: Schema/Service/Router/Repository 저장키(name) 확정 및 구현

## 신규 2) 애널리스트 목표가 상향/하향 종목 분석

- 목적: 최근 1주 Analyst PT 상향/하향/커버리지 개시·중단 종목과 근거 요약.
- 엔드포인트
  - GET `GET /news/analyst-price-targets`
    - 쿼리: `target_date?: date, tickers?: comma-separated, action?: UP|DOWN|INIT|DROP, limit?, sort_by?: impact|date`
    - 응답: `AnalystPTGetResponse`
  - POST `POST /news/analyst-price-targets`
    - 바디: `AnalystPTCreateRequest { tickers?: List[str], target_date?: date, llm_policy?: ... }`
    - 동작: `WebSearchService.create_analyst_price_targets(..., llm_policy)`
- Service 설계
  - 프롬프트: 주요 하우스·애널리스트 변동 근거, 이전/신규 PT, 컨센서스, 소스 포함 JSON 스키마
  - 저장: `name="analyst_price_targets_weekly"`, 항목별 `ticker` 포함, ai_model/llm_policy 메타 포함

#TODO: 스키마 정의, 정렬 기준(impact 산식), 예시 응답 추가

## 신규 3) 이번주 ETF 거래량/자금 유입 순위 + 섹터별 자금 흐름

- 목적: 1주 집계 기준 ETF 유입/유출 상위, 거래량 급증, 섹터 ETF 자금 흐름 파악.
- 엔드포인트
  - GET `GET /news/etf/flows`
    - 쿼리: `target_date?: date, provider?: string(소스), sector_only?: bool`
    - 응답: `ETFWeeklyFlowGetResponse`
  - POST `POST /news/etf/flows`
    - 바디: `ETFWeeklyFlowCreateRequest { universe?: List[str], target_date?: date, llm_policy?: ... }`
    - 동작: `WebSearchService.create_etf_weekly_flows(..., llm_policy)`
- Service 설계
  - 프롬프트: “지난 5영업일 기준 순유입/순유출 상위 20, 거래량 급변 상위, 섹터 묶음(테마) 요약” JSON 스키마
  - 저장: `name="etf_flows_weekly"`

#TODO: 섹터 매핑 룰(티커→섹터), 외부 소스 가이드, 스키마 확정

## 신규 4) 유동성 지표: 미국 M2, 역레포(RRP)

- 목적: 최근 4~8주 M2·역레포 추이와 시장 영향 요약.
- 엔드포인트
  - GET `GET /news/liquidity`
    - 응답: `LiquidityGetResponse { m2_series, rrp_series, commentary }`
  - POST `POST /news/liquidity`
    - 동작: `WebSearchService.create_liquidity_weekly(...)`
- Service 설계
  - 데이터 소스 우선: FRED/NYFRB 등 1차 출처를 LLM 리서치로 유도, 스키마 검증
  - 저장: `name="us_liquidity_weekly"`

#TODO: 시계열 저장 포맷 합의(AiAnalysis value에 배열 저장), 주간 스냅샷 날짜 정칙

## 신규 5) 데일리 시장 체력/변동성 요약(주간 리포트에 인라인 첨부)

- 항목: VIX, 상승/하락 종목 비율(AD Line), 52주 신고가/신저가 수, TRIN 등 핵심 지표
- 엔드포인트(조회 전용 또는 POST로 캐싱 생성)
  - GET `GET /news/market-breadth`
  - POST `POST /news/market-breadth`
- 저장: `name="market_breadth_daily"` (주간 보고서 작성 시 최근 5영업일을 조합)

#TODO: 데이터 항목·정의서, 스키마·소스, 주간 조합 규칙 문서화

## 섹터/테마 매핑(LLM 응답 기반)

- 내부 매핑 테이블 없이 LLM이 섹터/테마를 명시적으로 응답하도록 강제
  - 각 종목/ETF에 대해 `sector`, `themes[]` 필수
  - 불확실 시 `sector_inferred: true`, `evidence` 포함
- HYBRID 병합 규칙(예시)
  - 동일 티커 섹터 불일치 시 다수결 + 출처 신뢰도 가중
  - provenance에 모델별 판단 기록

## 저장 규칙(주간 배치 기준)

- `analysis_date = 배치 실행일(YYYY-MM-DD)`로 저장(주간 스냅샷)
- value 공통 필드: `ai_model`, `llm_policy`, `prompt_hash`, `provenance`, `window`
- Insider/Analyst/PT/ETF Flows/Liquidity/Market Breadth 모두 `AiAnalysis` 테이블 저장(각 기능별 name)

## 보안/인증

- POST는 `verify_bearer_token` 강제. 배치에서는 `settings.auth_token` 사용해 SQS로 큐잉.
- 외부 호출은 Service 내부 LLM 호출 외 네트워크 접근 없음(현재 구조 유지).

## 배치/스케줄링 가이드

- 예시: `myapi/routers/batch_router.py` 의 `execute_batch_jobs` 참고.
- 신규 작업 예시 추가
  - insider-trend: `POST news/insider-trend { target_date: today }`
  - analyst-pt: `POST news/analyst-price-targets { target_date: today }`
  - etf-flows: `POST news/etf/flows { target_date: today }`
- 중복 제거 ID 규칙: `path-yyyy-mm-dd` 형태 유지.

## 테스트 체크리스트

- Service 프롬프트 함수가 안정적으로 스키마를 충족하는지(샘플 응답 검증).
- Repository 저장 name, `ticker` 키 유무, 날짜 필터 정상 동작.
- Router 쿼리 파싱(티커 대문자·공백 제거), `validate_date` 적용.
- 번역 실패 시 로깅만 하고 진행되는지.
- 권한: POST 401/403 경로 검증.

## 오픈 이슈/결정 필요

- LLM 모델 사용 기준: `gemini_search_grounding` vs `perplexity_completion` 선택 기준.
- 스키마 버저닝 방법: 스키마 변경 시 name suffix(`_v2`) 또는 value.version 필드 채택 여부.
- 대용량 시계열 저장 전략: 주간 집계 시 `ai_analysis` 1레코드에 통합 저장 vs 분할 저장.
- 섹터/테마 매핑 소스 고정 여부(내부 테이블 vs LLM 추론).

---

## 빠른 시작(구현 순서 제안)

1. ETF 플로우 → 2) 내부자 동향 → 3) 애널리스트 PT → 4) 유동성 → 5) 데일리 체력

#TODO: 각 항목 별 스키마 초안 작성 → PR로 확정
#TODO: Service 프롬프트 초안 및 예시 응답 추가
#TODO: Router/Service/Repository 배선 및 배치 등록
#TODO: 최소 단위 E2E 테스트 루트 추가(tests/…)

## 구현 현황(2025-08-31)

- LLM 이중화
  - `run_llm` 도입, `AUTO|GEMINI|PERPLEXITY|BOTH|FALLBACK|HYBRID` 지원, `provenance/prompt_hash` 기록.
  - HYBRID 병합: 아이템 기반은 유니온, 시계열은 날짜 기준 유니온.
- 스키마 추가
  - Insider/Analyst PT/ETF Flows/Liquidity/Breadth 전체 스키마 초안 반영.
- 서비스 구현
  - Insider: 생성/조회, 정렬(value|date)/limit, BOTH/HYBRID 저장 전략.
  - Analyst PT: 생성/조회, impact 정렬(UP/DOWN: |Δ|/old, INIT/DROP: base+|Δ|/consensus), date/limit.
  - ETF Flows: 생성/조회, provider/sector_only 필터, per-item 저장.
  - Liquidity: 스냅샷 생성/조회(name: `us_liquidity_weekly`).
  - Market Breadth: 스냅샷 생성/조회(name: `market_breadth_daily`).
- 라우터/배치
  - `/news/*` GET/POST 엔드포인트 추가(POST 보호). 배치에 5개 POST 작업 추가.
- 테스트
  - dual-LLM 정책 동작, HYBRID 병합, BOTH 개별 저장 검증 테스트 추가.

## 앞으로 해야 할 일

- 프롬프트/응답 고도화: 예제·소스 신뢰도 태깅·누락 필드 대비 강화.
- HYBRID 병합 고급화: 소스 신뢰도·중복 해소 규칙 도입.
- Repository 확장: `ai_model/llm_policy` 필터 옵션, 스냅샷 다중 저장(BOTH) 조회 병합.
- 정렬/필터 보강: ETF Flows 정렬(net_flow/volume_change), Analyst PT broker 필터, Insider role 필터.
- 테스트 보강: Analyst PT impact 케이스, ETF provider/sector_only, Liquidity/Breadth HYBRID, 라우터 401/403.
- 문서화: OpenAPI 예시, 저장 메타(ai_model/llm_policy/prompt_hash/provenance/window) 샘플.
- 운영: 배치 재시도/에러 핸들링, Rate-limit/감사 로깅.
