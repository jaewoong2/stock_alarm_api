# 페이지네이션 구현 문서

## 개요

`/signals/date` API와 `get-signals` API에 페이지네이션 기능을 추가했습니다. 대용량 데이터 조회 시 성능을 개선하고 클라이언트에서 더 나은 사용자 경험을 제공할 수 있습니다.

## 변경 사항

### 1. 새로운 스키마 추가

#### PaginationRequest
```python
class PaginationRequest(BaseModel):
    page: int = Field(default=1, ge=1, description="Page number (starting from 1)")
    page_size: int = Field(default=20, ge=1, le=100, description="Number of items per page (1-100)")
```

#### PaginationResponse
```python
class PaginationResponse(BaseModel):
    page: int = Field(description="Current page number")
    page_size: int = Field(description="Number of items per page")
    total_items: int = Field(description="Total number of items")
    total_pages: int = Field(description="Total number of pages")
    has_next: bool = Field(description="Whether there is a next page")
    has_previous: bool = Field(description="Whether there is a previous page")
```

#### PaginatedSignalsResponse
```python
class PaginatedSignalsResponse(BaseModel):
    data: List[SignalBaseResponse] = Field(description="List of signals for the current page")
    pagination: PaginationResponse = Field(description="Pagination metadata")
```

#### PaginatedSignalJoinTickerResponse
```python
class PaginatedSignalJoinTickerResponse(BaseModel):
    data: List[SignalJoinTickerResponse] = Field(description="List of signals with ticker info for the current page")
    pagination: PaginationResponse = Field(description="Pagination metadata")
```

### 2. 수정된 스키마

#### GetSignalRequest
```python
class GetSignalRequest(BaseModel):
    tickers: List[str] | None = None
    start_date: str | None = None
    end_date: str | None = None
    actions: List[Literal["Buy", "Sell", "Hold"]] | None = None
    pagination: PaginationRequest = Field(default_factory=PaginationRequest)  # 추가됨
```

### 3. Repository 레벨 변경사항

#### SignalsRepository 메서드 수정
- `get_signals()`: 페이지네이션 적용
- `get_signals_count()`: 총 개수 조회를 위한 새 메서드 추가
- `get_signals_with_ticker()`: 페이지네이션 매개변수 추가
- `get_signals_with_ticker_count()`: 총 개수 조회를 위한 새 메서드 추가

### 4. Service 레벨 변경사항

#### DBSignalService 메서드 수정
- `get_all_signals()`: 반환 타입이 `PaginatedSignalsResponse`로 변경
- `get_signals_result()`: 반환 타입이 `PaginatedSignalJoinTickerResponse`로 변경, 페이지네이션 매개변수 추가

### 5. Router 레벨 변경사항

#### 수정된 엔드포인트들

##### POST `/signals/get-signals`
- **응답 모델**: `List[SignalBaseResponse]` → `PaginatedSignalsResponse`
- **요청 본문**: `GetSignalRequest`에 `pagination` 필드 추가

##### GET `/signals/date`
- **응답 모델**: 기존 구조 → `PaginatedSignalJoinTickerResponse`
- **쿼리 매개변수**: `page`, `page_size` 추가

## API 사용법

### 1. POST `/signals/get-signals`

#### 요청 예시
```json
{
  "tickers": ["AAPL", "MSFT"],
  "start_date": "2024-01-01",
  "end_date": "2024-12-31",
  "actions": ["Buy", "Sell"],
  "pagination": {
    "page": 1,
    "page_size": 20
  }
}
```

#### 응답 예시
```json
{
  "data": [
    {
      "id": 1,
      "ticker": "AAPL",
      "entry_price": 150.0,
      "action": "buy",
      "timestamp": "2024-07-14T10:00:00Z",
      ...
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total_items": 150,
    "total_pages": 8,
    "has_next": true,
    "has_previous": false
  }
}
```

### 2. GET `/signals/date`

#### 요청 예시
```
GET /signals/date?date=2024-07-14&symbols=AAPL,MSFT&strategy_type=AI_GENERATED&page=1&page_size=20
```

#### 쿼리 매개변수
- `date`: 조회할 날짜 (YYYY-MM-DD 형식, 필수)
- `symbols`: 쉼표로 구분된 티커 심볼 목록 (선택)
- `strategy_type`: 전략 유형 ('AI_GENERATED', 'NOT_AI_GENERATED', 또는 생략시 모든 전략)
- `page`: 페이지 번호 (기본값: 1, 최소: 1)
- `page_size`: 페이지 크기 (기본값: 20, 최소: 1, 최대: 100)

#### 응답 예시
```json
{
  "data": [
    {
      "signal": {
        "ticker": "AAPL",
        "strategy": "AI_GENERATED",
        "entry_price": 150.0,
        "action": "buy",
        ...
      },
      "ticker": {
        "symbol": "AAPL",
        "close_price": 155.0,
        ...
      },
      "result": {
        "action": "up",
        "is_correct": true,
        "price_diff": 5.0
      }
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total_items": 45,
    "total_pages": 3,
    "has_next": true,
    "has_previous": false
  }
}
```

## 기본값 및 제한사항

### 페이지네이션 기본값
- **page**: 1 (첫 번째 페이지)
- **page_size**: 20 (페이지당 항목 수)

### 제한사항
- **page**: 최소 1
- **page_size**: 최소 1, 최대 100

