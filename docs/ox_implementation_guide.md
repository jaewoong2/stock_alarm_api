# 미국주식 O/X 예측 서비스 - 구현 가이드

## 1. 프로젝트 폴더 아키텍처

### 1.1 최적화된 폴더 구조

```
tqqq/
├── README.md
├── requirements.txt
├── docker-compose.yaml
├── Dockerfile
├── .env.example
├── .gitignore
├── pytest.ini
├── alembic.ini
│
├── app/                              # 메인 애플리케이션
│   ├── __init__.py
│   ├── main.py                       # FastAPI 앱 진입점
│   ├── config.py                     # 환경 설정
│   ├── dependencies.py               # 의존성 주입
│   │
│   ├── core/                         # 핵심 비즈니스 로직
│   │   ├── __init__.py
│   │   ├── security.py               # JWT, OAuth 보안
│   │   ├── exceptions.py             # 커스텀 예외
│   │   ├── events.py                 # 이벤트 처리
│   │   └── constants.py              # 상수 정의
│   │
│   ├── models/                       # SQLAlchemy 모델
│   │   ├── __init__.py
│   │   ├── base.py                   # 베이스 모델
│   │   ├── user.py                   # 사용자 모델
│   │   ├── session.py                # 세션 제어 모델
│   │   ├── prediction.py             # 예측 모델
│   │   ├── settlement.py             # 정산 모델
│   │   ├── points.py                 # 포인트 모델
│   │   └── rewards.py                # 리워드 모델
│   │
│   ├── schemas/                      # Pydantic 스키마
│   │   ├── __init__.py
│   │   ├── base.py                   # 베이스 스키마
│   │   ├── auth.py                   # 인증 스키마
│   │   ├── user.py                   # 사용자 스키마
│   │   ├── prediction.py             # 예측 스키마
│   │   ├── settlement.py             # 정산 스키마
│   │   ├── points.py                 # 포인트 스키마
│   │   └── rewards.py                # 리워드 스키마
│   │
│   ├── api/                          # API 라우터
│   │   ├── __init__.py
│   │   ├── deps.py                   # API 의존성
│   │   ├── v1/
│   │   │   ├── __init__.py
│   │   │   ├── router.py             # 메인 라우터
│   │   │   ├── auth.py               # 인증 엔드포인트
│   │   │   ├── users.py              # 사용자 엔드포인트
│   │   │   ├── session.py            # 세션 엔드포인트
│   │   │   ├── universe.py           # 종목 유니버스
│   │   │   ├── predictions.py        # 예측 엔드포인트
│   │   │   ├── settlements.py        # 정산 엔드포인트
│   │   │   ├── points.py             # 포인트 엔드포인트
│   │   │   ├── rewards.py            # 리워드 엔드포인트
│   │   │   └── ads.py                # 광고/성장 엔드포인트
│   │   └── internal/
│   │       ├── __init__.py
│   │       ├── router.py             # 내부 API 라우터
│   │       ├── session.py            # 내부 세션 관리
│   │       ├── universe.py           # 내부 종목 관리
│   │       ├── settlement.py         # 내부 정산
│   │       └── eod.py                # EOD 데이터 수집
│   │
│   ├── services/                     # 비즈니스 로직 서비스
│   │   ├── __init__.py
│   │   ├── base.py                   # 베이스 서비스
│   │   ├── auth_service.py           # 인증 서비스
│   │   ├── user_service.py           # 사용자 서비스
│   │   ├── session_service.py        # 세션 서비스
│   │   ├── universe_service.py       # 종목 유니버스 서비스
│   │   ├── prediction_service.py     # 예측 서비스
│   │   ├── settlement_service.py     # 정산 서비스
│   │   ├── eod_service.py            # EOD 데이터 서비스
│   │   ├── points_service.py         # 포인트 서비스
│   │   ├── rewards_service.py        # 리워드 서비스
│   │   ├── ads_service.py            # 광고 서비스
│   │   └── monitoring_service.py     # 모니터링 서비스
│   │
│   ├── repositories/                 # 데이터 액세스 계층
│   │   ├── __init__.py
│   │   ├── base.py                   # 베이스 리포지토리
│   │   ├── user_repository.py        # 사용자 리포지토리
│   │   ├── session_repository.py     # 세션 리포지토리
│   │   ├── prediction_repository.py  # 예측 리포지토리
│   │   ├── settlement_repository.py  # 정산 리포지토리
│   │   ├── points_repository.py      # 포인트 리포지토리
│   │   └── rewards_repository.py     # 리워드 리포지토리
│   │
│   ├── providers/                    # 외부 서비스 제공자
│   │   ├── __init__.py
│   │   ├── base.py                   # 베이스 제공자
│   │   ├── oauth/
│   │   │   ├── __init__.py
│   │   │   ├── google.py             # 구글 OAuth
│   │   │   └── kakao.py              # 카카오 OAuth
│   │   ├── eod/
│   │   │   ├── __init__.py
│   │   │   ├── alpha_vantage.py      # Alpha Vantage API
│   │   │   └── yahoo_finance.py      # Yahoo Finance API
│   │   └── queue/
│   │       ├── __init__.py
│   │       ├── sqs.py                # AWS SQS
│   │       └── events.py             # 이벤트 정의
│   │
│   ├── middleware/                   # 미들웨어
│   │   ├── __init__.py
│   │   ├── rate_limit.py             # 레이트 리밋
│   │   ├── cors.py                   # CORS 설정
│   │   └── logging.py                # 로깅 미들웨어
│   │
│   ├── utils/                        # 유틸리티
│   │   ├── __init__.py
│   │   ├── datetime.py               # 시간 유틸리티
│   │   ├── validation.py             # 검증 유틸리티
│   │   ├── crypto.py                 # 암호화 유틸리티
│   │   └── helpers.py                # 헬퍼 함수
│   │
│   └── database/                     # 데이터베이스 관련
│       ├── __init__.py
│       ├── connection.py             # DB 연결 설정
│       └── session.py                # DB 세션 관리
│
├── batch/                            # 배치 작업
│   ├── __init__.py
│   ├── main.py                       # 배치 실행 진입점
│   ├── scheduler.py                  # 스케줄러
│   ├── jobs/
│   │   ├── __init__.py
│   │   ├── daily_universe.py         # 일일 종목 선정
│   │   ├── session_control.py        # 세션 제어
│   │   ├── eod_fetch.py              # EOD 데이터 수집
│   │   ├── settlement.py             # 정산 실행
│   │   └── cleanup.py                # 데이터 정리
│   └── workers/
│       ├── __init__.py
│       ├── sqs_worker.py             # SQS 워커
│       └── base_worker.py            # 베이스 워커
│
├── alembic/                          # 데이터베이스 마이그레이션
│   ├── versions/
│   ├── env.py
│   ├── script.py.mako
│   └── README
│
├── tests/                            # 테스트
│   ├── __init__.py
│   ├── conftest.py                   # 테스트 설정
│   ├── test_auth.py                  # 인증 테스트
│   ├── test_predictions.py           # 예측 테스트
│   ├── test_settlements.py           # 정산 테스트
│   ├── test_points.py                # 포인트 테스트
│   ├── test_rewards.py               # 리워드 테스트
│   ├── unit/                         # 단위 테스트
│   │   ├── services/
│   │   ├── repositories/
│   │   └── utils/
│   └── integration/                  # 통합 테스트
│       ├── api/
│       └── batch/
│
├── docs/                             # 문서
│   ├── api/                          # API 문서
│   ├── architecture/                 # 아키텍처 문서
│   ├── deployment/                   # 배포 가이드
│   └── user_guide/                   # 사용자 가이드
│
├── scripts/                          # 유틸리티 스크립트
│   ├── setup_db.py                   # 데이터베이스 셋업
│   ├── seed_data.py                  # 시드 데이터
│   └── deploy.py                     # 배포 스크립트
│
└── infra/                            # 인프라스트럭처
    ├── docker/
    │   ├── Dockerfile.app
    │   ├── Dockerfile.batch
    │   └── docker-compose.yml
    ├── terraform/                    # 기존 terraform 폴더
    └── kubernetes/                   # K8s 매니페스트 (선택사항)
```

