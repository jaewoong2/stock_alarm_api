import json
from fastapi import APIRouter, Depends, HTTPException
from dependency_injector.wiring import inject, Provide

from myapi.containers import Container
from myapi.domain.news.news_schema import MahaneyAnalysisRequest
from myapi.services.aws_service import AwsService
from myapi.utils.auth import verify_bearer_token
from myapi.utils.config import Settings
from myapi.domain.signal.signal_schema import DefaultTickers
from myapi.utils.date_utils import get_latest_market_date

router = APIRouter(
    prefix="/batch",
    tags=["batch"],
)


@router.post("/execute", dependencies=[Depends(verify_bearer_token)])
@inject
def execute_batch_jobs(
    aws_service: AwsService = Depends(Provide[Container.services.aws_service]),
    settings: Settings = Depends(Provide[Container.config.config]),
):
    """
    미리 정의된 여러 작업을 SQS 큐에 메시지로 보내 일괄 실행을 트리거합니다.
    """

    # SQS FIFO 큐 URL (실제 환경에 맞게 수정 필요)
    queue_url = "https://sqs.ap-northeast-2.amazonaws.com/849441246713/crypto.fifo"
    market_date = get_latest_market_date()
    market_date_str = market_date.isoformat()

    # 호출할 API 엔드포인트 목록
    jobs = [
        {
            "path": "news/market-analysis",
            "method": "POST",
            "body": {},
            "group_id": "news",
        },
        {
            "path": "news/market-forecast",
            "method": "POST",
            "body": {},
            "group_id": "news-major",
            "query_string_parameters": {"source": "Major"},
        },
        {
            "path": "news/market-forecast",
            "method": "POST",
            "body": {},
            "group_id": "news-minor",
            "query_string_parameters": {"source": "Minor"},
        },
        {"path": "news/summary", "method": "GET", "body": {}, "group_id": "news"},
        {
            "path": "signals/market-direction/analyze",
            "method": "POST",
            "body": {"analysis_date": None, "force_refresh": False},
            "group_id": "market-direction",
        },
    ]

    responses = []
    for job in jobs:
        try:
            # HTTP 요청을 SQS 메시지 형식으로 변환
            message_body = aws_service.generate_queue_message_http(
                path=job["path"],
                method=job["method"],
                body=json.dumps(job["body"]),
                auth_token=settings.auth_token,
                query_string_parameters=(
                    job["query_string_parameters"]
                    if "query_string_parameters" in job
                    else None
                ),
            )

            # 고유한 중복 제거 ID 생성 (경로 + 날짜)
            deduplication_id = f"{job['path'].replace('/', '-')}-{market_date_str}"

            # SQS FIFO 큐에 메시지 전송
            response = aws_service.send_sqs_fifo_message(
                queue_url=queue_url,
                message_body=json.dumps(message_body),
                message_group_id=job["group_id"],
                message_deduplication_id=deduplication_id,
            )
            responses.append(
                {"job": job["path"], "status": "queued", "response": response}
            )
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to queue job {job['path']}: {str(e)}"
            )

    return {
        "message": "Batch jobs have been successfully queued.",
        "details": responses,
    }


@router.post("/tech-stock/analysis", dependencies=[Depends(verify_bearer_token)])
@inject
def create_mahaney_analysis_batch(
    aws_service: AwsService = Depends(Provide[Container.services.aws_service]),
    settings: Settings = Depends(Provide[Container.config.config]),
):
    """
    Mahaney 분석을 10개씩 분할하여 SQS 큐에 메시지로 보내 일괄 실행을 트리거합니다.
    """

    # SQS FIFO 큐 URL (실제 환경에 맞게 수정 필요)
    queue_url = "https://sqs.ap-northeast-2.amazonaws.com/849441246713/crypto.fifo"
    market_date = get_latest_market_date()
    market_date_str = market_date.strftime("%Y%m%d")

    # 티커 목록을 10개씩 분할
    ticker_chunks = [
        DefaultTickers[i : i + 3] for i in range(0, len(DefaultTickers), 3)
    ]

    responses = []
    for i, chunk in enumerate(ticker_chunks):
        try:
            # HTTP 요청을 SQS 메시지 형식으로 변환
            message_body = aws_service.generate_queue_message_http(
                path="news/tech-stock/analysis",
                method="POST",
                body=MahaneyAnalysisRequest(
                    tickers=chunk, target_date=market_date
                ).model_dump_json(),
                auth_token=settings.auth_token,
            )

            # 고유한 중복 제거 ID 생성 (경로 + 날짜 + 청크 인덱스)
            deduplication_id = f"newstechstockanalysis{market_date_str}{i}"

            # SQS FIFO 큐에 메시지 전송
            response = aws_service.send_sqs_fifo_message(
                queue_url=queue_url,
                message_body=json.dumps(message_body),
                message_group_id="mahaneyanalysis",
                message_deduplication_id=deduplication_id,
            )
            responses.append(
                {
                    "job": f"mahaney_analysis_chunk_{i}",
                    "status": "queued",
                    "response": response,
                }
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to queue job mahaney_analysis_chunk_{i}: {str(e)}",
            )

    return {
        "message": "Mahaney analysis batch jobs have been successfully queued.",
        "details": responses,
    }
