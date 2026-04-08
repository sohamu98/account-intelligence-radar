# Architecture Documentation

## System Overview

Account Intelligence Radar is a three-layer pipeline that transforms a company name or geography query into a structured business intelligence report.

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (React)                       │
│  ┌──────────┐  ┌──────────────┐  ┌───────────────────┐  │
│  │ Input    │  │ Job Status   │  │ Results Display   │  │
│  │ Form     │  │ Polling      │  │ JSON/MD/CSV       │  │
│  └────┬─────┘  └──────┬───────┘  └─────────┬─────────┘  │
│       │               │                    │             │
└───────┼───────────────┼────────────────────┼────────────┘
        │ POST /api/jobs │ GET /api/jobs/{id}  │ GET /download
        ▼               ▼                    ▼
┌─────────────────────────────────────────────────────────┐
│                  Backend (FastAPI)                        │
│  ┌────────────────────┐  ┌────────────────────────────┐  │
│  │  Job Manager       │  │  REST API Endpoints        │  │
│  │  (APScheduler)     │  │  /api/jobs/*               │  │
│  │                    │  │  /health                   │  │
│  │  job_queue: dict   │  └────────────────────────────┘  │
│  │  status tracking   │                                  │
│  └─────────┬──────────┘                                  │
└────────────┼────────────────────────────────────────────┘
             │ async execution
             ▼
┌─────────────────────────────────────────────────────────┐
│                Intelligence Pipeline                      │
│                                                          │
│  1. SerpAPI          2. DeepSeek           3. Firecrawl  │
│  ┌──────────┐        ┌──────────┐          ┌──────────┐  │
│  │ Google   │ ──→    │ URL      │  ──→     │ Extract  │  │
│  │ Search   │        │ Selection│          │ & Parse  │  │
│  │ Results  │        │ Reasoning│          │ JSON     │  │
│  └──────────┘        └──────────┘          └──────────┘  │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

## Component Details

### 1. Frontend (React + Vite)
- **Mode selector**: Company vs Geography
- **Form validation**: Client-side using React state
- **Job polling**: `setInterval` at 2-second intervals
- **Results display**: JSON formatted, Markdown preview, CSV download
- **Error handling**: User-friendly messages with 402 balance hints

### 2. Backend API (FastAPI)
- **Endpoints**: POST company/geography jobs, GET job status, GET downloads
- **CORS**: Configured for local dev (5173, 3000) and production (port 80)
- **Async**: All endpoint handlers are async for non-blocking I/O
- **Lifespan**: Startup/shutdown hooks for job manager lifecycle

### 3. Job Manager (APScheduler)
- **Queue**: In-memory dict of `Job` objects (suitable for single-server)
- **Scheduler**: `AsyncIOScheduler` — jobs execute on the asyncio event loop
- **Progress**: Callback pattern — pipeline updates `job.progress` string
- **Error isolation**: Catches both `ValueError` (user-facing) and unexpected exceptions

### 4. Intelligence Pipeline
#### Step 1: SerpAPI Discovery
- Constructs a search query: `{company} official site annual report news`
- Returns up to 10 organic results with title, URL, snippet
- Raises `ValueError` if no results returned

#### Step 2: DeepSeek URL Selection
- Sends filtered results to DeepSeek model
- Filters blocked domains (LinkedIn, social media) before sending
- Returns indices of top N most relevant URLs
- Gracefully falls back to first N results if JSON parsing fails
- Handles HTTP 402 with user-friendly balance error message

#### Step 3: Firecrawl Extraction
- Sends URLs + structured schema to Firecrawl Extract API
- Supports both synchronous and async (polling) Firecrawl responses
- Schema covers: company identifiers, executives, initiatives, etc.
- Handles 402 (balance), 429 (rate limit), and timeout scenarios

### 5. Report Builder
- Maps raw extracted data to Pydantic `IntelligenceReport` model
- Attaches evidence source URLs to each report
- Converts to JSON, Markdown, and CSV for download

## Data Flow

```
User Input
    │
    ▼
POST /api/jobs/company
    │
    ▼
JobManager.create_job() → returns job_id immediately
    │
    ▼ (async, background)
Pipeline executes:
    ├── search_serp(query) → 10 organic results
    ├── filter_urls(results) → remove blocked domains
    ├── select_urls_with_llm(filtered) → top 5 URLs
    ├── extract_with_firecrawl(urls) → structured JSON
    └── build_report(extracted) → IntelligenceReport
    │
    ▼
job.status = COMPLETED, job.result = report_dict
    │
    ▼
GET /api/jobs/{id} → {status: "completed", result: {...}}
```

## Error Handling Matrix

| Error Type | Source | Handling |
|-----------|--------|---------|
| No SERP results | SerpAPI | `ValueError` with retry hint |
| DeepSeek 402 | DeepSeek | User-friendly balance top-up message |
| DeepSeek invalid JSON | DeepSeek | Fallback to first N URLs |
| Firecrawl 402 | Firecrawl | User-friendly balance message |
| Firecrawl 429 | Firecrawl | Rate limit message with retry hint |
| Firecrawl timeout | Firecrawl polling | Timeout error after 30 attempts |
| Network timeout | httpx | `HTTPError` caught, generic error message |
| Unexpected exception | Any | Generic error, full trace in server logs only |

## Security & Governance

| Concern | Mitigation |
|---------|-----------|
| Secret exposure in logs | All logging uses `type(e).__name__` only; no payloads logged |
| LinkedIn scraping | `filter_urls()` blocks `linkedin.com` and subdomains |
| Social media scraping | `BLOCKED_DOMAINS` set covers major social platforms |
| API key storage | `.env` file only; `.env.example` committed without values |
| robots.txt compliance | Firecrawl handles robots.txt; no direct crawling in pipeline |
| Input injection | Pydantic validation on all request models |

## Scalability Notes

The current architecture uses APScheduler with in-memory job storage, suitable for:
- Single server deployments
- Development and small teams
- Demonstration and pilot use cases

For production scale, consider:
- Replace in-memory store with Redis or PostgreSQL
- Use Celery + Redis for distributed job queue
- Add job result persistence (currently in-memory only, lost on restart)
- Implement authentication (API keys or OAuth2)
- Add rate limiting per user/IP
