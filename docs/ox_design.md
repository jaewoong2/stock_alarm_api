# 미국주식 O/X 예측 서비스 - 설계 문서

## 1. 시스템 개요

### 1.1 서비스 목적

- 미국 주식 종목에 대한 O/X(상승/하락) 예측 참여
- 정산 후 포인트 지급 및 리워드 교환 시스템
- 매일 약 10개 종목 선정, 장 마감 후 ~ 다음 개장 전 예측 접수

### 1.2 기술 스택

- **Backend**: FastAPI + Python 3.12
- **Database**: PostgreSQL (crypto 스키마만 사용)
- **Queue**: AWS SQS (FIFO 큐)
- **Storage**: AWS S3 (선택사항)
- **Cache**: Redis 없음 (PostgreSQL로 대체)
- **Time Zone**: KST 기준 운영
- **외부 API**: 종가 데이터 제공 API (Alpha Vantage, Yahoo Finance 등)

### 1.3 세션 모델 (2-Phase)

- `PREDICT`: 시장 종료 후 → 다음 개장 직전 (예측 접수)
- `SETTLE`: 장 마감 후 EOD 확정 → 정산/포인트 지급

## 2. API 인터페이스 설계

### 2.1 공통 규약

#### 2.1.1 응답 포맷

```python
class BaseResponse(BaseModel):
    success: bool = True
    data: Optional[Any] = None
    error: Optional[Error] = None
    meta: Optional[dict] = None

class Error(BaseModel):
    code: str
    message: str
    details: Optional[dict] = None
```

#### 2.1.2 에러 코드 체계

```python
class ErrorCode(str, Enum):
    # 예측 관련
    PREDICTION_CUTOFF = "PRED_001"      # 예측 제출 시간 초과
    SLOT_EXCEEDED = "PRED_002"          # 예측 슬롯 초과
    COOLDOWN_ACTIVE = "PRED_003"        # 쿨다운 중
    NOT_IN_UNIVERSE = "PRED_004"        # 오늘의 종목에 없음
    DUPLICATE_PREDICTION = "PRED_005"   # 중복 예측

    # 시스템 관련
    RATE_LIMITED = "SYS_429"            # 레이트 리밋
    UNAUTHORIZED = "AUTH_401"           # 인증 실패
    FORBIDDEN = "AUTH_403"              # 권한 없음
    NOT_FOUND = "SYS_404"              # 리소스 없음
    INTERNAL_ERROR = "SYS_500"         # 내부 오류

    # 포인트 관련
    INSUFFICIENT_POINTS = "POINT_001"   # 포인트 부족
    POINT_HOLD_FAILED = "POINT_002"     # 포인트 보류 실패

    # 리워드 관련
    REWARD_OUT_OF_STOCK = "REWARD_001"  # 재고 부족
    REWARD_ALREADY_REDEEMED = "REWARD_002" # 이미 교환됨

    # OAuth 관련
    OAUTH_INVALID_CODE = "OAUTH_001"    # OAuth 코드 무효
    OAUTH_STATE_MISMATCH = "OAUTH_002"  # OAuth state 불일치
```

#### 2.1.3 인증

```python
# JWT Bearer Token
Authorization: Bearer <jwt_token>

# OAuth2 Authorization Code Flow
GET /v1/auth/oauth/google?redirect_uri=<uri>
POST /v1/auth/oauth/callback

# 멱등성 키 (선택사항)
Idempotency-Key: <uuid>
```

#### 2.1.4 시간 포맷

- 모든 timestamp는 KST 기준 ISO8601 포맷
- 예: `2025-08-18T22:30:00+09:00`

### 2.2 엔드포인트 명세

#### 2.2.1 인증/사용자 (Auth/Users)

