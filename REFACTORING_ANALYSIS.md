# 코드 리팩토링 분석 문서

## 개요

본 문서는 FastAPI 기반 주식 분석 API 프로젝트의 Service, Router, Repository 레이어에 대한 종합적인 리팩토링 분석을 제공합니다. 각 파일의 현재 상태, 문제점, 개선 방안을 상세히 기술합니다.

---

## 📊 Services Layer 분석

### 1. AIService (`myapi/services/ai_service.py`)

#### 현재 상태
- **라인 수**: 534줄
- **주요 기능**: 다양한 AI 모델(OpenAI, Gemini, AWS Bedrock, Perplexity 등) 통합
- **의존성**: OpenAI, Google Gemini, AWS Boto3, Pydantic

#### 문제점
1. **단일 책임 원칙 위반**: 하나의 클래스가 너무 많은 AI 서비스를 처리
2. **중복 코드**: 각 AI 서비스마다 유사한 에러 처리 로직 반복
3. **하드코딩**: 모델 ID와 설정값들이 하드코딩됨
4. **동기식 처리**: 모든 AI API 호출이 동기식으로 처리됨

#### 개선 방안
```python
# 개선된 구조 예시
class BaseAIProvider(ABC):
    @abstractmethod
    async def complete(self, prompt: str, schema: Type[T]) -> T:
        pass

class OpenAIProvider(BaseAIProvider):
    async def complete(self, prompt: str, schema: Type[T]) -> T:
        # OpenAI 전용 구현
        pass

class AIServiceFactory:
    def get_provider(self, provider_type: str) -> BaseAIProvider:
        # 팩토리 패턴으로 AI 제공자 선택
        pass
```

#### 리팩토링 우선순위: 🔴 높음

---

### 2. AwsService (`myapi/services/aws_service.py`)

#### 현재 상태
- **라인 수**: 241줄
- **주요 기능**: AWS Secrets Manager, S3, SQS 통합
- **의존성**: Boto3

#### 문제점
1. **혼재된 책임**: AWS 서비스들이 하나의 클래스에 모두 포함
2. **하드코딩**: 큐 URL, 리전 정보 하드코딩
3. **에러 처리 부족**: AWS 서비스별 특화된 에러 처리 미흡

#### 개선 방안
```python
class AWSSecretsService:
    async def get_secret(self, secret_name: str) -> dict:
        pass

class AWSSQSService:
    async def send_message(self, queue_url: str, message: str) -> dict:
        pass

class AWSS3Service:
    async def upload_file(self, bucket: str, key: str, file_data: bytes) -> str:
        pass
```

#### 리팩토링 우선순위: 🟡 중간

---

### 3. SignalService (`myapi/services/signal_service.py`)

#### 현재 상태
- **라인 수**: 1400+줄 (매우 큰 파일)
- **주요 기능**: 기술적 분석, 시그널 생성, 뉴스 분석
- **의존성**: yfinance, pandas, ta 라이브러리

#### 문제점
1. **거대한 클래스**: 하나의 클래스가 너무 많은 책임을 가짐
2. **복잡한 메서드**: 일부 메서드가 100줄 이상으로 너무 길음
3. **동기식 데이터 처리**: pandas 데이터 처리가 모두 동기식
4. **하드코딩된 전략**: 기술적 분석 전략들이 하드코딩됨

#### 개선 방안
```python
class TechnicalAnalysisService:
    async def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        pass

class SignalGenerationService:
    async def evaluate_signals(self, df: pd.DataFrame, strategies: List[Strategy]) -> List[TechnicalSignal]:
        pass

class MarketDataService:
    async def fetch_ohlcv(self, ticker: str, start: date, end: date) -> pd.DataFrame:
        pass
```

#### 리팩토링 우선순위: 🔴 높음

---

### 4. TranslateService (`myapi/services/translate_service.py`)

#### 현재 상태
- **라인 수**: 600+줄
- **주요 기능**: AWS Translate를 통한 번역, AI 서비스 통합
- **의존성**: AWS Translate, AIService

#### 문제점
1. **복잡한 데이터 변환**: SignalValueObject 변환 로직이 복잡
2. **동기식 번역**: 모든 번역이 동기식으로 처리
3. **중복된 에러 처리**: 각 메서드마다 유사한 try-catch 블록

#### 개선 방안
```python
class AsyncTranslateService:
    async def translate_batch(self, texts: List[str]) -> List[str]:
        pass
    
    async def translate_signal_batch(self, signals: List[SignalValueObject]) -> List[SignalValueObject]:
        pass
```