## 2. 시스템 아키텍처 구성도

### 2.1 전체 시스템 아키텍처

```mermaid
graph TB
    subgraph "Client Layer"
        WEB[Web Frontend]
        MOBILE[Mobile App]
        API_CLIENT[API Client]
    end

    subgraph "API Gateway Layer"
        ALB[Application Load Balancer]
        RATE_LIMIT[Rate Limiter]
    end

    subgraph "Application Layer"
        API[FastAPI App]
        BATCH[Batch Workers]
        WORKER[SQS Workers]
    end

    subgraph "Service Layer"
        AUTH_SVC[Auth Service]
        PRED_SVC[Prediction Service]
        SETTLE_SVC[Settlement Service]
        POINTS_SVC[Points Service]
        REWARDS_SVC[Rewards Service]
    end

    subgraph "Data Layer"
        PG[(PostgreSQL)]
        REDIS[(Redis Cache)]
    end

    subgraph "Message Queue"
        SQS[AWS SQS]
    end

    subgraph "External APIs"
        GOOGLE[Google OAuth]
        ALPHA[Alpha Vantage]
        YAHOO[Yahoo Finance]
    end

    subgraph "Monitoring"
        LOGS[CloudWatch Logs]
        METRICS[CloudWatch Metrics]
        ALERTS[CloudWatch Alarms]
    end

    WEB --> ALB
    MOBILE --> ALB
    API_CLIENT --> ALB
    
    ALB --> RATE_LIMIT
    RATE_LIMIT --> API
    
    API --> AUTH_SVC
    API --> PRED_SVC
    API --> SETTLE_SVC
    API --> POINTS_SVC
    API --> REWARDS_SVC
    
    AUTH_SVC --> PG
    PRED_SVC --> PG
    SETTLE_SVC --> PG
    POINTS_SVC --> PG
    REWARDS_SVC --> PG
    
    API --> SQS
    BATCH --> SQS
    WORKER --> SQS
    
    BATCH --> PG
    WORKER --> PG
    
    AUTH_SVC --> GOOGLE
    BATCH --> ALPHA
    BATCH --> YAHOO
    
    API --> LOGS
    BATCH --> LOGS
    WORKER --> LOGS
    
    API --> METRICS
    BATCH --> METRICS
    WORKER --> METRICS
```

