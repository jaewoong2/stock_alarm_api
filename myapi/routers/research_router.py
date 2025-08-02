from typing import Optional, Literal
import datetime as dt
from fastapi import APIRouter, Depends, HTTPException
from dependency_injector.wiring import inject, Provide

from myapi.containers import Container
from myapi.utils.auth import verify_bearer_token
from myapi.utils.date_utils import validate_date
from myapi.services.research_service import ResearchService
from myapi.domain.research.research_schema import (
    ResearchRequest,
    ResearchResponse,
    SectorAnalysisRequest,
    SectorAnalysisResponse,
    LeadingStockRequest,
    LeadingStockResponse,
    ComprehensiveResearchResponse,
    CreateResearchAnalysisRequest,
    GetResearchAnalysisRequest,
    GetResearchAnalysisResponse,
    ResearchAnalysisVO,
)

router = APIRouter(prefix="/research", tags=["research"])


@router.post("/search", response_model=ResearchResponse)
@inject
async def perplexity_research(
    request: ResearchRequest,
    research_service: ResearchService = Depends(
        Provide[Container.services.research_service]
    ),
):
    """
    Perplexity API를 사용하여 최신 이슈/정책/보도자료를 검색합니다.

    **사용 예시:**
    ```json
    {
        "region": "미국",
        "topic": "AI 데이터센터",
        "period_days": 14,
        "language": "한국어"
    }
    ```
    """
    try:
        return await research_service.perplexity_research(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Research search failed: {str(e)}")


@router.post("/sector-analysis", response_model=SectorAnalysisResponse)
@inject
async def sector_analysis(
    request: SectorAnalysisRequest,
    research_service: ResearchService = Depends(
        Provide[Container.services.research_service]
    ),
):
    """
    o4-mini를 사용하여 뉴스/정책의 4단계 섹터 파급효과를 분석합니다.

    **분석 단계:**
    1. 1차 수혜 섹터 (직접적 수혜)
    2. 2차 수혜 섹터 (전방/공급망 수혜)
    3. 3차 수혜 섹터 (문제 해결/병목 현상 수혜)
    4. 4차 수혜 섹터 (인프라/생태계 확장 수혜)
    """
    try:
        return await research_service.o4_mini_sector_analysis(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sector analysis failed: {str(e)}")


@router.post("/leading-stocks", response_model=LeadingStockResponse)
@inject
async def leading_stocks_analysis(
    request: LeadingStockRequest,
    research_service: ResearchService = Depends(
        Provide[Container.services.research_service]
    ),
):
    """
    Perplexity API를 사용하여 특정 섹터의 주도 종목을 분석합니다.

    **선별 기준:**
    - 기술주 위주 (AI, 반도체, 소프트웨어, 바이오테크 등)
    - 매출 성장률이 성장 중
    - S&P500 대비 RS 강도가 강한 종목
    - 시가총액 및 거래량 기준 충족
    """
    try:
        return await research_service.perplexity_leading_stocks(request)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Leading stocks analysis failed: {str(e)}"
        )


@router.post("/comprehensive", response_model=ComprehensiveResearchResponse)
@inject
async def comprehensive_research_analysis(
    research_service: ResearchService = Depends(
        Provide[Container.services.research_service]
    ),
):
    """
    종합 리서치 분석을 수행합니다. (Perplexity 검색 + o4-mini 섹터 분석 + Perplexity 주도종목 분석)

    **프로세스:**
    1. Perplexity로 최신 뉴스/정책 검색 (기본값: 미국, AI 기술 및 인프라, 14일)
    2. o4-mini로 4단계 섹터 파급효과 분석
    3. Perplexity로 주도 종목 선별 및 분석 (기본값: 매출성장률 15%, RS강도 70%)
    4. 결과 통합 및 반환
    """
    try:
        response = await research_service.comprehensive_research_analysis()
        return response
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Comprehensive research analysis failed: {str(e)}"
        )


