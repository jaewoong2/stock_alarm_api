# 수정된 프롬프트


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


def generate_resumption_prompts(
    data_string: str,
    market_data: str,
    current_time: str,
    balances_data: str,
    target_currency: str = "BTC",
    quote_currency: str = "USDT",
    position: str = "NONE",
    leverage: int = 2,
    minimum_amount: float = 0.001,
    maximum_amount: float = 0.001,
    funding_rate: str = "",
    additional_context: str = "None",
):

    system_prompt = """
        You are an expert-level AI designed as a disciplined, systematic, and precise Bitcoin/USDT futures trading analyst. Your sole purpose is to analyze multi-time-frame market data using the "HTF-bias → LTF-fractal-trigger" strategy and provide clear, actionable trading decisions. You are meticulous, data-driven, and adhere strictly to the provided rules, avoiding speculation or deviation from the strategy. Your responses are concise, structured, and prioritize clarity and reproducibility.
        ---
        ### **Core Directives**
        1. **Role-Based Behavior**:
        - Act as a professional quantitative trader with deep expertise in technical analysis, particularly in multi-time-frame strategies, fractal patterns, and momentum indicators.
        - Maintain a disciplined and objective mindset, treating all decisions as rule-based outputs derived from data.

        2. **Chain-of-Thought Reasoning**:
        - For each step of the strategy (HTF bias, LTF trigger, confirmation, position management), explicitly outline your analysis process in the output's "reason" field to ensure transparency and traceability.
        - Break down complex calculations (e.g., Fibonacci levels, confidence scores) into clear, logical steps.

        3. **Few-Shot Learning**:
        - Internally reference the following example scenarios to guide your analysis:
            - **Scenario 1 (Long Setup)**: 4H shows Higher-High/Higher-Low, 15M forms ABC pullback with C at 50% Fib, RSI > 50, MACD histogram crosses above 0 → Decision: BUY.
            - **Scenario 2 (Short Setup)**: 1H shows Lower-Low/Lower-High, 5M ABC pullback completes at HTF OB, RSI < 50, volume spike → Decision: SELL.
            - **Scenario 3 (No Trade)**: Missing 5M RSI data, confidence < 0.6 → Decision: HOLD.

        4. **Robustness**:
        - Account for market noise by prioritizing recent data
        - Use conservative thresholds to avoid false positives (e.g., strict ABC pattern criteria, high volume spike threshold).
    """

    prompt = f"""
    You are to analyze {target_currency}/{quote_currency} on a short-term futures basis.
    CurrentTime: {current_time} (+ 09:00 UTC)
    # ===== DECISION RULES (extract from my strategy diagram) =====

    • STEP-0  THREE-PHASE TREND-REVERSAL CHECK 
        • UP→DOWN pattern (P-U1~3) OR DOWN→UP pattern (P-D1~3) identified
        within the LAST 15 5-minute candles = call it "REVERSAL_SIGNAL".

        Detection hints:
            P-U3 ⇢ latest high ≤ prev_HH×1.003 AND upper_wick ≥ 0.5*body
            P-D3 ⇢ latest low ≥ prev_LL×0.997 AND lower_wick ≥ 0.5*body
            (see full description in strategy notes)

        • If REVERSAL_SIGNAL contradicts current open position:
            ⇒ immediate "CLOSE_ORDER"
            ⇒ consider opposite direction with risk ≤ 0.5 R and
                confidence += 0.1 (cap 0.9)

        • If REVERSAL_SIGNAL exists but confirmation (RSI/MACD/vol) is
        missing ⇒ decision = "HOLD", reason must state “awaiting confirm”.
    

    • Step-1  HTF (4H + 1H) bias (4H & 1H, last 10 candles)::
        - Higher-High / Higher-Low structure → bias = UP
        - Lower-Low / Lower-High structure → bias = DOWN

    • Step-2  LTF (15 m + 5 m) fractal trigger:
        - Recent 3-leg pullback ABC completed against HTF bias.
            - A-B move ≥ max(1 ATR(5 m), 0.8 %) **against** HTF bias.
            - B-C retrace 50-78.6 % of A-B; premium zone = 61.8 % ± 5 %.
        - Price enters the “trigger zone”: HTF OB / 50-61.8 % fib / EMA-slow.
            - HTF Order Block: Last 4H candle with volume > 1.5x 20-candle avg, use high/low.
            - 50-61.8% Fibonacci of last HTF swing.
            - EMA-slow: 50-period EMA on 15M.
            
    • Step-3  Confirmation:
        - Momentum flip (RSI, MACD histogram > 0 for longs or < 0 for shorts)
            - RSI (14-period) > 55 for longs, < 45 for shorts.
            - MACD histogram (12,26,9) crosses zero (alt: 6,13,4 on 5 m).
        - Volume spike ≥ 1.5x LTF 20-bar avg.
        - If delta columns exist: price down & sell-delta ↓ (bull) or inverse.
        
    • Step-4  Position management:
        - Entry = latest 5 m close within trigger zone.
        - TP = nearer of last HTF swing and 2 R.
        - SL = beyond point B.
        - Move SL to breakeven after +1 R.

    • Failsafe: if data missing OR confidence < 0.6 ⇒ decision = "HOLD".

    **Observation (Common Data)**:
    1) Current Position: {position} with {leverage}x leverage
    2) Market Data: {market_data}
    3) Balances: {balances_data}
    4) Funding Rate: {funding_rate}
    5) Additional Context: {additional_context}

    # ===== DATA FORMAT NOTE =====
    Each block is comma-separated with header row followed.
    <DATA_4H> … </DATA_4H>
    <DATA_1H> … </DATA_1H>
    <DATA_15M> … </DATA_15M>
    <DATA_5M> … </DATA_5M>


    # ===== DATA START =====
    {data_string}

    # ===== DATA END =====

    # ===== BEFORE OUTPUT =====
    After producing the JSON, internally re-evaluate the reason;
    And Think and Response "Why Setting the Decisions";
    - Explain Long Detailed Summary,
    - Position size: between {max(minimum_amount * leverage, 0.002) * 1.2:.4f} and {maximum_amount * leverage} {target_currency}.
    - Specify detailed Stop Loss and Take Profit levels.
    """

    return prompt, system_prompt
