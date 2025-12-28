# ETF Weekly Flows Enhancement

## Summary

Enhanced the ETF weekly flows analysis to provide institutional-grade research with deep insights into market flows, investor behavior, and actionable trading opportunities.

## Changes Made

### 1. Schema Enhancement (`myapi/domain/news/news_schema.py`)

Added comprehensive fields to `ETFFlowItem`:

#### New Flow Metrics
- `aum`: Assets Under Management
- `aum_change_1w`: 1-week AUM change percentage
- `avg_daily_volume`: Average daily trading volume
- `expense_ratio`: ETF expense ratio

#### Flow Analysis Fields
- `flow_rank`: Rank by net inflow (1 = highest)
- `flow_percentile`: Percentile among all ETFs (0-100)
- `flow_trend`: "Accelerating", "Steady", "Decelerating", "Reversing"
- `historical_flow_comparison`: Comparison to historical averages

#### Market Context & Sentiment
- `market_sentiment`: "Very Bullish" to "Very Bearish"
- `key_catalysts`: List of specific events driving flows
- `investor_behavior`: "Risk-on", "Risk-off", "Rotation", etc.
- `institutional_vs_retail`: Flow composition analysis

#### Performance Metrics
- `performance_1w`: 1-week return %
- `performance_1m`: 1-month return %
- `performance_ytd`: Year-to-date return %
- `vs_benchmark`: Performance vs benchmark

#### Detailed Rationale
- `flow_rationale`: Why investors are buying/selling
- `macro_context`: Macro factors affecting the ETF
- `forward_outlook`: What to expect next

#### Risk & Opportunity
- `risk_factors`: List of key risks to monitor
- `opportunities`: List of potential opportunities

### 2. Prompt Enhancement (`myapi/services/web_search_service.py`)

Completely redesigned `generate_etf_weekly_flows_prompt()` to:

#### Analysis Requirements
1. **Flow Data Collection**: Comprehensive 7-day flow metrics
2. **Performance Analysis**: Multi-timeframe performance tracking
3. **Flow Trend Analysis**: Historical comparison and ranking
4. **Market Context & Catalysts**: Specific events and macro themes
5. **Sector/Theme Classification**: Detailed exposure analysis
6. **Market Sentiment Analysis**: Institutional positioning insights
7. **Forward-Looking Analysis**: Actionable predictions
8. **Detailed Rationale**: Deep dive into WHY flows are happening

#### Key Improvements
- Role-based prompt: "Institutional ETF research analyst"
- Emphasis on **WHY** flows happen (not just WHAT)
- **WHAT it means** for broader markets
- Focus on **ACTIONABLE INSIGHTS**
- Real-time data requirements with source citations
- Comprehensive JSON schema with examples

#### Focus Areas
- Top 10-15 ETFs by absolute flow magnitude
- Mix of sector, thematic, broad market, and fixed income ETFs
- Contrarian plays (outflows in winners, inflows in losers)
- Sector rotation pattern identification

## API Usage

### GET Endpoint (Retrieve cached flows)
```bash
GET /news/etf/flows?target_date=2025-01-15&tickers=QQQ,SPY,XLK
```

### POST Endpoint (Generate new analysis)
```bash
POST /news/etf/flows
{
  "universe": ["QQQ", "SPY", "XLK", "XLE", "TLT"],
  "target_date": "2025-01-15",
  "llm_policy": "PERPLEXITY"
}
```

## Response Example

```json
{
  "items": [
    {
      "ticker": "QQQ",
      "name": "Invesco QQQ Trust",
      "net_flow": 1500000000.0,
      "flow_1w": 2200000000.0,
      "volume_change": 0.35,
      "aum": 280000000000.0,
      "aum_change_1w": 0.54,

      "sector": "Technology",
      "themes": ["AI", "Megacap Growth", "NASDAQ 100"],

      "flow_rank": 1,
      "flow_percentile": 98.5,
      "flow_trend": "Accelerating",
      "historical_flow_comparison": "150% above 4-week avg",

      "market_sentiment": "Very Bullish",
      "key_catalysts": [
        "NVIDIA Q4 earnings beat drove AI optimism",
        "Fed pivot expectations strengthened"
      ],
      "investor_behavior": "Risk-on with tech concentration",

      "performance_1w": 5.2,
      "performance_1m": 8.7,
      "performance_ytd": 12.3,
      "vs_benchmark": 2.1,

      "flow_rationale": "Massive inflows driven by AI euphoria...",
      "macro_context": "Fed pivot narrative strengthening...",
      "forward_outlook": "Expect continued inflows if...",

      "risk_factors": [
        "Valuation risk: QQQ trading at 30x P/E",
        "Concentration risk: Top 10 = 55%"
      ],
      "opportunities": [
        "AI theme has multi-year runway",
        "Buyback activity provides support"
      ]
    }
  ],
  "window": "2025-01-08~2025-01-15"
}
```

## Benefits

1. **Institutional-Grade Analysis**: Matches professional ETF research quality
2. **Actionable Insights**: Clear risk/opportunity identification
3. **Market Context**: Understand WHY flows happen, not just the numbers
4. **Forward-Looking**: Predictions and catalysts to watch
5. **Risk Management**: Explicit risk factors for each ETF
6. **Sector Rotation**: Identify market rotation patterns in real-time

## Use Cases

- **Portfolio Managers**: Identify institutional money flow trends
- **Traders**: Find rotation opportunities before they're obvious
- **Risk Managers**: Monitor sentiment shifts and risk-on/risk-off behavior
- **Analysts**: Deep research for client reports and recommendations
- **Retail Investors**: Follow smart money and understand market positioning

## Backward Compatibility

All new fields are **optional** (`Optional[...]` or default values), ensuring:
- ✅ Existing API calls continue to work
- ✅ Old database records remain valid
- ✅ No breaking changes to existing integrations

## Next Steps

Consider adding:
1. Historical flow charting endpoint
2. Flow correlation analysis (which ETFs move together)
3. Alert system for unusual flow patterns
4. Comparison to analyst consensus
5. Social sentiment integration
