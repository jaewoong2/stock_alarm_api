# ai_analysis 관련 API 정리

프론트엔드에서 `crypto.ai_analysis` 테이블을 소비할 때 필요한 라우터, 요청/응답 규격을 아래에 정리했다. 인용한 스키마와 서비스 로직은 모두 현재 코드 기준이며, 파일 경로·라인을 명시해두었다.

---

## 공통 데이터 모델 (`crypto.ai_analysis`)

```python
class AiAnalysisModel(Base):
    __tablename__ = "ai_analysis"
    __table_args__ = {"schema": "crypto"}

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False)
    name = Column(String, nullable=False, default="market_analysis")
    value = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

- 위치: `myapi/domain/news/news_models.py:38-45`
- 모든 분석 결과는 날짜(`date`)와 분석 타입(`name`)으로 구분된다. `name`은 `market_analysis`, `comprehensive_research`, `research_results`, `sector_analysis`, `leading_stocks` 등으로 사용된다.
- `value` 필드에 Pydantic 스키마(`MarketAnalysis`, `ComprehensiveResearchData` 등)의 JSON 직렬화 값이 저장된다.
- `created_at`은 DB 서버 시간이 자동 기록돼, 언제 생성됐는지 추적 가능하다.

---

## 1. `/news/market-analysis`

| 항목 | 내용 |
| --- | --- |
| HTTP Method | `GET` |
| 정의 위치 | `myapi/routers/news_router.py:148-172` |
| 서비스 구현 | `myapi/services/web_search_service.py:311-410` |
| 저장소 접근 | `myapi/repositories/web_search_repository.py:598-626` |
| 저장되는 name | `"market_analysis"` |

### 요청 파라미터

```http
GET /news/market-analysis?today=YYYY-MM-DD
```

* `today` (query, optional): 기본값은 서버 기준 `dt.date.today()` 후 `validate_date()` 로 검증된다.

### 응답 스키마

서비스는 `WebSearchService.get_market_analysis()`에서 `AiAnalysisModel`( `myapi/domain/news/news_models.py:38-45`)을 조회하고, 값이 존재하면 `MarketAnalysis` 스키마로 검증 후 그대로 반환한다. 스키마 정의는 `myapi/domain/news/news_schema.py:155-161`.

```python
class MarketAnalysis(BaseModel):
    analysis_date_est: str
    market_overview: MarketOverview
    top_momentum_sectors: List[TopMomentumSector]
```

* `market_overview` → `summary`, `major_catalysts: List[str]`.
* `top_momentum_sectors` → 각 섹터의 `sector_ranking`, `sector`, `reason`, `risk_factor`, `themes[]`.
* `themes[].stocks[]` → `ticker`, `name`, `pre_market_change`, `key_news`, `short_term_strategy`.

> 캐시가 없을 경우 빈 구조 (`summary=""`, 빈 리스트)로 내려오니 FE는 비어있는 경우 UI 처리 필요.

---

## 2. `/research/analysis` (및 변형 라우터)

| Path | 설명 |
| --- | --- |
| `GET /research/analysis` | 날짜/정렬 파라미터로 리스트 조회 (`myapi/routers/research_router.py:155-189`) |
| `GET /research/analysis/by-date/{analysis_date}` | Path param으로 특정 날짜 조회 (`myapi/routers/research_router.py:192-219`) |
| `GET /research/analysis/latest` | 최신 1건만 반환 (`myapi/routers/research_router.py:222-251`) |

공통적으로 `ResearchService.get_research_analysis()` (`myapi/services/research_service.py:409-472`)를 호출하며, repository에서는 `name="comprehensive_research"` 조건으로 `AiAnalysisModel` 레코드를 끌어온다. 저장 시점(`save_research_analysis`)에도 동일한 name으로 insert한다 (`myapi/services/research_service.py:347-405`).

### 요청 파라미터

| 파라미터 | 타입/기본값 | 설명 |
| --- | --- | --- |
| `target_date` | `date`, 기본 오늘 | 기준 날짜. `by-date`는 path param `analysis_date`를 동일 의미로 사용 |
| `limit` | `int`, optional | 최대 반환 개수 (`latest`는 내부에서 `limit=1`) |
| `sort_by` | Literal `"date"` | 현재 date만 지원 |
| `sort_order` | `"asc"` 또는 `"desc"`, 기본 `"desc"` | 정렬 순서 |

### 응답 스키마

라우터 response model: `GetResearchAnalysisResponse` (`myapi/domain/research/research_schema.py:82-115`).

```python
class GetResearchAnalysisResponse(BaseModel):
    analyses: List[ResearchAnalysisVO]
    total_count: int
    filtered_count: int
    actual_date: Optional[dt.date]
    is_exact_date_match: bool = True
    request_params: GetResearchAnalysisRequest
```

`ResearchAnalysisVO` 의 `value` 는 `ComprehensiveResearchData` 타입이며 같은 파일에 정의되어 있다.

```python
class ComprehensiveResearchData(BaseModel):
    research_date: str
    research_results: ResearchResponse
    sector_analysis: SectorAnalysisResponse
    leading_stocks: LeadingStockResponse
```

#### 하위 컴포넌트

* `research_results`: `ResearchResponse` (`research_schema.py:24-37`) → `research_items[]` (제목, 날짜, 출처, 요약, `entities[]`, `event_type`).
* `sector_analysis`: `SectorAnalysisResponse` (`research_schema.py:43-59`) → 4단계 수혜 섹터 리스트.
* `leading_stocks`: `LeadingStockResponse` (`research_schema.py:67-78`) → 각 종목별 `stock_metrics`, `analysis_summary`, `growth_potential`, `risk_factors[]`, `target_price`, `recommendation`.

`save_research_analysis()`에서는 동일 날짜에 대해 컴포넌트를 개별 name(`research_results`, `sector_analysis`, `leading_stocks`)으로도 저장하니, 필요 시 별도 엔드포인트 (`/research/components/{target_date}` 등) 로 접근 가능 (`research_router.py:254-303` 참고).

---

## 참고 흐름도

1. **생성**  
   * `/news/market-analysis` → `POST` 버전(`news_router.py:160-172`)이 `verify_bearer_token`을 요구하며, `WebSearchService.create_market_analysis()`가 Perplexity 호출 후 `name="market_analysis"`로 저장.
   * `/research/analysis` → `POST /research/analysis` (`research_router.py:126-152`)가 `ResearchService.save_research_analysis()`를 호출, `name="comprehensive_research"` 로 저장.

2. **조회**  
   * GET 라우터는 모두 같은 name 조건으로 `AiAnalysisModel`을 읽어 FE에 전달.

이 문서를 프론트 동료에게 공유하면, 엔드포인트와 응답 JSON 구조를 빠르게 파악하여 통신 규격을 맞출 수 있다.
