"""Unit tests for utility functions: URL filtering, JSON parsing, error scenarios."""
import pytest
from backend.utils import filter_urls, safe_parse_json, report_to_markdown, report_to_csv_rows


class TestFilterUrls:
    """Tests for URL filtering (LinkedIn and blocked domain exclusion)."""
    
    def test_filters_linkedin_urls(self):
        """LinkedIn URLs must be filtered per ToS."""
        urls = [
            "https://www.linkedin.com/company/acme",
            "https://linkedin.com/in/john-doe",
        ]
        result = filter_urls(urls)
        assert result == []
    
    def test_keeps_non_blocked_urls(self):
        """Non-blocked URLs should pass through."""
        urls = [
            "https://www.acme.com/about",
            "https://news.example.com/article",
            "https://en.wikipedia.org/wiki/ACME",
        ]
        result = filter_urls(urls)
        assert result == urls
    
    def test_filters_facebook_twitter(self):
        """Social media domains should be filtered."""
        urls = [
            "https://www.facebook.com/acme",
            "https://twitter.com/acme",
            "https://x.com/acme",
        ]
        result = filter_urls(urls)
        assert result == []
    
    def test_mixed_urls(self):
        """Mix of blocked and allowed URLs."""
        urls = [
            "https://www.acme.com/about",
            "https://www.linkedin.com/company/acme",
            "https://news.acme.com/press-release",
            "https://twitter.com/acme",
        ]
        result = filter_urls(urls)
        assert "https://www.acme.com/about" in result
        assert "https://news.acme.com/press-release" in result
        assert "https://www.linkedin.com/company/acme" not in result
        assert "https://twitter.com/acme" not in result
    
    def test_handles_empty_list(self):
        """Empty URL list returns empty list."""
        assert filter_urls([]) == []
    
    def test_handles_malformed_urls(self):
        """Malformed URLs should be silently skipped."""
        urls = ["not-a-url", "https://www.valid.com/page"]
        result = filter_urls(urls)
        assert "https://www.valid.com/page" in result
    
    def test_custom_blocked_domains(self):
        """Custom blocked domains work correctly."""
        urls = ["https://www.custom-block.com/page", "https://www.allowed.com/page"]
        result = filter_urls(urls, blocked_domains={"custom-block.com"})
        assert "https://www.allowed.com/page" in result
        assert "https://www.custom-block.com/page" not in result
    
    def test_subdomain_blocking(self):
        """Subdomains of blocked domains are also filtered."""
        urls = ["https://uk.linkedin.com/company/acme"]
        result = filter_urls(urls)
        assert result == []


class TestSafeParseJson:
    """Tests for JSON parsing with LLM response handling."""
    
    def test_parses_valid_json(self):
        """Clean JSON string parses correctly."""
        text = '{"key": "value", "number": 42}'
        result = safe_parse_json(text)
        assert result == {"key": "value", "number": 42}
    
    def test_parses_json_in_markdown_block(self):
        """JSON wrapped in markdown code block."""
        text = '''Here is the result:
```json
{"companies": ["Acme", "Beta Corp"]}
```'''
        result = safe_parse_json(text)
        assert result == {"companies": ["Acme", "Beta Corp"]}
    
    def test_parses_json_in_unmarked_code_block(self):
        """JSON wrapped in unmarked markdown code block."""
        text = '''```
{"key": "value"}
```'''
        result = safe_parse_json(text)
        assert result == {"key": "value"}
    
    def test_extracts_json_from_surrounding_text(self):
        """JSON embedded in surrounding text."""
        text = 'Some explanation here. {"result": true} More text.'
        result = safe_parse_json(text)
        assert result == {"result": True}
    
    def test_returns_none_for_invalid_json(self):
        """Invalid JSON returns None."""
        text = "This is not JSON at all."
        result = safe_parse_json(text)
        assert result is None
    
    def test_returns_none_for_empty_string(self):
        """Empty string returns None."""
        assert safe_parse_json("") is None
        assert safe_parse_json("   ") is None
    
    def test_returns_none_for_none(self):
        """None input returns None."""
        assert safe_parse_json(None) is None
    
    def test_handles_nested_json(self):
        """Nested JSON structures parse correctly."""
        text = '{"executives": [{"name": "John", "title": "CEO"}]}'
        result = safe_parse_json(text)
        assert result["executives"][0]["name"] == "John"


