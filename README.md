# 미국주식 O/X 예측 서비스 API

> AI 리서치와 시그널 데이터를 통합해 미국 주식의 상승/하락(O/X) 판단을 돕는 FastAPI 기반 백엔드

## 서비스 개요
- 미국 주식 종목을 대상으로 매일 시그널을 생성하고 정확도를 추적합니다.
- 대형 언어 모델(LLM)과 웹 리서치 결과를 결합해 시황, 뉴스, ETF 흐름, 리서치 리포트를 생성합니다.
- 번역, 요약, PDF 추출, 테크니컬 지표 계산 등 투자 의사결정에 필요한 분석 도구를 제공합니다.
- AWS SQS·Lambda와 연동돼 배치 파이프라인을 자동화하고, PostgreSQL에 주요 결과를 적재합니다.

## 주요 기능
- **시그널 생성·저장**: `SignalService`가 yfinance 데이터, 테크니컬/펀더멘털 분석, LLM 응답을 결합해 매수·매도 시나리오를 작성하고 `SignalsRepository`에 저장합니다.
- **티커 데이터 허브**: 일별 시세를 저장하고 변화율, 주간 상승·하락 횟수, 최신 데이터 + 시그널을 한 번에 제공합니다.
- **시장 뉴스 & 리서치**: Perplexity, Gemini, AWS Bedrock 모델을 활용해 시장 분석, Mahaney Tech Stock 분석, ETF 자금 흐름, 내부자 거래 트렌드를 수집/요약합니다.
- **자동 번역 & 리포트 생성**: AWS Translate + LLM을 이용해 시그널을 한국어 마크다운 레포트로 변환하고, 필요한 경우 PDF를 추출해 전문을 제공합니다.
- **배치 오케스트레이션**: `/batch/execute`가 여러 API 호출을 SQS FIFO 메시지로 보내 자동 수집 파이프라인을 트리거합니다.

## 아키텍처 한눈에
- FastAPI 애플리케이션이 서비스 계층과 저장소 계층을 의존성 주입으로 연결합니다.
- PostgreSQL이 시그널/티커/리서치 데이터를 저장하며, SQLAlchemy ORM을 사용합니다.
- `AIService`는 OpenAI, Google Gemini, AWS Bedrock Nova, Perplexity, Hugging Face 등 다양한 모델을 추상화합니다.
- AWS SQS, Translate, (필요 시) S3를 사용하고, Lambda 배포를 위한 Mangum 어댑터를 포함합니다.

```
Clients / Batching
        │
        ▼
FastAPI Routers → Service Layer → SQLAlchemy Repositories → PostgreSQL
        │                    ├→ AIService (OpenAI · Gemini · Bedrock · Perplexity)
        │                    ├→ WebSearch/AWS Translate
        │                    └→ AWS SQS (Batch Trigger)
        ▼
   Responses / Reports / Dashboards
```

## 기술 스택
- **Backend**: Python 3.12, FastAPI, Mangum, Dependency Injector
- **Data & Analytics**: SQLAlchemy, pandas, pandas-ta, pandas_datareader, yfinance, pdfplumber, cloudscraper
- **AI & NLP**: OpenAI, Google Generative AI (Gemini), AWS Bedrock (Nova), Perplexity API, Hugging Face
- **AWS**: SQS FIFO, Translate, (옵션) S3, Lambda
- **Infra & Dev**: Docker, docker-compose, uvicorn, pytest(폴더만 존재), dotenv

## 디렉터리 가이드
```
.
├── myapi/
│   ├── main.py                # FastAPI 진입점 및 라우터 연결
│   ├── containers.py          # Dependency Injector 구성
│   ├── database.py            # SQLAlchemy 세션 & 스키마 설정
│   ├── domain/                # Pydantic 스키마 & ORM 모델
│   ├── routers/               # HTTP 엔드포인트 (signals, tickers, news, batch 등)
│   ├── services/              # 비즈니스 로직 (AI, 리서치, 번역, SQS 등)
│   ├── repositories/          # 데이터 접근 계층
│   ├── utils/                 # 공통 유틸 (인증, 날짜, 지표)
│   └── exceptions/            # 커스텀 예외
├── docs/                      # 상세 아키텍처 및 프론트엔드 가이드
├── requirements.txt
├── Dockerfile / Dockerfile.fastapi / Dockerfile.lambda
├── docker-compose*.yaml
└── tests/                     # 테스트 스켈레톤
```