#### 리팩토링 우선순위: 🟡 중간

---

### 5. TickerService (`myapi/services/ticker_service.py`)

#### 현재 상태
- **라인 수**: 450줄
- **주요 기능**: 티커 정보 관리, 대량 데이터 업데이트
- **의존성**: TickerRepository, SignalsRepository, SignalService

#### 문제점
1. **블로킹 루프**: `update_ticker_informations`에서 pandas 데이터를 순차 처리
2. **메모리 비효율**: 대량 데이터를 메모리에 한번에 로드
3. **트랜잭션 관리 부족**: 배치 처리 중 실패 시 롤백 처리 미흡

#### 개선 방안
```python
class AsyncTickerService:
    async def update_ticker_informations_batch(self, ticker: str, start: date, end: date) -> dict:
        # 비동기 배치 처리
        async with self.repository.get_session() as session:
            # 벡터화된 pandas 연산 사용
            # 청크 단위로 처리하여 메모리 효율성 개선
            pass
```

#### 리팩토링 우선순위: 🟡 중간

---

### 6. WebSearchService (`myapi/services/web_search_service.py`)

#### 현재 상태
- **라인 수**: 200줄
- **주요 기능**: 웹 검색 결과 캐싱, AI 기반 시장 분석
- **의존성**: WebSearchResultRepository, AIService

#### 문제점
1. **캐싱 전략 부족**: 간단한 DB 기반 캐싱만 구현
2. **동기식 AI 호출**: AI 서비스 호출이 모두 동기식

#### 개선 방안
```python
class AsyncWebSearchService:
    def __init__(self, redis_cache: RedisCache):
        self.cache = redis_cache
    
    async def get_market_forecast_cached(self, date: date) -> MarketForecast:
        # Redis 캐싱 구현
        pass
```

#### 리팩토링 우선순위: 🟢 낮음

---

## 🛣️ Routers Layer 분석

### 1. AuthRouter (`myapi/routers/auth_router.py`)

#### 현재 상태
- **라인 수**: 550줄
- **주요 기능**: JWT 토큰 생성, 로고 다운로드
- **엔드포인트 수**: 8개

#### 문제점
1. **책임 혼재**: 인증과 로고 다운로드 기능이 함께 있음
2. **동기식 파일 다운로드**: 로고 다운로드가 동기식으로 처리
3. **하드코딩**: API 키와 URL이 하드코딩됨

#### 개선 방안
```python
# auth_router.py (인증만)
@router.post("/token")
async def generate_token(credentials: HTTPBasicCredentials = Depends(security)):
    pass

# logo_router.py (별도 라우터)
@router.get("/download/{ticker}")
async def download_logo(ticker: str, logo_service: LogoService = Depends()):
    pass
```

#### 리팩토링 우선순위: 🟡 중간

---

### 2. SignalRouter (`myapi/routers/signal_router.py`)

#### 현재 상태
- **라인 수**: 450줄
- **주요 기능**: 시그널 조회, 생성, LLM 쿼리
- **엔드포인트 수**: 12개

#### 문제점
1. **혼재된 동기/비동기**: 일부는 async, 일부는 sync로 처리
2. **복잡한 요청 처리**: 단일 엔드포인트에서 너무 많은 로직 처리
3. **SQS 의존성**: 라우터에서 직접 SQS 메시지 생성

#### 개선 방안
```python
@router.post("/signals")
async def create_signals(
    request: SignalCreateRequest,
    signal_service: AsyncSignalService = Depends(),
    queue_service: QueueService = Depends()
):
    # 라우터는 요청 검증과 응답만 담당
    result = await signal_service.create_signals(request)
    await queue_service.publish_signal_created(result)
    return result
```

#### 리팩토링 우선순위: 🔴 높음

---

### 3. TickerRouter (`myapi/routers/ticker_router.py`)

#### 현재 상태
- **라인 수**: 200줄
- **주요 기능**: 티커 CRUD, 변화율 조회
- **엔드포인트 수**: 10개

#### 문제점
1. **일관성 없는 비동기 처리**: 일부 엔드포인트만 async
2. **복잡한 쿼리 파라미터**: 여러 필터링 옵션이 복잡하게 구현

#### 개선 방안
```python
# 모든 엔드포인트를 async로 통일
@router.get("/", response_model=List[TickerResponse])
async def get_tickers(
    filters: TickerFilters = Depends(),
    pagination: Pagination = Depends(),
    ticker_service: AsyncTickerService = Depends()
):
    return await ticker_service.get_tickers(filters, pagination)
```

#### 리팩토링 우선순위: 🟡 중간