### 자동 보정
- `page < 1`인 경우 자동으로 1로 설정
- `page_size < 1` 또는 `page_size > 100`인 경우 자동으로 20으로 설정

## 마이그레이션 가이드

### 기존 클라이언트 코드 수정

#### Before (기존)
```python
# POST /signals/get-signals
response = requests.post("/signals/get-signals", json={
    "tickers": ["AAPL"]
})
signals = response.json()  # List[SignalBaseResponse]

# GET /signals/date
response = requests.get("/signals/date?date=2024-07-14")
result = response.json()
signals = result["signals"]  # List[SignalJoinTickerResponse]
```

#### After (수정 후)
```python
# POST /signals/get-signals
response = requests.post("/signals/get-signals", json={
    "tickers": ["AAPL"],
    "pagination": {"page": 1, "page_size": 20}
})
result = response.json()
signals = result["data"]  # List[SignalBaseResponse]
pagination_info = result["pagination"]

# GET /signals/date
response = requests.get("/signals/date?date=2024-07-14&page=1&page_size=20")
result = response.json()
signals = result["data"]  # List[SignalJoinTickerResponse]
pagination_info = result["pagination"]
```

## 호환성 참고사항

### 하위 호환성
- `GetSignalRequest`의 `pagination` 필드는 기본값을 가지므로, 기존 요청도 정상 작동합니다.
- 기존 클라이언트가 페이지네이션을 명시하지 않으면 기본값(page=1, page_size=20)이 적용됩니다.

### 주의사항
- **응답 구조 변경**: 모든 페이지네이션이 적용된 엔드포인트의 응답 구조가 변경되었으므로, 클라이언트 코드에서 `data` 필드를 통해 실제 데이터에 접근해야 합니다.
- **GET `/signals/date` 응답 변경**: 기존의 `{"date": "...", "signals": [...]}` 구조에서 `{"data": [...], "pagination": {...}}` 구조로 변경되었습니다.

## 성능 고려사항

### 데이터베이스 쿼리 최적화
- `OFFSET`과 `LIMIT`을 사용하여 필요한 데이터만 조회합니다.
- 총 개수 조회를 위한 별도 쿼리를 실행합니다.
- 대용량 데이터셋에서 `OFFSET`이 큰 경우 성능이 저하될 수 있으므로, 필요시 커서 기반 페이지네이션을 고려할 수 있습니다.

### 권장사항
- 클라이언트에서는 적절한 `page_size`를 설정하여 네트워크 트래픽과 응답 시간의 균형을 맞추세요.
- 대량의 데이터를 조회할 때는 여러 페이지로 나누어 처리하세요.

## 파일 변경 목록

### 수정된 파일들
1. `myapi/domain/signal/signal_schema.py`
   - `PaginationRequest`, `PaginationResponse` 클래스 추가
   - `PaginatedSignalsResponse`, `PaginatedSignalJoinTickerResponse` 클래스 추가
   - `GetSignalRequest`에 `pagination` 필드 추가

2. `myapi/repositories/signals_repository.py`
   - `get_signals()` 메서드에 페이지네이션 적용
   - `get_signals_count()` 메서드 추가
   - `get_signals_with_ticker()` 메서드에 페이지네이션 매개변수 추가
   - `get_signals_with_ticker_count()` 메서드 추가

3. `myapi/services/db_signal_service.py`
   - `get_all_signals()` 메서드 반환 타입 변경
   - `get_signals_result()` 메서드에 페이지네이션 적용

4. `myapi/routers/signal_router.py`
   - `/signals/get-signals` 엔드포인트 응답 모델 변경
   - `/signals/date` 엔드포인트에 페이지네이션 매개변수 추가 및 응답 모델 변경

## 예시 클라이언트 코드

### JavaScript/TypeScript
```typescript
interface PaginationRequest {
  page?: number;
  page_size?: number;
}

interface PaginationResponse {
  page: number;
  page_size: number;
  total_items: number;
  total_pages: number;
  has_next: boolean;
  has_previous: boolean;
}

interface PaginatedSignalsResponse {
  data: SignalBaseResponse[];
  pagination: PaginationResponse;
}

// 사용 예시
const getSignals = async (page: number = 1, pageSize: number = 20) => {
  const response = await fetch('/signals/get-signals', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      tickers: ['AAPL', 'MSFT'],
      pagination: { page, page_size: pageSize }
    })
  });
  
  const result: PaginatedSignalsResponse = await response.json();
  return result;
};
```

### Python
```python
import requests
from typing import List, Optional

def get_signals(
    tickers: Optional[List[str]] = None,
    page: int = 1,
    page_size: int = 20
) -> dict:
    payload = {
        "pagination": {"page": page, "page_size": page_size}
    }
    if tickers:
        payload["tickers"] = tickers
    
    response = requests.post("/signals/get-signals", json=payload)
    return response.json()

def get_signals_by_date(
    date: str,
    symbols: Optional[List[str]] = None,
    page: int = 1,
    page_size: int = 20
) -> dict:
    params = {"date": date, "page": page, "page_size": page_size}
    if symbols:
        params["symbols"] = ",".join(symbols)
    
    response = requests.get("/signals/date", params=params)
    return response.json()
```

이 페이지네이션 구현으로 대용량 시그널 데이터를 효율적으로 조회하고 클라이언트에서 더 나은 사용자 경험을 제공할 수 있습니다.