# Research Service Implementation

## Overview

This document describes the comprehensive research and analysis service implementation that combines multiple AI services to provide investment research capabilities. The service integrates Perplexity AI for research, OpenAI o4-mini for sector analysis, and additional Perplexity analysis for leading stock identification.

## 🏗️ Architecture

### Service Components

1. **Perplexity Research Service** - Searches for recent issues/policies/press releases
2. **O4-Mini Sector Analysis Service** - Analyzes 4-stage sector ripple effects  
3. **Perplexity Leading Stocks Service** - Identifies leading technology stocks
4. **Comprehensive Research Service** - Combines all three services
5. **Database Integration** - Saves and retrieves analysis results

## 📁 File Structure

```
myapi/
├── domain/
│   └── research/
│       ├── __init__.py
│       └── research_schema.py          # Pydantic schemas for all services
├── services/
│   └── research_service.py             # Main research service implementation
├── routers/
│   └── research_router.py              # FastAPI endpoints
├── containers.py                       # Updated with research service DI
└── main.py                            # Updated with research router
```

## 🔧 Implementation Details

### 1. Pydantic Schemas (`research_schema.py`)

#### Core Research Schemas
```python
class ResearchItem(BaseModel):
    title: str
    date: str = Field(..., description="YYYY-MM-DD format")
    source: str = Field(..., description="URL")
    summary: str = Field(..., description="1-2 sentence summary")
    entities: List[str] = Field(..., description="Key entities")
    event_type: Literal["policy", "budget", "tech", "regulation", "sanction", "capex", "rfp"]

class ResearchRequest(BaseModel):
    region: str = Field(..., description="e.g., US/Korea/Europe")
    topic: str = Field(..., description="e.g., AI data centers, SMRs")
    period_days: int = Field(14, description="Recent days")
    language: str = Field("Korean", description="Summary language")
```

#### Sector Analysis Schemas
```python
class SectorAnalysis(BaseModel):
    sector: str
    reason: str
    companies: List[str]

class SectorAnalysisData(BaseModel):
    primary_beneficiaries: List[SectorAnalysis]
    supply_chain_beneficiaries: List[SectorAnalysis]
    bottleneck_solution_beneficiaries: List[SectorAnalysis]
    infrastructure_beneficiaries: List[SectorAnalysis]
```

#### Leading Stock Schemas
```python
class StockMetrics(BaseModel):
    ticker: str
    company_name: str
    revenue_growth_rate: Optional[float]
    rs_strength: Optional[float]
    market_cap: Optional[float]
    sector: str
    current_price: Optional[float]
    volume_trend: Optional[str]

class LeadingStock(BaseModel):
    stock_metrics: StockMetrics
    analysis_summary: str
    growth_potential: str
    risk_factors: List[str]
    target_price: Optional[float]
    recommendation: Literal["Strong Buy", "Buy", "Hold", "Sell", "Strong Sell"]
```

### 2. Research Service (`research_service.py`)

#### Core Methods

**Perplexity Research**
```python
async def perplexity_research(self, request: ResearchRequest) -> ResearchResponse:
    """Execute Perplexity search for research topics."""
    prompt = self._build_research_prompt(request)
    response = self.ai_service.perplexity_completion(prompt=prompt, schema=ResearchResponse)
    return response
```

**O4-Mini Sector Analysis**
```python
async def o4_mini_sector_analysis(self, request: SectorAnalysisRequest) -> SectorAnalysisResponse:
    """Execute o4-mini sector analysis."""
    prompt = self._build_sector_analysis_prompt(request.news_content)
    response = self.ai_service.completions_parse(
        prompt=prompt,
        schema=SectorAnalysisResponse,
        system_prompt="You are an expert financial analyst...",
        chat_model=ChatModel.O4_MINI,
    )
    return response
```

**Comprehensive Analysis**
```python
async def comprehensive_research_analysis(self, request: ComprehensiveResearchRequest) -> ComprehensiveResearchResponse:
    """Execute comprehensive research analysis combining all services."""
    # Step 1: Perplexity Research
    research_results = await self.perplexity_research(research_request)
    
    # Step 2: Sector Analysis
    sector_analysis = await self.o4_mini_sector_analysis(sector_analysis_request)
    
    # Step 3: Leading Stocks Analysis
    leading_stocks = await self.perplexity_leading_stocks(leading_stock_request)
    
    # Step 4: Combine Results
    return ComprehensiveResearchResponse(analysis=comprehensive_data)
```

### 3. AI Prompts (English)

#### Perplexity Research Prompt
```
Role: You are an evidence-based research assistant.
Task: Search for recent issues/policies/press releases based on the parameters below and return each item as a JSON array.
Required: (1) Source link, (2) Initial announcement 'date', (3) Summary in 1-2 sentences, (4) Key entities (institutions/companies/regions), (5) Event type (policy/budget/tech announcement/regulation/sanctions/Capex/RFP, etc.).
Quality requirements: Remove duplicate articles of the same event, prioritize official documents/press releases.
```

#### O4-Mini Sector Analysis Prompt
```
# Role Assignment
You are a top-tier securities analyst with 20 years of experience. You specialize in analyzing macroeconomic and industry trends to predict cascading ripple effects, and through this, you discover hidden beneficiary sectors and stocks.

### Primary Beneficiary Sectors (Direct Benefits)
### Secondary Beneficiary Sectors (Supply Chain/Upstream Benefits)  
### Tertiary Beneficiary Sectors (Problem Solving/Bottleneck Benefits)
### Quaternary Beneficiary Sectors (Infrastructure/Ecosystem Expansion Benefits)
```