```python
# 일반 회원가입
POST /v1/auth/signup
Content-Type: application/json

{
    "email": "user@example.com",
    "password": "password123",
    "nickname": "user123"
}

Response 201:
{
    "success": true,
    "data": {
        "user_id": 12345,
        "token": "jwt_token_here",
        "nickname": "user123"
    }
}

# 일반 로그인
POST /v1/auth/login
{
    "email": "user@example.com",
    "password": "password123"
}

Response 200:
{
    "success": true,
    "data": {
        "user_id": 12345,
        "token": "jwt_token_here",
        "nickname": "user123"
    }
}

# OAuth 로그인 - Google
GET /v1/auth/oauth/google?redirect_uri=<encoded_uri>&state=<state>

Response 302: Redirect to Google OAuth

# OAuth 콜백
POST /v1/auth/oauth/callback
{
    "provider": "google",
    "code": "oauth_authorization_code",
    "state": "state_value",
    "redirect_uri": "https://yourapp.com/callback"
}

Response 200:
{
    "success": true,
    "data": {
        "user_id": 12345,
        "token": "jwt_token_here",
        "nickname": "user123",
        "is_new_user": false
    }
}

# 사용자 정보 조회
GET /v1/users/me
Authorization: Bearer <token>

Response 200:
{
    "success": true,
    "data": {
        "user_id": 12345,
        "email": "user@example.com",
        "nickname": "user123",
        "auth_provider": "google",
        "created_at": "2025-08-18T10:00:00+09:00"
    }
}
```

#### 2.2.2 세션 관리 (Session)

```python
# 오늘의 세션 상태 조회
GET /v1/session/today

Response 200:
{
    "success": true,
    "data": {
        "trading_day": "2025-08-18",
        "phase": "PREDICT",  # PREDICT | SETTLE
        "predict_open_at": "2025-08-18T06:05:00+09:00",
        "predict_cutoff_at": "2025-08-18T22:30:00+09:00",
        "settled_at": null
    }
}

# 내부 API - 예측 단계로 전환
POST /internal/session/flip-to-predict
{
    "trading_day": "2025-08-18"
}

Response 204: No Content

# 내부 API - 예측 마감
POST /internal/session/cutoff
{
    "trading_day": "2025-08-18"
}

Response 204: No Content
```

#### 2.2.3 종목 유니버스 (Universe)

```python
# 오늘의 종목 목록 조회
GET /v1/universe/today

Response 200:
{
    "success": true,
    "data": [
        {"symbol": "AAPL", "seq": 1},
        {"symbol": "MSFT", "seq": 2},
        {"symbol": "GOOGL", "seq": 3}
    ]
}

# 내부 API - 종목 목록 업데이트
POST /internal/universe/upsert
{
    "trading_day": "2025-08-18",
    "symbols": [
        {"symbol": "AAPL", "seq": 1},
        {"symbol": "MSFT", "seq": 2}
    ]
}

Response 204: No Content
```

#### 2.2.4 예측 (Predictions)

```python
# 예측 제출
POST /v1/predictions/{symbol}
Authorization: Bearer <token>
Idempotency-Key: <uuid>

{
    "choice": "UP"  # UP | DOWN
}

Response 202:
{
    "success": true,
    "data": {
        "status": "accepted",
        "trading_day": "2025-08-18",
        "symbol": "AAPL",
        "choice": "UP",
        "submitted_at": "2025-08-18T15:30:00+09:00"
    }
}

# 에러 예시 - 컷오프 시간 초과
Response 400:
{
    "success": false,
    "error": {
        "code": "PRED_001",
        "message": "예측 제출 가능 시간이 아닙니다.",
        "details": {
            "cutoff_at": "2025-08-18T22:30:00+09:00"
        }
    }
}
```

#### 2.2.5 정산 (Settlements)

```python
# 정산 결과 조회
GET /v1/settlements/{trading_day}

Response 200:
{
    "success": true,
    "data": [
        {
            "trading_day": "2025-08-18",
            "symbol": "AAPL",
            "outcome": "UP",  # UP | DOWN | VOID
            "close_price": "150.25",
            "prev_close_price": "149.50",
            "computed_at": "2025-08-19T06:10:00+09:00"
        }
    ]
}

# 내부 API - 정산 실행
POST /internal/settlement/run
{
    "trading_day": "2025-08-18"
}

Response 202: Accepted

# 내부 API - EOD 가격 데이터 수집 (배치)
POST /internal/eod/fetch
{
    "trading_day": "2025-08-18",
    "symbols": ["AAPL", "MSFT", "GOOGL"]
}

Response 202: Accepted
```

