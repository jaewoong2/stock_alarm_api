# Mahaney Analysis API Documentation

## Overview
Mark Mahaney의 7단계 체크리스트를 기반으로 한 기술주 분석 API입니다. 분석 생성 및 조회 기능을 제공합니다.

## Endpoints

### 1. GET `/news/tech-stock/analysis` - Mahaney 분석 조회

#### Description
저장된 Mahaney 분석 결과를 필터링, 정렬, 페이징 옵션과 함께 조회합니다.

#### Request Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `target_date` | `string (YYYY-MM-DD)` | No | `today` | 조회할 분석 날짜 |
| `tickers` | `string` | No | `null` | 필터할 티커 목록 (쉼표로 구분, 예: "AAPL,GOOGL,MSFT") |
| `recommendation` | `string` | No | `null` | 추천 등급 필터 (`"Buy"`, `"Sell"`, `"Hold"`) |
| `limit` | `integer` | No | `null` | 결과 개수 제한 |
| `sort_by` | `string` | No | `"stock_name"` | 정렬 기준 (`"stock_name"`, `"recommendation_score"`, `"final_assessment"`) |
| `sort_order` | `string` | No | `"asc"` | 정렬 순서 (`"asc"`, `"desc"`) |

#### Example Requests

```typescript
// 기본 조회
GET /news/tech-stock/analysis

// 특정 티커만 조회
GET /news/tech-stock/analysis?tickers=AAPL,GOOGL&limit=10

// Buy 추천만 조회 (추천 점수 내림차순)
GET /news/tech-stock/analysis?recommendation=Buy&sort_by=recommendation_score&sort_order=desc

// 특정 날짜 조회
GET /news/tech-stock/analysis?target_date=2024-01-15
```

#### Response Schema

```typescript
interface MahaneyAnalysisGetResponse {
  stocks: MahaneyStockAnalysis[];
  total_count: number;
  filtered_count: number;
  request_params: MahaneyAnalysisGetRequest;
}

interface MahaneyStockAnalysis {
  stock_name: string;
  revenue_growth: MahaneyCriterionEvaluation;
  valuation: MahaneyCriterionEvaluation;
  product_innovation: MahaneyCriterionEvaluation;
  tam: MahaneyCriterionEvaluation;
  customer_value: MahaneyCriterionEvaluation;
  management_quality: MahaneyCriterionEvaluation;
  timing: MahaneyCriterionEvaluation;
  final_assessment: string;
  recommendation: "Buy" | "Sell" | "Hold";
  recommendation_score: string;
  summary: string;
  detail_summary: string;
}

interface MahaneyCriterionEvaluation {
  pass_criterion: boolean;
  score: number;
  metric: string;
  comment: string;
}

interface MahaneyAnalysisGetRequest {
  target_date: string | null;
  tickers: string[] | null;
  recommendation: "Buy" | "Sell" | "Hold" | null;
  limit: number | null;
  sort_by: "recommendation_score" | "final_assessment" | "stock_name";
  sort_order: "asc" | "desc";
}
```

#### Example Response

```json
{
  "stocks": [
    {
      "stock_name": "AAPL",
      "revenue_growth": {
        "pass_criterion": true,
        "score": 8,
        "metric": "25,30,22,28,26",
        "comment": "5 consecutive quarters above 20%"
      },
      "valuation": {
        "pass_criterion": true,
        "score": 7,
        "metric": "PEG: 0.9",
        "comment": "PEG below 1.0, reasonable valuation"
      },
      "product_innovation": {
        "pass_criterion": true,
        "score": 9,
        "metric": "R&D: 6.2% of revenue",
        "comment": "Strong R&D investment and product pipeline"
      },
      "tam": {
        "pass_criterion": true,
        "score": 10,
        "metric": "$2.5T smartphone market",
        "comment": "Large addressable market with expansion potential"
      },
      "customer_value": {
        "pass_criterion": true,
        "score": 9,
        "metric": "NPS: 72, Retention: 95%",
        "comment": "Excellent customer satisfaction and loyalty"
      },
      "management_quality": {
        "pass_criterion": true,
        "score": 8,
        "metric": "CEO tenure: 12 years",
        "comment": "Proven leadership with strong execution track record"
      },
      "timing": {
        "pass_criterion": true,
        "score": 7,
        "metric": "22% below 52-week high",
        "comment": "Good entry point with recent pullback"
      },
      "final_assessment": "Strong Buy",
      "recommendation": "Buy",
      "recommendation_score": "9.2/10 - Exceptional fundamentals with attractive valuation",
      "summary": "Apple demonstrates strong performance across all Mahaney criteria",
      "detail_summary": "Apple shows consistent revenue growth, reasonable valuation metrics, strong product innovation pipeline, massive TAM, excellent customer metrics, proven management, and attractive entry timing."
    }
  ],
  "total_count": 15,
  "filtered_count": 8,
  "request_params": {
    "target_date": "2024-01-15",
    "tickers": ["AAPL", "GOOGL"],
    "recommendation": "Buy",
    "limit": 10,
    "sort_by": "recommendation_score",
    "sort_order": "desc"
  }
}
```

