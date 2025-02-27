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
    target_currency: str = "BTC",
    quote_currency: str = "KRW",
    trigger_action: str = "",
    additional_context: str = "",
):
    """
    Generate an advanced prompt with complex condition support and dynamic learning:
      - 6-hour plan with 15-minute updates
      - Supports technical indicator combinations (e.g., "BB_upper > price and RSI > 70")
      - Learns from trade_history to improve strategie
      - Outputs OrderRequest-compatible
    """

    prompt = f"""
      You are an AI financial assistant for short-term spot cryptocurrency trading on Coinone.
      Your goal is to maximize profits and minimize risk.

      ### 1. Analyze Market Conditions and Validate Trigger Action
         - A trigger has detected a potential trading opportunity: {trigger_action or "No trigger detected"}.
         - Use market data, technical indicators (RSI, MACD, BB, VWAP), order book, volatility, volume, and trade history to validate this trigger.
         - Data is based on **1-hour candles**, reflecting longer-term trends triggered by 15-minute checks.
         - Example validation:
            - For BUY: "Confirm if RSI < 30, price < BB_lower, and volume rising."
            - For SELL: "Confirm if RSI > 70, price > BB_upper, and volume dropping."
         - If no trigger is provided, analyze conditions and suggest an action (BUY, SELL, HOLD).
         - Flag high volatility if 1-hour volatility > 5% or price change > 3%.

      2. Return valid with:
         - "action": list of objects, each with:
            - "order": object matching "Coinone OrderRequest schema" (or "HOLD" if no action)
            - "reason": string more specific than scenario-based conditions
            - "prediction": "UP" | "DOWN" (If the price will be up, "UP" else the price will be down, "DOWN")
            - "market_outlook": string describing your best guess if price will rise or fall in the next few hours
            
      3. Coinone OrderRequest Schema:
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

      4. Ensure non-conflicting scenarios and optimize costs:
         - Prefer LIMIT with post_only=true unless urgency high (volatility < 5%).
         - Use limit_price for MARKET to cap at ±5% of current price.
         - Halt trading if PnL < -5% of initial balance.

      5. Input Data:
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
         - additional_context: {additional_context}

      6. Constraints:
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
         
      7. Balance Limits:
         - BUY: 5000 < (qty * price OR amount) ≤ {balances_data["KRW"]["available"]}.
         - SELL: qty ≤ {balances_data["BTC"]["available"]}.
         - For CANCEL, use order_id from {current_active_orders}.
      """
    return prompt