#### 2.2.6 포인트 (Points)

```python
# 포인트 잔액 조회
GET /v1/points/balance
Authorization: Bearer <token>

Response 200:
{
    "success": true,
    "data": {
        "balance": 1500
    }
}

# 포인트 내역 조회
GET /v1/points/ledger?limit=50&offset=0
Authorization: Bearer <token>

Response 200:
{
    "success": true,
    "data": [
        {
            "id": 123,
            "trading_day": "2025-08-18",
            "symbol": "AAPL",
            "delta_points": 100,
            "reason": "SETTLEMENT_WIN",
            "ref_type": "SETTLEMENT",
            "ref_id": "2025-08-18:AAPL:12345",
            "balance_after": 1500,
            "created_at": "2025-08-19T06:15:00+09:00"
        }
    ],
    "meta": {
        "total": 25,
        "limit": 50,
        "offset": 0
    }
}
```

#### 2.2.7 리워드 (Rewards)

```python
# 리워드 카탈로그 조회
GET /v1/rewards/catalog

Response 200:
{
    "success": true,
    "data": [
        {
            "sku": "GIFT_CARD_10",
            "title": "10달러 기프트카드",
            "cost_points": 1000,
            "stock": 50
        }
    ]
}

# 리워드 교환
POST /v1/rewards/redeem
Authorization: Bearer <token>

{
    "sku": "GIFT_CARD_10",
    "cost_points": 1000
}

Response 202:
{
    "success": true,
    "data": {
        "status": "accepted",
        "redemption_id": 67890
    }
}
```

#### 2.2.8 광고/성장 (Ads/Growth)

```python
# 광고 상태 조회
GET /v1/ads/status
Authorization: Bearer <token>

Response 200:
{
    "success": true,
    "data": {
        "can_unlock": true,
        "cooldown_min": 5,
        "today": {
            "base_slots": 3,
            "used_slots": 2,
            "ad_slots_used": 1,
            "ad_slots_max": 7
        },
        "cooldown_until": null
    }
}

# 추가 슬롯 해제
POST /v1/ads/unlock
Authorization: Bearer <token>

{
    "method": "AD"  # AD | COOLDOWN
}

Response 200:
{
    "success": true,
    "data": {
        "unlocked_slots": 1,
        "used_slots": 2,
        "ad_slots_used": 2
    }
}
```

## 3. 데이터 모델 설계

### 3.1 데이터베이스 스키마 (crypto 스키마만 사용)

