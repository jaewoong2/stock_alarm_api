# 수정된 프롬프트
import json
from typing import Dict, List


def generate_prompt(
    market_data: Dict,
    technical_indicators: Dict,
    previous_trade_info: str,
    balances_data: Dict,
    volatility_data: Dict | None = None,
    orderbook_data: Dict | None = None,
    sentiment_data: Dict | None = None,
    news_data: Dict | None = None,
    current_active_orders: Dict | None = None,
    trade_history: List[Dict] | None = None,  # 동적 학습용 과거 거래 데이터
    max_trades_per_update: int = 1,
    target_currency: str = "BTC",
    quote_currency: str = "KRW",
):
    """
    Generate an advanced prompt with complex condition support and dynamic learning:
      - 6-hour plan with 15-minute updates
      - Supports technical indicator combinations (e.g., "BB_upper > price and RSI > 70")
      - Learns from trade_history to improve strategie
      - Outputs OrderRequest-compatible
    """

    prompt = f"""
      You are an AI financial assistant for short-term (15-minute) spot cryptocurrency trading on Coinone.
      Your goal is to maximize profits and minimize risk over a 6-hour window, adapting every 15 minutes.

      1. Analyze market conditions and define trading strategy:
         - Use market data, technical indicators (RSI, MACD, BB, VWAP), order book, volatility, volume, and trade history.
         - Example condition: "BULLISH if RSI < 70, VWAP < price, and volume rising."
         - Flag high volatility if 15-minute volatility > 5% or price change > 3%.

      2. Define scenario-based trading conditions with complex technical indicator support:
         - Normal: "price > VWAP and MACD > 0, set price = VWAP * 1.002 (0.2% slippage), qty adjusted for ATR."
         - Volatility protection:
         - If volatility > 5% or price_change > 3% in 15 minutes:
            - HOLD: "No new trades, monitor existing positions."
            - Reduce: "Cut qty by 50% for new orders."
         - If volatility > 10% sustained for 15 minutes, halt all new trades.
         - Example: "price > EMA_50 and volatility < 5%, else HOLD."

      3. Incorporate dynamic learning from trade history:
         - Quantify patterns: "If RSI > 70 led to >60% loss rate, reduce qty by 20%."
         - Volatility adjustment: "If past trades during >5% volatility lost >2%, prioritize HOLD next time."

      4. Adapt every 15 minutes while respecting open positions:
         - Avoid conflicts unless >2% price shift or volatility >5%.
         - Limit new trades to {max_trades_per_update} per update.
         - If volatility > 5%, HOLD new trades unless breakout confirmed (e.g., price > BB_upper + 1%).

      5. Return valid with:
         - "action": list of objects, each with:
            - "order": object matching "Coinone OrderRequest schema" (or "HOLD" if no action)
            - "reason": string more specific than scenario-based conditions

      6. Coinone OrderRequest Schema:
         - side: string (required, "BUY" or "SELL" or "CANCEL")
         - quote_currency: string (required, e.g., "KRW")
         - target_currency: string (required, e.g., "BTC")
         - type: string (required, "LIMIT", "MARKET", "STOP_LIMIT")
         - price: optional string (required for LIMIT or STOP_LIMIT, adjust for 0.2% slippage)
         - qty: optional string (required for LIMIT, STOP_LIMIT, or MARKET SELL, adjust for risk)
         - amount: optional string (required for MARKET BUY)
         - post_only: optional boolean (default true for LIMIT)
         - limit_price: optional string (set for MARKET, e.g., current_price * 1.05)
         - trigger_price: optional string (required for STOP_LIMIT, price - 2*ATR)
         - order_id: optional string (for canceling orders only <IF Side is "CANCEL", The Order_id is required>)
            - order_id is in "Input Data: Current Active Orders"

      7. Ensure non-conflicting scenarios and optimize costs:
         - Prefer LIMIT with post_only=true unless urgency high (volatility < 5%).
         - Use limit_price for MARKET to cap at ±5% of current price.
         - Halt trading if PnL < -5% of initial balance.

      8. Input Data:
         - Quote Currency (Fiat): {quote_currency}
         - Target Currency (Sell|Buy|Hold Currency): {target_currency}
         - Market Data (15-minute candles): {json.dumps(market_data, indent=2)}
         - Technical Indicators (RSI, MACD, BB, VWAP, etc.): {json.dumps(technical_indicators, indent=2)}
         - Previous Trade Info: {previous_trade_info}
         - Balances Data: {json.dumps(balances_data, indent=2)}
         - Sentiment Data: {json.dumps(sentiment_data, indent=2)}
         - News Data: {json.dumps(news_data, indent=2)}
         - Volatility Data: {json.dumps(volatility_data, indent=2)}
         - Orderbook Data: {json.dumps(orderbook_data, indent=2)}
         - Trade History: {json.dumps(trade_history, indent=2)}
         - Current Active Orders: {json.dumps(current_active_orders, indent=2)}

      9. Constraints:
         - Default quote_currency: "KRW", target_currency: "BTC" (configurable).
         - Volatility thresholds:
         - NORMAL: <5%
         - HIGH: 5-10% (reduce qty or HOLD)
         - EXTREME: >10% (halt new trades)
         - Reflect risk in price/qty/trigger_price (e.g., 1:3 risk/reward).
         - Return only valid JSON, no extra text.
         - Buy Cost Must Be More Than 5000 KRW (amount or price * qty)
         - Sell Cost Must Be More Than 5000 KRW
         - For CANCEL, include the order_id from current_active_orders (if cancle order, order_id is required).
         _ [Required] Do Not Exceed MY Balances KRW (IF You Buy, Do Not Exceed My KRW Balance) [qty * price Do Not Exceed My KRW Balance]
         - [Required] Do Not Exceed MY Balances BTC (IF You Sell, Do Not Exceed My BTC Balance)
         
      10. Balance Limits:
         - BUY: 5000 < (qty * price OR amount) ≤ {balances_data["KRW"]["available"]}.
         - SELL: qty ≤ {balances_data["BTC"]["available"]}.
         - For CANCEL, use order_id from {current_active_orders}.
      """
    return prompt
