# Market Direction Analysis API

## 개요
QQQ/SPY/VIX 옵션 데이터를 기반으로 다음날 시장 방향성을 AI로 분석하는 API입니다.

**주요 특징:**
- 순수 옵션 데이터 기반 분석 (기술적 지표 미사용)
- 100일 옵션 트렌드 분석
- AI 기반 시장 방향성 예측 (상승/하락/횡보)
- 매일 자동 업데이트 (EventBridge)

---

## API 엔드포인트

### 1. 최신 분석 조회 (READ-ONLY)
**프론트엔드에서 사용할 메인 엔드포인트입니다.**

```http
GET /signals/market-direction/latest
```

#### Request
```bash
curl -X GET "https://your-api-domain.com/signals/market-direction/latest" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### Response
```json
{
  "analysis_date": "2025-12-13",
  "overall_direction": "bearish",
  "confidence_score": 72.5,
  "tomorrow_bias": "down",
  "expected_volatility": "high",

  "qqq_sentiment": "QQQ 옵션 시장에서 풋 매수세가 크게 증가하고 있으며, 풋/콜 비율이 1.45로 30일 평균 대비 높은 수준입니다. 이는 기술주에 대한 하락 방어 수요가 늘어나고 있음을 시사합니다.",

  "spy_sentiment": "SPY는 상대적으로 중립적인 포지셔닝을 보이고 있으며, 풋/콜 비율은 1.08로 정상 범위 내에 있습니다. 브로드 마켓은 기술주 대비 안정적인 모습입니다.",

  "vix_signal": "VIX가 18.5로 상승하며 100일 기준 65번째 백분위수를 기록 중입니다. 텀 스트럭처가 역전되어 단기 변동성 우려가 커지고 있습니다.",

  "key_observations": [
    "QQQ 풋/콜 비율이 1.45로 30일 최고치 기록",
    "SPY는 600 스트라이크에서 콜 월 형성",
    "VIX 텀 스트럭처 역전 - 단기 스트레스 시그널",
    "IV Rank가 70 이상으로 옵션 프리미엄 비싸짐"
  ],

  "risk_factors": [
    "높은 풋 거래량이 급격히 반전될 수 있음",
    "VIX 텀 스트럭처가 단기 스트레스를 나타냄",
    "기술주와 브로드 마켓 간 디커플링 위험",
    "고평가된 옵션 프리미엄으로 인한 변동성 증폭 가능성"
  ],

  "reasoning": "현재 옵션 시장은 명확한 방어적 포지셔닝을 보이고 있습니다. QQQ의 높은 풋/콜 비율과 VIX의 상승은 투자자들이 단기 하락을 방어하고 있음을 의미합니다. 특히 VIX 텀 스트럭처의 역전은 역사적으로 단기 변동성이 높아지는 시그널입니다. SPY가 상대적으로 안정적이라는 점은 하락이 기술주 중심으로 제한될 수 있음을 시사하지만, 전반적인 시장 심리는 방어적입니다. IV Rank가 70 이상으로 옵션이 비싸진 상황에서 딜러 헤징 압력도 하방 모멘텀을 가속화할 수 있습니다. 따라서 내일 하락 가능성이 높으며, 변동성도 높을 것으로 예상됩니다.",

  "qqq_data": {
    "symbol": "QQQ",
    "underlying_close": 523.45,
    "underlying_100d_return_pct": 12.34,
    "put_call_ratio": 1.45,
    "put_call_ratio_oi": 1.32,
    "atm_put_iv": null,
    "atm_call_iv": null,
    "iv_rank_100d": 72.0,
    "skew": null,
    "total_put_volume": null,
    "total_call_volume": null,
    "total_put_oi": null,
    "total_call_oi": null,
    "unusual_activity": "Heavy put buying detected"
  },

  "spy_data": {
    "symbol": "SPY",
    "underlying_close": 598.23,
    "underlying_100d_return_pct": 8.67,
    "put_call_ratio": 1.08,
    "put_call_ratio_oi": 1.15,
    "atm_put_iv": null,
    "atm_call_iv": null,
    "iv_rank_100d": 55.0,
    "skew": null,
    "total_put_volume": null,
    "total_call_volume": null,
    "total_put_oi": null,
    "total_call_oi": null,
    "unusual_activity": "Normal options activity"
  },

  "vix_data": {
    "vix_level": 18.5,
    "vix_100d_percentile": 65.0,
    "vix_100d_high": 25.3,
    "vix_100d_low": 11.2,
    "term_structure": "inverted",
    "fear_level": "fear"
  }
}
```

#### Response 상태 코드
- `200 OK`: 분석 데이터 조회 성공
- `404 Not Found`: 최신 장일에 대한 분석이 없음 (배치 실행 전 상태)
- `401 Unauthorized`: 인증 토큰 없음 또는 유효하지 않음

---

### 2. 특정 날짜 분석 조회 (READ-ONLY)
**과거 분석 데이터를 조회할 때 사용합니다.**

```http
GET /signals/market-direction/{date}
```

#### Request
```bash
curl -X GET "https://your-api-domain.com/signals/market-direction/2025-12-12" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### Path Parameters
| 파라미터 | 타입 | 설명 | 예시 |
|---------|------|------|------|
| `date` | string | 조회할 날짜 (YYYY-MM-DD 형식) | `2025-12-12` |