```sql
-- 기본 스키마 생성
CREATE SCHEMA IF NOT EXISTS crypto;

-- 사용자 테이블 (OAuth 지원)
CREATE TABLE IF NOT EXISTS crypto.users (
    id bigserial PRIMARY KEY,
    email text UNIQUE NOT NULL,
    nickname text NOT NULL,
    password_hash text, -- OAuth 사용자는 NULL 가능
    auth_provider text DEFAULT 'local', -- 'local' | 'google' | 'kakao'
    provider_id text, -- OAuth 제공업체 사용자 ID
    created_at timestamptz DEFAULT now(),
    last_login_at timestamptz,
    UNIQUE(auth_provider, provider_id)
);

-- OAuth 상태 관리 (임시 테이블)
CREATE TABLE IF NOT EXISTS crypto.oauth_states (
    state text PRIMARY KEY,
    redirect_uri text NOT NULL,
    created_at timestamptz DEFAULT now(),
    expires_at timestamptz NOT NULL
);

-- 세션 컨트롤 (2-Phase)
CREATE TYPE crypto.phase AS ENUM ('PREDICT', 'SETTLE');

CREATE TABLE IF NOT EXISTS crypto.session_control (
    trading_day date PRIMARY KEY,
    phase crypto.phase NOT NULL,
    predict_open_at timestamptz NOT NULL,
    predict_cutoff_at timestamptz NOT NULL,
    settle_ready_at timestamptz,
    settled_at timestamptz,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

-- 활성 유니버스 (오늘의 종목 ~10개)
CREATE TABLE IF NOT EXISTS crypto.active_universe (
    trading_day date NOT NULL,
    symbol text NOT NULL,
    seq smallint NOT NULL,
    PRIMARY KEY (trading_day, symbol)
);

-- 예측
CREATE TYPE crypto.choice AS ENUM ('UP', 'DOWN');

CREATE TABLE IF NOT EXISTS crypto.predictions (
    id bigserial PRIMARY KEY,
    trading_day date NOT NULL,
    user_id bigint NOT NULL REFERENCES crypto.users(id),
    symbol text NOT NULL,
    choice crypto.choice NOT NULL,
    submitted_at timestamptz NOT NULL DEFAULT now(),
    locked_at timestamptz,
    trading_day_kst date GENERATED ALWAYS AS ((submitted_at AT TIME ZONE 'Asia/Seoul')::date) STORED,
    UNIQUE (trading_day, user_id, symbol)
);

-- 정산 결과
CREATE TYPE crypto.outcome AS ENUM ('UP', 'DOWN', 'VOID');

CREATE TABLE IF NOT EXISTS crypto.settlements (
    trading_day date NOT NULL,
    symbol text NOT NULL,
    outcome crypto.outcome NOT NULL,
    close_price numeric(18,6) NOT NULL,
    prev_close_price numeric(18,6) NOT NULL,
    computed_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (trading_day, symbol)
);

-- EOD 가격 스냅샷 (배치로 수집)
CREATE TABLE IF NOT EXISTS crypto.eod_prices (
    asof date NOT NULL,
    symbol text NOT NULL,
    close_price numeric(18,6) NOT NULL,
    prev_close_price numeric(18,6) NOT NULL,
    vendor_rev int NOT NULL DEFAULT 0,
    fetched_at timestamptz DEFAULT now(), -- 데이터 수집 시간
    PRIMARY KEY (asof, symbol, vendor_rev)
);

-- 포인트 원장 (crypto 스키마 내)
CREATE TABLE IF NOT EXISTS crypto.points_ledger (
    id bigserial PRIMARY KEY,
    user_id bigint NOT NULL REFERENCES crypto.users(id),
    trading_day date,
    symbol text,
    delta_points bigint NOT NULL,
    reason text NOT NULL,
    ref_type text NOT NULL,
    ref_id text NOT NULL,
    balance_after bigint NOT NULL,
    created_at timestamptz DEFAULT now(),
    UNIQUE (ref_type, ref_id)
);

-- 포인트 보류 (Saga 중간상태)
CREATE TYPE crypto.hold_status AS ENUM ('OPEN', 'COMMITTED', 'CANCELLED');

CREATE TABLE IF NOT EXISTS crypto.points_holds (
    id bigserial PRIMARY KEY,
    user_id bigint NOT NULL REFERENCES crypto.users(id),
    amount bigint NOT NULL,
    reason text NOT NULL,
    ref_type text NOT NULL,
    ref_id text NOT NULL,
    status crypto.hold_status NOT NULL DEFAULT 'OPEN',
    created_at timestamptz DEFAULT now(),
    UNIQUE (ref_type, ref_id)
);

-- 리워드 인벤토리 (crypto 스키마 내)
CREATE TABLE IF NOT EXISTS crypto.rewards_inventory (
    sku text PRIMARY KEY,
    title text NOT NULL,
    cost_points int NOT NULL,
    stock int NOT NULL,
    reserved int NOT NULL DEFAULT 0,
    vendor text NOT NULL,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

-- 리워드 교환
CREATE TYPE crypto.redemption_status AS ENUM ('REQUESTED', 'RESERVED', 'ISSUED', 'CANCELLED', 'FAILED');

CREATE TABLE IF NOT EXISTS crypto.rewards_redemptions (
    id bigserial PRIMARY KEY,
    user_id bigint NOT NULL REFERENCES crypto.users(id),
    sku text NOT NULL REFERENCES crypto.rewards_inventory(sku),
    cost_points int NOT NULL,
    status crypto.redemption_status NOT NULL DEFAULT 'REQUESTED',
    vendor_code text,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

-- 사용자 제한 (슬롯/쿨다운)
CREATE TABLE IF NOT EXISTS crypto.user_limits (
    user_id bigint PRIMARY KEY REFERENCES crypto.users(id),
    trading_day date NOT NULL,
    base_slots smallint NOT NULL DEFAULT 3,
    ad_slots_used smallint NOT NULL DEFAULT 0,
    ad_slots_max smallint NOT NULL DEFAULT 7,
    used_slots smallint NOT NULL DEFAULT 0,
    cooldown_until timestamptz,
    updated_at timestamptz DEFAULT now()
);

-- 광고 해제 이력
CREATE TABLE IF NOT EXISTS crypto.ad_unlocks (
    id bigserial PRIMARY KEY,
    user_id bigint NOT NULL REFERENCES crypto.users(id),
    trading_day date NOT NULL,
    method text NOT NULL, -- 'AD' | 'COOLDOWN'
    unlocked_slots smallint NOT NULL DEFAULT 1,
    created_at timestamptz DEFAULT now()
);

-- 레이트 리밋
CREATE TABLE IF NOT EXISTS crypto.rate_limits (
    key text NOT NULL,
    window_start timestamptz NOT NULL,
    window_type text NOT NULL, -- 'minute' | 'hour'
    count int NOT NULL DEFAULT 0,
    max_allowed int NOT NULL,
    expire_at timestamptz NOT NULL,
    PRIMARY KEY(key, window_start, window_type)
);

-- 아웃박스 (이벤트 발행)
CREATE TABLE IF NOT EXISTS crypto.outbox (
    id bigserial PRIMARY KEY,
    topic text NOT NULL,
    payload jsonb NOT NULL,
    published boolean NOT NULL DEFAULT false,
    created_at timestamptz DEFAULT now(),
    published_at timestamptz
);

-- 외부 API 호출 로그 (배치 서비스용)
CREATE TABLE IF NOT EXISTS crypto.eod_fetch_logs (
    id bigserial PRIMARY KEY,
    trading_day date NOT NULL,
    provider text NOT NULL, -- 'alpha_vantage' | 'yahoo_finance'
    symbols text[] NOT NULL,
    status text NOT NULL, -- 'SUCCESS' | 'FAILED' | 'PARTIAL'
    response_data jsonb,
    error_message text,
    fetched_at timestamptz DEFAULT now()
);
```