#### Perplexity Leading Stocks Prompt
```
You are a technology stock specialist analyst. Please find and analyze leading stocks in the following sectors:

**Selection Criteria:**
1. Revenue growth rate averaging 15% or higher over the last 4 quarters
2. Relative Strength (RS) index of 70 or higher compared to S&P500
3. Focus on technology stocks (AI, semiconductors, software, biotech, cleantech, etc.)
4. Market capitalization of $1 billion or more
5. Recent trading volume showing an increasing trend compared to average
```

### 4. API Endpoints (`research_router.py`)

#### Available Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/research/search` | Perplexity research only |
| POST | `/research/sector-analysis` | O4-mini sector analysis only |
| POST | `/research/leading-stocks` | Perplexity stock analysis only |
| POST | `/research/comprehensive` | Combined analysis (all 3 steps) |
| POST | `/research/analysis` | Save comprehensive analysis to database |
| GET | `/research/analysis` | Retrieve saved analyses with filtering |
| GET | `/research/analysis/by-date/{date}` | Get analyses by specific date |
| GET | `/research/analysis/latest` | Get most recent analysis |
| GET | `/research/health` | Health check |

#### Example API Usage

**Create Comprehensive Research Analysis:**
```bash
POST /research/analysis
{
    "region": "United States",
    "topic": "AI Data Centers",
    "period_days": 14,
    "language": "Korean",
    "min_revenue_growth": 15.0,
    "min_rs_strength": 70.0,
    "target_date": "2025-01-02"
}
```

**Get Research Analysis:**
```bash
GET /research/analysis?target_date=2025-01-02&region=United%20States&limit=10
```

### 5. Database Integration

#### Model Updates
- Fixed `AiAnalysisModel` duplicate column issue
- Removed duplicate `name` column
- Added proper `created_at` timestamp

#### Repository Usage
Uses existing `WebSearchResultRepository` patterns:
- `create_analysis()` - Save comprehensive research data
- `get_all_analyses()` - Retrieve with filtering
- `get_analysis_by_date()` - Date-specific retrieval

### 6. Dependency Injection (`containers.py`)

```python
# Added ResearchService to ServiceModule
research_service = providers.Factory(
    ResearchService,
    websearch_repository=repositories.web_search_repository,
    ai_service=ai_service,
    translate_service=translate_service,
)

# Added research_router to wiring_config
wiring_config = containers.WiringConfiguration(
    modules=[
        # ... existing modules
        "myapi.routers.research_router",
    ]
)
```

## 🚀 Usage Examples

### 1. Individual Service Calls

**Perplexity Research:**
```python
request = ResearchRequest(
    region="United States",
    topic="AI Semiconductors",
    period_days=7,
    language="English"
)
result = await research_service.perplexity_research(request)
```

**Sector Analysis:**
```python
request = SectorAnalysisRequest(
    news_content="Government announces $10B AI chip subsidy program..."
)
result = await research_service.o4_mini_sector_analysis(request)
```

**Leading Stocks:**
```python
request = LeadingStockRequest(
    sectors=["Semiconductors", "AI Software"],
    min_revenue_growth=20.0,
    min_rs_strength=80.0
)
result = await research_service.perplexity_leading_stocks(request)
```

### 2. Comprehensive Analysis

```python
request = ComprehensiveResearchRequest(
    region="United States",
    topic="AI Infrastructure Investment",
    period_days=14,
    language="Korean",
    min_revenue_growth=15.0,
    min_rs_strength=70.0
)
result = await research_service.comprehensive_research_analysis(request)
```

### 3. Database Operations

**Save Analysis:**
```python
request = CreateResearchAnalysisRequest(
    region="United States",
    topic="Green Energy Policy",
    period_days=14,
    target_date=date.today()
)
saved = await research_service.save_research_analysis(request)
```

**Retrieve Analysis:**
```python
request = GetResearchAnalysisRequest(
    target_date=date.today(),
    region="United States",
    limit=5,
    sort_by="date",
    sort_order="desc"
)
results = await research_service.get_research_analysis(request)
```

## 🔧 Configuration

### AI Models Used
- **Perplexity**: `sonar-pro` for research and stock analysis
- **OpenAI**: `o4-mini` for sector analysis
- **Translation**: Integrated with existing `TranslateService`

### Environment Variables Required
- `PERPLEXITY_API_KEY` - For Perplexity AI API access
- `OPENAI_API_KEY` - For OpenAI o4-mini access

## 🐛 Error Handling

The service includes comprehensive error handling:
- Invalid response format validation
- API timeout handling
- Database transaction rollback
- Logging for debugging

## 📊 Data Flow

```
1. User Request → API Endpoint
2. Perplexity Research → Extract news/policies
3. O4-Mini Analysis → 4-stage sector analysis
4. Perplexity Stocks → Leading stock identification
5. Data Combination → Comprehensive result
6. Database Storage → AiAnalysisModel
7. Response Return → Structured JSON
```

## 🔄 Integration Points

### Existing Services
- `AIService` - Core AI model interactions
- `TranslateService` - Korean translation support
- `WebSearchResultRepository` - Database operations

### New Dependencies
- `ResearchService` - Main service implementation
- `research_schema` - Pydantic models
- `research_router` - API endpoints

## 🚀 Deployment

The service is fully integrated into the existing FastAPI application and requires no additional deployment steps beyond the standard application deployment process.

## 📈 Future Enhancements

1. **Caching** - Add Redis caching for expensive API calls
2. **Rate Limiting** - Implement API rate limiting for external services
3. **Async Processing** - Queue-based processing for large research requests
4. **Real-time Updates** - WebSocket support for live analysis updates
5. **Advanced Filtering** - More sophisticated filtering and search capabilities

---

*This implementation provides a robust foundation for investment research and analysis, combining multiple AI services to deliver comprehensive market insights.*