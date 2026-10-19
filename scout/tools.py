"""Tools for the agent: free web search (DuckDuckGo) and page fetching.

Live tools need internet but no API keys. ``mock_search`` / ``mock_fetch``
are deterministic, offline stand-ins used by ``--mock`` mode, tests and the demo.
"""

from __future__ import annotations

import html as html_module
import urllib.parse
from html.parser import HTMLParser

import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) ScoutResearchAgent/0.1 (+local research tool)"
}
DDG_HTML_URL = "https://html.duckduckgo.com/html/"


# -- DuckDuckGo result parsing --------------------------------------------

class _DDGParser(HTMLParser):
    """Extracts (title, url, snippet) triples from DuckDuckGo's html endpoint."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.results: list[dict] = []
        self._cap_title = False
        self._cap_snippet = False
        self._href = ""
        self._buf: list[str] = []
        self._sbuf: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        cls = dict(attrs).get("class", "") or ""
        if tag == "a" and "result__a" in cls:
            self._cap_title = True
            self._href = dict(attrs).get("href", "") or ""
            self._buf = []
        elif "result__snippet" in cls:
            self._cap_snippet = True
            self._sbuf = []

    def handle_data(self, data: str) -> None:
        if self._cap_title:
            self._buf.append(data)
        elif self._cap_snippet:
            self._sbuf.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._cap_title:
            self._cap_title = False
            url = self._href
            if url.startswith("/l/?"):  # DuckDuckGo redirect wrapper
                qs = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
                url = qs.get("uddg", [url])[0]
            title = "".join(self._buf).strip()
            if url.startswith("http") and title:
                self.results.append({"title": title, "url": url, "snippet": ""})
        elif self._cap_snippet and tag in ("a", "td", "div"):
            self._cap_snippet = False
            snippet = "".join(self._sbuf).strip()
            if snippet and self.results and not self.results[-1]["snippet"]:
                self.results[-1]["snippet"] = snippet


def web_search(query: str, max_results: int = 5, timeout: int = 20) -> list[dict]:
    """Free web search via DuckDuckGo's html endpoint. No API key needed."""
    try:
        resp = requests.get(
            DDG_HTML_URL,
            params={"q": query},
            headers=HEADERS,
            timeout=timeout,
        )
        resp.raise_for_status()
    except Exception as exc:
        return [{"title": "", "url": "", "snippet": f"[search failed: {exc}]"}]
    parser = _DDGParser()
    parser.feed(resp.text)
    return parser.results[:max_results]


# -- Page fetching / text extraction ---------------------------------------

class _TextParser(HTMLParser):
    """Naive readable-text extractor: drops script/style/noscript content."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style", "noscript"):
            self._skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "noscript") and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip:
            text = data.strip()
            if text:
                self.parts.append(text)


def _extract_title(html_text: str) -> str:
    class _Title(HTMLParser):
        def __init__(self) -> None:
            super().__init__(convert_charrefs=True)
            self.in_title = False
            self.buf: list[str] = []

        def handle_starttag(self, tag, attrs):
            if tag == "title":
                self.in_title = True

        def handle_endtag(self, tag):
            if tag == "title":
                self.in_title = False

        def handle_data(self, data):
            if self.in_title:
                self.buf.append(data)

    p = _Title()
    p.feed(html_text[:20000])
    return html_module.unescape("".join(p.buf).strip())


def fetch_page(url: str, max_chars: int = 8000, timeout: int = 15) -> dict:
    """Fetch a URL and return {'url', 'title', 'text'} (plain text, truncated)."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
    except Exception as exc:
        return {"url": url, "title": "", "text": f"[fetch failed: {exc}]"}
    ctype = resp.headers.get("Content-Type", "")
    if "html" not in ctype and "text" not in ctype:
        return {"url": url, "title": "", "text": "[non-HTML content skipped]"}
    raw = resp.text[: max_chars * 4]
    parser = _TextParser()
    parser.feed(raw)
    text = " ".join(parser.parts)
    text = " ".join(text.split())
    return {"url": url, "title": _extract_title(raw), "text": text[:max_chars]}


# -- Deterministic mock tools (offline) ------------------------------------

_MOCK_PAGES = {
    "https://arxiv.org/abs/2005.11401": {
        "title": "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks (arXiv:2005.11401)",
        "text": (
            "Retrieval-Augmented Generation (RAG) combines pre-trained parametric memory "
            "with non-parametric retrieved passages. A dense retriever fetches relevant "
            "documents from an index such as Wikipedia, and a sequence-to-sequence model "
            "conditions on both the query and the retrieved text to generate answers. "
            "The paper shows this reduces hallucination on knowledge-intensive tasks."
        ),
    },
    "https://aws.amazon.com/what-is/retrieval-augmented-generation/": {
        "title": "What is Retrieval-Augmented Generation (RAG)? — AWS",
        "text": (
            "Retrieval-Augmented Generation grounds large language model outputs in "
            "external knowledge sources. A typical RAG pipeline has three stages: "
            "create an index of external data, retrieve the most relevant chunks for a "
            "query, and augment the prompt so the model answers from retrieved context. "
            "This keeps answers current without retraining the model."
        ),
    },
    "https://www.ibm.com/think/topics/retrieval-augmented-generation": {
        "title": "What is retrieval-augmented generation (RAG)? — IBM",
        "text": (
            "RAG improves LLM accuracy by connecting the model to authoritative external "
            "sources. Common limitations include retrieval quality dependence, added "
            "latency from the search step, and the need for good chunking strategies. "
            "Use cases span customer support, enterprise search, and document Q&A."
        ),
    },
}


def mock_search(query: str, max_results: int = 5, **kwargs) -> list[dict]:
    """Deterministic fake search: always returns the canned RAG pages."""
    results = [
        {
            "title": page["title"],
            "url": url,
            "snippet": page["text"][:160],
        }
        for url, page in _MOCK_PAGES.items()
    ]
    return results[:max_results]


def mock_fetch(url: str, max_chars: int = 8000, **kwargs) -> dict:
    """Deterministic fake fetch: returns canned page text for known URLs."""
    page = _MOCK_PAGES.get(url)
    if page is None:
        return {
            "url": url,
            "title": "Unknown mock page",
            "text": "No mock content for this URL.",
        }
    return {"url": url, "title": page["title"], "text": page["text"][:max_chars]}