#### Response
동일한 구조의 분석 데이터 (위 참조)

#### Response 상태 코드
- `200 OK`: 해당 날짜 분석 조회 성공
- `400 Bad Request`: 잘못된 날짜 형식
- `404 Not Found`: 해당 날짜에 대한 분석 없음
- `401 Unauthorized`: 인증 실패

---

## Response 필드 설명

### 메인 예측 필드

| 필드 | 타입 | 가능한 값 | 설명 |
|------|------|-----------|------|
| `analysis_date` | string | - | 분석 기준일 (YYYY-MM-DD) |
| `overall_direction` | string | `"bullish"` `"bearish"` `"neutral"` | 전반적인 시장 방향성 |
| `confidence_score` | float | 0-100 | AI 신뢰도 점수 (높을수록 확신) |
| `tomorrow_bias` | string | `"up"` `"down"` `"sideways"` | 내일 예상 방향 |
| `expected_volatility` | string | `"low"` `"moderate"` `"high"` | 예상 변동성 수준 |

### 분석 필드

| 필드 | 타입 | 설명 |
|------|------|------|
| `qqq_sentiment` | string | QQQ 옵션 시장 해석 (2-3문장) |
| `spy_sentiment` | string | SPY 옵션 시장 해석 (2-3문장) |
| `vix_signal` | string | VIX 지수 해석 (2-3문장) |
| `key_observations` | string[] | 주요 관찰 사항 (3-5개 bullet points) |
| `risk_factors` | string[] | 리스크 요인 (3-5개) |
| `reasoning` | string | 상세한 AI 분석 (200-300 단어) |

### 옵션 데이터 (qqq_data, spy_data)

| 필드 | 타입 | 설명 |
|------|------|------|
| `symbol` | string | 티커 심볼 |
| `underlying_close` | float | 기초자산 현재가 |
| `underlying_100d_return_pct` | float | 100일 수익률 (%) |
| `put_call_ratio` | float | 풋/콜 비율 (거래량 기준) |
| `put_call_ratio_oi` | float | 풋/콜 비율 (미결제약정 기준) |
| `iv_rank_100d` | float | IV Rank (100일 기준 백분위수) |
| `unusual_activity` | string | 비정상 옵션 활동 감지 메시지 |

#### 풋/콜 비율 해석 가이드
- **> 1.2**: 약세 포지셔닝 (풋 매수 많음) → 하락 방어 수요
- **0.8-1.2**: 중립적 포지셔닝
- **< 0.8**: 강세 포지셔닝 (콜 매수 많음) → 상승 베팅

### VIX 데이터 (vix_data)

| 필드 | 타입 | 설명 |
|------|------|------|
| `vix_level` | float | 현재 VIX 레벨 |
| `vix_100d_percentile` | float | 100일 기준 백분위수 |
| `vix_100d_high` | float | 100일 최고치 |
| `vix_100d_low` | float | 100일 최저치 |
| `term_structure` | string | VIX 선물 구조 (`"normal"` `"inverted"` `"flat"`) |
| `fear_level` | string | 공포 레벨 (`"extreme_fear"` `"fear"` `"neutral"` `"greed"`) |

