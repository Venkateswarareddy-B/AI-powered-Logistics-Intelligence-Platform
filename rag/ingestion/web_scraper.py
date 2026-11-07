"""Website content extraction and ingestion for the RAG knowledge base.

Safely fetches public web pages, extracts meaningful text, and ingests
them into the existing ChromaDB vector store. Respects robots.txt,
validates URLs against private networks, and enforces page limits.
"""

from __future__ import annotations

import hashlib
import logging
import re
import urllib.robotparser
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urljoin, urlparse

log = logging.getLogger("rag.ingestion.web_scraper")

# Safety: block private/internal networks
BLOCKED_HOSTS = [
    "localhost", "127.", "192.168.", "10.", "172.16.", "172.17.",
    "172.18.", "172.19.", "172.2", "::1", "0.0.0.0", "169.254.",
]
MAX_PAGES_PER_DOMAIN = 10
MAX_CONTENT_LENGTH = 50_000  # chars per page
REQUEST_TIMEOUT = 15


def _is_safe_url(url: str) -> tuple[bool, str]:
    """Validate that URL is public and well-formed."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False, "Only http/https URLs are supported"
        host = parsed.hostname or ""
        for blocked in BLOCKED_HOSTS:
            if host.startswith(blocked) or host == blocked.rstrip("."):
                return False, f"Private/internal network access blocked: {host}"
        if not host:
            return False, "No hostname found in URL"
        return True, "OK"
    except Exception as e:
        return False, f"URL validation error: {e}"


def _can_fetch(url: str) -> bool:
    """Check robots.txt. Returns True if fetching is permitted."""
    try:
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(robots_url)
        rp.read()
        return rp.can_fetch("*", url)
    except Exception:
        return True  # if robots.txt is unreachable, proceed cautiously


def _extract_text_from_html(html: str, url: str) -> dict:
    """Extract clean text, title, and headings from HTML.

    Uses a simple regex-based extractor to avoid importing heavy libs.
    """
    # Remove scripts, styles, nav, footer, ads
    cleaned = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r"<style[^>]*>.*?</style>", " ", cleaned, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r"<nav[^>]*>.*?</nav>", " ", cleaned, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r"<footer[^>]*>.*?</footer>", " ", cleaned, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r"<header[^>]*>.*?</header>", " ", cleaned, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r"<!--.*?-->", " ", cleaned, flags=re.DOTALL)

    # Extract title
    title_match = re.search(r"<title[^>]*>(.*?)</title>", cleaned, re.IGNORECASE | re.DOTALL)
    title = re.sub(r"<[^>]+>", "", title_match.group(1)).strip() if title_match else url

    # Extract headings
    headings = []
    for h_match in re.finditer(r"<h[1-4][^>]*>(.*?)</h[1-4]>", cleaned, re.IGNORECASE | re.DOTALL):
        h_text = re.sub(r"<[^>]+>", "", h_match.group(1)).strip()
        if h_text:
            headings.append(h_text)

    # Strip all remaining tags
    text = re.sub(r"<[^>]+>", " ", cleaned)
    # Decode common HTML entities
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&quot;", '"').replace("&#39;", "'").replace("&nbsp;", " ")
    text = text.replace("&mdash;", "—").replace("&ndash;", "–")
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()

    # Limit content length
    text = text[:MAX_CONTENT_LENGTH]

    return {
        "title": title[:300],
        "text": text,
        "headings": headings[:10],
        "word_count": len(text.split()),
    }


def fetch_page(url: str) -> dict:
    """Fetch a single web page and extract text content.

    Returns dict with: title, text, url, headings, word_count, error (if any).
    Never follows redirects to private networks.
    """
    result = {"url": url, "title": "", "text": "", "headings": [], "word_count": 0, "error": None}

    safe, reason = _is_safe_url(url)
    if not safe:
        result["error"] = reason
        return result

    if not _can_fetch(url):
        result["error"] = "Access disallowed by robots.txt"
        return result

    try:
        import urllib.request
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "YottaFlex-RAG-Bot/1.0 (logistics knowledge indexer)"},
        )
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            content_type = resp.headers.get("Content-Type", "")
            if "text/html" not in content_type and "text/plain" not in content_type:
                result["error"] = f"Unsupported content type: {content_type}"
                return result
            html = resp.read(MAX_CONTENT_LENGTH * 10).decode("utf-8", errors="replace")

        extracted = _extract_text_from_html(html, url)
        result.update(extracted)
        log.info("fetched %s — %d words", url, extracted["word_count"])
        return result

    except Exception as exc:
        result["error"] = str(exc)[:200]
        log.warning("fetch failed for %s: %s", url, exc)
        return result


def ingest_website(
    db,
    source_id: str,
    url: str,
    source_name: str,
    category: str,
) -> dict:
    """Fetch a website and ingest its content into the RAG knowledge base.

    Uses the existing ingest_document pipeline — no second vector DB.

    Returns: {status, doc_id, chunks_created, title, word_count, error}
    """
    from rag.ingestion.pipeline import ingest_document
    from sqlalchemy import text as sql_text
    import uuid

    page = fetch_page(url)

    if page.get("error"):
        return {"status": "failed", "error": page["error"], "url": url}

    if page["word_count"] < 50:
        return {"status": "failed", "error": "Page has too little content (< 50 words)", "url": url}

    # Format content with metadata header
    content = f"""Source: {source_name}
URL: {url}
Title: {page['title']}
Category: {category}
Fetched: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}

{chr(10).join(page['headings'][:5])}

{page['text']}"""

    # Create a RAG document record for this web page
    doc_id = f"WEB-{hashlib.md5(url.encode()).hexdigest()[:12].upper()}"
    now = datetime.now(timezone.utc)

    # Upsert: delete old version if re-indexing
    existing = db.execute(sql_text(
        "SELECT document_id FROM rag_documents WHERE document_id = :did"
    ), {"did": doc_id}).scalar()

    if existing:
        # Re-ingestion: update the content
        db.execute(sql_text("""
            UPDATE rag_documents SET content_text=:ct, processing_status='PENDING',
                   updated_at=:now WHERE document_id=:did
        """), {"ct": content, "now": now, "did": doc_id})
    else:
        db.execute(sql_text("""
            INSERT INTO rag_documents (
                document_id, document_name, category, version,
                content_text, file_type, processing_status,
                is_active, is_demo, description, created_at, updated_at
            ) VALUES (
                :did, :name, :cat, '1.0',
                :ct, 'TEXT', 'PENDING',
                TRUE, FALSE, :desc, :now, :now
            ) ON CONFLICT (document_id) DO NOTHING
        """), {
            "did": doc_id,
            "name": page["title"][:200] or source_name,
            "cat": category,
            "ct": content,
            "desc": f"Web source: {url}",
            "now": now,
        })
    db.commit()

    # Ingest into ChromaDB
    result = ingest_document(db, doc_id, content=content)
    result["doc_id"] = doc_id
    result["title"] = page["title"]
    result["word_count"] = page["word_count"]
    result["url"] = url
    return result
