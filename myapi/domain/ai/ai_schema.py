from myapi.domain.trading.coinone_schema import OrderRequest


class AnalyzeResponseModel(OrderRequest):
    action: str
    reason: str
