# Fundamental Analysis API - Frontend Integration Guide

## 📋 목차
- [개요](#개요)
- [API 엔드포인트](#api-엔드포인트)
- [TypeScript 타입 정의](#typescript-타입-정의)
- [React Query 구현](#react-query-구현)
- [컴포넌트 예제](#컴포넌트-예제)
- [에러 처리](#에러-처리)
- [성능 최적화](#성능-최적화)

---

## 개요

**Fundamental Analysis API**는 특정 주식(티커)에 대한 종합적인 펀더멘탈 분석을 제공합니다.

### 주요 기능
- 🔍 네러티브 및 비전 분석
- 📊 섹터 및 경쟁 분석
- 💰 재무 지표 (성장, 수익성, 밸류에이션 등)
- 👔 경영진 분석
- ⚠️ 리스크 분석
- 🎯 투자 추천 (목표가, 시나리오)
- 🕐 30일 캐싱 (API 비용 절감)

### Base URL
```
http://localhost:8002  # 개발 환경
https://api.yourapp.com  # 프로덕션
```

---

## API 엔드포인트

### GET `/news/fundamental-analysis`

티커에 대한 펀더멘탈 분석을 조회합니다. (캐시 우선)

#### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `ticker` | string | ✅ Yes | - | 주식 티커 심볼 (예: AAPL, TSLA, NVDA) |
| `force_refresh` | boolean | ❌ No | false | 캐시 무시하고 새로 생성 여부 |
| `target_date` | string | ❌ No | today | 분석 기준 날짜 (YYYY-MM-DD) |

#### Example Request
```bash
curl -X 'GET' \
  'http://localhost:8002/news/fundamental-analysis?ticker=IREN&force_refresh=false&target_date=2025-10-03' \
  -H 'accept: application/json'
```

#### Response: 200 OK
```json
{
  "analysis": {
    "ticker": "IREN",
    "company_name": "Iris Energy Limited",
    "industry": "Bitcoin Mining",
    "analysis_date": "2025-10-03",
    "narrative_vision": {
      "key_narrative": "AI 및 비트코인 마이닝 인프라 성장",
      "vision_status": "Strong",
      "narrative_drivers": [
        "비트코인 반감기 후 해시레이트 확대",
        "AI 데이터센터 수요 증가",
        "친환경 에너지 활용"
      ],
      "market_sentiment": "Bullish",
      "sentiment_reasoning": "비트코인 가격 상승과 AI 인프라 수요로 긍정적"
    },
    "recommendation": {
      "rating": "Buy",
      "target_price": 25.0,
      "current_price": 18.5,
      "upside_downside": 35.1,
      "conviction_level": "High",
      "time_horizon": "Medium-term"
    },
    "executive_summary": "IREN은 친환경 비트코인 마이닝 및 AI 데이터센터를 운영하며...",
    "investment_thesis": "...",
    "key_takeaways": ["...", "..."]
  },
  "is_cached": true,
  "cache_date": "2025-10-01",
  "days_until_expiry": 28
}
```

#### Error Responses

**400 Bad Request**
```json
{
  "detail": "Invalid ticker symbol"
}
```

**500 Internal Server Error**
```json
{
  "detail": "Failed to create fundamental analysis: ..."
}
```

---

## TypeScript 타입 정의

### `types/fundamental-analysis.ts`

```typescript
// ============================================
// Enums
// ============================================

export type VisionStatus = 'Strong' | 'Moderate' | 'Weak' | 'Dead';
export type MarketSentiment = 'Very Bullish' | 'Bullish' | 'Neutral' | 'Bearish' | 'Very Bearish';
export type RelativeStrength = 'Leading' | 'In-line' | 'Lagging';
export type MoatRating = 'Wide' | 'Narrow' | 'None';
export type PipelineStrength = 'Strong' | 'Moderate' | 'Weak';
export type InnovationScore = 'Leader' | 'Fast Follower' | 'Laggard';
export type ManagementScore = 'Excellent' | 'Good' | 'Average' | 'Poor';
export type RiskScore = 'Low' | 'Medium' | 'High' | 'Very High';
export type Rating = 'Strong Buy' | 'Buy' | 'Hold' | 'Sell' | 'Strong Sell';
export type TimeHorizon = 'Short-term' | 'Medium-term' | 'Long-term';
export type ConvictionLevel = 'Very High' | 'High' | 'Medium' | 'Low';
export type MarginTrend = 'Expanding' | 'Stable' | 'Contracting';

// ============================================
// Source Reference
// ============================================

export interface SourceRef {
  name?: string;
  url?: string;
  date?: string;
  confidence?: number; // 0.0 ~ 1.0
}

// ============================================
// Analysis Sections
// ============================================

export interface NarrativeVisionAnalysis {
  key_narrative: string;
  vision_status: VisionStatus;
  narrative_drivers: string[];
  vision_sustainability: string;
  narrative_shift_risks: string[];
  market_sentiment: MarketSentiment;
  sentiment_reasoning: string;
  sources: SourceRef[];
}

export interface SectorAnalysis {
  sector_name: string;
  sector_performance: string;
  sector_ytd_return?: number;
  rotation_trend: string;
  key_catalysts: string[];
  key_headwinds: string[];
  relative_strength: RelativeStrength;
  peer_comparison?: string;
  sector_outlook: string;
  sources: SourceRef[];
}

export interface CompetitivePosition {
  market_share?: number;
  market_share_trend?: string;
  key_competitors: string[];
  competitive_advantages: string[];
  competitive_threats: string[];
  moat_rating: MoatRating;
  moat_explanation: string;
}

export interface ProductInnovation {
  recent_product_launches: string[];
  pipeline_strength: PipelineStrength;
  rd_spending?: number; // % of revenue
  innovation_score: InnovationScore;
  key_patents_or_tech: string[];
  product_cycle_stage: string;
}

export interface MarketOpportunity {
  total_addressable_market?: number; // in billions USD
  serviceable_addressable_market?: number;
  market_growth_rate?: number; // CAGR %
  company_penetration?: number; // % of TAM
  expansion_opportunities: string[];
  geographic_breakdown?: string;
}

// ============================================
// Financial Metrics
// ============================================

export interface GrowthMetrics {
  revenue_growth_yoy?: number;
  revenue_growth_qoq?: number;
  revenue_growth_3yr_cagr?: number;
  eps_growth_yoy?: number;
  eps_growth_3yr_cagr?: number;
  revenue_guidance?: string;
  earnings_surprise_history?: string;
}

export interface ProfitabilityMetrics {
  gross_margin?: number;
  operating_margin?: number;
  net_margin?: number;
  margin_trend?: MarginTrend;
  roe?: number;
  roic?: number;
  roa?: number;
}

export interface BalanceSheetMetrics {
  debt_to_equity?: number;
  net_debt?: number;
  current_ratio?: number;
  quick_ratio?: number;
  cash_and_equivalents?: number;
  total_debt?: number;
  debt_maturity_profile?: string;
  interest_coverage?: number;
}

export interface CashFlowMetrics {
  free_cash_flow?: number;
  fcf_yield?: number;
  operating_cash_flow?: number;
  capex?: number;
  fcf_conversion_rate?: number;
  cash_flow_trend?: string;
}

export interface ValuationMetrics {
  pe_ratio?: number;
  forward_pe?: number;
  peg_ratio?: number;
  price_to_sales?: number;
  price_to_book?: number;
  ev_to_ebitda?: number;
  valuation_vs_peers?: string;
  valuation_vs_historical?: string;
  fair_value_estimate?: number;
}

export interface FundamentalMetrics {
  growth: GrowthMetrics;
  profitability: ProfitabilityMetrics;
  balance_sheet: BalanceSheetMetrics;
  cash_flow: CashFlowMetrics;
  valuation: ValuationMetrics;
  sources: SourceRef[];
}

// ============================================
// Management & Risk
// ============================================

export interface ManagementAnalysis {
  ceo_name?: string;
  ceo_tenure?: string;
  ceo_background?: string;
  management_quality_score: ManagementScore;
  key_strengths: string[];
  key_concerns: string[];
  execution_track_record: string;
  capital_allocation_score: ManagementScore;
  insider_ownership?: number;
  recent_insider_activity?: string;
  compensation_alignment?: string;
  board_quality?: string;
  sources: SourceRef[];
}

export interface RiskAnalysis {
  regulatory_risks: string[];
  competitive_risks: string[];
  execution_risks: string[];
  macro_risks: string[];
  financial_risks: string[];
  overall_risk_score: RiskScore;
  black_swan_scenarios: string[];
}

export interface CatalystAnalysis {
  near_term_catalysts: string[];
  medium_term_catalysts: string[];
  long_term_catalysts: string[];
  earnings_date?: string;
  product_launches: string[];
  regulatory_milestones: string[];
}

// ============================================
// Recommendation
// ============================================

export interface InvestmentRecommendation {
  rating: Rating;
  target_price?: number;
  current_price?: number;
  upside_downside?: number;
  time_horizon: TimeHorizon;
  conviction_level: ConvictionLevel;
  key_bullish_factors: string[];
  key_bearish_factors: string[];
  base_case_scenario: string;
  bull_case_scenario: string;
  bear_case_scenario: string;
  risk_level: RiskScore;
  confidence_level: ConvictionLevel;
  ideal_entry_point?: string;
  stop_loss_suggestion?: number;
}

// ============================================
// Main Response
// ============================================

export interface FundamentalAnalysisResponse {
  ticker: string;
  company_name: string;
  industry?: string;
  analysis_date: string;

  // Core sections
  narrative_vision: NarrativeVisionAnalysis;
  sector_analysis: SectorAnalysis;
  competitive_position: CompetitivePosition;
  product_innovation: ProductInnovation;
  market_opportunity: MarketOpportunity;
  fundamental_metrics: FundamentalMetrics;
  management_analysis: ManagementAnalysis;
  risk_analysis: RiskAnalysis;
  catalyst_analysis: CatalystAnalysis;
  recommendation: InvestmentRecommendation;

  // Summary
  executive_summary: string;
  investment_thesis: string;
  key_takeaways: string[];
  last_updated: string;
}

export interface FundamentalAnalysisGetResponse {
  analysis: FundamentalAnalysisResponse;
  is_cached: boolean;
  cache_date?: string;
  days_until_expiry?: number;
}

// ============================================
// API Request Params
// ============================================

export interface FundamentalAnalysisParams {
  ticker: string;
  force_refresh?: boolean;
  target_date?: string; // YYYY-MM-DD
}
```

---

## React Query 구현

### `hooks/useFundamentalAnalysis.ts`

```typescript
import { useQuery, UseQueryOptions } from '@tanstack/react-query';
import type {
  FundamentalAnalysisGetResponse,
  FundamentalAnalysisParams,
} from '@/types/fundamental-analysis';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8002';

/**
 * Fetch fundamental analysis from API
 */
async function fetchFundamentalAnalysis(
  params: FundamentalAnalysisParams
): Promise<FundamentalAnalysisGetResponse> {
  const { ticker, force_refresh = false, target_date } = params;

  const queryParams = new URLSearchParams({
    ticker: ticker.toUpperCase(),
    force_refresh: String(force_refresh),
    ...(target_date && { target_date }),
  });

  const response = await fetch(
    `${API_BASE_URL}/news/fundamental-analysis?${queryParams}`,
    {
      headers: {
        'Accept': 'application/json',
      },
    }
  );

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to fetch fundamental analysis');
  }

  return response.json();
}

/**
 * React Query hook for fundamental analysis
 *
 * @example
 * ```tsx
 * const { data, isLoading, error } = useFundamentalAnalysis({ ticker: 'AAPL' });
 * ```
 */
export function useFundamentalAnalysis(
  params: FundamentalAnalysisParams,
  options?: Omit<
    UseQueryOptions<FundamentalAnalysisGetResponse, Error>,
    'queryKey' | 'queryFn'
  >
) {
  return useQuery<FundamentalAnalysisGetResponse, Error>({
    queryKey: ['fundamental-analysis', params.ticker, params.target_date],
    queryFn: () => fetchFundamentalAnalysis(params),
    enabled: !!params.ticker, // Only run if ticker exists
    staleTime: 1000 * 60 * 30, // 30 minutes
    gcTime: 1000 * 60 * 60 * 24, // 24 hours (formerly cacheTime)
    retry: 2,
    ...options,
  });
}

/**
 * Prefetch fundamental analysis (for SSR or optimistic loading)
 */
export async function prefetchFundamentalAnalysis(
  queryClient: any,
  params: FundamentalAnalysisParams
) {
  await queryClient.prefetchQuery({
    queryKey: ['fundamental-analysis', params.ticker, params.target_date],
    queryFn: () => fetchFundamentalAnalysis(params),
  });
}
```

---

## 컴포넌트 예제

### `components/FundamentalAnalysis.tsx`

```typescript
'use client';

import { useState } from 'react';
import { useFundamentalAnalysis } from '@/hooks/useFundamentalAnalysis';
import type { Rating } from '@/types/fundamental-analysis';

interface FundamentalAnalysisProps {
  ticker: string;
}

export default function FundamentalAnalysis({ ticker }: FundamentalAnalysisProps) {
  const [forceRefresh, setForceRefresh] = useState(false);

  const { data, isLoading, error, refetch } = useFundamentalAnalysis({
    ticker,
    force_refresh: forceRefresh,
  });

  // Loading state
  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600" />
        <p className="ml-4 text-gray-600">분석 중...</p>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-6">
        <h3 className="text-red-800 font-semibold mb-2">분석 실패</h3>
        <p className="text-red-600">{error.message}</p>
        <button
          onClick={() => refetch()}
          className="mt-4 px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700"
        >
          다시 시도
        </button>
      </div>
    );
  }

  if (!data) return null;

  const { analysis, is_cached, days_until_expiry } = data;
  const recommendation = analysis.recommendation;

  // Rating color mapping
  const getRatingColor = (rating: Rating): string => {
    const colors: Record<Rating, string> = {
      'Strong Buy': 'text-green-600 bg-green-50',
      'Buy': 'text-green-500 bg-green-50',
      'Hold': 'text-yellow-600 bg-yellow-50',
      'Sell': 'text-red-500 bg-red-50',
      'Strong Sell': 'text-red-600 bg-red-50',
    };
    return colors[rating] || 'text-gray-600 bg-gray-50';
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">
            {analysis.ticker} - {analysis.company_name}
          </h1>
          <p className="text-gray-500 mt-1">{analysis.industry}</p>
        </div>

        {is_cached && (
          <div className="text-sm text-gray-500">
            📦 캐시됨 ({days_until_expiry}일 남음)
          </div>
        )}
      </div>

      {/* Investment Recommendation Card */}
      <div className="bg-white border border-gray-200 rounded-lg p-6 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold">투자 추천</h2>
          <span className={`px-4 py-2 rounded-full font-semibold ${getRatingColor(recommendation.rating)}`}>
            {recommendation.rating}
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <div>
            <p className="text-sm text-gray-500">현재가</p>
            <p className="text-2xl font-bold">${recommendation.current_price?.toFixed(2)}</p>
          </div>
          <div>
            <p className="text-sm text-gray-500">목표가</p>
            <p className="text-2xl font-bold text-blue-600">${recommendation.target_price?.toFixed(2)}</p>
          </div>
          <div>
            <p className="text-sm text-gray-500">상승 여력</p>
            <p className="text-2xl font-bold text-green-600">+{recommendation.upside_downside?.toFixed(1)}%</p>
          </div>
        </div>

        <div className="prose max-w-none">
          <h3 className="text-lg font-semibold mb-2">투자 논리</h3>
          <p className="text-gray-700">{analysis.investment_thesis}</p>
        </div>
      </div>

      {/* Executive Summary */}
      <div className="bg-white border border-gray-200 rounded-lg p-6 shadow-sm">
        <h2 className="text-xl font-semibold mb-4">요약</h2>
        <p className="text-gray-700 leading-relaxed">{analysis.executive_summary}</p>
      </div>

      {/* Key Takeaways */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
        <h2 className="text-xl font-semibold mb-4 text-blue-900">핵심 포인트</h2>
        <ul className="space-y-2">
          {analysis.key_takeaways.map((takeaway, idx) => (
            <li key={idx} className="flex items-start">
              <span className="text-blue-600 mr-2">✓</span>
              <span className="text-gray-700">{takeaway}</span>
            </li>
          ))}
        </ul>
      </div>

      {/* Bullish vs Bearish Factors */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Bullish */}
        <div className="bg-green-50 border border-green-200 rounded-lg p-6">
          <h3 className="text-lg font-semibold text-green-900 mb-4">
            📈 긍정적 요인
          </h3>
          <ul className="space-y-2">
            {recommendation.key_bullish_factors.map((factor, idx) => (
              <li key={idx} className="text-green-800 text-sm">• {factor}</li>
            ))}
          </ul>
        </div>

        {/* Bearish */}
        <div className="bg-red-50 border border-red-200 rounded-lg p-6">
          <h3 className="text-lg font-semibold text-red-900 mb-4">
            📉 부정적 요인
          </h3>
          <ul className="space-y-2">
            {recommendation.key_bearish_factors.map((factor, idx) => (
              <li key={idx} className="text-red-800 text-sm">• {factor}</li>
            ))}
          </ul>
        </div>
      </div>

      {/* Refresh Button */}
      <div className="flex justify-end">
        <button
          onClick={() => {
            setForceRefresh(true);
            refetch();
          }}
          className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium"
        >
          🔄 새로고침 (새 분석 생성)
        </button>
      </div>
    </div>
  );
}
```

### `app/stock/[ticker]/page.tsx` (Next.js App Router)

```typescript
import { Suspense } from 'react';
import FundamentalAnalysis from '@/components/FundamentalAnalysis';
import { prefetchFundamentalAnalysis } from '@/hooks/useFundamentalAnalysis';
import { getQueryClient } from '@/lib/query-client';
import { HydrationBoundary, dehydrate } from '@tanstack/react-query';

interface PageProps {
  params: {
    ticker: string;
  };
}

export default async function StockPage({ params }: PageProps) {
  const queryClient = getQueryClient();

  // SSR: Prefetch data
  await prefetchFundamentalAnalysis(queryClient, {
    ticker: params.ticker,
  });

  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
      <div className="container mx-auto px-4 py-8">
        <Suspense fallback={<LoadingState />}>
          <FundamentalAnalysis ticker={params.ticker} />
        </Suspense>
      </div>
    </HydrationBoundary>
  );
}

function LoadingState() {
  return (
    <div className="animate-pulse space-y-4">
      <div className="h-8 bg-gray-200 rounded w-1/3" />
      <div className="h-64 bg-gray-200 rounded" />
      <div className="h-32 bg-gray-200 rounded" />
    </div>
  );
}
```

---

## 에러 처리

### `lib/error-handler.ts`

```typescript
export class APIError extends Error {
  constructor(
    public statusCode: number,
    public detail: string
  ) {
    super(detail);
    this.name = 'APIError';
  }
}

export function handleAPIError(error: unknown): string {
  if (error instanceof APIError) {
    return error.detail;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return 'An unexpected error occurred';
}
```

### Error Boundary 사용

```typescript
'use client';

import { Component, ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error?: Error;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="bg-red-50 border border-red-200 rounded-lg p-6">
          <h2 className="text-xl font-semibold text-red-800 mb-2">
            Something went wrong
          </h2>
          <p className="text-red-600">{this.state.error?.message}</p>
        </div>
      );
    }

    return this.props.children;
  }
}
```

---

## 성능 최적화

### 1. **캐시 활용**

```typescript
// 30일 캐시 활용 (API 비용 절감)
const { data } = useFundamentalAnalysis({ ticker: 'AAPL' });
// is_cached: true이면 DB에서 즉시 반환 (빠름)
// is_cached: false이면 AI 분석 수행 (느림, ~30초)
```

### 2. **Prefetching**

```typescript
// SSR에서 미리 데이터 로드
await prefetchFundamentalAnalysis(queryClient, { ticker: 'NVDA' });
```

### 3. **Optimistic Updates**

```typescript
const mutation = useMutation({
  mutationFn: (ticker: string) =>
    fetchFundamentalAnalysis({ ticker, force_refresh: true }),
  onMutate: async (ticker) => {
    // Cancel ongoing queries
    await queryClient.cancelQueries({ queryKey: ['fundamental-analysis', ticker] });

    // Optimistically show loading state
    return { ticker };
  },
  onSuccess: (data, ticker) => {
    // Update cache
    queryClient.setQueryData(['fundamental-analysis', ticker], data);
  },
});
```

### 4. **React Query DevTools**

```typescript
// app/providers.tsx
'use client';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { useState } from 'react';

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 1000 * 60 * 5, // 5 minutes
        retry: 1,
      },
    },
  }));

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  );
}
```

---

## 테스트

### `__tests__/useFundamentalAnalysis.test.ts`

```typescript
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useFundamentalAnalysis } from '@/hooks/useFundamentalAnalysis';

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });

  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  );
};

describe('useFundamentalAnalysis', () => {
  it('should fetch fundamental analysis', async () => {
    const { result } = renderHook(
      () => useFundamentalAnalysis({ ticker: 'AAPL' }),
      { wrapper: createWrapper() }
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data?.analysis.ticker).toBe('AAPL');
  });
});
```

---

## 추가 리소스

### 환경 변수 설정 (`.env.local`)

```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8002
```

### Package.json 의존성

```json
{
  "dependencies": {
    "@tanstack/react-query": "^5.0.0",
    "next": "^14.0.0",
    "react": "^18.0.0",
    "react-dom": "^18.0.0"
  },
  "devDependencies": {
    "@tanstack/react-query-devtools": "^5.0.0",
    "@testing-library/react": "^14.0.0",
    "typescript": "^5.0.0"
  }
}
```

---

## 문의 사항

문제가 발생하거나 질문이 있으면 백엔드 팀에 문의하세요:
- API 문서: http://localhost:8002/docs
- Swagger UI: http://localhost:8002/redoc

---

**마지막 업데이트**: 2025-10-03
**API 버전**: v1.0