@router.post(
    "/analysis",
    response_model=ResearchAnalysisVO,
    dependencies=[Depends(verify_bearer_token)],
)
@inject
async def create_research_analysis(
    request: CreateResearchAnalysisRequest,
    research_service: ResearchService = Depends(
        Provide[Container.services.research_service]
    ),
):
    """
    종합 리서치 분석을 수행하고 데이터베이스에 저장합니다.

    **저장되는 데이터:**
    - 검색 결과 (Perplexity) - 기본값: 미국, AI 기술 및 인프라, 14일
    - 섹터 분석 (o4-mini)
    - 주도 종목 분석 (Perplexity) - 기본값: 매출성장률 15%, RS강도 70%
    - 메타데이터 (날짜, AI 모델 정보 등)
    """
    try:
        return await research_service.save_research_analysis(request)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to create research analysis: {str(e)}"
        )


@router.get("/analysis", response_model=GetResearchAnalysisResponse)
@inject
async def get_research_analysis(
    target_date: Optional[dt.date] = dt.date.today(),
    limit: Optional[int] = None,
    sort_by: Optional[Literal["date"]] = "date",
    sort_order: Optional[Literal["asc", "desc"]] = "desc",
    research_service: ResearchService = Depends(
        Provide[Container.services.research_service]
    ),
):
    """
    저장된 리서치 분석 결과를 조회합니다.

    **필터링 옵션:**
    - target_date: 분석 날짜
    - limit: 결과 개수 제한
    - sort_by: 정렬 기준 (date)
    - sort_order: 정렬 순서 (asc, desc)
    """
    try:
        target_date = validate_date(target_date if target_date else dt.date.today())

        request_params = GetResearchAnalysisRequest(
            target_date=target_date,
            limit=limit,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        return await research_service.get_research_analysis(request_params)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get research analysis: {str(e)}"
        )


@router.get("/analysis/by-date/{analysis_date}")
@inject
async def get_research_analysis_by_date(
    analysis_date: dt.date,
    research_service: ResearchService = Depends(
        Provide[Container.services.research_service]
    ),
):
    """
    특정 날짜의 리서치 분석 결과를 조회합니다.

    **Path Parameters:**
    - analysis_date: 조회할 분석 날짜 (YYYY-MM-DD)
    """
    try:
        analysis_date = validate_date(analysis_date)

        request_params = GetResearchAnalysisRequest(
            target_date=analysis_date,
            sort_by="date",
            sort_order="desc",
        )

        return await research_service.get_research_analysis(request_params)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get research analysis by date: {str(e)}"
        )


@router.get("/analysis/latest")
@inject
async def get_latest_research_analysis(
    research_service: ResearchService = Depends(
        Provide[Container.services.research_service]
    ),
):
    """
    가장 최근의 리서치 분석 결과를 조회합니다.
    """
    try:
        request_params = GetResearchAnalysisRequest(
            target_date=dt.date.today(),
            limit=1,
            sort_by="date",
            sort_order="desc",
        )

        result = await research_service.get_research_analysis(request_params)

        if not result.analyses:
            raise HTTPException(status_code=404, detail="No research analysis found")

        return result.analyses[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get latest research analysis: {str(e)}"
        )


# Additional endpoints for component access
@router.get("/components/{target_date}")
@inject
async def get_research_components(
    target_date: dt.date,
    research_service: ResearchService = Depends(
        Provide[Container.services.research_service]
    ),
):
    """
    특정 날짜의 개별 연구 컴포넌트들을 조회합니다.
    
    **반환 컴포넌트:**
    - research_results: Perplexity 검색 결과
    - sector_analysis: o4-mini 섹터 분석
    - leading_stocks: 주도 종목 분석
    - comprehensive_research: 종합 분석
    """
    try:
        target_date = validate_date(target_date)
        return await research_service.get_research_components_by_date(target_date)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get research components: {str(e)}"
        )


@router.get("/summary/latest")
@inject
async def get_latest_analysis_summary(
    research_service: ResearchService = Depends(
        Provide[Container.services.research_service]
    ),
):
    """
    오늘의 최신 분석 요약을 조회합니다.
    
    **요약 정보:**
    - 분석 날짜
    - 사용 가능한 컴포넌트
    - 각 컴포넌트별 통계 요약
    """
    try:
        return await research_service.get_latest_analysis_summary()
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get analysis summary: {str(e)}"
        )


# Health check endpoint
@router.get("/health")
def health_check():
    """Research service health check."""
    return {"status": "healthy", "service": "research"}