### 2.2 데이터 플로우 다이어그램

```mermaid
sequenceDiagram
    participant U as User
    participant API as FastAPI
    participant DB as PostgreSQL
    participant SQS as AWS SQS
    participant BATCH as Batch Worker
    participant EXT as External API

    Note over U,EXT: Daily Session Lifecycle

    %% Morning: Universe Selection & Session Open
    BATCH->>EXT: Fetch market data
    BATCH->>DB: Update active_universe
    BATCH->>DB: Set session to PREDICT
    
    %% Day: User Predictions
    U->>API: Submit prediction
    API->>DB: Validate constraints
    API->>DB: Store prediction
    API->>SQS: Send prediction event
    
    %% Evening: Prediction Cutoff
    BATCH->>DB: Set session to CLOSED
    
    %% Night: Settlement
    BATCH->>EXT: Fetch EOD prices
    BATCH->>DB: Store EOD data
    BATCH->>SQS: Send settlement event
    SQS->>BATCH: Process settlement
    BATCH->>DB: Compute outcomes
    BATCH->>DB: Award points
    BATCH->>DB: Set session to SETTLING
```

### 2.3 데이터베이스 ERD

```mermaid
erDiagram
    users {
        bigint id PK
        text email UK
        text nickname
        text password_hash
        text auth_provider
        text provider_id
        timestamptz created_at
        timestamptz last_login_at
    }

    oauth_states {
        text state PK
        text redirect_uri
        timestamptz created_at
        timestamptz expires_at
    }

    session_control {
        date trading_day PK
        phase phase
        timestamptz predict_open_at
        timestamptz predict_cutoff_at
        timestamptz settle_ready_at
        timestamptz settled_at
    }

    active_universe {
        date trading_day PK
        text symbol PK
        smallint seq
    }

    predictions {
        bigint id PK
        date trading_day
        bigint user_id FK
        text symbol
        choice choice
        timestamptz submitted_at
        timestamptz locked_at
    }

    settlements {
        date trading_day PK
        text symbol PK
        outcome outcome
        numeric close_price
        numeric prev_close_price
        numeric price_change_percent
        text void_reason
        timestamptz computed_at
    }

    eod_prices {
        date asof PK
        text symbol PK
        numeric close_price
        numeric prev_close_price
        int vendor_rev PK
        timestamptz fetched_at
    }

    points_ledger {
        bigint id PK
        bigint user_id FK
        date trading_day
        text symbol
        bigint delta_points
        text reason
        text ref_id UK
        bigint balance_after
        timestamptz created_at
    }

    rewards_inventory {
        text sku PK
        text title
        int cost_points
        int stock
        int reserved
        text vendor
        timestamptz created_at
        timestamptz updated_at
    }

    rewards_redemptions {
        bigint id PK
        bigint user_id FK
        text sku FK
        int cost_points
        redemption_status status
        text vendor_code
        timestamptz created_at
        timestamptz updated_at
    }

    user_daily_stats {
        bigint user_id FK,PK
        date trading_day PK
        smallint predictions_made
        smallint max_predictions
        timestamptz created_at
        timestamptz updated_at
    }

    ad_unlocks {
        bigint id PK
        bigint user_id FK
        date trading_day
        text method
        smallint unlocked_slots
        timestamptz created_at
    }

    users ||--o{ predictions : "makes"
    users ||--o{ points_ledger : "owns"
    users ||--o{ rewards_redemptions : "redeems"
    users ||--o{ user_daily_stats : "has"
    users ||--o{ ad_unlocks : "unlocks"
    
    active_universe ||--o{ predictions : "contains"
    active_universe ||--o{ settlements : "settles"
    
    predictions ||--o{ settlements : "settles_to"
    settlements ||--o{ points_ledger : "awards"
    
    rewards_inventory ||--o{ rewards_redemptions : "redeemed_as"
```

