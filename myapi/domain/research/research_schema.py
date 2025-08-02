from pydantic import BaseModel, Field
from typing import List, Literal, Optional
import datetime as dt


# 1. Perplexity Research Schemas
class ResearchItem(BaseModel):
    title: str
    date: str = Field(..., description="YYYY-MM-DD format")
    source: str = Field(..., description="URL")
    summary: str = Field(..., description="1-2 sentence summary")
    entities: List[str] = Field(
        ..., description="Key entities like institutions/companies/regions"
    )
    event_type: Literal[
        "policy", "budget", "tech", "regulation", "sanction", "capex", "rfp"
    ]


class ResearchRequest(BaseModel):
    region: str = Field(..., description="e.g., 미국/한국/유럽")
    topic: str = Field(
        ..., description="e.g., AI 데이터센터, 소형모듈원전, 반도체 보조금"
    )
    period_days: int = Field(14, description="최근 며칠")


class ResearchResponse(BaseModel):
    research_items: List[ResearchItem]


# 2. Sector Analysis Schemas
class SectorAnalysis(BaseModel):
    sector: str
    reason: str
    companies: List[str]


class SectorAnalysisData(BaseModel):
    primary_beneficiaries: List[SectorAnalysis] = Field(
        ..., description="1차 수혜 섹터"
    )
    supply_chain_beneficiaries: List[SectorAnalysis] = Field(
        ..., description="2차 수혜 섹터"
    )
    bottleneck_solution_beneficiaries: List[SectorAnalysis] = Field(
        ..., description="3차 수혜 섹터"
    )
    infrastructure_beneficiaries: List[SectorAnalysis] = Field(
        ..., description="4차 수혜 섹터"
    )


class SectorAnalysisRequest(BaseModel):
    news_content: str = Field(..., description="News article content to analyze")


class SectorAnalysisResponse(BaseModel):
    analysis: SectorAnalysisData


# 3. Leading Stock Analysis Schemas
class StockMetrics(BaseModel):
    ticker: str
    company_name: str
    revenue_growth_rate: Optional[float] = Field(None, description="매출 성장률 (%)")
    rs_strength: Optional[float] = Field(None, description="S&P500 대비 RS 강도")
    market_cap: Optional[float] = Field(None, description="시가총액")
    sector: str
    current_price: Optional[float] = None
    volume_trend: Optional[str] = Field(None, description="거래량 추세")


class LeadingStock(BaseModel):
    stock_metrics: StockMetrics
    analysis_summary: str = Field(..., description="분석 요약")
    growth_potential: str = Field(..., description="성장 잠재력")
    risk_factors: List[str] = Field(..., description="리스크 요인")
    target_price: Optional[float] = Field(None, description="목표 주가")
    recommendation: Literal["Strong Buy", "Buy", "Hold", "Sell", "Strong Sell"]


class LeadingStockRequest(BaseModel):
    sectors: List[str] = Field(..., description="분석할 섹터 리스트")


class LeadingStockResponse(BaseModel):
    leading_stocks: List[LeadingStock]


# 4. Comprehensive Research Analysis Schemas
class ComprehensiveResearchData(BaseModel):
    research_date: str = Field(..., description="분석 날짜 YYYY-MM-DD")
    research_results: ResearchResponse
    sector_analysis: SectorAnalysisResponse
    leading_stocks: LeadingStockResponse


class ComprehensiveResearchResponse(BaseModel):
    analysis: ComprehensiveResearchData


# 5. Database Schema for storing comprehensive research
class ResearchAnalysisVO(BaseModel):
    id: Optional[int] = None
    date: str = Field(..., description="분석 날짜 YYYY-MM-DD")
    name: str = Field(default="comprehensive_research", description="분석 타입")
    value: ComprehensiveResearchData = Field(..., description="분석 데이터")
    created_at: Optional[str] = None


# 6. API Request/Response Schemas
class CreateResearchAnalysisRequest(BaseModel):
    target_date: Optional[dt.date] = Field(default_factory=dt.date.today)


class GetResearchAnalysisRequest(BaseModel):
    target_date: Optional[dt.date] = Field(default_factory=dt.date.today)
    limit: Optional[int] = None
    sort_by: Optional[Literal["date"]] = "date"
    sort_order: Optional[Literal["asc", "desc"]] = "desc"


class GetResearchAnalysisResponse(BaseModel):
    analyses: List[ResearchAnalysisVO]
    total_count: int
    filtered_count: int
    actual_date: Optional[dt.date] = None
    is_exact_date_match: bool = True
    request_params: GetResearchAnalysisRequest