### 5. BatchRouter (`myapi/routers/batch_router.py`)

#### 현재 상태
- **라인 수**: 180줄
- **주요 기능**: 배치 작업 실행, SQS 큐 관리
- **엔드포인트 수**: 2개

#### 문제점
1. **하드코딩된 작업 정의**: 배치 작업들이 코드에 하드코딩됨
2. **에러 처리 부족**: 배치 실행 중 실패 처리 미흡

#### 개선 방안
```python
class BatchJobRegistry:
    def register_job(self, job_name: str, job_config: JobConfig):
        pass

@router.post("/execute")
async def execute_batch_jobs(
    job_names: List[str],
    job_registry: BatchJobRegistry = Depends(),
    batch_service: AsyncBatchService = Depends()
):
    return await batch_service.execute_jobs(job_names)
```

#### 리팩토링 우선순위: 🟢 낮음

---

## 🗄️ Repositories Layer 분석

### 1. SignalsRepository (`myapi/repositories/signals_repository.py`)

#### 현재 상태
- **라인 수**: 400줄
- **주요 기능**: 시그널 CRUD, 복잡한 조인 쿼리
- **데이터베이스**: PostgreSQL

#### 문제점
1. **복잡한 쿼리**: `get_signals_join_ticker` 메서드가 매우 복잡
2. **N+1 쿼리 문제**: 관련 데이터 로딩 시 다중 쿼리 발생 가능
3. **트랜잭션 관리**: 수동 트랜잭션 관리로 인한 복잡성

#### 개선 방안
```python
class AsyncSignalsRepository:
    async def get_signals_with_ticker(
        self, 
        filters: SignalFilters,
        pagination: Pagination
    ) -> List[SignalWithTicker]:
        # SQLAlchemy 2.0 async 쿼리 사용
        # selectinload로 N+1 문제 해결
        stmt = (
            select(Signals)
            .options(selectinload(Signals.ticker))
            .where(filters.to_where_clause())
            .limit(pagination.limit)
            .offset(pagination.offset)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
```

#### 리팩토링 우선순위: 🔴 높음

---

### 2. TickerRepository (`myapi/repositories/ticker_repository.py`)

#### 현재 상태
- **라인 수**: 350줄
- **주요 기능**: 티커 CRUD, 날짜별 조회, 변화율 계산
- **특징**: 동기/비동기 세션 모두 지원

#### 문제점
1. **세션 타입 분기**: AsyncSession과 Session 분기 처리로 복잡성 증가
2. **복잡한 집계 쿼리**: `get_ticker_order_by` 메서드의 서브쿼리가 복잡
3. **인덱스 최적화 부족**: 날짜와 심볼 조합 쿼리 최적화 필요

#### 개선 방안
```python
# 비동기 전용으로 통일
class AsyncTickerRepository:
    async def get_ticker_changes(
        self, 
        symbol: str, 
        date_range: DateRange
    ) -> List[TickerChange]:
        # CTE(Common Table Expression) 사용으로 쿼리 최적화
        # 윈도우 함수로 변화율 계산
        pass
    
    async def bulk_upsert(self, tickers: List[TickerCreate]) -> List[Ticker]:
        # PostgreSQL의 ON CONFLICT 활용
        pass
```

#### 리팩토링 우선순위: 🟡 중간

---

### 3. WebSearchRepository (`myapi/repositories/web_search_repository.py`)

#### 현재 상태
- **라인 수**: 580줄
- **주요 기능**: 웹 검색 결과 저장, AI 분석 결과 저장
- **특징**: JSON 필드를 활용한 유연한 데이터 저장

#### 문제점
1. **JSON 쿼리 최적화**: PostgreSQL JSON 쿼리 최적화 부족
2. **복잡한 필터링**: `get_all_analyses` 메서드의 동적 필터링이 복잡
3. **타입 안전성**: JSON 데이터의 타입 안전성 부족

#### 개선 방안
```python
class AsyncWebSearchRepository:
    async def get_analyses_typed(
        self, 
        filters: AnalysisFilters,
        result_type: Type[T]
    ) -> List[T]:
        # JSON 스키마 검증 추가
        # GIN 인덱스 활용 최적화
        pass
    
    async def upsert_analysis(
        self, 
        analysis: AnalysisData,
        conflict_resolution: ConflictResolution = ConflictResolution.UPDATE
    ) -> AnalysisResult:
        pass
```

#### 리팩토링 우선순위: 🟡 중간

---

## 🔧 공통 개선 사항

