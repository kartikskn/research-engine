"""Talking to arXiv: turn pasted links into ids, and ids into metadata.

(Fetching and flattening the LaTeX source is added to this module in step 3.)
Only the standard library is used for HTTP and XML.
"""

import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date

from research_engine.models import PaperMetadata

API_URL = "https://export.arxiv.org/api/query?id_list={arxiv_id}"
USER_AGENT = "research-engine/0.1"  # generic on purpose: arXiv asks clients to identify themselves
REQUEST_DELAY_SECONDS = 3  # arXiv's rule of thumb: at most one request every 3 seconds
TIMEOUT_SECONDS = 30

# New-style ids only: 4 digits, a dot, then 4 or 5 digits ("2310.01234").
# The lookarounds stop us matching inside a longer number; the optional v2 is dropped.
# Old-style ids like "math/0601001" are a known limitation.
_ARXIV_ID = re.compile(r"(?<!\d)(\d{4}\.\d{4,5})(?:v\d+)?(?!\d)")

_ATOM = "{http://www.w3.org/2005/Atom}"
_ARXIV = "{http://arxiv.org/schemas/atom}"


def parse_links(text: str) -> tuple[list[str], list[str]]:
    """Split pasted text (one link per line) into (arxiv ids, lines we couldn't read).

    Ids come back without a version, in the order first seen, with duplicates removed.
    """
    ids: list[str] = []
    bad_lines: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        match = _ARXIV_ID.search(line)
        if match is None:
            bad_lines.append(line)
        elif match.group(1) not in ids:
            ids.append(match.group(1))
    return ids, bad_lines


def parse_metadata(xml_text: str) -> PaperMetadata:
    """Read one paper out of an arXiv Atom API response. Raises ValueError if there isn't one."""
    feed = ET.fromstring(xml_text)
    entry = feed.find(f"{_ATOM}entry")
    # An unknown id gives either no entry or an "error" entry whose id points at /api/errors.
    if entry is None or "/api/errors" in (entry.findtext(f"{_ATOM}id") or ""):
        raise ValueError("paper not found")

    versioned_id = entry.findtext(f"{_ATOM}id") or ""
    id_match = _ARXIV_ID.search(versioned_id)
    if id_match is None:
        raise ValueError(f"unexpected arXiv id: {versioned_id!r}")

    # Titles and abstracts are hard-wrapped across lines in the XML; join them into one line.
    primary = entry.find(f"{_ARXIV}primary_category")
    return PaperMetadata(
        arxiv_id=id_match.group(1),
        title=_one_line(entry.findtext(f"{_ATOM}title")),
        authors=[_one_line(a.findtext(f"{_ATOM}name")) for a in entry.findall(f"{_ATOM}author")],
        published=date.fromisoformat((entry.findtext(f"{_ATOM}published") or "")[:10]),
        # Use primary_category, not the first <category>: that one is just the first listed.
        primary_category=primary.get("term", "") if primary is not None else "",
        abstract=_one_line(entry.findtext(f"{_ATOM}summary")),
    )


def fetch_metadata(arxiv_id: str) -> PaperMetadata:
    """Ask the arXiv API about one paper. Raises ValueError if it doesn't exist."""
    return parse_metadata(_get(API_URL.format(arxiv_id=arxiv_id)))


def _get(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        body = response.read().decode("utf-8")
    time.sleep(REQUEST_DELAY_SECONDS)  # wait after every request so a batch stays polite
    return body


def _one_line(text: str | None) -> str:
    return " ".join((text or "").split())
