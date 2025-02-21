# 수정된 프롬프트
import json
from typing import Dict, List

from myapi.domain.trading.coinone_schema import OrderRequest


def generate_prompt(
    market_data: Dict,
    technical_indicators: Dict,
    previous_trade_info: str,
    balances_data: Dict,
    volatility_data: Dict | None = None,
    volume_trends: Dict | None = None,
    sentiment_data: Dict | None = None,
    trade_history: List[Dict] | None = None,  # 동적 학습용 과거 거래 데이터
    quote_currency: str = "KRW",
    target_currency: str = "BTC",
    max_trades_per_update: int = 1,
):
    """
    Generate an advanced prompt with complex condition support and dynamic learning:
      - 6-hour plan with 5-minute updates
      - Supports technical indicator combinations (e.g., "BB_upper > price and RSI > 70")
      - Learns from trade_history to improve strategies
      - Outputs OrderRequest-compatible JSON
    """

    prompt = f"""
You are an AI financial assistant for short-term (15-minute) spot cryptocurrency trading.
Your goal is to maximize profits and minimize risk over a 6-hour window, adapting every 5 minutes.

1. Provide a 6-hour outlook (bullish, bearish, or mixed) with confidence:
   - Analyze market data, technical indicators, order book, volatility, volume, sentiment, and trade history.
   - Example: "BULLISH (confidence: 0.85) if RSI < 70 and volume rising."

2. Define scenario-based trading conditions with complex technical indicator support:
   - Use a structured condition syntax: indicator_name(operator, value) combined with 'and', 'or'.
   - Examples:
     - "price > 145000000 and volume > 1000"
     - "BB_upper < price and RSI > 70" (Bollinger Band upper breakout with overbought RSI)
     - "MACD > 0 and price > EMA_50" (MACD bullish crossover with price above 50 EMA)
   - Adjust order parameters (price, qty) dynamically based on volatility and liquidity.

3. Incorporate dynamic learning from trade history:
   - Analyze past trades (order, execution price, PnL) to refine strategies.
   - Example: "If previous BUY at RSI > 70 led to loss, reduce position size or tighten stop."
   - Suggest improvements based on success/failure patterns.

4. Adapt every 5 minutes while respecting open positions:
   - Avoid conflicting trades unless justified (e.g., >2% price shift).
   - Limit new trades to {max_trades_per_update} per update.

5. Return valid JSON with:
   - "6h_outlook": string (e.g., "BULLISH") with "confidence" (0-1).
   - "actions": list of objects, each with:
       - "order": object matching OrderRequest schema (지정가로 설정)
       - "reason": string (e.g., "Bollinger breakout with overbought signal")
       - "priority": integer (1-5, 1 = highest)
       - action: "SELL" | "BUY"
   - "immediate_action": optional OrderRequest-compatible object.
   - "time_window": string (e.g., "6h" or "15m").
   - "learned_insight": string (e.g., "Reduced qty due to past overbought losses").

6. OrderRequest Schema:
   - side: string (e.g., "BUY" or "SELL")
   - quote_currency: string (e.g., "KRW")
   - target_currency: string (e.g., "BTC")
   - type: string (e.g., "LIMIT", "MARKET", "STOP_LIMIT")
   - price: optional string (required for LIMIT or STOP_LIMIT)
   - qty: optional string (required for LIMIT, STOP_LIMIT, or MARKET SELL)
   - amount: optional string (required for MARKET BUY)
   - post_only: optional boolean (applies to LIMIT)
   - limit_price: optional string (applies to MARKET)
   - trigger_price: optional string (required for STOP_LIMIT)
 
7. Ensure non-conflicting scenarios:
   - Use 'priority' to resolve overlaps.
   - Fallback to HOLD if conditions are unclear.

8. Optimize costs:
   - Prefer LIMIT orders with post_only=True; use MARKET only if urgent or low liquidity.
   - Consider maker/taker fees from fee_info.

9. Input Data:
Market Data (5-minute candles):
{json.dumps(market_data, indent=2)}

Technical Indicators (RSI, MACD, BB, EMA, etc.):
{json.dumps(technical_indicators, indent=2)}

Previous Trade Info:
{previous_trade_info}

Current My Balances Data:
{json.dumps(balances_data, indent=2)}

Volatility Data:
{json.dumps(volatility_data if volatility_data else {}, indent=2)}

Volume Trends:
{json.dumps(volume_trends if volume_trends else {}, indent=2)}

Sentiment Data:
{json.dumps(sentiment_data if sentiment_data else {}, indent=2)}

Trade History (past orders, execution prices, PnL):
{json.dumps(trade_history if trade_history else [], indent=2)}

Constraints:
- Default quote_currency: {quote_currency}, target_currency: {target_currency}.
- Ensure orders match OrderRequest validation (e.g., MARKET BUY needs amount).
- Support complex conditions with technical indicators (BB_upper, RSI, MACD, etc.).
- Learn from trade_history to refine risk/reward.
- Return only valid JSON, no extra text.

Return JSON matching the above structure.
"""
    return prompt
