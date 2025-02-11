from pydantic import BaseModel


class TqqqFetchResponse(BaseModel):
    current_price: str
    latest_envelope: str
    latest_ma: str
    recommendation: str