#### VIX 레벨 해석 가이드
- **> 30**: 극도의 공포 (반전 가능성)
- **20-30**: 높은 공포
- **12-20**: 중립
- **< 12**: 안일함 (조정 위험)

#### Term Structure 해석
- **normal**: 정상 구조 (장기 > 단기) → 안정적
- **inverted**: 역전 구조 (단기 > 장기) → 단기 스트레스
- **flat**: 평탄 구조

---

## 프론트엔드 구현 가이드

### 1. 기본 데이터 페칭 예시

```typescript
// TypeScript 타입 정의
interface MarketDirectionAnalysis {
  analysis_date: string;
  overall_direction: 'bullish' | 'bearish' | 'neutral';
  confidence_score: number;
  tomorrow_bias: 'up' | 'down' | 'sideways';
  expected_volatility: 'low' | 'moderate' | 'high';

  qqq_sentiment: string;
  spy_sentiment: string;
  vix_signal: string;

  key_observations: string[];
  risk_factors: string[];
  reasoning: string;

  qqq_data: OptionsSnapshot;
  spy_data: OptionsSnapshot;
  vix_data: VixSnapshot;
}

interface OptionsSnapshot {
  symbol: string;
  underlying_close: number;
  underlying_100d_return_pct: number;
  put_call_ratio: number | null;
  put_call_ratio_oi: number | null;
  iv_rank_100d: number;
  unusual_activity: string;
}

interface VixSnapshot {
  vix_level: number;
  vix_100d_percentile: number;
  vix_100d_high: number;
  vix_100d_low: number;
  term_structure: string;
  fear_level: string;
}

// API 호출 함수
async function getLatestMarketDirection(): Promise<MarketDirectionAnalysis> {
  const response = await fetch('/signals/market-direction/latest', {
    headers: {
      'Authorization': `Bearer ${YOUR_TOKEN}`
    }
  });

  if (!response.ok) {
    if (response.status === 404) {
      throw new Error('분석 데이터가 아직 생성되지 않았습니다.');
    }
    throw new Error('API 호출 실패');
  }

  return await response.json();
}

// 특정 날짜 조회
async function getMarketDirectionByDate(date: string): Promise<MarketDirectionAnalysis> {
  const response = await fetch(`/signals/market-direction/${date}`, {
    headers: {
      'Authorization': `Bearer ${YOUR_TOKEN}`
    }
  });

  if (!response.ok) {
    throw new Error('해당 날짜의 분석을 찾을 수 없습니다.');
  }

  return await response.json();
}
```

### 2. React 컴포넌트 예시

```tsx
import { useEffect, useState } from 'react';

function MarketDirectionDashboard() {
  const [analysis, setAnalysis] = useState<MarketDirectionAnalysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchData() {
      try {
        setLoading(true);
        const data = await getLatestMarketDirection();
        setAnalysis(data);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : '데이터 로딩 실패');
      } finally {
        setLoading(false);
      }
    }

    fetchData();
  }, []);

  if (loading) return <div>로딩 중...</div>;
  if (error) return <div>에러: {error}</div>;
  if (!analysis) return null;

  return (
    <div className="market-direction-dashboard">
      {/* 메인 시그널 카드 */}
      <div className="signal-card">
        <h2>시장 방향성 분석</h2>
        <div className="date">{analysis.analysis_date}</div>

        <div className={`direction ${analysis.overall_direction}`}>
          {analysis.overall_direction === 'bullish' && '📈 강세'}
          {analysis.overall_direction === 'bearish' && '📉 약세'}
          {analysis.overall_direction === 'neutral' && '➡️ 중립'}
        </div>

        <div className="metrics">
          <div>신뢰도: {analysis.confidence_score.toFixed(1)}%</div>
          <div>내일 예상: {analysis.tomorrow_bias}</div>
          <div>예상 변동성: {analysis.expected_volatility}</div>
        </div>
      </div>

      {/* 주요 관찰사항 */}
      <div className="observations">
        <h3>주요 포인트</h3>
        <ul>
          {analysis.key_observations.map((obs, i) => (
            <li key={i}>{obs}</li>
          ))}
        </ul>
      </div>

      {/* 리스크 요인 */}
      <div className="risks">
        <h3>⚠️ 리스크 요인</h3>
        <ul>
          {analysis.risk_factors.map((risk, i) => (
            <li key={i}>{risk}</li>
          ))}
        </ul>
      </div>

      {/* 옵션 데이터 */}
      <div className="options-grid">
        <OptionsCard data={analysis.qqq_data} sentiment={analysis.qqq_sentiment} />
        <OptionsCard data={analysis.spy_data} sentiment={analysis.spy_sentiment} />
      </div>

      {/* VIX 지표 */}
      <VixCard data={analysis.vix_data} signal={analysis.vix_signal} />

      {/* AI 분석 상세 */}
      <div className="reasoning">
        <h3>AI 분석</h3>
        <p>{analysis.reasoning}</p>
      </div>
    </div>
  );
}
```

