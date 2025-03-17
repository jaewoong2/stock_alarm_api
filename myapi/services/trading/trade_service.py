# myapi/services/trading/trading_service.py

from typing import Any, Optional
from myapi.services.trading.trade_monitor import TradeMonitor
from myapi.services.trading.trade_executor import TradeExecutor
from myapi.utils.trading_utils import TradingUtils


class TradingService:
    def __init__(
        self,
        ai_service: Any,
        backdata_service: Any,
        coinone_service: Any,
        trading_repository: Any,
    ) -> None:
        self.trading_utils = TradingUtils(
            rsi_overbought=70,
            rsi_oversold=30,
            macd_tolerance=0.01,
            ma_tolerance=0.01,
        )
        self.trade_monitor = TradeMonitor(backdata_service, self.trading_utils)
        self.trade_executor = TradeExecutor(
            ai_service=ai_service,
            backdata_service=backdata_service,
            coinone_service=coinone_service,
            trading_repository=trading_repository,
            trading_utils=self.trading_utils,
        )

    def monitor_triggers(
        self, symbol: str, interval: str = "15m", size: int = 200
    ) -> Any:
        return self.trade_monitor.monitor_triggers(symbol, interval, size)

    def execute_trade(
        self,
        symbol: str,
        interval: str = "1h",
        opinion: Optional[str] = None,
        size: int = 500,
    ) -> Any:
        return self.trade_executor.execute_trade(symbol, interval, opinion, size)
