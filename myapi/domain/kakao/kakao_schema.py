from typing import Optional
from pydantic import BaseModel, Field, field_validator


# Kakao 토큰 정보를 위한 Pydantic 모델
class KakaoToken(BaseModel):
    access_token: str
    refresh_token: str


class KakaoMessageRequest(BaseModel):
    message: str


class KakaoJSONResponse(BaseModel):
    message: Optional[str] = None
    code: Optional[str] = None
    result_code: Optional[str] = None

    @field_validator("code", mode="before")
    def transform_code(cls, v):
        if isinstance(v, int):
            return str(v)
        return v

    @field_validator("result_code", mode="before")
    def transform_result_code(cls, v):
        if isinstance(v, int):
            return str(v)
        return v


class KakaoTokenResponse(BaseModel):
    token_type: str = Field(..., description="토큰 타입, bearer로 고정")
    access_token: str = Field(..., description="갱신된 사용자 액세스 토큰 값")
    id_token: Optional[str] = Field(
        None,
        description="갱신된 ID 토큰 값 (제공 조건: ID 토큰과 함께 발급된 리프레시 토큰으로 토큰 갱신을 요청한 경우)",
    )
    expires_in: int = Field(..., description="액세스 토큰 만료 시간(초)")
    refresh_token: Optional[str] = Field(
        None,
        description="갱신된 사용자 리프레시 토큰 값 (기존 리프레시 토큰의 유효기간이 1개월 미만인 경우에만 갱신)",
    )
    refresh_token_expires_in: Optional[int] = Field(
        None, description="리프레시 토큰 만료 시간(초)"
    )