class TestReportToMarkdown:
    """Tests for Markdown report generation."""
    
    def _make_report(self, **overrides):
        """Create a minimal report dict."""
        report = {
            "company_identifiers": {
                "name": "Test Corp",
                "headquarters": "Riyadh, Saudi Arabia",
                "website": "https://testcorp.com",
            },
            "business_snapshot": {
                "business_units": ["Unit A", "Unit B"],
                "products_and_services": ["Product 1"],
                "target_industries": ["Energy"],
            },
            "leadership_signals": {
                "executives": [{"name": "Jane Doe", "title": "CEO"}],
                "note": "From official sources",
            },
            "strategic_initiatives": {
                "transformation": ["Digital transformation program"],
                "ai_initiatives": ["AI deployment"],
                "erp_implementations": [],
                "supply_chain": [],
                "investments": [],
                "expansions": [],
                "other": [],
            },
            "evidence_sources": [
                {"url": "https://testcorp.com/about", "title": "About Us", "relevance": "Official"}
            ],
            "generated_at": "2024-01-01T00:00:00",
        }
        report.update(overrides)
        return report
    
    def test_contains_company_name(self):
        """Markdown contains the company name."""
        md = report_to_markdown(self._make_report())
        assert "Test Corp" in md
    
    def test_contains_headquarters(self):
        """Markdown includes headquarters."""
        md = report_to_markdown(self._make_report())
        assert "Riyadh, Saudi Arabia" in md
    
    def test_contains_executive(self):
        """Markdown lists executives."""
        md = report_to_markdown(self._make_report())
        assert "Jane Doe" in md
        assert "CEO" in md
    
    def test_contains_evidence_url(self):
        """Markdown includes evidence source URLs."""
        md = report_to_markdown(self._make_report())
        assert "https://testcorp.com/about" in md
    
    def test_handles_empty_sections(self):
        """Report with no executives or initiatives doesn't crash."""
        report = self._make_report()
        report["leadership_signals"]["executives"] = []
        report["strategic_initiatives"] = {
            "transformation": [], "ai_initiatives": [], "erp_implementations": [],
            "supply_chain": [], "investments": [], "expansions": [], "other": [],
        }
        md = report_to_markdown(report)
        assert "Test Corp" in md
        assert "No executive data found" in md
    
    def test_contains_strategic_initiatives(self):
        """Markdown lists strategic initiatives."""
        md = report_to_markdown(self._make_report())
        assert "Digital transformation program" in md
        assert "AI deployment" in md


class TestReportToCsvRows:
    """Tests for CSV export."""
    
    def _make_report(self):
        return {
            "company_identifiers": {
                "name": "Test Corp",
                "headquarters": "Riyadh",
                "website": "https://testcorp.com",
                "industry": "Energy",
            },
            "business_snapshot": {
                "business_units": ["Unit A"],
                "products_and_services": ["Product 1"],
                "target_industries": ["Energy"],
                "revenue": "$1B",
                "employees": "10000",
            },
            "leadership_signals": {
                "executives": [{"name": "Jane", "title": "CEO"}],
            },
            "strategic_initiatives": {
                "transformation": ["Digital program"],
                "ai_initiatives": [],
                "erp_implementations": [],
                "investments": [],
                "expansions": [],
            },
            "evidence_sources": [{"url": "https://testcorp.com"}],
            "generated_at": "2024-01-01",
        }
    
    def test_returns_list_of_rows(self):
        """CSV export returns list of rows."""
        rows = report_to_csv_rows(self._make_report())
        assert isinstance(rows, list)
        assert len(rows) > 1
    
    def test_first_row_is_header(self):
        """First row is the header."""
        rows = report_to_csv_rows(self._make_report())
        assert rows[0] == ["Field", "Value"]
    
    def test_contains_company_name(self):
        """CSV includes company name."""
        rows = report_to_csv_rows(self._make_report())
        values = [row[1] for row in rows if row[0] == "Company Name"]
        assert values[0] == "Test Corp"
    
    def test_contains_executives(self):
        """CSV includes executives."""
        rows = report_to_csv_rows(self._make_report())
        exec_values = [row[1] for row in rows if row[0] == "Executives"]
        assert "Jane" in exec_values[0]