## 동작 흐름 요약
1. **데이터 수집**: yfinance·pandas_datareader가 일별 가격과 재무 지표를 가져오고, 기술적 지표(`pandas_ta`)를 계산합니다.
2. **AI 분석**: `SignalService`와 `WebSearchService`가 AI 프롬프트를 생성하고 `AIService`를 통해 모델을 호출한 뒤, 스키마에 맞춰 검증합니다.
3. **번역 및 요약**: `TranslateService`가 AWS Translate와 LLM을 활용해 한국어 레포트를 생성하며, 불필요한 반복/링크를 정리합니다.
4. **저장 & 제공**: 결과는 PostgreSQL의 `signals`, `tickers`, `web_search_results` 등에 저장되고, FastAPI 라우터를 통해 REST 응답으로 노출됩니다.
5. **배치 자동화**: `/batch/execute` 같은 엔드포인트가 여러 작업을 SQS FIFO 큐에 던져 Lambda 워커가 순차 실행하도록 합니다.

## 배포 및 운영
- **로컬 개발**: uvicorn으로 API를 실행하고 PostgreSQL 인스턴스에 연결합니다.
- **Docker**: `Dockerfile`은 FastAPI 서버용, `Dockerfile.lambda`는 Lambda 패키징을 위한 이미지 구성을 제공합니다.
- **AWS Lambda**: Mangum 핸들러(`handler = Mangum(app)`)로 Lambda + API Gateway 배포가 가능합니다.

## 시작하기

### 요구 사항
- Python 3.12
- PostgreSQL (권장: AWS RDS). `crypto` 스키마 사용을 가정하고 있으니 사전에 생성합니다.
- 필수 환경 변수: OpenAI/Gemini/Perplexity/Bedrock API 키, AWS credentials, PostgreSQL 접속 정보, JWT 시크릿 등.
- (선택) AWS SQS, AWS Translate, S3 권한

### 설치 & 로컬 실행
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 환경 변수 세팅 (예: cp myapi/.env.example myapi/.env 후 값 입력)
uvicorn myapi.main:app --reload
```

API 문서는 `http://localhost:8000/docs`에서 OpenAPI 스펙으로 확인할 수 있습니다.

### Docker로 실행
```bash
docker build -t stock-alarm-api -f Dockerfile .
docker run --env-file myapi/.env -p 8000:8000 stock-alarm-api
```

로컬 테스트용 docker-compose 구성(`docker-compose.fastapi.yaml`)도 제공됩니다.

### Lambda 패키징
```bash
docker build -t stock-alarm-lambda -f Dockerfile.lambda .
```
빌드 결과 이미지를 ECR에 푸시하고 Lambda에 연결하거나, `deploy.sh` 스크립트를 참고해 배포 파이프라인을 구성할 수 있습니다.

## 환경 변수
`myapi/utils/config.py`의 `Settings` 클래스를 기준으로 주요 항목이 정의되어 있습니다.

- **데이터베이스**: `database_engine`, `database_username`, `database_password`, `database_host`, `database_port`, `database_dbname`, `database_schema`, `database_pool_size`, `database_max_overflow`
  - `database_engine`: SQLAlchemy 드라이버 문자열 (예: `postgresql+psycopg` - psycopg3 사용)
  - 기존 `postgresql+psycopg2`에서 `postgresql+psycopg`로 변경됨 (psycopg3)
- **JWT & 인증**: `AUTH_USERNAME`, `AUTH_PASSWORD`, `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `JWT_EXPIRE_MINUTES`, `auth_token`
- **AI 서비스 키**: `OPENAI_API_KEY`, `GEMINI_API_KEY`, `PERPLEXITY_API_KEY`, `BEDROCK_API_KEY`, `BEDROCK_BASE_URL`, `HYPERBOLIC_API_KEY`, `HUGGINGFACE_API_KEY`
- **AWS**: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION`, `AWS_S3_*` (Translate/S3용), `KAKAO_*` (카카오 OAuth)
- **외부 데이터**: `NEWS_API_KEY`, `FRED_API_KEY`, `COIN_*`, `NAVER_CLIENT_*`

환경 변수는 기본적으로 `myapi/.env`에서 로드되며, 배포 환경에서는 운영 환경 변수를 우선시하도록 구성하는 것이 좋습니다.

