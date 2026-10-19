"""Tests for tools. Parsing/extraction tests are offline (fixture HTML)."""

from scout import tools


DDG_FIXTURE = """
<html><body>
<div class="result">
  <a class="result__a" href="/l/?kh=-1&amp;uddg=https%3A%2F%2Fexample.com%2Fpage1">First Title</a>
  <a class="result__snippet" href="https://example.com/page1">first snippet text</a>
</div>
<div class="result">
  <a class="result__a" href="https://example.org/direct">Second Title</a>
</div>
</body></html>
"""

PAGE_FIXTURE = """
<html><head><title>Fixture Page</title><script>var x = 1;</script></head>
<body><h1>Hello</h1><p>World of  testing.</p><style>.a{color:red}</style></body></html>
"""


def test_ddg_parser_extracts_results_and_unwraps_redirect():
    parser = tools._DDGParser()
    parser.feed(DDG_FIXTURE)
    assert len(parser.results) == 2
    assert parser.results[0]["title"] == "First Title"
    assert parser.results[0]["url"] == "https://example.com/page1"
    assert parser.results[0]["snippet"] == "first snippet text"
    assert parser.results[1]["url"] == "https://example.org/direct"


def test_fetch_page_extracts_text_and_drops_script_style(monkeypatch):
    class FakeResp:
        headers = {"Content-Type": "text/html"}

        def raise_for_status(self):
            pass

        text = PAGE_FIXTURE

    monkeypatch.setattr(
        tools.requests, "get", lambda *a, **k: FakeResp()
    )
    page = tools.fetch_page("https://example.com")
    assert page["title"] == "Fixture Page"
    assert "Hello" in page["text"] and "World of testing." in page["text"]
    assert "var x = 1" not in page["text"]
    assert "color:red" not in page["text"]


def test_fetch_page_failure_is_reported_not_raised(monkeypatch):
    def boom(*a, **k):
        raise ConnectionError("offline")

    monkeypatch.setattr(tools.requests, "get", boom)
    page = tools.fetch_page("https://example.com")
    assert page["text"].startswith("[fetch failed:")


def test_web_search_failure_is_reported_not_raised(monkeypatch):
    def boom(*a, **k):
        raise ConnectionError("offline")

    monkeypatch.setattr(tools.requests, "get", boom)
    results = tools.web_search("anything")
    assert results and results[0]["snippet"].startswith("[search failed:")


def test_mock_search_and_fetch_are_deterministic():
    r1 = tools.mock_search("anything at all")
    r2 = tools.mock_search("something else entirely")
    assert r1 == r2
    assert len(r1) >= 2
    for r in r1:
        page = tools.mock_fetch(r["url"])
        assert page["title"] == r["title"]
        assert len(page["text"]) > 50


def test_mock_fetch_unknown_url():
    page = tools.mock_fetch("https://example.com/unknown")
    assert "No mock content" in page["text"]
