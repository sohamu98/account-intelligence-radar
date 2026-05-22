from src.utils import is_blocked_url, canonicalize_url

def test_blocked_linkedin():
    assert is_blocked_url("https://www.linkedin.com/company/example/")

def test_canonicalize_drops_fragment():
    u = canonicalize_url("https://example.com/page#section")
    assert u == "https://example.com/page"