### 3. UI 권장 사항

#### 방향성 표시 색상 가이드
```css
.direction.bullish {
  color: #10b981; /* 녹색 */
  background: #d1fae5;
}

.direction.bearish {
  color: #ef4444; /* 빨간색 */
  background: #fee2e2;
}

.direction.neutral {
  color: #6b7280; /* 회색 */
  background: #f3f4f6;
}
```

#### 변동성 레벨 아이콘
- **low**: 🟢 낮음
- **moderate**: 🟡 보통
- **high**: 🔴 높음

#### VIX Fear Level 색상
- **extreme_fear**: 🔴 극도의 공포
- **fear**: 🟠 공포
- **neutral**: 🟡 중립
- **greed**: 🟢 탐욕

---

## 데이터 업데이트 주기

- **자동 업데이트**: 매일 EventBridge를 통해 자동 실행
- **실행 시간**: 장 마감 후 (구체적 시간은 배치 스케줄에 따름)
- **데이터 신선도**: 최신 장일 기준 분석

### 프론트엔드 폴링 권장사항
```typescript
// 5분마다 데이터 갱신 (선택사항)
useEffect(() => {
  const interval = setInterval(() => {
    fetchData();
  }, 5 * 60 * 1000); // 5분

  return () => clearInterval(interval);
}, []);
```

---

## 에러 처리

### 공통 에러 응답 형식
```json
{
  "detail": "에러 메시지"
}
```

### 에러별 처리 가이드

```typescript
async function handleApiCall() {
  try {
    const data = await getLatestMarketDirection();
    return data;
  } catch (error) {
    if (error.status === 404) {
      // 아직 분석이 생성되지 않음 (배치 실행 전)
      return showMessage('오늘의 분석이 아직 준비되지 않았습니다.');
    } else if (error.status === 401) {
      // 인증 실패
      return redirectToLogin();
    } else {
      // 기타 에러
      return showError('데이터를 불러올 수 없습니다.');
    }
  }
}
```

---

## FAQ

### Q1: 데이터가 404 에러로 조회되지 않아요
**A**: 배치 작업이 아직 실행되지 않았거나, 해당 날짜가 주말/공휴일일 수 있습니다. 최신 장일(market day) 기준으로 데이터가 생성됩니다.

### Q2: 주말에는 데이터가 업데이트되나요?
**A**: 아니요. 주말과 미국 증시 휴장일에는 새로운 분석이 생성되지 않습니다. 가장 최근 장일의 데이터가 조회됩니다.

### Q3: 실시간 데이터인가요?
**A**: 아니요. 하루에 한 번 장 마감 후 배치로 생성되는 데이터입니다. 실시간 옵션 데이터는 제공하지 않습니다.

### Q4: `null` 값이 있는 필드들은 무엇인가요?
**A**: `atm_put_iv`, `atm_call_iv`, `total_put_volume` 등 일부 필드는 현재 데이터 소스(yfinance) 제약으로 인해 제공되지 않습니다. 향후 개선 예정입니다.

### Q5: 신뢰도(confidence_score)는 어떻게 해석하나요?
**A**:
- **80-100**: 매우 높은 신뢰도
- **60-80**: 높은 신뢰도
- **40-60**: 중간 신뢰도
- **< 40**: 낮은 신뢰도 (불확실성 높음)

---

## 연락처
API 관련 문의사항이나 버그 리포트는 백엔드 팀에 문의해주세요.

**업데이트 이력:**
- 2025-12-13: 초기 버전 릴리스
