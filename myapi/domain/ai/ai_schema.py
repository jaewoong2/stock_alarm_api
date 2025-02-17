from pydantic import BaseModel


class AnalyzeResponseModel(BaseModel):
    action: str
    reason: str