### 1. 비동기 처리 통일
```python
# 현재: 혼재된 동기/비동기
def sync_method():
    pass

async def async_method():
    pass

# 개선: 비동기로 통일
async def unified_async_method():
    pass
```

### 2. 의존성 주입 개선
```python
# 현재: 직접 인스턴스 생성
class Service:
    def __init__(self):
        self.external_api = ExternalAPI()

# 개선: 인터페이스 기반 의존성 주입
class Service:
    def __init__(self, external_api: ExternalAPIInterface):
        self.external_api = external_api
```

### 3. 에러 처리 표준화
```python
# 공통 에러 처리 데코레이터
def handle_service_errors(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except DatabaseError as e:
            logger.error(f"Database error in {func.__name__}: {e}")
            raise HTTPException(status_code=500, detail="Database error")
        except ValidationError as e:
            logger.error(f"Validation error in {func.__name__}: {e}")
            raise HTTPException(status_code=400, detail="Validation error")
    return wrapper
```

### 4. 설정 관리 개선
```python
# 환경별 설정 분리
class Settings(BaseSettings):
    # AI 서비스 설정
    openai_api_key: str
    gemini_api_key: str
    
    # AWS 설정
    aws_region: str = "ap-northeast-2"
    sqs_queue_url: str
    
    # 캐싱 설정
    redis_url: str
    cache_ttl: int = 3600
    
    class Config:
        env_file = ".env"
        case_sensitive = True
```

---

## 📋 리팩토링 로드맵

### Phase 1: 기초 인프라 개선 (2주)
1. **비동기 처리 통일**: 모든 I/O 작업을 비동기로 전환
2. **에러 처리 표준화**: 공통 에러 처리 로직 구현
3. **설정 관리 개선**: 환경별 설정 분리

### Phase 2: Service Layer 리팩토링 (4주)
1. **AIService 분할**: 각 AI 제공자별로 서비스 분리
2. **SignalService 분할**: 기능별로 여러 서비스로 분리
3. **캐싱 레이어 추가**: Redis 기반 캐싱 구현

### Phase 3: Repository Layer 최적화 (3주)
1. **쿼리 최적화**: 복잡한 쿼리들을 최적화
2. **인덱스 추가**: 성능 개선을 위한 데이터베이스 인덱스 추가
3. **배치 처리 개선**: 대량 데이터 처리 최적화

### Phase 4: API Layer 개선 (2주)
1. **라우터 정리**: 책임 분리 및 일관성 개선
2. **API 문서화**: OpenAPI 스펙 개선
3. **테스트 커버리지**: 단위 테스트 및 통합 테스트 추가

---

## 🎯 성능 목표

| 지표 | 현재 | 목표 | 개선 방법 |
|------|------|------|-----------|
| API 응답 시간 | 2-5초 | 500ms-1초 | 비동기 처리, 캐싱 |
| 데이터베이스 쿼리 | N+1 문제 | 최적화된 쿼리 | selectinload, 인덱스 |
| 메모리 사용량 | 높음 | 50% 감소 | 스트리밍 처리, 배치 크기 조정 |
| 동시 처리 능력 | 제한적 | 10배 향상 | 비동기 처리, 커넥션 풀링 |

---

## 🔍 모니터링 및 관찰 가능성

### 1. 로깅 개선
```python
# 구조화된 로깅
import structlog

logger = structlog.get_logger()

async def process_signal(signal_id: str):
    logger.info("Processing signal started", signal_id=signal_id)
    try:
        result = await signal_service.process(signal_id)
        logger.info("Processing signal completed", 
                   signal_id=signal_id, 
                   result_status=result.status)
        return result
    except Exception as e:
        logger.error("Processing signal failed", 
                    signal_id=signal_id, 
                    error=str(e))
        raise
```

### 2. 메트릭 수집
```python
# Prometheus 메트릭
from prometheus_client import Counter, Histogram

request_count = Counter('api_requests_total', 'Total API requests', ['method', 'endpoint'])
request_duration = Histogram('api_request_duration_seconds', 'API request duration')

@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    
    request_count.labels(method=request.method, endpoint=request.url.path).inc()
    request_duration.observe(duration)
    
    return response
```

### 3. 분산 추적
```python
# OpenTelemetry 추적
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

async def fetch_stock_data(ticker: str):
    with tracer.start_as_current_span("fetch_stock_data") as span:
        span.set_attribute("ticker", ticker)
        # 실제 데이터 조회 로직
        pass
```

---

이 문서는 전체 프로젝트의 리팩토링 방향성을 제시하며, 각 단계별로 점진적인 개선을 통해 코드 품질과 성능을 향상시키는 것을 목표로 합니다.