## 3. 핵심 구현 가이드

### 3.1 애플리케이션 진입점 (app/main.py)

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.api.v1.router import api_router
from app.api.internal.router import internal_router
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.logging import LoggingMiddleware
from app.database.connection import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    yield
    # Shutdown
    pass


def create_app() -> FastAPI:
    app = FastAPI(
        title="O/X Prediction API",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
        redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
    )

    # Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(LoggingMiddleware)

    # Routers
    app.include_router(api_router, prefix="/v1")
    app.include_router(internal_router, prefix="/internal")

    return app


app = create_app()
```

### 3.2 환경 설정 (app/config.py)

```python
from pydantic_settings import BaseSettings
from typing import List, Optional
import os


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "OX Prediction API"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    
    # Database
    DATABASE_URL: str
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    
    # Security
    SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    
    # OAuth
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    OAUTH_STATE_EXPIRE_MINUTES: int = 10
    
    # External APIs
    ALPHA_VANTAGE_API_KEY: str
    EOD_FETCH_RETRY_COUNT: int = 3
    
    # AWS
    AWS_REGION: str = "ap-northeast-2"
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    SQS_ENDPOINT_URL: Optional[str] = None
    
    # Queue Names
    SQS_EOD_FETCH_QUEUE: str = "ox-eod-fetch"
    SQS_SETTLEMENT_QUEUE: str = "ox-settlement"
    SQS_POINTS_AWARD_QUEUE: str = "ox-points-award"
    
    # Business Rules
    POINTS_WIN_REWARD: int = 100
    POINTS_VOID_REWARD: int = 0
    BASE_PREDICTION_SLOTS: int = 3
    MAX_AD_SLOTS: int = 7
    COOLDOWN_MINUTES: int = 5
    
    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = 60
    
    # CORS
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "https://yourapp.com"]
    
    # Timezone
    TIMEZONE: str = "Asia/Seoul"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
```

### 3.3 베이스 모델 (app/models/base.py)

```python
from sqlalchemy import Column, DateTime, func
from sqlalchemy.ext.declarative import declarative_base, declared_attr
from sqlalchemy.orm import Session
from typing import TypeVar, Generic

Base = declarative_base()
ModelType = TypeVar("ModelType", bound=Base)


class TimestampMixin:
    """타임스탬프 필드를 위한 믹스인"""
    
    @declared_attr
    def created_at(cls):
        return Column(DateTime(timezone=True), server_default=func.now())
    
    @declared_attr
    def updated_at(cls):
        return Column(
            DateTime(timezone=True), 
            server_default=func.now(), 
            onupdate=func.now()
        )


class BaseModel(Base, TimestampMixin):
    """모든 모델의 베이스 클래스"""
    __abstract__ = True

    def dict(self):
        """모델을 딕셔너리로 변환"""
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }
```

### 3.4 베이스 서비스 (app/services/base.py)

```python
from abc import ABC, abstractmethod
from typing import TypeVar, Generic, Optional, List, Dict, Any
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.core.exceptions import ServiceException

T = TypeVar('T')


class BaseService(Generic[T], ABC):
    """모든 서비스의 베이스 클래스"""
    
    def __init__(self, db: Session = None):
        self.db = db or next(get_db())
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.db.rollback()
        else:
            self.db.commit()
        self.db.close()


