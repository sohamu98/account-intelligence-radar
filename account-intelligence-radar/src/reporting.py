from __future__ import annotations

import json
from pathlib import Path
from typing import Dict


def write_report_files(out_dir: Path, company: str, report: Dict) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / "report.json"
    md_path = out_dir / "summary.md"

    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    # Markdown: consultant-friendly one-pager
    status = report.get("status", "unknown")
    evidence = report.get("evidence", []) or []
    selected_urls = report.get("selected_urls", []) or []

    md = []
    md.append(f"# Account Intelligence Radar — {company}\n")
    md.append(f"**Status:** `{status}`\n")

    if status != "ok":
        md.append("## Notes\n")
        md.append("- The run did not complete successfully. See `report.json` for details.\n")

    if status == "ok":
        ci = report.get("company_identifiers", {}) or {}
        bs = report.get("business_snapshot", {}) or {}
        ls = report.get("leadership_signals", {}) or {}
        si = report.get("strategic_initiatives", []) or []

        md.append("## Company identifiers\n")
        md.append(f"- **Name:** {((ci.get('name') or {}).get('value') or '').strip()}\n")
        md.append(f"- **Headquarters:** {((ci.get('headquarters') or {}).get('value') or '').strip()}\n")

        md.append("\n## Business snapshot\n")
        md.append("- **Business units:**\n")
        for x in (bs.get("business_units") or []):
            md.append(f"  - {x.get('value','')}\n")
        md.append("- **Products & services:**\n")
        for x in (bs.get("products_services") or []):
            md.append(f"  - {x.get('value','')}\n")
        md.append("- **Target industries:**\n")
        for x in (bs.get("target_industries") or []):
            md.append(f"  - {x.get('value','')}\n")

        md.append("\n## Leadership signals (official sources only)\n")
        for ex in (ls.get("executives") or []):
            md.append(f"- {ex.get('name','')} — {ex.get('title','')}\n")

        md.append("\n## Strategic initiatives (signals)\n")
        for x in si:
            md.append(f"- {x.get('value','')}\n")

    md.append("\n## Selected sources (top 5)\n")
    for s in selected_urls:
        md.append(f"- {s.get('url')} — {s.get('reason','')}\n")

    md.append("\n## Evidence URLs used\n")
    for u in evidence:
        md.append(f"- {u}\n")

    md_path.write_text("".join(md), encoding="utf-8")