# Account Intelligence Radar (Option A — Local CLI)

## Demo Video

https://youtu.be/B9ThpG4nTDA

## What this solves

Consultants lose outreach time because:

1. we don't consistently prioritize the right companies/sources, and
2. we don't systematically extract decision signals with evidence.

This tool turns a company name + objective into:

- a structured JSON report with evidence per claim, and
- a readable one-page Markdown summary for outreach prep.

## Architecture (happy path)

1. **Discovery**: SerpAPI Google Search API → candidate URLs
2. **Decision**: OpenAI → select best **5** URLs for the objective (LinkedIn/social blocked)
3. **Acquisition/Extraction**: Firecrawl Extract → structured facts + evidence links
4. **Reporting**: `/reports/<timestamp>_<company>/report.json` and `summary.md`

## Setup (Python 3.12.10)

```powershell
cd account-intelligence-radar
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

## Configuration

Create a `.env` file (do NOT commit it) based on `.env.example`:

```bash
SERPAPI_API_KEY=...
OPENAI_API_KEY=...
FIRECRAWL_API_KEY=...
```

## Run

```powershell
python company_research.py
```

If you press Enter at the objective prompt, a default objective is used.

## Outputs

- `reports/<timestamp>_<company>/report.json`
- `reports/<timestamp>_<company>/summary.md`

## Governance / constraints

- LinkedIn and social domains are excluded from selection (no automated LinkedIn activity).
- Secrets are never printed.
- Traceability: claims are stored with evidence URLs.
- Failure modes are handled (no results, API errors, invalid JSON, partial extraction).

## Next improvements (if more time)

- Add geography mode
- Better de-duplication / canonicalization and domain trust scoring
- Stronger schema validation + JSON repair loop
- CI + pytest included by default