### 3.2 주요 인덱스

```sql
-- 성능 최적화 인덱스
CREATE INDEX IF NOT EXISTS idx_users_auth_provider ON crypto.users(auth_provider, provider_id);
CREATE INDEX IF NOT EXISTS idx_oauth_states_expires ON crypto.oauth_states(expires_at);
CREATE INDEX IF NOT EXISTS idx_session_control_phase ON crypto.session_control(phase);
CREATE INDEX IF NOT EXISTS idx_predictions_user_day ON crypto.predictions(user_id, trading_day);
CREATE INDEX IF NOT EXISTS idx_predictions_day_kst ON crypto.predictions(trading_day_kst);
CREATE INDEX IF NOT EXISTS idx_settlements_day ON crypto.settlements(trading_day);
CREATE INDEX IF NOT EXISTS idx_eod_prices_asof_symbol ON crypto.eod_prices(asof, symbol);
CREATE INDEX IF NOT EXISTS idx_points_ledger_user ON crypto.points_ledger(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_outbox_published ON crypto.outbox(published, created_at);
CREATE INDEX IF NOT EXISTS idx_rate_limits_expire ON crypto.rate_limits(expire_at);
CREATE INDEX IF NOT EXISTS idx_eod_fetch_logs_day ON crypto.eod_fetch_logs(trading_day, status);
```

## 4. 서비스 계층 설계

### 4.1 핵심 서비스 클래스