class CRUDService(BaseService[T]):
    """CRUD 작업을 위한 베이스 서비스"""
    
    def __init__(self, model_class: type, db: Session = None):
        super().__init__(db)
        self.model_class = model_class
    
    def get(self, id: Any) -> Optional[T]:
        """ID로 단일 레코드 조회"""
        return self.db.query(self.model_class).filter(
            self.model_class.id == id
        ).first()
    
    def get_multi(
        self, 
        skip: int = 0, 
        limit: int = 100,
        filters: Dict[str, Any] = None
    ) -> List[T]:
        """다중 레코드 조회"""
        query = self.db.query(self.model_class)
        
        if filters:
            for key, value in filters.items():
                if hasattr(self.model_class, key):
                    query = query.filter(getattr(self.model_class, key) == value)
        
        return query.offset(skip).limit(limit).all()
    
    def create(self, obj_in: Dict[str, Any]) -> T:
        """새 레코드 생성"""
        db_obj = self.model_class(**obj_in)
        self.db.add(db_obj)
        self.db.flush()
        self.db.refresh(db_obj)
        return db_obj
    
    def update(self, db_obj: T, obj_in: Dict[str, Any]) -> T:
        """기존 레코드 업데이트"""
        for field, value in obj_in.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)
        
        self.db.add(db_obj)
        self.db.flush()
        self.db.refresh(db_obj)
        return db_obj
    
    def delete(self, id: Any) -> bool:
        """레코드 삭제"""
        obj = self.get(id)
        if obj:
            self.db.delete(obj)
            return True
        return False
```

### 3.5 베이스 리포지토리 (app/repositories/base.py)

```python
from abc import ABC, abstractmethod
from typing import TypeVar, Generic, Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

T = TypeVar('T')


class BaseRepository(Generic[T], ABC):
    """모든 리포지토리의 베이스 클래스"""
    
    def __init__(self, model_class: type, db: Session):
        self.model_class = model_class
        self.db = db
    
    def get_by_id(self, id: Any) -> Optional[T]:
        """ID로 조회"""
        return self.db.query(self.model_class).filter(
            self.model_class.id == id
        ).first()
    
    def get_by_field(self, field_name: str, value: Any) -> Optional[T]:
        """특정 필드로 조회"""
        return self.db.query(self.model_class).filter(
            getattr(self.model_class, field_name) == value
        ).first()
    
    def find_all(
        self,
        filters: Dict[str, Any] = None,
        order_by: str = None,
        limit: int = None,
        offset: int = None
    ) -> List[T]:
        """조건에 맞는 모든 레코드 조회"""
        query = self.db.query(self.model_class)
        
        if filters:
            for key, value in filters.items():
                if hasattr(self.model_class, key):
                    query = query.filter(getattr(self.model_class, key) == value)
        
        if order_by and hasattr(self.model_class, order_by):
            query = query.order_by(getattr(self.model_class, order_by))
        
        if offset:
            query = query.offset(offset)
        
        if limit:
            query = query.limit(limit)
        
        return query.all()
    
    def create(self, **kwargs) -> T:
        """새 레코드 생성"""
        instance = self.model_class(**kwargs)
        self.db.add(instance)
        self.db.flush()
        self.db.refresh(instance)
        return instance
    
    def update(self, instance: T, **kwargs) -> T:
        """레코드 업데이트"""
        for key, value in kwargs.items():
            if hasattr(instance, key):
                setattr(instance, key, value)
        
        self.db.add(instance)
        self.db.flush()
        self.db.refresh(instance)
        return instance
    
    def delete(self, instance: T) -> bool:
        """레코드 삭제"""
        try:
            self.db.delete(instance)
            self.db.flush()
            return True
        except Exception:
            return False
    
    def count(self, filters: Dict[str, Any] = None) -> int:
        """레코드 수 조회"""
        query = self.db.query(self.model_class)
        
        if filters:
            for key, value in filters.items():
                if hasattr(self.model_class, key):
                    query = query.filter(getattr(self.model_class, key) == value)
        
        return query.count()
    
    def exists(self, filters: Dict[str, Any]) -> bool:
        """레코드 존재 여부 확인"""
        query = self.db.query(self.model_class)
        
        for key, value in filters.items():
            if hasattr(self.model_class, key):
                query = query.filter(getattr(self.model_class, key) == value)
        
        return query.first() is not None
```

## 4. 배치 작업 아키텍처

### 4.1 배치 스케줄러 (batch/scheduler.py)

```python
import asyncio
import schedule
import time
from datetime import datetime, timezone
from typing import Dict, List, Callable
from app.core.config import settings
from app.utils.datetime import get_kst_now
from batch.jobs.daily_universe import DailyUniverseJob
from batch.jobs.session_control import SessionControlJob
from batch.jobs.eod_fetch import EODFetchJob
from batch.jobs.settlement import SettlementJob