### 2. POST `/news/tech-stock/analysis` - Mahaney 분석 생성

#### Description
지정된 티커들에 대해 새로운 Mahaney 분석을 생성합니다. (인증 필요)

#### Request Body

```typescript
interface MahaneyAnalysisRequest {
  tickers: string[];
  target_date?: string; // YYYY-MM-DD format
}
```

#### Example Request

```json
{
  "tickers": ["AAPL", "GOOGL", "MSFT", "AMZN"],
  "target_date": "2024-01-15"
}
```

#### Response
생성된 분석 데이터를 `MahaneyAnalysisData` 형태로 반환합니다.

## React TypeScript Implementation Guide

### 1. Type Definitions

```typescript
// types/mahaney.ts
export interface MahaneyCriterionEvaluation {
  pass_criterion: boolean;
  score: number;
  metric: string;
  comment: string;
}

export interface MahaneyStockAnalysis {
  stock_name: string;
  revenue_growth: MahaneyCriterionEvaluation;
  valuation: MahaneyCriterionEvaluation;
  product_innovation: MahaneyCriterionEvaluation;
  tam: MahaneyCriterionEvaluation;
  customer_value: MahaneyCriterionEvaluation;
  management_quality: MahaneyCriterionEvaluation;
  timing: MahaneyCriterionEvaluation;
  final_assessment: string;
  recommendation: "Buy" | "Sell" | "Hold";
  recommendation_score: string;
  summary: string;
  detail_summary: string;
}

export interface MahaneyAnalysisGetRequest {
  target_date?: string;
  tickers?: string[];
  recommendation?: "Buy" | "Sell" | "Hold";
  limit?: number;
  sort_by?: "recommendation_score" | "final_assessment" | "stock_name";
  sort_order?: "asc" | "desc";
}

export interface MahaneyAnalysisGetResponse {
  stocks: MahaneyStockAnalysis[];
  total_count: number;
  filtered_count: number;
  request_params: MahaneyAnalysisGetRequest;
}

export interface MahaneyAnalysisRequest {
  tickers: string[];
  target_date?: string;
}
```

### 2. API Service

```typescript
// services/mahaneyApi.ts
import { 
  MahaneyAnalysisGetRequest, 
  MahaneyAnalysisGetResponse,
  MahaneyAnalysisRequest 
} from '../types/mahaney';

const BASE_URL = 'http://your-api-domain.com';

export class MahaneyAnalysisService {
  private baseUrl: string;
  private token?: string;

  constructor(baseUrl: string = BASE_URL, token?: string) {
    this.baseUrl = baseUrl;
    this.token = token;
  }

  async getMahaneyAnalysis(params: MahaneyAnalysisGetRequest): Promise<MahaneyAnalysisGetResponse> {
    const searchParams = new URLSearchParams();
    
    if (params.target_date) searchParams.append('target_date', params.target_date);
    if (params.tickers?.length) searchParams.append('tickers', params.tickers.join(','));
    if (params.recommendation) searchParams.append('recommendation', params.recommendation);
    if (params.limit) searchParams.append('limit', params.limit.toString());
    if (params.sort_by) searchParams.append('sort_by', params.sort_by);
    if (params.sort_order) searchParams.append('sort_order', params.sort_order);

    const response = await fetch(
      `${this.baseUrl}/news/tech-stock/analysis?${searchParams.toString()}`
    );

    if (!response.ok) {
      throw new Error(`Failed to fetch Mahaney analysis: ${response.statusText}`);
    }

    return response.json();
  }

  async createMahaneyAnalysis(request: MahaneyAnalysisRequest): Promise<any> {
    if (!this.token) {
      throw new Error('Authentication token required for creating analysis');
    }

    const response = await fetch(`${this.baseUrl}/news/tech-stock/analysis`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${this.token}`,
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      throw new Error(`Failed to create Mahaney analysis: ${response.statusText}`);
    }

    return response.json();
  }
}
```

### 3. React Hook

```typescript
// hooks/useMahaneyAnalysis.ts
import { useState, useEffect } from 'react';
import { MahaneyAnalysisService } from '../services/mahaneyApi';
import { 
  MahaneyAnalysisGetRequest, 
  MahaneyAnalysisGetResponse 
} from '../types/mahaney';

