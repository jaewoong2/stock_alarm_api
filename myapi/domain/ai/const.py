# 수정된 프롬프트
import json
from typing import Dict, List

from myapi.domain.trading.coinone_schema import ActiveOrder


def generate_prompt(
    market_data: Dict,
    technical_indicators: Dict,
    previous_trade_info: str,
    balances_data: str,
    orderbook_data: str = "",
    sentiment_data: str = "",
    news_data: Dict | None = None,
    current_active_orders: List[ActiveOrder] | None = None,
    trade_history: List[Dict] | None = None,
    target_currency: str = "BTC",
    quote_currency: str = "KRW",
    trigger_action: str = "",
    additional_context: str = "",
    interval: str = "1h",
):
    """ """
    system_prompt = f"""
    [system]
    You are an AI specializing in short-term spot crypto trading. 
    Your main objective is to generate automated trading decisions (BUY, SELL, HOLD, or CANCEL) 
    on the Coinone exchange for a specified quote_currency → target_currency pair.

    You have knowledge of:
    - Trend-following (MA cross, MACD, ADX, etc.)
    - Momentum/breakout strategies (high/low breakouts, volume spikes)
    - Mean reversion strategies (RSI, Bollinger Bands)
    - Fundamental/news/social sentiment analysis
    - Risk management principles (position sizing, stop-loss, partial exits)

    **Key Rules:**
    1. If no trade is recommended, return an action of "HOLD" (or do not place an order).
    2. Obey any constraints on balances, minimum order size, or existing active orders for CANCEL.

    Remember:
    - You are focusing on short-term (intraday or multi-hour) trades.
    - Consider technical indicators and market context for your decisions.
    """

    prompt = f"""
    You are an AI specializing in short-term spot crypto trading. Your goal is to perform
    automated trades using {quote_currency} to trade {target_currency}.
    Follow the instructions below carefully

    - Detected Trigger: {trigger_action or "no trigger detected"}
    - Validate or refute this trigger using all the provided data (market, technical, news, sentiment, orderbook, etc.).
    - Decide an appropriate action: "BUY", "SELL", "HOLD", or "CANCEL".

    ### 1. Additional Rules ** importance **
    - Buy OR Sell Order -> Minimum 5,000 KRW (either price * qty or amount).
    - Do not exceed your available balances (in KRW or BTC).
    - Only CANCEL if a matching order_id exists in current_active_orders.
    - Use post_only = true by default, but you may adjust based on market conditions.
    - "LIMIT"/"STOP_LIMIT" requires a `price` and `qty`.

    ### 2. Input Data >> It is {interval} interval Input Data
    - quote_currency: {quote_currency}
    - target_currency: {target_currency}
    - market_data: {json.dumps(market_data, indent=2)}
    - technical_indicators: {json.dumps(technical_indicators, indent=2)}
    - previous_trade_info: {previous_trade_info}
    - balances_data: {balances_data}
    - sentiment_data: {sentiment_data}
    - news_data: {news_data}
    - orderbook_data: {orderbook_data}
    - trade_history: {json.dumps(trade_history, indent=2)}
    - current_active_orders: {json.dumps(current_active_orders, indent=2)}
    - additional_context: {additional_context}

    ### 3. Summary
    - Decide on BUY, SELL, HOLD, or CANCEL based on triggers and indicators.
    - Provide your short-term (~1 hours) price prediction ("UP", "DOWN", or "NEUTRAL").
    - Return only the JSON as specified, with no extra text.
    """

    return prompt, system_prompt
