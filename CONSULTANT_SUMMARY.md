# Consultant Summary: Account Intelligence Radar

**Deliverable**: Account Intelligence Radar — Web Application (Option B)  
**Prepared by**: Engineering Team  
**Date**: December 2024

---

## Problem Solved

Business development teams waste significant time on manual company research — spending hours per prospect to find HQ location, business units, current initiatives, and decision makers. This creates inconsistent targeting and missed outreach opportunities.

**Account Intelligence Radar** solves this by automating the research pipeline: given a company name or geography, the tool generates a structured intelligence report in minutes, with every claim linked to a verified source URL. A business consultant can use this output directly for outreach prioritization, account planning, and stakeholder identification.

---

## Architecture Decisions

### 1. Three-API Pipeline (SerpAPI → DeepSeek → Firecrawl)
I chose this split because each API does one thing well:
- **SerpAPI** provides clean, structured Google results without scraping complexity
- **DeepSeek** adds LLM reasoning to filter and rank URLs by relevance — a step that would be brittle with heuristics alone
- **Firecrawl** handles the hard problem of structured extraction from arbitrary web pages, including robots.txt compliance

### 2. APScheduler over Celery + Redis
For a single-server self-hosted deployment, APScheduler eliminates the operational overhead of maintaining a Redis broker and Celery worker cluster. The trade-off is that job results are in-memory (lost on restart), which is acceptable for this use case. The architecture documents the clear migration path to Celery if needed.

### 3. FastAPI over Flask
FastAPI's async-first design aligns with our pipeline's I/O-bound nature (multiple API calls per job). Pydantic models provide automatic validation and documentation. The OpenAPI spec generated at `/docs` is an added benefit for team collaboration.

### 4. React + Vite over Streamlit
Streamlit produces quick demos but creates a "script-like" user experience. A React frontend allows real-time job polling, tab-based results display, and professional download UX — the kind of interface a consultant would actually use. Vite's instant dev server also improves development velocity.

### 5. LinkedIn Exclusion by Design
LinkedIn explicitly prohibits automated crawling in its ToS. Rather than implementing soft filters, I made LinkedIn exclusion a first-class function (`filter_urls`) that is tested and applied at multiple pipeline stages. This protects the organization from ToS violations and potential IP blocking.

---

## Key Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| **DeepSeek 402 (balance depleted)** | Detected explicitly by HTTP status; user-friendly message with link to top-up page |
| **Firecrawl extraction incomplete** | Structured JSON schema ensures partial extractions are handled gracefully; empty arrays preferred over null |
| **SerpAPI no results** | Explicit `ValueError` with retry guidance; query construction adds fallback terms |
| **LLM returns invalid JSON** | `safe_parse_json()` with multiple fallback strategies (markdown strip, regex extraction); falls back to first N URLs |
| **In-memory job loss on restart** | Documented as known limitation; migration path to Redis/PostgreSQL documented in ARCHITECTURE.md |
| **API rate limiting** | HTTP 429 detected and surfaced as user-friendly message; exponential backoff is the recommended next improvement |
| **Secret exposure** | OWASP-compliant logging: exceptions logged by type only, never by content; no API keys in code |

---

## What I Would Improve Next

Given more time, the following would meaningfully increase production readiness:

1. **Job Persistence** — Store job results in SQLite or PostgreSQL so reports survive server restarts and can be retrieved later

2. **User Authentication** — Add API key or OAuth2 authentication to prevent unauthorized use and enable per-user rate limiting

3. **Report History** — Dashboard showing past reports with search and filter, enabling a report library over time

4. **Confidence Scoring** — Add a data quality score per field (e.g., "headquarters: HIGH confidence — from official about page") to help users calibrate trust

5. **Webhook Notifications** — Long extractions (geography mode, 5+ companies) could benefit from email/webhook notification on completion rather than polling

6. **Expanded Source Coverage** — Integrate company filings APIs (SEC EDGAR, Tadawul disclosures) for more authoritative financial data

7. **Retry Logic with Backoff** — Implement exponential backoff for API rate limits (currently surfaced as errors)

8. **Unit Test Coverage** — Expand test coverage to include pipeline integration tests with mocked API responses

---

*This tool demonstrates that with the right API orchestration and a clean engineering foundation, structured business intelligence can be automated at scale — turning days of analyst work into minutes.*
