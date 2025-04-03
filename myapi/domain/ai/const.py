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
    arbitrage_signal: str = "",
    interval: str = "1h",
):
    """ """
    system_prompt = f"""
    [system]
    You are an AI specializing in short-term spot crypto trading. 
    Your main objective is to generate automated trading decisions (BUY, SELL, HOLD, or CLOSE_ORDER) 
    on the Coinone exchange for a specified quote_currency → target_currency pair.

    Your primary objective:
    - Generate a trading decision (BUY, SELL, HOLD, or CLOSE_ORDER) based on the partial
    or sometimes ambiguous data you receive.
    - Where data is incomplete or unclear, make reasonable assumptions and use your
    best judgment.
    - Emphasize a balanced risk management approach (don’t lose my money completely,
    but don’t fear making a trade if you see a good opportunity).
    
    **Key Rules:**
    1. If no trade is recommended, return an action of "HOLD" (or do not place an order).
    2. Obey any constraints on balances, or existing active orders for CLOSE_ORDER.

    Remember:
    - You are focusing on short-term (intraday or multi-hour) trades.
    - Consider technical indicators and market context for your decisions.
    """

    prompt = f"""
    You are an AI specializing in short-term spot crypto trading. Your goal is to perform
    automated trades using {quote_currency} to trade {target_currency}.
    - Detected Trigger: {trigger_action or "no trigger detected"}
    - Decide an appropriate action: "BUY", "SELL", "HOLD", or "CLOSE_ORDER".
    
    to maximize profit by "buying low and selling high". Follow these steps:
    Use all provided data (market, technical, news, sentiment, orderbook) to make an informed prediction. For each prediction, explain your reasoning based on the data.
    ### 0. Steps
        1. Evaluate the current market state using market_data (price, volume, high/low).
        2. Assess technical_indicators
        3. Synthesize all findings and predict UP, DOWN, or NEUTRAL, explaining your reasoning.
        4. Synthesize all data and predict the price direction with a confidence score (0-100%). If <60%, default to NEUTRAL.
        5. Don't Lose My Money

    ### 1. Additional Rules ** importance **
    - Buy OR Sell Order -> Minimum 5,000 KRW (either price * qty or amount).
    - Do not exceed your available balances (in KRW or BTC).
    - Only CLOSE_ORDER if a matching order_id exists in current_active_orders.
    - Use post_only = true by default, but you may adjust based on market conditions.
    - "LIMIT"/"STOP_LIMIT" requires a `price` and `qty`.

    ### 2. Input Data >> It is {interval} interval Input Data
    - quote_currency: {quote_currency}
    - target_currency: {target_currency}
    - market_data: {market_data}
    - technical_indicators: {technical_indicators}
    - previous_trade_info: {previous_trade_info}
    - my current balances_data: {balances_data}
    - sentiment_data: {sentiment_data}
    - news_data: {news_data}
    - orderbook_data: {orderbook_data}
    - arbitrage_signal: {arbitrage_signal}
    - trade_history: {trade_history}
    - current_active_orders: {"\n".join([order.description for order in current_active_orders]) if current_active_orders else "None"}

    ### 3. Additional Context
    - additional_context: {additional_context}

    ### 4. Summary
    - Decide on BUY, SELL, HOLD, or CLOSE_ORDER based on triggers and indicators.
    - Provide your short-term (~4 hours) price prediction ("UP", "DOWN", or "NEUTRAL").
    - Return only the JSON as specified, with no extra text.
    """

    return prompt, system_prompt


def split_interval(interval: str):
    """ """
    if interval.endswith("m"):
        return int(interval[:-1]), "minutes"
    elif interval.endswith("h"):
        return int(interval[:-1]), "hours"
    elif interval.endswith("d"):
        return int(interval[:-1]), "days"
    else:
        return 1, "hours"


def generate_futures_prompt(
    market_data: str,
    latest_technical_indicators: str,
    mean_technical_indicators: str,
    technical_analysis: str,
    balances_data: str,
    target_currency: str = "BTC",
    quote_currency: str = "USDT",
    additional_context: str = "None",
    interval: str = "15m",
    position: str = "NONE",
    leverage: int = 2,
    minimum_amount: float = 0.001,
    maximum_amount: float = 0.001,
    funding_rate: str = "",
):
    interval_, interval_str = split_interval(interval)

    system_prompt = f"""
    You are an AI specializing in short-term futures crypto trading.
    Your Goal is to generate automated trading decisions (LONG, SHORT, HOLD, CLOSE_ORDER)
    for {target_currency}/{quote_currency} pair based on current market data.

    Key Objectives:
    1. Analyze provided data thoroughly, even if partial or ambiguous.
    2. Predict movements for the next {interval_}-{interval_ * 2} {interval_str}, possibly extending to {interval_ * 4} {interval_str} if confidence > 80%.
    3. Always prioritize avoiding liquidation and consistently profitable decisions
    """

    prompt = f"""
    You are an AI specializing in short-term futures crypto.
    Your task is to use {quote_currency} to trade {target_currency} efficiently.

    Steps to Follow:
    1. Analyze market data thoroughly (current price, volume, highs/lows, ATR-based volatility).
    2. Provide decision: "LONG", "SHORT", "HOLD", or "CLOSE_ORDER" based on refined criteria below.
    3. Predict market direction (UP/DOWN/NEUTRAL) for {interval_}-{interval_ * 2} {interval_str} and clearly justify with reasoning.
    4. Provide confidence score (0-100%). Default to NEUTRAL if below 65%.
    5. Define Take Profit (TP) and Stop Loss (SL) levels dynamically based on Input Data.
    6. If Current Position should be closed, "CLOSE_ORDER".

    Risk Management & Capital Allocation:
    - TP: Minimum risk/reward ratio of 1:2 / SL: Max loss 1%~1.5% of entry price
    - TP/SL shoud be set by reachable prices and reached at least 2 hours
    - Think Earn Many Money, Not Lose Money
    - ** Minimum Quantity: {max(minimum_amount * leverage, 0.002) * 1.2} {target_currency} **.
    - ** Maximum Quantity: {maximum_amount * leverage} {target_currency} **.
    - if you are confidence, you can use more more money. !important!
    - Prioritize capital preservation.

    Additional Rules:
    - Weight oversold/overbought RSI conditions heavily in ranging markets (ADX < 25).
    - Use Fibonacci levels (e.g., 38.2%, 61.8%) as secondary TP/SL targets.
    
    - "Please provide a clear step-by-step reasoning process to reach your final decision:
     1) Summarize the key market data
     2) Analyze Input Data's indicators
     3) Brief overview of volume or order flow
     4) Potential near-term support/resistance (or high/low) scenarios
     5) Final conclusion (position type, TP, SL)"

    - "Consider three possible short-term scenarios:
     A) The price goes up
     B) The price goes down
     C) The price moves sideways with minimal volatility

    - "After you present your final conclusion, provide a brief self-critique.
     - Identify any potential oversight or missing analysis
     - If necessary, adjust or refine the final decision accordingly."
    
    Input Data [{interval} interval]:
    - Current position: {position} with leverage {leverage}x.
    - Market Data: {market_data}
    - Mean Technical Indicators With Latest 24 Candles: {mean_technical_indicators}
    - Latest 1 Candle Technical Indicators: {latest_technical_indicators}
    - Technical Analysis: {technical_analysis}
    - Balances: {balances_data}
    - Funding Rate Description: {funding_rate}

    Additional Context: {additional_context}
    """

    return prompt, system_prompt