## 배치 & 자동화
- `POST /batch/execute`: 신호 생성, 시장 분석, 뉴스 요약, 리서치, ETF 포트폴리오, 내부자 거래, 애널리스트 목표가, ETF 흐름, 유동성, 시장 폭 엔드포인트를 SQS 메시지로 큐잉합니다.
- `POST /batch/tech-stock/analysis`: DefaultTickers를 3개씩 묶어 마허니(Mahaney) 테크 주식 분석을 순차 실행합니다.
- 배치 요청에는 JWT 토큰이 필요하며, `AwsService`가 메시지 그룹/중복 제거 ID를 관리합니다.

## API 살펴보기

| Router | Prefix | 용도 |
|--------|--------|------|
| `signal_router` | `/signals` | LLM 기반 시그널 생성, PDF 추출, Discord/Webhook, AI-only 시그널 저장 등 |
| `ticker_router` | `/tickers` | 티커 CRUD, 날짜별/주간 변화율, 시그널 결합, 레퍼런스 조회 |
| `news_router` | `/news` | 시장 뉴스, Mahaney 테크 분석, ETF 포트폴리오/자금 흐름, 내부자 거래, 애널리스트 목표가 |
| `translate_router` | `/translate` | 시그널 번역 및 마크다운 리포트 생성/조회 |
| `research_router` | `/research` | Perplexity 기반 최신 이슈 검색, 섹터 파급효과 분석, 주도 종목 분석, 종합 리서치 저장/조회 |
| `batch_router` | `/batch` | SQS 큐 기반 배치 작업 트리거 |
| `auth_router` | `/auth` | Basic Auth → JWT 발급, 티커 로고 다운로드 |

엔드포인트별 상세 파라미터와 응답 스키마는 `docs/FRONTEND_API_GUIDE.md` 및 각 `domain/*/schema.py`에서 확인할 수 있습니다.

## 데이터 모델
- `myapi/domain/signal` : 시그널/전략/뉴스/리포트 스키마, `DefaultTickers`, `SignalPromptResponse` 등 LLM 응답 구조 정의
- `myapi/domain/ticker` : 티커 ORM 모델과 응답 스키마, 변화율·주간 빈도 계산에 필요한 모델 포함
- `myapi/domain/news` : 시장 분석, ETF 흐름, 내부자 거래, 애널리스트 목표가 등 다양한 리포트 구조 정의
- `myapi/domain/research` : 리서치 요청/응답, 섹터 분석, 종합 리포트 저장 모델 정의

## 로깅 & 예외 처리
- `myapi/utils/config.init_logging()`이 Python 기본 로깅을 INFO 레벨로 초기화합니다.
- `ServiceException` 핸들러가 공통 예외 응답을 JSON으로 반환하고, 전역 미들웨어가 예외를 캐치해 500 응답을 제공합니다.
- HTTP 요청/응답 로깅 미들웨어가 기본적으로 활성화되어 있습니다.

## 개발 팁
- 의존성 주입: `dependency_injector` 컨테이너를 활용해 서비스/리포지토리/설정을 주입합니다.
- AI 스키마 검증: 모든 AI 응답은 Pydantic 모델(`signal_schema.py`, `news_schema.py`, `research_schema.py`)로 파싱되므로, 새 모델을 추가할 때는 스키마 정의와 예외 처리를 함께 추가하세요.
- 캐싱: `myapi/utils/yfinance_cache.configure_yfinance_cache()`가 yfinance 캐시 디렉터리를 설정합니다.
- 테스트: `tests/` 폴더가 비어 있으므로, 주요 서비스에 대한 단위 테스트/통합 테스트를 추가하는 것이 좋습니다.

## 추가 문서
- `docs/ox_design.md` : 전체 서비스 설계 개요
- `docs/ox_implementation_guide.md` : 이상적인 폴더 구조 및 구현 가이드
- `docs/FRONTEND_API_GUIDE.md` : 프론트엔드에서 사용하는 상세 API 명세
- `docs/OX_Predict_requirement.md`, `docs/ox_task.md` 등 : 요구사항/작업 항목 정리

---
외부 협력사나 신규 팀원이 README 하나로 서비스의 목적, 구조, 실행 방법을 이해하고 빠르게 온보딩할 수 있도록 위 내용을 유지보수해 주세요.
