from typing import List, Optional, Union

from openai import BaseModel
from pydantic import ConfigDict


class Source(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None


class Article(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    publishedAt: Optional[str] = None

    model_config = ConfigDict(extra="ignore")


class ErrorResponse(BaseModel):
    error: str
    message: str


# Pydantic models for the response
class SentimentDataItem(BaseModel):
    value: str  # The index value (e.g., "73")
    value_classification: str  # Classification like "Greed" or "Fear"
    timestamp: str  # UNIX timestamp
    time_until_update: Optional[str] = None  # Time until next update (optional)

    model_config = ConfigDict(extra="ignore")


class Metadata(BaseModel):
    error: Optional[str] = None  # Error field in metadata


class SentimentResponse(BaseModel):
    name: str  # Name of the index
    data: List[SentimentDataItem]  # List of sentiment data points

    model_config = ConfigDict(extra="ignore")


SentimentResponseType = Union[SentimentResponse, ErrorResponse]
ArticleResponseType = Union[List[Article], ErrorResponse]
