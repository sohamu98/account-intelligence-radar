import json

def test_expected_shape():
    content = '{"selected":[{"url":"https://example.com","reason":"official"}]}'
    parsed = json.loads(content)
    assert "selected" in parsed
    assert isinstance(parsed["selected"], list)