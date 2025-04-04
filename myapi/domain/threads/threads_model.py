from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


# 스레드 데이터 모델
class Thread(BaseModel):
    id: str
    text: str
    username: str
    likes: int
    created_at: datetime

    class Config:
        from_attributes = True


# API 응답 모델
class ThreadsResponse(BaseModel):
    threads: List[Thread]
    total_count: int


# 요청 모델 (키워드 검색용 - 기존)
class SearchRequest(BaseModel):
    keyword: str
    limit: Optional[int] = 10


# 요청 모델 (유저 스레드 조회용 - 기존)
class UserThreadsRequest(BaseModel):
    username: str
    limit: Optional[int] = 10


# 요청 모델 (태그 검색용 - 신규)
class TagSearchRequest(BaseModel):
    tag: str  # 예: "비트코인"
    limit: Optional[int] = 10