export const useMahaneyAnalysis = (
  initialParams: MahaneyAnalysisGetRequest = {},
  token?: string
) => {
  const [data, setData] = useState<MahaneyAnalysisGetResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const service = new MahaneyAnalysisService(undefined, token);

  const fetchAnalysis = async (params: MahaneyAnalysisGetRequest = {}) => {
    setLoading(true);
    setError(null);
    
    try {
      const result = await service.getMahaneyAnalysis({ ...initialParams, ...params });
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAnalysis();
  }, []);

  return {
    data,
    loading,
    error,
    refetch: fetchAnalysis,
  };
};
```

### 4. React Component Example

```typescript
// components/MahaneyAnalysisTable.tsx
import React, { useState } from 'react';
import { useMahaneyAnalysis } from '../hooks/useMahaneyAnalysis';
import { MahaneyAnalysisGetRequest } from '../types/mahaney';

interface FilterState {
  tickers: string;
  recommendation: 'Buy' | 'Sell' | 'Hold' | '';
  sortBy: 'stock_name' | 'recommendation_score' | 'final_assessment';
  sortOrder: 'asc' | 'desc';
  limit: number;
}

export const MahaneyAnalysisTable: React.FC = () => {
  const [filters, setFilters] = useState<FilterState>({
    tickers: '',
    recommendation: '',
    sortBy: 'stock_name',
    sortOrder: 'asc',
    limit: 20,
  });

  const { data, loading, error, refetch } = useMahaneyAnalysis();

  const handleFilterSubmit = () => {
    const params: MahaneyAnalysisGetRequest = {
      tickers: filters.tickers ? filters.tickers.split(',').map(t => t.trim()) : undefined,
      recommendation: filters.recommendation || undefined,
      sort_by: filters.sortBy,
      sort_order: filters.sortOrder,
      limit: filters.limit,
    };
    
    refetch(params);
  };

  if (loading) return <div>Loading...</div>;
  if (error) return <div>Error: {error}</div>;

  return (
    <div className="mahaney-analysis-container">
      {/* Filters */}
      <div className="filters">
        <input
          type="text"
          placeholder="Tickers (comma-separated)"
          value={filters.tickers}
          onChange={(e) => setFilters(prev => ({ ...prev, tickers: e.target.value }))}
        />
        
        <select
          value={filters.recommendation}
          onChange={(e) => setFilters(prev => ({ 
            ...prev, 
            recommendation: e.target.value as any 
          }))}
        >
          <option value="">All Recommendations</option>
          <option value="Buy">Buy</option>
          <option value="Hold">Hold</option>
          <option value="Sell">Sell</option>
        </select>

        <select
          value={filters.sortBy}
          onChange={(e) => setFilters(prev => ({ 
            ...prev, 
            sortBy: e.target.value as any 
          }))}
        >
          <option value="stock_name">Stock Name</option>
          <option value="recommendation_score">Recommendation Score</option>
          <option value="final_assessment">Final Assessment</option>
        </select>

        <button onClick={handleFilterSubmit}>Apply Filters</button>
      </div>

      {/* Results Info */}
      {data && (
        <div className="results-info">
          Showing {data.filtered_count} of {data.total_count} stocks
        </div>
      )}

      {/* Table */}
      <table className="analysis-table">
        <thead>
          <tr>
            <th>Stock</th>
            <th>Recommendation</th>
            <th>Score</th>
            <th>Assessment</th>
            <th>Revenue Growth</th>
            <th>Valuation</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {data?.stocks.map((stock) => (
            <tr key={stock.stock_name}>
              <td>{stock.stock_name}</td>
              <td>
                <span className={`recommendation ${stock.recommendation.toLowerCase()}`}>
                  {stock.recommendation}
                </span>
              </td>
              <td>{stock.recommendation_score}</td>
              <td>{stock.final_assessment}</td>
              <td>{stock.revenue_growth.pass_criterion ? '✅' : '❌'}</td>
              <td>{stock.valuation.pass_criterion ? '✅' : '❌'}</td>
              <td>
                <button onClick={() => console.log('View details', stock)}>
                  Details
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
```

## Usage Examples

### 기본 사용법
```typescript
// 모든 분석 조회
const { data, loading, error } = useMahaneyAnalysis();

// 특정 조건으로 조회
const { data, loading, error, refetch } = useMahaneyAnalysis({
  recommendation: 'Buy',
  sort_by: 'recommendation_score',
  sort_order: 'desc',
  limit: 10
});

// 동적 필터링
const handleFilter = () => {
  refetch({
    tickers: ['AAPL', 'GOOGL'],
    recommendation: 'Buy'
  });
};
```

### 분석 생성
```typescript
const service = new MahaneyAnalysisService(BASE_URL, token);

const createAnalysis = async () => {
  try {
    await service.createMahaneyAnalysis({
      tickers: ['AAPL', 'GOOGL', 'MSFT'],
      target_date: '2024-01-15'
    });
    // 성공 처리
  } catch (error) {
    // 에러 처리
  }
};
```