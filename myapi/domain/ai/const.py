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
    next_latest_technical_indicators: str,
    next_mean_technical_indicators: str,
    next_technical_analysis: str,
    technical_analysis: str,
    balances_data: str,
    target_currency: str = "BTC",
    quote_currency: str = "USDT",
    additional_context: str = "None",
    interval: str = "15m",
    next_interval: str = "1h",
    position: str = "NONE",
    leverage: int = 2,
    minimum_amount: float = 0.001,
    maximum_amount: float = 0.001,
    funding_rate: str = "",
):
    """ """
    interval_, interval_str = split_interval(interval)

    # 시스템 프롬프트
    system_prompt = f"""
    You are The World Best short-term futures crypto trading AI.
    Our primary goal: minimize drawdowns and preserve capital. [Maximize profits!].
    """

    # 메인 프롬프트
    prompt = f"""
    You specialize in short-term futures trading for {target_currency}/{quote_currency}.
    Analyze the latest data, but do not force trades if signals are conflicting or weak.

    **Key Instructions**:
    1) Distinguish between a trending market (e.g., strong momentum, price well above/below major MAs) 
       and a ranging market (e.g., Bollinger bands narrow, ADX low).
       - If trending, you may consider partial entry or straightforward LONG/SHORT if confluence is high.
       - If ranging, be more cautious; consider smaller scalps or HOLD.
    2) If indicators conflict (trend says up, oscillator says down, etc.), default to HOLD or minimal position.
    3) Provide a confidence score (0-100%). If <65%, prefer no trade or minimal size.
    4) Use risk/reward ~1:2. Stop Loss around 1–1.5% from entry. 
       Take Profit levels aiming ~2–3% or key fib/pivot levels.
    5) Partial entry/exit is allowed: you can propose entering 50% now, 50% later if confirmation arises.
    6) Summarize the logic for each step, from data analysis to final conclusion.
    7) Provide a short self-critique, highlighting any potential missing info or contradictory signals.

    **Input Data**:
    - Current Position: {position} (Leverage: {leverage}x)
    - Market Data: {market_data}
    - Balances: {balances_data}
    - Funding Rate: {funding_rate}

    **[{interval} interval]**:
    - Mean Indicators (last 24 candles): {mean_technical_indicators}
    - Latest 1 Candle Indicators: {latest_technical_indicators}
    - Technical Analysis: {technical_analysis}

    **[{next_interval} interval]**:
    - Mean Indicators (last 24 candles): {next_mean_technical_indicators}
    - Latest 1 Candle Indicators: {next_latest_technical_indicators}
    - Technical Analysis: {next_technical_analysis}

    Additional Context:
    {additional_context}

    Position Sizing:
    - Minimum: {max(minimum_amount * leverage, 0.002) * 1.2} {target_currency}
    - Maximum: {maximum_amount * leverage} {target_currency}
    
    If uncertain, do not overtrade. Avoid unnecessary risks.
    """

    return prompt, system_prompt