class BatchScheduler:
    """배치 작업 스케줄러"""
    
    def __init__(self):
        self.jobs: Dict[str, Callable] = {
            "daily_universe": DailyUniverseJob(),
            "session_control": SessionControlJob(),
            "eod_fetch": EODFetchJob(),
            "settlement": SettlementJob(),
        }
        self.setup_schedules()
    
    def setup_schedules(self):
        """배치 스케줄 설정 (KST 기준)"""
        
        # 05:30 KST - 일일 종목 선정 및 세션 OPEN
        schedule.every().day.at("05:30").do(
            self.run_job, "daily_universe_and_session_open"
        )
        
        # 22:00 KST - 예측 마감
        schedule.every().day.at("22:00").do(
            self.run_job, "prediction_cutoff"
        )
        
        # 06:00 KST - EOD 데이터 수집 및 정산
        schedule.every().day.at("06:00").do(
            self.run_job, "eod_and_settlement"
        )
        
        # 매시간 정각 - 헬스 체크
        schedule.every().hour.at(":00").do(
            self.run_job, "health_check"
        )
    
    async def run_job(self, job_name: str):
        """개별 작업 실행"""
        try:
            if job_name == "daily_universe_and_session_open":
                await self.jobs["daily_universe"].run()
                await self.jobs["session_control"].open_session()
            
            elif job_name == "prediction_cutoff":
                await self.jobs["session_control"].cutoff_predictions()
            
            elif job_name == "eod_and_settlement":
                await self.jobs["eod_fetch"].run()
                await self.jobs["settlement"].run()
                await self.jobs["session_control"].complete_settlement()
            
            elif job_name == "health_check":
                await self.health_check()
            
            print(f"✅ Job {job_name} completed at {get_kst_now()}")
            
        except Exception as e:
            print(f"❌ Job {job_name} failed: {str(e)}")
            # 알림 발송 로직 추가
    
    async def health_check(self):
        """시스템 헬스 체크"""
        # DB 연결 확인
        # SQS 연결 확인
        # 외부 API 상태 확인
        pass
    
    def run(self):
        """스케줄러 실행"""
        print(f"🚀 Batch scheduler started at {get_kst_now()}")
        
        while True:
            schedule.run_pending()
            time.sleep(60)  # 1분마다 체크


if __name__ == "__main__":
    scheduler = BatchScheduler()
    scheduler.run()
```

### 4.2 SQS 워커 (batch/workers/sqs_worker.py)

```python
import asyncio
import json
from typing import Dict, Any
import boto3
from app.core.config import settings
from app.providers.queue.events import (
    EODFetchEvent,
    SettlementComputeEvent,
    PointsAwardEvent
)


class SQSWorker:
    """SQS 메시지 처리 워커"""
    
    def __init__(self):
        self.sqs = boto3.client(
            'sqs',
            region_name=settings.AWS_REGION,
            endpoint_url=settings.SQS_ENDPOINT_URL
        )
        self.handlers = {
            settings.SQS_EOD_FETCH_QUEUE: self.handle_eod_fetch,
            settings.SQS_SETTLEMENT_QUEUE: self.handle_settlement,
            settings.SQS_POINTS_AWARD_QUEUE: self.handle_points_award,
        }
    
    async def handle_eod_fetch(self, event: EODFetchEvent):
        """EOD 데이터 수집 이벤트 처리"""
        from batch.jobs.eod_fetch import EODFetchJob
        
        job = EODFetchJob()
        await job.fetch_symbols(
            trading_day=event.trading_day,
            symbols=event.symbols,
            provider=event.provider
        )
    
    async def handle_settlement(self, event: SettlementComputeEvent):
        """정산 이벤트 처리"""
        from batch.jobs.settlement import SettlementJob
        
        job = SettlementJob()
        await job.compute_for_day(trading_day=event.trading_day)
    
    async def handle_points_award(self, event: PointsAwardEvent):
        """포인트 지급 이벤트 처리"""
        from app.services.points_service import PointsService
        
        async with PointsService() as service:
            await service.process_settlement_points(
                user_id=event.user_id,
                trading_day=event.trading_day
            )
    
    async def process_queue(self, queue_name: str):
        """큐에서 메시지 처리"""
        queue_url = await self.get_queue_url(queue_name)
        
        while True:
            try:
                response = self.sqs.receive_message(
                    QueueUrl=queue_url,
                    MaxNumberOfMessages=10,
                    WaitTimeSeconds=20,
                    VisibilityTimeoutSeconds=300
                )
                
                messages = response.get('Messages', [])
                
                for message in messages:
                    try:
                        # 메시지 처리
                        body = json.loads(message['Body'])
                        await self.route_message(queue_name, body)
                        
                        # 메시지 삭제
                        self.sqs.delete_message(
                            QueueUrl=queue_url,
                            ReceiptHandle=message['ReceiptHandle']
                        )
                        
                    except Exception as e:
                        print(f"Error processing message: {e}")
                        # DLQ로 이동 로직
                
            except Exception as e:
                print(f"Error receiving messages: {e}")
                await asyncio.sleep(5)
    
    async def route_message(self, queue_name: str, body: Dict[str, Any]):
        """메시지를 적절한 핸들러로 라우팅"""
        handler = self.handlers.get(queue_name)
        if handler:
            await handler(body)
        else:
            print(f"No handler for queue: {queue_name}")
    
    async def get_queue_url(self, queue_name: str) -> str:
        """큐 URL 조회"""
        response = self.sqs.get_queue_url(QueueName=queue_name)
        return response['QueueUrl']
    
    async def run(self, queues: List[str]):
        """워커 실행"""
        tasks = [
            asyncio.create_task(self.process_queue(queue))
            for queue in queues
        ]
        
        await asyncio.gather(*tasks)