```python
from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import datetime, date

class AuthService:
    async def signup(self, email: str, password: str, nickname: str) -> dict
    async def login(self, email: str, password: str) -> dict
    async def oauth_login(self, provider: str, code: str, state: str, redirect_uri: str) -> dict
    async def generate_oauth_state(self, redirect_uri: str) -> str
    async def verify_oauth_state(self, state: str, redirect_uri: str) -> bool

class SessionService:
    async def get_current_session(self) -> SessionModel
    async def flip_to_predict(self, trading_day: date) -> None
    async def cutoff_predictions(self, trading_day: date) -> None

class UniverseService:
    async def get_today_symbols(self) -> List[UniverseItem]
    async def upsert_universe(self, trading_day: date, symbols: List[UniverseItem]) -> None

class PredictionService:
    async def submit_prediction(self, user_id: int, symbol: str, choice: str) -> PredictionResult
    async def validate_prediction_constraints(self, user_id: int, symbol: str) -> None

class SettlementService:
    async def compute_settlements(self, trading_day: date) -> None
    async def get_settlements(self, trading_day: date) -> List[SettlementResult]

class EODService:
    async def fetch_eod_prices(self, trading_day: date, symbols: List[str]) -> None
    async def get_price_from_provider(self, symbol: str, date: date, provider: str) -> dict

class PointsService:
    async def get_balance(self, user_id: int) -> int
    async def get_ledger(self, user_id: int, limit: int, offset: int) -> List[PointsLedgerEntry]
    async def award_points(self, user_id: int, amount: int, reason: str, ref_type: str, ref_id: str) -> None

class RewardsService:
    async def get_catalog(self) -> List[RewardItem]
    async def redeem_reward(self, user_id: int, sku: str, cost_points: int) -> int  # redemption_id

class AdsService:
    async def get_ad_status(self, user_id: int) -> AdStatus
    async def unlock_slot(self, user_id: int, method: str) -> UnlockResult
```

## 5. 이벤트/큐 설계

### 5.1 SQS 큐 구성

```python
SQS_QUEUES = {
    "prediction_submit": {
        "name": "q.prediction.submit.fifo",
        "type": "FIFO",
        "deduplication_scope": "queue",
        "fifo_throughput_limit": "perQueue"
    },
    "settlement_compute": {
        "name": "q.settlement.compute",
        "type": "Standard"
    },
    "eod_fetch": {
        "name": "q.eod.fetch",
        "type": "Standard"
    },
    "points_award": {
        "name": "q.points.award.fifo",
        "type": "FIFO"
    },
    "rewards_saga": {
        "name": "q.rewards.saga",
        "type": "Standard"
    },
    "outbox_publisher": {
        "name": "q.outbox.publisher",
        "type": "Standard"
    }
}
```

### 5.2 이벤트 페이로드 스키마

```python
# 예측 제출 이벤트
class PredictionSubmitEvent(BaseModel):
    user_id: int
    trading_day: str
    symbol: str
    choice: str
    submitted_at: str
    deduplication_id: str  # f"{user_id}:{trading_day}:{symbol}"

# EOD 데이터 수집 이벤트
class EODFetchEvent(BaseModel):
    trading_day: str
    symbols: List[str]
    provider: str  # "alpha_vantage" | "yahoo_finance"
    retry_count: int = 0

# 정산 컴퓨트 이벤트
class SettlementComputeEvent(BaseModel):
    trading_day: str
    trigger_source: str  # "eod_fetched" | "manual"

# 포인트 지급 이벤트
class PointsAwardEvent(BaseModel):
    user_id: int
    trading_day: str
    deduplication_id: str  # f"{user_id}:{trading_day}"

# 리워드 교환 이벤트
class RewardRedeemEvent(BaseModel):
    redemption_id: int
    user_id: int
    sku: str
    cost_points: int
```

## 6. 외부 API 연동 설계

### 6.1 EOD 데이터 제공업체 설정

```python
EOD_PROVIDERS = {
    "alpha_vantage": {
        "api_key": "YOUR_API_KEY",
        "base_url": "https://www.alphavantage.co/query",
        "rate_limit": "5_requests_per_minute",
        "function": "TIME_SERIES_DAILY"
    },
    "yahoo_finance": {
        "base_url": "https://query1.finance.yahoo.com/v8/finance/chart",
        "rate_limit": "100_requests_per_hour",
        "backup": True  # 메인 실패시 백업용
    }
}
```

