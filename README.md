# Account Intelligence Radar 🎯

> Production-grade business intelligence research tool for company discovery and outreach analysis.

## Overview

Account Intelligence Radar transforms a company name or geography into an actionable intelligence report for business outreach. It orchestrates three AI-powered APIs to discover, reason about, and extract structured business intelligence from the web.

**Pipeline**: SerpAPI (discovery) → DeepSeek (reasoning & URL selection) → Firecrawl (data extraction)

### Key Features

- 🏢 **Company Mode** — Input a company name → receive a structured intelligence report with HQ, executives, strategic initiatives, and evidence links
- 🌍 **Geography Mode** — Input a location + sector → discover relevant companies and generate reports for top N
- ⚡ **Async Job Processing** — APScheduler-based queue with real-time status updates
- 📊 **Multi-format Export** — Download reports as JSON, Markdown, or CSV
- 🔒 **OWASP-Compliant** — No secrets in logs, no LinkedIn scraping, robots.txt respected via Firecrawl
- 🐳 **Docker Ready** — One command to run the entire stack

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 18+
- API keys for: [SerpAPI](https://serpapi.com), [DeepSeek](https://platform.deepseek.com), [Firecrawl](https://firecrawl.dev)

### 1. Clone and configure

```bash
git clone https://github.com/sohamu98/account-intelligence-radar.git
cd account-intelligence-radar
cp .env.example .env
# Edit .env and add your API keys
```

### 2. Run with Docker (Recommended)

```bash
docker-compose up --build
```

Then open: http://localhost

### 3. Run Locally (Development)

**Backend:**
```bash
python -m venv venv
# Windows:
.\venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000
```

**Frontend (separate terminal):**
```bash
cd frontend
npm install
npm run dev
```

Then open: http://localhost:5173

## API Keys Setup

| Variable | Where to Get | Free Tier? |
|----------|-------------|------------|
| `SERPAPI_KEY` | [serpapi.com](https://serpapi.com) | 100 free searches/month |
| `DEEPSEEK_API_KEY` | [platform.deepseek.com](https://platform.deepseek.com) | Low cost, top up as needed |
| `FIRECRAWL_API_KEY` | [firecrawl.dev](https://firecrawl.dev) | 500 free credits/month |

> ⚠️ **Note on DeepSeek 402 errors**: If you get an HTTP 402 error, your DeepSeek balance is depleted. Top up at [platform.deepseek.com](https://platform.deepseek.com). The application will display a user-friendly message in this case.

## API Reference

### Submit Company Job
```http
POST /api/jobs/company
Content-Type: application/json

{
  "company_name": "Saudi Aramco",
  "objective_prompt": "Extract headquarters, business units, executives, and strategic initiatives."
}
```

### Submit Geography Job
```http
POST /api/jobs/geography
Content-Type: application/json

{
  "location": "Saudi Arabia",
  "criteria": "energy, manufacturing",
  "objective_prompt": "Extract key business intelligence for outreach.",
  "top_n": 3
}
```

### Check Job Status
```http
GET /api/jobs/{job_id}
```

### Download Results
```http
GET /api/jobs/{job_id}/download/json
GET /api/jobs/{job_id}/download/markdown
GET /api/jobs/{job_id}/download/csv
```

## Sample Reports

Pre-generated sample reports are in the `/reports` directory:

| Company | Files |
|---------|-------|
| Saudi Aramco (large, well-documented) | `reports/saudi_aramco_report.json`, `reports/saudi_aramco_report.md` |
| ACWA Power (mid-market KSA) | `reports/acwa_power_report.json`, `reports/acwa_power_report.md` |

## Running Tests

```bash
python -m pytest tests/ -v
```

## Project Structure

```
account-intelligence-radar/
├── backend/
│   ├── main.py          # FastAPI app with all endpoints
│   ├── pipeline.py      # SerpAPI → DeepSeek → Firecrawl orchestration
│   ├── job_manager.py   # APScheduler-based async job queue
│   ├── models.py        # Pydantic request/response models
│   ├── config.py        # Environment-based configuration
│   └── utils.py         # URL filtering, JSON parsing, MD/CSV export
├── frontend/
│   └── src/
│       └── App.jsx      # React SPA with all UI components
├── reports/             # Sample intelligence reports
├── tests/               # Unit tests
├── docker-compose.yml   # Full stack deployment
├── Dockerfile           # Backend container
├── requirements.txt     # Python dependencies
├── .env.example         # Environment template
├── ARCHITECTURE.md      # System design documentation
└── CONSULTANT_SUMMARY.md # Professional summary
```

## Governance & Compliance

- **No LinkedIn scraping** — Explicitly blocked per platform ToS
- **OWASP logging** — API keys and payloads never written to logs
- **robots.txt respect** — All web crawling via Firecrawl (which handles robots.txt)
- **Source traceability** — Every claim links to an evidence URL
- **Graceful error handling** — All API failures (402, 429, timeout) produce user-friendly messages
