# ETF Portfolio API Guide for Frontend

## Overview
ETF 포트폴리오 변동 분석 데이터를 조회하는 API 사용법을 안내합니다.

## GET /news/etf/portfolio

### Base URL
```
https://your-api-domain.com/news/etf/portfolio
```

### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `target_date` | date | No | 오늘 날짜 | 조회할 날짜 (YYYY-MM-DD 형식) |
| `etf_tickers` | string | No | null | 필터할 ETF 티커 (쉼표로 구분) |
| `limit` | integer | No | null | 결과 제한 개수 |
| `sort_by` | string | No | "date" | 정렬 기준 ("date", "etf_name", "total_value") |
| `sort_order` | string | No | "desc" | 정렬 순서 ("asc", "desc") |

### 요청 예시

#### 1. ARKK ETF 포트폴리오 조회
```javascript
// Fetch API 사용
const response = await fetch('/news/etf/portfolio?etf_tickers=ARKK&target_date=2024-01-15');
const data = await response.json();
```

```bash
# cURL 사용
curl -X GET "https://your-api-domain.com/news/etf/portfolio?etf_tickers=ARKK&target_date=2024-01-15"
```

#### 2. QQQ ETF 포트폴리오 조회
```javascript
const response = await fetch('/news/etf/portfolio?etf_tickers=QQQ&limit=10&sort_by=total_value&sort_order=desc');
const data = await response.json();
```

#### 3. ARKK + QQQ 복수 ETF 조회
```javascript
const response = await fetch('/news/etf/portfolio?etf_tickers=ARKK,QQQ&target_date=2024-01-15&limit=20');
const data = await response.json();
```

### 응답 형태 (ETFAnalysisGetResponse)

```json
{
  "etf_portfolios": [
    {
      "etf_ticker": "ARKK",
      "etf_name": "ARK Innovation ETF",
      "analysis_date": "2024-01-15",
      "total_value": 5200000000,
      "changes": [
        {
          "ticker": "TSLA",
          "company_name": "Tesla Inc",
          "action": "ADDED",
          "shares": 1500000,
          "value": 320000000,
          "percentage": 6.15,
          "change_reason": "Strong Q4 earnings and production growth"
        },
        {
          "ticker": "ROKU",
          "company_name": "Roku Inc", 
          "action": "REDUCED",
          "shares": -500000,
          "value": -45000000,
          "percentage": -0.87,
          "change_reason": "Concerns over streaming market competition"
        }
      ],
      "summary": "ARKK showed significant portfolio rebalancing with technology focus...",
      "market_impact": "Positive outlook for innovation sector with selective stock picking..."
    }
  ]
}
```

### Frontend 구현 예시

#### React Hook 예시
```javascript
import { useState, useEffect } from 'react';

const useETFPortfolio = (etfTickers = '', targetDate = null) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchETFPortfolio = async () => {
      if (!etfTickers) return;
      
      setLoading(true);
      setError(null);
      
      try {
        const params = new URLSearchParams();
        params.append('etf_tickers', etfTickers);
        if (targetDate) params.append('target_date', targetDate);
        
        const response = await fetch(`/news/etf/portfolio?${params}`);
        
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const result = await response.json();
        setData(result);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchETFPortfolio();
  }, [etfTickers, targetDate]);

  return { data, loading, error };
};

// 컴포넌트에서 사용
function ETFPortfolioComponent() {
  const { data, loading, error } = useETFPortfolio('ARKK,QQQ', '2024-01-15');

  if (loading) return <div>Loading...</div>;
  if (error) return <div>Error: {error}</div>;

  return (
    <div>
      {data?.etf_portfolios?.map(portfolio => (
        <div key={portfolio.etf_ticker}>
          <h3>{portfolio.etf_name} ({portfolio.etf_ticker})</h3>
          <p>Total Value: ${portfolio.total_value.toLocaleString()}</p>
          
          <h4>Recent Changes:</h4>
          {portfolio.changes?.map((change, index) => (
            <div key={index} className={change.action === 'ADDED' ? 'added' : 'reduced'}>
              <strong>{change.ticker}</strong> - {change.action}
              <br />
              Shares: {change.shares.toLocaleString()}
              <br />
              Value: ${change.value.toLocaleString()}
              <br />
              Reason: {change.change_reason}
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
```

#### Vue.js 예시
```javascript
<template>
  <div>
    <div v-if="loading">Loading...</div>
    <div v-else-if="error">Error: {{ error }}</div>
    <div v-else>
      <div v-for="portfolio in etfData?.etf_portfolios" :key="portfolio.etf_ticker">
        <h3>{{ portfolio.etf_name }} ({{ portfolio.etf_ticker }})</h3>
        <p>Total Value: ${{ portfolio.total_value.toLocaleString() }}</p>
        
        <h4>Recent Changes:</h4>
        <div v-for="(change, index) in portfolio.changes" :key="index" 
             :class="change.action.toLowerCase()">
          <strong>{{ change.ticker }}</strong> - {{ change.action }}<br />
          Shares: {{ change.shares.toLocaleString() }}<br />
          Value: ${{ change.value.toLocaleString() }}<br />
          Reason: {{ change.change_reason }}
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'

export default {
  setup() {
    const etfData = ref(null)
    const loading = ref(false)
    const error = ref(null)

    const fetchETFPortfolio = async (tickers, date) => {
      loading.value = true
      error.value = null
      
      try {
        const params = new URLSearchParams()
        params.append('etf_tickers', tickers)
        if (date) params.append('target_date', date)
        
        const response = await fetch(`/news/etf/portfolio?${params}`)
        
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`)
        }
        
        etfData.value = await response.json()
      } catch (err) {
        error.value = err.message
      } finally {
        loading.value = false
      }
    }

    onMounted(() => {
      fetchETFPortfolio('ARKK,QQQ', '2024-01-15')
    })

    return {
      etfData,
      loading,
      error,
      fetchETFPortfolio
    }
  }
}
</script>
```

### 에러 처리

일반적인 에러 응답:
```json
{
  "detail": "No ETF portfolio data found for the specified criteria"
}
```

HTTP 상태 코드:
- `200`: 성공
- `400`: 잘못된 요청 (날짜 형식 오류 등)
- `404`: 데이터 없음
- `500`: 서버 오류

### 데이터 생성 (POST) 필요시

만약 GET 요청에서 데이터가 없다면, 먼저 POST 요청으로 분석을 생성해야 합니다:

```javascript
// 먼저 데이터 생성
const createResponse = await fetch('/news/etf/portfolio', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer YOUR_TOKEN'
  },
  body: JSON.stringify({
    etf_tickers: ['ARKK', 'QQQ'],
    target_date: '2024-01-15'
  })
});

// 생성 완료 후 조회
if (createResponse.ok) {
  const getResponse = await fetch('/news/etf/portfolio?etf_tickers=ARKK,QQQ&target_date=2024-01-15');
  const data = await getResponse.json();
}
```