if __name__ == "__main__":
    worker = SQSWorker()
    asyncio.run(worker.run([
        settings.SQS_EOD_FETCH_QUEUE,
        settings.SQS_SETTLEMENT_QUEUE,
        settings.SQS_POINTS_AWARD_QUEUE,
    ]))
```

## 5. 배포 구성

### 5.1 Docker Compose (docker-compose.yaml)

```yaml
version: '3.8'

services:
  app:
    build: 
      context: .
      dockerfile: infra/docker/Dockerfile.app
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://postgres:password@db:5432/oxprediction
      - ENVIRONMENT=development
    depends_on:
      - db
      - localstack
    volumes:
      - .:/app
    
  batch:
    build: 
      context: .
      dockerfile: infra/docker/Dockerfile.batch
    environment:
      - DATABASE_URL=postgresql://postgres:password@db:5432/oxprediction
      - ENVIRONMENT=development
    depends_on:
      - db
      - localstack
    volumes:
      - .:/app
  
  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=oxprediction
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./scripts/init_db.sql:/docker-entrypoint-initdb.d/init_db.sql
  
  localstack:
    image: localstack/localstack:latest
    ports:
      - "4566:4566"
    environment:
      - SERVICES=sqs
      - DEBUG=1
      - DATA_DIR=/tmp/localstack/data
    volumes:
      - localstack_data:/tmp/localstack
      - ./scripts/setup_sqs.sh:/etc/localstack/init/ready.d/setup_sqs.sh
  
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./infra/nginx/nginx.conf:/etc/nginx/nginx.conf
      - ./infra/nginx/ssl:/etc/nginx/ssl
    depends_on:
      - app

volumes:
  postgres_data:
  localstack_data:
```

### 5.2 애플리케이션 Dockerfile (infra/docker/Dockerfile.app)

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# 시스템 패키지 설치
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 복사
COPY . .

# 환경 변수 설정
ENV PYTHONPATH=/app
ENV ENVIRONMENT=production

# 헬스체크
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 포트 노출
EXPOSE 8000

# 실행 명령
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 5.3 배치 Dockerfile (infra/docker/Dockerfile.batch)

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# 시스템 패키지 설치
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    cron \
    && rm -rf /var/lib/apt/lists/*

# Python 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 복사
COPY . .

# 환경 변수 설정
ENV PYTHONPATH=/app
ENV ENVIRONMENT=production

# 크론탭 설정
COPY infra/docker/crontab /etc/cron.d/batch-jobs
RUN chmod 0644 /etc/cron.d/batch-jobs
RUN crontab /etc/cron.d/batch-jobs

# 실행 명령 (스케줄러와 워커를 함께 실행)
CMD ["python", "batch/main.py"]
```

## 6. 프로젝트 초기화 스크립트

### 6.1 설정 스크립트 (scripts/setup_project.py)

