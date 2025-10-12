# 프론트엔드 API 가이드 - 마켓 데이터 대시보드

## 📋 목차
- [개요](#개요)
- [배치 작업으로 수집되는 데이터](#배치-작업으로-수집되는-데이터)
- [API 엔드포인트](#api-엔드포인트)
  - [1. 애널리스트 목표가 (Analyst Price Targets)](#1-애널리스트-목표가-analyst-price-targets)
  - [2. ETF 자금 흐름 (ETF Flows)](#2-etf-자금-흐름-etf-flows)
  - [3. 유동성 분석 (Liquidity)](#3-유동성-분석-liquidity)
  - [4. 시장 폭 지표 (Market Breadth)](#4-시장-폭-지표-market-breadth)
  - [5. 내부자 거래 트렌드 (Insider Trends)](#5-내부자-거래-트렌드-insider-trends)
  - [6. ETF 포트폴리오 분석](#6-etf-포트폴리오-분석)
  - [7. 테크 주식 분석 (Mahaney Analysis)](#7-테크-주식-분석-mahaney-analysis)
- [UI/UX 권장사항](#uiux-권장사항)
- [에러 핸들링](#에러-핸들링)

---

## 개요

이 API는 주식 시장 분석을 위한 다양한 데이터를 제공합니다. 모든 데이터는 매일 자동으로 배치 작업을 통해 수집되며, GET 엔드포인트를 통해 조회할 수 있습니다.

### 기본 정보
- **Base URL**: `https://api.your-domain.com` (실제 URL로 교체 필요)
- **인증**: Bearer Token (배치 작업 POST 엔드포인트만 필요)
- **데이터 갱신 주기**: 매일 자동 배치 작업 실행

### 배치 작업 실행 시간
배치 작업은 하루에 한 번 실행되며, 다음 데이터들을 자동으로 수집합니다:
- 시그널 분석
- 시장 분석 및 예측
- ETF 포트폴리오 변동
- 내부자 거래 트렌드
- 애널리스트 목표가
- ETF 자금 흐름
- 유동성 지표
- 시장 폭 지표

---

## 배치 작업으로 수집되는 데이터

### 실행 엔드포인트
```
POST /batch/execute
Authorization: Bearer {token}
```

이 엔드포인트가 실행하는 작업 목록:
1. **신호 분석** (`signals/signals/by-only-ai`)
2. **시장 분석** (`news/market-analysis`)
3. **시장 예측 (Major)** (`news/market-forecast?source=Major`)
4. **시장 예측 (Minor)** (`news/market-forecast?source=Minor`)
5. **뉴스 요약** (`news/summary`)
6. **리서치 분석** (`research/analysis`)
7. **ETF 포트폴리오** (`news/etf/portfolio`)
8. **내부자 거래 트렌드** (`news/insider-trend`)
9. **애널리스트 목표가** (`news/analyst-price-targets`)
10. **ETF 자금 흐름** (`news/etf/flows`)
11. **유동성 지표** (`news/liquidity`)
12. **시장 폭 지표** (`news/market-breadth`)

---

## API 엔드포인트

### 1. 애널리스트 목표가 (Analyst Price Targets)

애널리스트들의 주가 목표가 변경 사항을 조회합니다.

#### GET 엔드포인트
```
GET /news/analyst-price-targets
```

#### Query Parameters
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| target_date | date | No | today | 조회할 날짜 (YYYY-MM-DD) |
| tickers | string | No | null | 필터할 티커 (쉼표로 구분, 예: "AAPL,GOOGL") |
| action | string | No | null | 목표가 변경 유형: "UP", "DOWN", "INIT", "DROP" |
| limit | integer | No | null | 결과 개수 제한 |
| sort_by | string | No | null | 정렬 기준: "impact", "date" |
| sort_order | string | No | "desc" | 정렬 순서: "asc", "desc" |

#### 요청 예시
```bash
# 전체 조회
curl -X GET "https://api.your-domain.com/news/analyst-price-targets?target_date=2025-10-02"

# 특정 티커 필터
curl -X GET "https://api.your-domain.com/news/analyst-price-targets?tickers=AAPL,MSFT&action=UP"

# 상승 목표가만 조회 (impact 순)
curl -X GET "https://api.your-domain.com/news/analyst-price-targets?action=UP&sort_by=impact&limit=10"
```

#### 응답 예시
```json
{
  "items": [
    {
      "ticker": "AAPL",
      "action": "UP",
      "broker": "Goldman Sachs",
      "broker_rating": "Buy",
      "old_pt": 180.00,
      "new_pt": 195.00,
      "consensus": 185.00,
      "upside_pct": 8.33,
      "rationale": "Strong iPhone 15 demand and services growth",
      "sources": ["https://example.com/source1"],
      "source_details": [
        {
          "name": "Goldman Sachs Research",
          "url": "https://example.com/source1"
        }
      ],
      "impact_score": 8.5,
      "date": "2025-10-01",
      "published_at": "2025-10-01T14:30:00Z"
    }
  ],
  "total_count": 45,
  "filtered_count": 15,
  "actual_date": "2025-10-02",
  "is_exact_date_match": true,
  "request_params": {
    "target_date": "2025-10-02",
    "tickers": null,
    "action": "UP",
    "limit": 10,
    "sort_by": "impact",
    "sort_order": "desc"
  }
}
```

#### 응답 필드 설명
| Field | Type | Description |
|-------|------|-------------|
| ticker | string | 주식 티커 |
| action | string | 목표가 변경 유형 (UP/DOWN/INIT/DROP) |
| broker | string | 증권사명 |
| broker_rating | string | 투자의견 (Buy/Hold/Sell) |
| old_pt | float | 기존 목표가 |
| new_pt | float | 신규 목표가 |
| consensus | float | 컨센서스 목표가 |
| upside_pct | float | 상승 여력 (%) |
| rationale | string | 목표가 변경 사유 |
| impact_score | float | 영향도 점수 (0-10) |

---

### 2. ETF 자금 흐름 (ETF Flows)

ETF별 자금 유입/유출 현황을 조회합니다.

#### GET 엔드포인트
```
GET /news/etf/flows
```

#### Query Parameters
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| target_date | date | No | today | 조회할 날짜 (YYYY-MM-DD) |
| provider | string | No | null | 데이터 제공자 필터 |
| sector_only | boolean | No | false | 섹터 ETF만 조회 |
| tickers | string | No | null | 필터할 티커 (쉼표로 구분) |

#### 요청 예시
```bash
# 전체 ETF 자금 흐름
curl -X GET "https://api.your-domain.com/news/etf/flows?target_date=2025-10-02"

# 특정 ETF만 조회
curl -X GET "https://api.your-domain.com/news/etf/flows?tickers=SPY,QQQ,IWM"

# 섹터 ETF만 조회
curl -X GET "https://api.your-domain.com/news/etf/flows?sector_only=true"
```

#### 응답 예시
```json
{
  "items": [
    {
      "ticker": "SPY",
      "name": "SPDR S&P 500 ETF Trust",
      "net_flow": 1250000000.00,
      "flow_1w": 3500000000.00,
      "volume_change": 15.5,
      "sector": "Broad Market",
      "themes": ["Large Cap", "Index"],
      "sector_inferred": false,
      "evidence": "Strong inflows driven by market rally",
      "source": "ETF.com",
      "source_details": [
        {
          "name": "ETF.com Weekly Report",
          "url": "https://etf.com/weekly-flows"
        }
      ]
    },
    {
      "ticker": "XLK",
      "name": "Technology Select Sector SPDR Fund",
      "net_flow": -450000000.00,
      "flow_1w": -200000000.00,
      "volume_change": -8.2,
      "sector": "Technology",
      "themes": ["Tech", "Growth"],
      "sector_inferred": false,
      "evidence": "Profit taking after strong performance",
      "source": "ETF.com",
      "source_details": []
    }
  ],
  "total_count": 250,
  "filtered_count": 250,
  "actual_date": "2025-10-02",
  "is_exact_date_match": true,
  "request_params": {
    "target_date": "2025-10-02",
    "provider": null,
    "sector_only": false,
    "tickers": null
  }
}
```

#### 응답 필드 설명
| Field | Type | Description |
|-------|------|-------------|
| ticker | string | ETF 티커 |
| name | string | ETF 이름 |
| net_flow | float | 순 자금 흐름 (달러) |
| flow_1w | float | 주간 자금 흐름 (달러) |
| volume_change | float | 거래량 변화 (%) |
| sector | string | 섹터 분류 |
| themes | array | 투자 테마 목록 |
| evidence | string | 자금 흐름 해석/근거 |

---

### 3. 유동성 분석 (Liquidity)

미국 시장의 유동성 지표를 조회합니다 (M2, RRP 등).

#### GET 엔드포인트
```
GET /news/liquidity
```

#### Query Parameters
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| target_date | date | No | today | 조회할 날짜 (YYYY-MM-DD) |

#### 요청 예시
```bash
curl -X GET "https://api.your-domain.com/news/liquidity?target_date=2025-10-02"
```

#### 응답 예시
```json
{
  "series_m2": [
    {
      "date": "2025-09-01",
      "m2": 21500.5,
      "rrp": null
    },
    {
      "date": "2025-09-08",
      "m2": 21520.3,
      "rrp": null
    },
    {
      "date": "2025-09-15",
      "m2": 21545.8,
      "rrp": null
    }
  ],
  "series_rrp": [
    {
      "date": "2025-09-01",
      "m2": null,
      "rrp": 450.2
    },
    {
      "date": "2025-09-08",
      "m2": null,
      "rrp": 425.6
    },
    {
      "date": "2025-09-15",
      "m2": null,
      "rrp": 410.8
    }
  ],
  "commentary": "M2 money supply continues gradual expansion, while RRP balances decline indicating liquidity return to markets. This trend is generally supportive for risk assets.",
  "window": "Last 12 weeks",
  "sources": [
    {
      "name": "Federal Reserve Economic Data (FRED)",
      "url": "https://fred.stlouisfed.org"
    }
  ]
}
```

#### 응답 필드 설명
| Field | Type | Description |
|-------|------|-------------|
| series_m2 | array | M2 통화량 시계열 데이터 |
| series_rrp | array | 역레포 잔액 시계열 데이터 |
| m2 | float | M2 통화량 (단위: 조 달러) |
| rrp | float | 역레포 잔액 (단위: 십억 달러) |
| commentary | string | 유동성 분석 해석 |
| window | string | 데이터 기간 |

#### 차트 표시 권장사항
- **차트 타입**: 듀얼 축 라인 차트
- **X축**: 날짜 (주간)
- **Y축 (좌)**: M2 통화량
- **Y축 (우)**: RRP 잔액
- **추가 요소**: commentary를 차트 하단에 표시

---

### 4. 시장 폭 지표 (Market Breadth)

시장 폭 관련 지표들을 조회합니다 (VIX, 상승/하락 종목 수 등).

#### GET 엔드포인트
```
GET /news/market-breadth
```

#### Query Parameters
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| target_date | date | No | today | 조회할 날짜 (YYYY-MM-DD) |

#### 요청 예시
```bash
curl -X GET "https://api.your-domain.com/news/market-breadth?target_date=2025-10-02"
```

#### 응답 예시
```json
{
  "series": [
    {
      "date": "2025-09-25",
      "vix": 15.2,
      "advancers": 2150,
      "decliners": 1320,
      "new_highs": 85,
      "new_lows": 12,
      "trin": 0.85
    },
    {
      "date": "2025-09-26",
      "vix": 14.8,
      "advancers": 2280,
      "decliners": 1190,
      "new_highs": 92,
      "new_lows": 8,
      "trin": 0.75
    },
    {
      "date": "2025-09-27",
      "vix": 16.5,
      "advancers": 1890,
      "decliners": 1580,
      "new_highs": 45,
      "new_lows": 28,
      "trin": 1.15
    }
  ],
  "commentary": "Market breadth shows healthy participation with strong advance-decline ratio. VIX remains subdued indicating low volatility environment. New highs significantly outpacing new lows suggests bullish momentum.",
  "sources": [
    {
      "name": "NYSE Market Data",
      "url": "https://www.nyse.com"
    },
    {
      "name": "CBOE VIX Index",
      "url": "https://www.cboe.com"
    }
  ]
}
```

#### 응답 필드 설명
| Field | Type | Description |
|-------|------|-------------|
| date | string | 날짜 |
| vix | float | VIX 변동성 지수 |
| advancers | integer | 상승 종목 수 |
| decliners | integer | 하락 종목 수 |
| new_highs | integer | 신고가 종목 수 |
| new_lows | integer | 신저가 종목 수 |
| trin | float | TRIN 지표 (1 기준) |
| commentary | string | 시장 폭 분석 해석 |

#### 차트 표시 권장사항
- **차트 1**: VIX 라인 차트
- **차트 2**: 상승/하락 종목 수 적층 바 차트
- **차트 3**: 신고가/신저가 비교 바 차트
- **지표 카드**: 최신 TRIN 값 (1보다 낮으면 강세, 높으면 약세)

---

### 5. 내부자 거래 트렌드 (Insider Trends)

임원/내부자들의 주식 거래 동향을 조회합니다.

#### GET 엔드포인트
```
GET /news/insider-trend
```

#### Query Parameters
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| target_date | date | No | today | 조회할 날짜 (YYYY-MM-DD) |
| tickers | string | No | null | 필터할 티커 (쉼표로 구분) |
| action | string | No | null | 거래 유형: "BUY", "SELL" |
| limit | integer | No | null | 결과 개수 제한 |
| sort_by | string | No | null | 정렬 기준: "date", "value" |
| sort_order | string | No | "desc" | 정렬 순서: "asc", "desc" |

#### 요청 예시
```bash
# 전체 내부자 거래
curl -X GET "https://api.your-domain.com/news/insider-trend?target_date=2025-10-02"

# 매수 거래만 조회
curl -X GET "https://api.your-domain.com/news/insider-trend?action=BUY&sort_by=value&limit=20"

# 특정 종목의 내부자 거래
curl -X GET "https://api.your-domain.com/news/insider-trend?tickers=AAPL,MSFT"
```

#### 응답 예시
```json
{
  "items": [
    {
      "ticker": "NVDA",
      "action": "BUY",
      "insider_name": "Jensen Huang",
      "insider_title": "CEO",
      "shares": 50000,
      "value": 22500000.00,
      "price": 450.00,
      "date": "2025-09-28",
      "filing_date": "2025-09-30",
      "transaction_type": "Open Market Purchase",
      "sources": ["https://sec.gov/filing1"],
      "source_details": [
        {
          "name": "SEC Form 4",
          "url": "https://sec.gov/filing1"
        }
      ],
      "sentiment_score": 8.5
    }
  ],
  "total_count": 125,
  "filtered_count": 42,
  "actual_date": "2025-10-02",
  "is_exact_date_match": true,
  "request_params": {
    "target_date": "2025-10-02",
    "tickers": null,
    "action": "BUY",
    "limit": 20,
    "sort_by": "value",
    "sort_order": "desc"
  }
}
```

---

### 6. ETF 포트폴리오 분석

ETF의 포트폴리오 변동 사항을 조회합니다.

#### GET 엔드포인트
```
GET /news/etf/portfolio
```

#### Query Parameters
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| target_date | date | No | today | 조회할 날짜 (YYYY-MM-DD) |
| etf_tickers | string | No | null | 필터할 ETF 티커 (쉼표로 구분) |

#### 요청 예시
```bash
# 전체 ETF 포트폴리오 변동
curl -X GET "https://api.your-domain.com/news/etf/portfolio?target_date=2025-10-02"

# 특정 ETF만 조회
curl -X GET "https://api.your-domain.com/news/etf/portfolio?etf_tickers=ARKK,ARKW"
```

---

### 7. 테크 주식 분석 (Mahaney Analysis)

마하니 스타일의 테크 주식 종합 분석을 조회합니다.

#### GET 엔드포인트
```
GET /news/tech-stock/analysis
```

#### Query Parameters
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| target_date | date | No | today | 조회할 날짜 (YYYY-MM-DD) |
| tickers | string | No | null | 필터할 티커 (쉼표로 구분) |
| recommendation | string | No | null | 추천 등급: "Buy", "Sell", "Hold" |
| limit | integer | No | null | 결과 개수 제한 |
| sort_by | string | No | "stock_name" | 정렬 기준: "recommendation_score", "final_assessment", "stock_name" |
| sort_order | string | No | "asc" | 정렬 순서: "asc", "desc" |

#### 요청 예시
```bash
# 전체 분석 조회
curl -X GET "https://api.your-domain.com/news/tech-stock/analysis?target_date=2025-10-02"

# Buy 추천만 조회
curl -X GET "https://api.your-domain.com/news/tech-stock/analysis?recommendation=Buy&sort_by=recommendation_score&sort_order=desc"

# 특정 종목 분석
curl -X GET "https://api.your-domain.com/news/tech-stock/analysis?tickers=AAPL,GOOGL,MSFT"
```

---

## UI/UX 권장사항

### 대시보드 레이아웃 제안

#### 1. 메인 대시보드
```
┌─────────────────────────────────────────────────────┐
│  📊 Market Overview                                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐           │
│  │ VIX      │ │ Liquidity│ │ Breadth  │           │
│  │  15.2    │ │    +2.3% │ │   Strong │           │
│  └──────────┘ └──────────┘ └──────────┘           │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│  🎯 Analyst Price Targets                           │
│  [Filter: ▼ All Actions] [Sort: Impact ▼]          │
│                                                      │
│  ✅ AAPL: $180 → $195 (UP)    Impact: ⭐⭐⭐⭐⭐    │
│     Goldman Sachs - Buy                             │
│     "Strong iPhone demand..."                       │
│                                                      │
│  ✅ MSFT: $350 → $375 (UP)    Impact: ⭐⭐⭐⭐⭐    │
│     Morgan Stanley - Overweight                     │
│     "Azure growth acceleration..."                  │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│  💰 ETF Flows                                        │
│  [Filter: ▼ All Sectors] [Period: Last Week]       │
│                                                      │
│  📈 SPY:  +$1.25B  (↑ 15.5%)                       │
│  📉 XLK:  -$450M   (↓ 8.2%)                        │
│  📈 QQQ:  +$890M   (↑ 12.3%)                       │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│  👔 Insider Trends                                   │
│  [Filter: ▼ Buy Only]                               │
│                                                      │
│  🟢 NVDA: Jensen Huang (CEO)                        │
│     Bought 50,000 shares @ $450                     │
│     Value: $22.5M | Date: 2025-09-28               │
│                                                      │
│  🟢 AAPL: Tim Cook (CEO)                           │
│     Bought 25,000 shares @ $180                     │
│     Value: $4.5M | Date: 2025-09-27                │
└─────────────────────────────────────────────────────┘
```

### 2. 컴포넌트별 권장 사항

#### 애널리스트 목표가 카드
```typescript
interface PriceTargetCard {
  ticker: string;
  oldPrice: number;
  newPrice: number;
  action: 'UP' | 'DOWN' | 'INIT' | 'DROP';
  broker: string;
  rating: string;
  impactScore: number; // 0-10
  upside: number; // percentage
}

// UI 색상 가이드
UP: green (#10b981)
DOWN: red (#ef4444)
INIT: blue (#3b82f6)
DROP: gray (#6b7280)
```

#### ETF 자금 흐름 차트
- **차트 타입**: 수평 바 차트 (긍정적 흐름은 오른쪽, 부정적은 왼쪽)
- **색상**: 
  - 유입 (positive): Green gradient
  - 유출 (negative): Red gradient
- **정렬**: 절대값 기준 내림차순
- **추가 정보**: 섹터별 필터링, 기간별 토글 (1주/4주/12주)

#### 유동성 차트
- **차트 타입**: 듀얼 축 라인 차트
- **M2**: 파란색 실선, 좌측 축
- **RRP**: 빨간색 점선, 우측 축
- **기간**: 최근 12주
- **애니메이션**: 부드러운 라인 애니메이션
- **툴팁**: 날짜, 값, 변화율 표시

#### 시장 폭 대시보드
- **메인 지표 카드**:
  - VIX (큰 숫자로 표시 + 색상 코딩)
    - < 15: Green (낮은 변동성)
    - 15-20: Yellow (보통)
    - > 20: Red (높은 변동성)
  - Advance/Decline Ratio
  - New Highs vs New Lows
- **트렌드 차트**: 최근 10일 일별 데이터

#### 내부자 거래 테이블
- **컬럼**:
  1. 티커 (심볼 + 회사명)
  2. 내부자 (이름 + 직책)
  3. 거래 유형 (BUY/SELL 배지)
  4. 주식 수
  5. 거래 금액 (포맷: $22.5M)
  6. 거래 날짜
- **정렬**: 거래 금액 내림차순 기본
- **필터**: 거래 유형, 최소 거래 금액
- **강조**: 대규모 거래 (> $10M) 하이라이트

### 3. 반응형 디자인

#### Desktop (> 1024px)
- 2열 그리드 레이아웃
- 사이드바 필터 패널
- 확장 가능한 차트

#### Tablet (768px - 1024px)
- 1열 그리드
- 접을 수 있는 필터
- 축소된 차트

#### Mobile (< 768px)
- 세로 스크롤
- 탭 네비게이션
- 요약 카드 우선 표시

### 4. 인터랙션

#### 필터링
```typescript
// 모든 리스트 컴포넌트에 적용
- 날짜 범위 선택 (Date Picker)
- 티커 검색 (Autocomplete)
- 액션 타입 선택 (Multi-select)
- 정렬 옵션 (Dropdown)
```

#### 실시간 업데이트
```typescript
// 데이터 새로고침 전략
- 초기 로드: 최신 데이터 fetch
- 자동 새로고침: 매 5분 (optional)
- 수동 새로고침: 버튼 클릭
- 로딩 상태: Skeleton UI 또는 Spinner
```

#### 상세 보기
```typescript
// 클릭 시 모달 또는 사이드 패널
- 전체 소스 링크
- 상세 설명
- 관련 뉴스
- 히스토리 차트
```

---

## 에러 핸들링

### HTTP 상태 코드

| Code | Description | User Message |
|------|-------------|--------------|
| 200 | 성공 | - |
| 400 | 잘못된 요청 | "입력 값을 확인해주세요" |
| 401 | 인증 실패 | "로그인이 필요합니다" |
| 404 | 데이터 없음 | "해당 날짜의 데이터가 없습니다" |
| 500 | 서버 오류 | "일시적인 오류가 발생했습니다. 잠시 후 다시 시도해주세요" |

### 빈 데이터 처리

```typescript
// 데이터가 없을 때 UI
if (data.items.length === 0) {
  return (
    <EmptyState
      icon="📊"
      title="데이터가 없습니다"
      description="해당 날짜의 데이터가 아직 수집되지 않았습니다."
      action={{
        label: "이전 날짜 보기",
        onClick: () => setPreviousDate()
      }}
    />
  );
}
```

### 날짜 매칭 처리

API는 `is_exact_date_match` 필드를 반환합니다:
- `true`: 요청한 정확한 날짜의 데이터
- `false`: 가장 가까운 이전 날짜의 데이터

```typescript
if (!response.is_exact_date_match) {
  showWarning(
    `요청하신 ${requestDate}의 데이터가 없어 ` +
    `${response.actual_date}의 데이터를 표시합니다.`
  );
}
```

---

## 예제 코드

### React + TypeScript 예제

```typescript
import { useState, useEffect } from 'react';

interface AnalystPTItem {
  ticker: string;
  action: 'UP' | 'DOWN' | 'INIT' | 'DROP';
  broker: string;
  broker_rating: string;
  old_pt: number;
  new_pt: number;
  upside_pct: number;
  rationale: string;
  impact_score: number;
}

interface AnalystPTResponse {
  items: AnalystPTItem[];
  total_count: number;
  filtered_count: number;
  actual_date: string;
  is_exact_date_match: boolean;
}

const AnalystTargetsComponent = () => {
  const [data, setData] = useState<AnalystPTResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState({
    action: 'UP',
    limit: 20,
    sort_by: 'impact',
  });

  useEffect(() => {
    fetchAnalystTargets();
  }, [filters]);

  const fetchAnalystTargets = async () => {
    setLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams({
        target_date: new Date().toISOString().split('T')[0],
        action: filters.action,
        limit: filters.limit.toString(),
        sort_by: filters.sort_by,
        sort_order: 'desc',
      });

      const response = await fetch(
        `https://api.your-domain.com/news/analyst-price-targets?${params}`
      );

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const json = await response.json();
      setData(json);

      if (!json.is_exact_date_match) {
        console.warn(
          `Showing data from ${json.actual_date} instead of requested date`
        );
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <div>Loading...</div>;
  if (error) return <div>Error: {error}</div>;
  if (!data || data.items.length === 0) return <div>No data available</div>;

  return (
    <div className="analyst-targets">
      <h2>Analyst Price Targets</h2>
      <div className="filters">
        <select
          value={filters.action}
          onChange={(e) => setFilters({ ...filters, action: e.target.value })}
        >
          <option value="">All</option>
          <option value="UP">Upgrades</option>
          <option value="DOWN">Downgrades</option>
          <option value="INIT">Initiations</option>
          <option value="DROP">Dropped</option>
        </select>
      </div>

      <div className="results-info">
        Showing {data.filtered_count} of {data.total_count} results
      </div>

      <div className="targets-list">
        {data.items.map((item, index) => (
          <div key={index} className={`target-card action-${item.action.toLowerCase()}`}>
            <div className="ticker">{item.ticker}</div>
            <div className="price-change">
              ${item.old_pt.toFixed(2)} → ${item.new_pt.toFixed(2)}
              <span className="upside">({item.upside_pct.toFixed(1)}% upside)</span>
            </div>
            <div className="broker">
              {item.broker} - {item.broker_rating}
            </div>
            <div className="rationale">{item.rationale}</div>
            <div className="impact">
              Impact: {'⭐'.repeat(Math.round(item.impact_score / 2))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default AnalystTargetsComponent;
```

### 유동성 차트 예제 (Recharts)

```typescript
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

interface LiquidityChartProps {
  data: {
    series_m2: Array<{ date: string; m2: number }>;
    series_rrp: Array<{ date: string; rrp: number }>;
  };
}

const LiquidityChart = ({ data }: LiquidityChartProps) => {
  // Merge M2 and RRP data by date
  const chartData = data.series_m2.map((m2Item) => {
    const rrpItem = data.series_rrp.find((r) => r.date === m2Item.date);
    return {
      date: m2Item.date,
      m2: m2Item.m2,
      rrp: rrpItem?.rrp || null,
    };
  });

  return (
    <ResponsiveContainer width="100%" height={400}>
      <LineChart data={chartData}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis 
          dataKey="date" 
          tickFormatter={(date) => new Date(date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
        />
        <YAxis 
          yAxisId="left" 
          label={{ value: 'M2 ($T)', angle: -90, position: 'insideLeft' }}
        />
        <YAxis 
          yAxisId="right" 
          orientation="right"
          label={{ value: 'RRP ($B)', angle: 90, position: 'insideRight' }}
        />
        <Tooltip 
          labelFormatter={(date) => new Date(date).toLocaleDateString()}
          formatter={(value: number, name: string) => [
            name === 'm2' ? `$${value.toFixed(1)}T` : `$${value.toFixed(1)}B`,
            name === 'm2' ? 'M2 Money Supply' : 'Reverse Repo'
          ]}
        />
        <Legend />
        <Line 
          yAxisId="left"
          type="monotone" 
          dataKey="m2" 
          stroke="#3b82f6" 
          strokeWidth={2}
          name="M2"
          dot={false}
        />
        <Line 
          yAxisId="right"
          type="monotone" 
          dataKey="rrp" 
          stroke="#ef4444" 
          strokeWidth={2}
          strokeDasharray="5 5"
          name="RRP"
          dot={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
};

export default LiquidityChart;
```

---

## 추가 참고사항

### 데이터 갱신 주기
- 모든 데이터는 **매일 1회** 배치 작업으로 수집됩니다
- 장 마감 후 데이터가 업데이트됩니다 (미국 동부시간 기준 오후 6시 이후)
- 주말/공휴일에는 가장 최근 거래일의 데이터가 반환됩니다

### 날짜 처리
- 모든 날짜는 `YYYY-MM-DD` 형식 사용
- 타임존: UTC
- 미래 날짜 요청 시: 가장 최근 데이터 반환
- 과거 날짜 요청 시: 해당 날짜 또는 가장 가까운 이전 날짜의 데이터 반환

### 성능 최적화
- **캐싱**: 동일한 날짜의 요청은 클라이언트 측 캐싱 권장 (5분)
- **페이지네이션**: `limit` 파라미터 사용하여 초기 로드 최적화
- **Lazy Loading**: 스크롤 시 추가 데이터 로드
- **이미지 최적화**: 차트는 Canvas 기반 라이브러리 사용 권장

### 보안
- GET 엔드포인트는 인증 불필요 (공개 데이터)
- POST 엔드포인트는 Bearer Token 필수
- Rate Limiting: IP당 분당 60회 요청 제한

---

## 문의 및 지원

- **API 문서**: [Swagger UI](https://api.your-domain.com/docs)
- **기술 지원**: dev@your-domain.com
- **버그 리포트**: [GitHub Issues](https://github.com/your-repo/issues)

---

**작성일**: 2025-10-02
**버전**: 1.0.0