### 6.2 OAuth 제공업체 설정

```python
OAUTH_PROVIDERS = {
    "google": {
        "client_id": "YOUR_GOOGLE_CLIENT_ID",
        "client_secret": "YOUR_GOOGLE_CLIENT_SECRET",
        "auth_url": "https://accounts.google.com/o/oauth2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "user_info_url": "https://www.googleapis.com/oauth2/v2/userinfo",
        "scope": "openid email profile"
    }
}
```

## 7. 보안 설계

### 7.1 JWT 설정

```python
JWT_SETTINGS = {
    "algorithm": "RS256",
    "access_token_expire_minutes": 60,
    "refresh_token_expire_days": 7,
    "issuer": "ox-prediction-api",
    "audience": "ox-prediction-client"
}
```

### 7.2 OAuth 보안

```python
OAUTH_SECURITY = {
    "state_expire_minutes": 10,
    "csrf_protection": True,
    "secure_redirect": True,
    "allowed_redirect_domains": ["yourapp.com", "localhost"]
}
```

### 7.3 레이트 리밋 정책

```python
RATE_LIMITS = {
    "prediction_submit": {
        "requests_per_minute": 10,
        "requests_per_hour": 50
    },
    "points_balance": {
        "requests_per_minute": 30,
        "requests_per_hour": 200
    },
    "oauth_callback": {
        "requests_per_minute": 5,
        "requests_per_hour": 20
    },
    "global_per_ip": {
        "requests_per_minute": 100,
        "requests_per_hour": 1000
    }
}
```

## 8. 배치 작업 설계

### 8.1 일일 배치 스케줄 (KST 기준)

```python
BATCH_SCHEDULE = {
    "universe_selection": {
        "time": "05:30",  # 장 마감 30분 후
        "description": "오늘의 종목 10개 선정"
    },
    "session_flip_predict": {
        "time": "06:00",  # 장 마감 1시간 후
        "description": "예측 모드로 전환"
    },
    "eod_data_fetch": {
        "time": "06:15",  # 종가 데이터 안정화 대기
        "description": "EOD 가격 데이터 수집"
    },
    "settlement_compute": {
        "time": "06:30",  # EOD 수집 완료 후
        "description": "정산 계산 및 포인트 지급"
    },
    "prediction_cutoff": {
        "time": "22:25",  # 개장 5분 전
        "description": "예측 제출 마감"
    }
}
```

### 8.2 EOD 데이터 수집 배치

```python
class EODBatchService:
    async def fetch_daily_prices(self, trading_day: date, symbols: List[str]):
        """
        1. Alpha Vantage API 호출로 종가 데이터 수집
        2. 실패시 Yahoo Finance 백업 사용
        3. crypto.eod_prices 테이블에 저장
        4. crypto.eod_fetch_logs에 로깅
        5. 성공시 settlement_compute 큐에 이벤트 발행
        """
        pass
```

## 9. 환경 설정

### 9.1 환경 변수

```python
class Settings(BaseSettings):
    # Database
    DATABASE_URL: str
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    # JWT
    JWT_PRIVATE_KEY: str
    JWT_PUBLIC_KEY: str

    # OAuth
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str

    # EOD Data Providers
    ALPHA_VANTAGE_API_KEY: str
    EOD_FETCH_RETRY_COUNT: int = 3

    # SQS
    AWS_REGION: str = "ap-northeast-2"
    SQS_ENDPOINT_URL: Optional[str] = None

    # Points
    POINTS_WIN_REWARD: int = 100
    POINTS_VOID_REWARD: int = 0

    # Slots
    BASE_PREDICTION_SLOTS: int = 3
    MAX_AD_SLOTS: int = 7
    COOLDOWN_MINUTES: int = 5

    # Time
    TIMEZONE: str = "Asia/Seoul"

    class Config:
        env_file = ".env"
```

이 설계 문서를 기반으로 구현을 진행하면 됩니다. OAuth 로그인, 배치 기반 EOD 데이터 수집, 그리고 crypto 스키마만 사용하는 구조로 업데이트되었습니다.
