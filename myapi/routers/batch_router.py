import datetime as dt
import json
from fastapi import APIRouter, Depends, HTTPException
from dependency_injector.wiring import inject, Provide

from myapi.containers import Container
from myapi.domain.news.news_schema import MahaneyAnalysisRequest
from myapi.services.aws_service import AwsService
from myapi.utils.auth import verify_bearer_token
from myapi.utils.config import Settings
from myapi.domain.signal.signal_schema import DefaultTickers

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
    today_str = dt.date.today().isoformat()

    # 호출할 API 엔드포인트 목록
    jobs = [
        {
            "path": "signals/signals/by-only-ai",
            "method": "POST",
            "body": {"ai_model": "ALL"},
            "group_id": "signals",
        },
        {
            "path": "news/market-analysis",
            "method": "POST",
            "body": {},
            "group_id": "news",
        },
        {
            "path": "news/market-forecast?source=Major",
            "method": "POST",
            "body": {"source": "Major"},
            "group_id": "news-major",
        },
        {
            "path": "news/market-forecast?source=Minor",
            "method": "POST",
            "body": {},
            "group_id": "news-minor",
        },
        {"path": "news/summary", "method": "GET", "body": {}, "group_id": "news"},
    ]

    # 티커를 5개씩 분할하여 translate/signals 작업 추가
    ticker_chunks = [
        DefaultTickers[i : i + 5] for i in range(0, len(DefaultTickers), 5)
    ]

    for i, chunk in enumerate(ticker_chunks):
        jobs.append(
            {
                "path": "translate/signals",
                "method": "POST",
                "body": {"tickers": chunk, "model": "OPENAI"},
                "group_id": f"translate-{i}-OPENAI",
            }
        )

        jobs.append(
            {
                "path": "translate/signals",
                "method": "POST",
                "body": {"tickers": chunk, "model": "GOOGLE"},
                "group_id": f"translate-{i}-GOOGLE",
            }
        )

    responses = []
    for job in jobs:
        try:
            # HTTP 요청을 SQS 메시지 형식으로 변환
            message_body = aws_service.generate_queue_message_http(
                path=job["path"],
                method=job["method"],
                body=json.dumps(job["body"]),
                auth_token=settings.auth_token,
            )

            # 고유한 중복 제거 ID 생성 (경로 + 날짜)
            deduplication_id = f"{job['path'].replace('/', '-')}-{today_str}"

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
    today_str = dt.date.today().strftime("%Y%m%d")

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
                    tickers=chunk, target_date=dt.date.today()
                ).model_dump_json(),
                auth_token=settings.auth_token,
            )

            # 고유한 중복 제거 ID 생성 (경로 + 날짜 + 청크 인덱스)
            deduplication_id = f"newstechstockanalysis{today_str}{i}"

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