```python
#!/usr/bin/env python3

import os
import subprocess
import sys
from pathlib import Path


def create_folder_structure():
    """폴더 구조 생성"""
    folders = [
        "app/core",
        "app/models", 
        "app/schemas",
        "app/api/v1",
        "app/api/internal",
        "app/services",
        "app/repositories", 
        "app/providers/oauth",
        "app/providers/eod",
        "app/providers/queue",
        "app/middleware",
        "app/utils",
        "app/database",
        "batch/jobs",
        "batch/workers",
        "alembic/versions",
        "tests/unit/services",
        "tests/unit/repositories",
        "tests/integration/api",
        "tests/integration/batch",
        "docs/api",
        "docs/architecture", 
        "docs/deployment",
        "scripts",
        "infra/docker",
        "infra/kubernetes"
    ]
    
    for folder in folders:
        Path(folder).mkdir(parents=True, exist_ok=True)
        # __init__.py 파일 생성
        if folder.startswith(('app/', 'batch/', 'tests/')):
            init_file = Path(folder) / "__init__.py"
            init_file.touch(exist_ok=True)
    
    print("✅ Folder structure created")


def create_env_file():
    """환경 변수 파일 생성"""
    env_content = """
# Application
APP_NAME="OX Prediction API"
ENVIRONMENT=development
DEBUG=true
SECRET_KEY=your-secret-key-here

# Database
DATABASE_URL=postgresql://postgres:password@localhost:5432/oxprediction

# OAuth
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret

# External APIs
ALPHA_VANTAGE_API_KEY=your-alpha-vantage-key

# AWS
AWS_REGION=ap-northeast-2
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
SQS_ENDPOINT_URL=http://localhost:4566

# Queue Names
SQS_EOD_FETCH_QUEUE=ox-eod-fetch
SQS_SETTLEMENT_QUEUE=ox-settlement
SQS_POINTS_AWARD_QUEUE=ox-points-award

# Business Rules
POINTS_WIN_REWARD=100
BASE_PREDICTION_SLOTS=3
MAX_AD_SLOTS=7

# CORS
ALLOWED_ORIGINS=["http://localhost:3000","https://yourapp.com"]
"""
    
    with open(".env.example", "w") as f:
        f.write(env_content.strip())
    
    print("✅ .env.example file created")


def create_requirements():
    """requirements.txt 생성"""
    requirements = """
fastapi==0.104.1
uvicorn[standard]==0.24.0
pydantic==2.5.0
pydantic-settings==2.1.0
sqlalchemy==2.0.23
alembic==1.13.1
psycopg2-binary==2.9.9
python-jose[cryptography]==3.3.0
python-multipart==0.0.6
passlib[bcrypt]==1.7.4
httpx==0.25.2
boto3==1.34.0
schedule==1.2.0
pytest==7.4.3
pytest-asyncio==0.21.1
black==23.11.0
isort==5.12.0
flake8==6.1.0
"""
    
    with open("requirements.txt", "w") as f:
        f.write(requirements.strip())
    
    print("✅ requirements.txt created")


def setup_git():
    """Git 설정"""
    gitignore_content = """
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Environment
.env
.env.local
.env.*.local
venv/
env/
ENV/

# IDE
.vscode/
.idea/
*.swp
*.swo

# Database
*.db
*.sqlite3

# Logs
logs/
*.log

# OS
.DS_Store
Thumbs.db

# Testing
.coverage
.pytest_cache/
htmlcov/

# Deployment
*.tar.gz
*.zip
"""
    
    with open(".gitignore", "w") as f:
        f.write(gitignore_content.strip())
    
    print("✅ .gitignore created")


def main():
    """메인 실행 함수"""
    print("🚀 Setting up OX Prediction project...")
    
    create_folder_structure()
    create_env_file()
    create_requirements()
    setup_git()
    
    print("\n✅ Project setup completed!")
    print("\nNext steps:")
    print("1. Copy .env.example to .env and update values")
    print("2. Run: pip install -r requirements.txt")
    print("3. Run: docker-compose up -d")
    print("4. Run: alembic upgrade head")
    print("5. Start development: uvicorn app.main:app --reload")


if __name__ == "__main__":
    main()
```

이 구현 가이드는 ox_design.md 문서를 기반으로 한 완전한 프로젝트 아키텍처와 폴더 구조를 제공합니다. 이제 이 가이드를 따라 단계별로 구현을 진행할 수 있습니다.

핵심 특징:
1. **레이어드 아키텍처**: API → Service → Repository → Model 구조
2. **도메인 중심 설계**: 각 도메인별로 명확한 책임 분리
3. **배치 작업 분리**: API와 배치 워커의 명확한 분리
4. **테스트 친화적**: 의존성 주입과 추상화를 통한 테스트 용이성
5. **확장 가능성**: 새로운 기능 추가가 용이한 구조
6. **운영 고려**: 모니터링, 로깅, 헬스체크 포함
