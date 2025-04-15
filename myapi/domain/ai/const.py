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
    longterm_latest_technical_indicators: str,
    longterm_mean_technical_indicators: str,
    longterm_technical_analysis: str,
    technical_analysis: str,
    balances_data: str,
    target_currency: str = "BTC",
    quote_currency: str = "USDT",
    additional_context: str = "None",
    interval: str = "15m",
    next_interval: str = "1h",
    longterm_interval: str = "4h",
    position: str = "NONE",
    leverage: int = 2,
    minimum_amount: float = 0.001,
    maximum_amount: float = 0.001,
    funding_rate: str = "",
):
    """
    Generate a short-term futures trading prompt using:
      - ReAct: Observations → Thoughts → Actions
      - Chain-of-Thought (CoT): Detailed reasoning steps in the Thought stage

    Returns:
      (prompt: str, system_prompt: str)
    """

    interval_, interval_str = split_interval(interval)

    # ---------------------- SYSTEM PROMPT (고정 or 상황에 맞게 조절) ----------------------
    system_prompt = f"""
    You are an advanced short-term futures crypto trading AI.
    Your goal is to minimize drawdowns, preserve capital, and seek profitable entries when signals align.
    
    Please use the ReAct methodology (Observation → Thought → Action) and in the Thought part, 
    explicitly break down your reasoning with a Chain-of-Thought (CoT).
    Pay special attention to potential trend reversals by analyzing:
      - Candlestick reversal patterns (e.g., Hammer, Inverted Hammer, Shooting Star)
      - Divergence between momentum indicators (e.g., RSI vs MACD)
      - Significant changes in moving average slopes.
    Do not force trades if signals are ambiguous or indicate a reversal.
    """

    # ---------------------- MAIN PROMPT ----------------------
    # ReAct 포맷: Observation → Thought → Action
    # Thought 단계에서 CoT(Chain-of-Thought)로 상세한 reasoning steps 표현하도록 유도
    prompt = f"""
    You are to analyze {target_currency}/{quote_currency} on a short-term futures basis.
    
    Key Objectives:
    1. Predict movements for the next {interval_}-{interval_ * 2} {interval_str}, possibly extending to {interval_ * 4} {interval_str} if confidence > 80%.
    2. Always prioritize avoiding liquidation and consistently profitable decisions
    3. Provide decision: "LONG", "SHORT", "HOLD", or "CLOSE_ORDER" based on refined criteria below.
    4. Predict market direction (UP/DOWN/NEUTRAL) for {interval_}-{interval_ * 2} {interval_str} and clearly justify with reasoning.
    5. If Current Position will not have profit anymore, suggest to CLOSE_ORDER.
    
    **Observation (Data Summary)**:
    1) Current Position: {position} with {leverage}x leverage
    2) Market Data: {market_data}
    3) Balances: {balances_data}
    4) Funding Rate: {funding_rate}

    **{interval} Interval**:
    - Mean Indicators (24 candles): {mean_technical_indicators}
    - Latest 1 Candle Indicators: {latest_technical_indicators}
    - Technical Analysis (summarized): {technical_analysis}

    **{next_interval} Interval**:
    - Mean Indicators (24 candles): {next_mean_technical_indicators}
    - Latest 1 Candle Indicators: {next_latest_technical_indicators}
    - Technical Analysis (summarized): {next_technical_analysis}
    
    **{longterm_interval} Analysis**:
    - Mean Indicators (24 candles): {longterm_mean_technical_indicators}
    - Latest 1 Candle Indicators: {longterm_latest_technical_indicators}
    - Technical Analysis (summarized): {longterm_technical_analysis}
    
    Additional Context:
    {additional_context}

    **Thought (Chain-of-Thought Reasoning)**:
    1) Analyze if the market is trending or showing signs of reversal
    2) Check for divergence between key indicators (e.g., RSI vs MACD) as a confirmation of potential trend reversals.
    3) Review changes in moving averages (both short-term and long-term) to verify trend direction.
    4) Assess overall risk and estimate a confidence level (0~100%). If below 65% or if reversal signals are evident, favor HOLD or CLOSE_ORDER.
    5) Define Possible Entry, Stop Loss (e.g., ~1.0% current away), and Possible Take Profit (e.g., ~2.0% current away) levels if signals are aligned.
    
    **Action (Final Decision)**:
    - If confluence is strong and confidence ≥65%, propose clear trade plan:
      - Position size: between {max(minimum_amount * leverage, 0.002) * 1.2:.4f} and {maximum_amount * leverage} {target_currency}.
      - Specify detailed Stop Loss and Take Profit levels.
    - Otherwise, summarize your analysis with a recommendation to HOLD or CLOSE_ORDER.
    """

    return prompt, system_prompt
