"""SEC EDGAR full-text filings — fetch, extract sections, search, and diff.

This is the "actually reads the 10-K" layer the research terminal needs.
get_sec_financials (agent_tools) already pulls structured XBRL numbers; this
module reads the *text*: recent filings via the EDGAR submissions API, the
primary document stripped to plain text, Item-level section extraction
(Risk Factors, MD&A), semantic passage search, and a quarter/year-over-year
Risk Factors diff — the classic "what changed in the language" alpha read.

Free data, no API key. EDGAR fair-use: declared User-Agent, modest rates,
and everything cached (filing text 24h, filing lists 1h).
"""
from __future__ import annotations

import asyncio
import difflib
import html as html_lib
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

_HEADERS = {"User-Agent": "MarketFlux research@marketflux.app"}
_MAX_FILING_CHARS = 1_500_000  # a 10-K stripped to text comfortably fits
_TOC_MIN_SECTION_CHARS = 1_000  # headings followed by less than this are TOC rows

SUPPORTED_FORMS = ("10-K", "10-Q", "8-K")


# ---------------------------------------------------------------------------
# Pure text helpers (unit-tested in tests/test_sec_filings.py)
# ---------------------------------------------------------------------------
_BLOCK_TAGS = re.compile(r"</(p|div|tr|table|h[1-6]|li|section)>|<br\s*/?>", re.I)
_SCRIPT_STYLE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.I | re.S)
_TAGS = re.compile(r"<[^>]+>")
_XBRL_HIDDEN = re.compile(r"<ix:header.*?</ix:header>", re.I | re.S)


def strip_html(raw: str) -> str:
    """Reduce an EDGAR HTML document to readable plain text.

    Stdlib-only by design (no bs4 dependency): drop script/style and inline-XBRL
    headers, turn block-level closes into newlines, strip tags, unescape
    entities, collapse whitespace but keep line structure.
    """
    if not raw:
        return ""
    text = _XBRL_HIDDEN.sub(" ", raw)
    text = _SCRIPT_STYLE.sub(" ", text)
    text = _BLOCK_TAGS.sub("\n", text)
    text = _TAGS.sub(" ", text)
    text = html_lib.unescape(text)
    text = text.replace("\xa0", " ")
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln)


def extract_item(text: str, item: str, end_items: Tuple[str, ...]) -> str:
    """Extract one Item section (e.g. "1A") from a stripped filing.

    Filings repeat headings in the table of contents, so every candidate
    occurrence is measured and the one followed by real content (longest span
    to the next end-item heading, above a TOC threshold) wins.
    """
    if not text:
        return ""
    flags = re.I
    start_re = re.compile(rf"^\s*item\s+{re.escape(item)}\.?\b", flags)
    end_re = re.compile(
        r"^\s*item\s+(" + "|".join(re.escape(e) for e in end_items) + r")\.?\b", flags)

    lines = text.splitlines()
    starts = [i for i, ln in enumerate(lines) if start_re.match(ln)]
    best = ""
    for s in starts:
        end = len(lines)
        for j in range(s + 1, len(lines)):
            if end_re.match(lines[j]):
                end = j
                break
        section = "\n".join(lines[s:end]).strip()
        if len(section) > len(best):
            best = section
    # Headings that only appear in the table of contents carry no content.
    return best if len(best) >= _TOC_MIN_SECTION_CHARS else ""


def _paragraphs(section: str) -> List[str]:
    """Normalize a section into comparable paragraphs (>= 200 chars merged)."""
    paras: List[str] = []
    buf: List[str] = []
    for ln in section.splitlines():
        buf.append(ln)
        joined = " ".join(buf)
        if len(joined) >= 200:
            paras.append(re.sub(r"\s+", " ", joined).strip())
            buf = []
    if buf:
        tail = re.sub(r"\s+", " ", " ".join(buf)).strip()
        if len(tail) > 80:
            paras.append(tail)
    return paras


def diff_sections(old: str, new: str, max_items: int = 8) -> Dict[str, Any]:
    """Paragraph-level diff between two filing sections.

    Returns added/removed paragraph snippets (the language that changed) plus
    summary stats. Uses difflib opcodes over normalized paragraphs so memetic
    boilerplate that merely moved doesn't count as change.
    """
    old_p, new_p = _paragraphs(old), _paragraphs(new)
    sm = difflib.SequenceMatcher(a=old_p, b=new_p, autojunk=False)
    added: List[str] = []
    removed: List[str] = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op in ("insert", "replace"):
            added.extend(new_p[j1:j2])
        if op in ("delete", "replace"):
            removed.extend(old_p[i1:i2])
    similarity = round(sm.ratio() * 100, 1)
    return {
        "similarity_pct": similarity,
        "old_word_count": sum(len(p.split()) for p in old_p),
        "new_word_count": sum(len(p.split()) for p in new_p),
        "added_count": len(added),
        "removed_count": len(removed),
        "added": [p[:500] for p in added[:max_items]],
        "removed": [p[:500] for p in removed[:max_items]],
    }


# ---------------------------------------------------------------------------
# EDGAR fetch layer (cached via agent_tools' cache)
# ---------------------------------------------------------------------------
async def _list_filings_raw(symbol: str, forms: Tuple[str, ...], limit: int) -> List[Dict[str, Any]]:
    from agent_tools import _cache_get, _cache_set, _get_cik

    cache_key = f"sec_filings_list:{symbol}:{','.join(forms)}:{limit}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    cik = await _get_cik(symbol)
    if not cik:
        return []
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.get(url, headers=_HEADERS)
        if resp.status_code != 200:
            logger.warning("EDGAR submissions %s -> %s", symbol, resp.status_code)
            return []
        data = resp.json()

    recent = (data.get("filings") or {}).get("recent") or {}
    out: List[Dict[str, Any]] = []
    forms_list = recent.get("form") or []
    for i, form in enumerate(forms_list):
        if form not in forms:
            continue
        accession = (recent.get("accessionNumber") or [""])[i]
        out.append({
            "form": form,
            "filed": (recent.get("filingDate") or [""])[i],
            "report_date": (recent.get("reportDate") or [""])[i],
            "accession": accession,
            "primary_doc": (recent.get("primaryDocument") or [""])[i],
            "items": (recent.get("items") or [""])[i] if recent.get("items") else "",
            "cik": cik,
        })
        if len(out) >= limit:
            break
    _cache_set(cache_key, out, expire=3600)
    return out


async def _fetch_filing_text(cik: str, accession: str, primary_doc: str) -> str:
    from agent_tools import _cache_get, _cache_set

    cache_key = f"sec_filing_text:{accession}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    acc_nodash = accession.replace("-", "")
    url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc_nodash}/{primary_doc}"
    async with httpx.AsyncClient(timeout=40.0, follow_redirects=True) as client:
        resp = await client.get(url, headers=_HEADERS)
        if resp.status_code != 200:
            logger.warning("EDGAR doc fetch %s -> %s", url, resp.status_code)
            return ""
        raw = resp.text[: _MAX_FILING_CHARS * 4]

    text = strip_html(raw)[:_MAX_FILING_CHARS]
    if text:
        _cache_set(cache_key, text, expire=86400)
    return text


def _section_spec(form: str, section: str) -> Tuple[str, Tuple[str, ...]]:
    """Map a friendly section name to (item, end_items) per form type."""
    section = (section or "risk_factors").lower()
    if form == "10-K":
        if section in ("mdna", "md&a", "mda"):
            return "7", ("7A", "8")
        if section == "business":
            return "1", ("1A", "1B", "2")
        return "1A", ("1B", "2")
    # 10-Q: Part II Item 1A is risk factors; MD&A is Part I Item 2.
    if section in ("mdna", "md&a", "mda"):
        return "2", ("3", "4")
    return "1A", ("2", "5", "6")


# ---------------------------------------------------------------------------
# Agent tools — docstrings are the LLM-facing manuals
# ---------------------------------------------------------------------------
async def get_recent_filings(symbol: str) -> dict:
    """List a company's recent SEC filings (10-K, 10-Q, 8-K) from EDGAR.

    Use this FIRST when the user asks about filings — it shows what exists and
    when it was filed (8-K items hint at the event type: 2.02 = earnings,
    5.02 = executive changes, 1.01 = material agreements). Follow up with
    search_filings to read inside a specific form, or diff_risk_factors to see
    what changed year-over-year.

    Args:
        symbol: Stock ticker, e.g. "NVDA".
    """
    symbol = (symbol or "").strip().upper()
    if not symbol:
        return {"ok": False, "error": "symbol is required"}
    try:
        rows = await _list_filings_raw(symbol, SUPPORTED_FORMS, limit=12)
    except Exception as exc:  # noqa: BLE001
        logger.warning("get_recent_filings(%s) failed: %s", symbol, exc)
        return {"ok": False, "error": f"EDGAR list failed: {exc}"}
    if not rows:
        return {"ok": False, "error": f"No EDGAR filings found for {symbol}."}
    return {"ok": True, "symbol": symbol, "count": len(rows),
            "filings": [{k: v for k, v in r.items() if k != "cik"} for r in rows],
            "source": "SEC EDGAR (official)"}


async def search_filings(symbol: str, query: str, form: str = "10-K") -> dict:
    """Semantically search INSIDE a company's latest 10-K or 10-Q text.

    This reads the actual filing, not a summary: the latest document is pulled
    from EDGAR, chunked, embedded, and the passages most relevant to your query
    are returned with citations (form + filing date). Use it for questions like
    "what does the 10-K say about China exposure / litigation / customer
    concentration / supply chain". Quote the passages in your answer.

    Args:
        symbol: Stock ticker, e.g. "AAPL".
        query: What to look for, e.g. "supply chain concentration risk".
        form: "10-K" (default) or "10-Q".
    """
    symbol = (symbol or "").strip().upper()
    form = (form or "10-K").strip().upper()
    if form not in ("10-K", "10-Q"):
        return {"ok": False, "error": "form must be 10-K or 10-Q"}
    if not symbol or not (query or "").strip():
        return {"ok": False, "error": "symbol and query are required"}
    try:
        rows = await _list_filings_raw(symbol, (form,), limit=1)
        if not rows:
            return {"ok": False, "error": f"No recent {form} found for {symbol}."}
        f = rows[0]
        text = await _fetch_filing_text(f["cik"], f["accession"], f["primary_doc"])
        if not text:
            return {"ok": False, "error": "Could not download the filing document."}

        from agent_tools import _chunk_text, _get_embedding_model
        chunks = _chunk_text(text)
        model = _get_embedding_model()
        if model is None or not chunks:
            return {"ok": True, "symbol": symbol, "form": form, "filed": f["filed"],
                    "passages": [{"text": c[:600]} for c in chunks[:3]],
                    "note": "no embedding model; returning leading chunks"}

        import numpy as np
        emb = model.encode(chunks, normalize_embeddings=True, show_progress_bar=False)
        q_emb = model.encode([query], normalize_embeddings=True, show_progress_bar=False)[0]
        sims = np.dot(emb, q_emb)
        top = np.argsort(sims)[::-1][:5]
        passages = [{"text": chunks[i][:900], "relevance": round(float(sims[i]), 3)}
                    for i in top if sims[i] >= 0.15]
        return {"ok": True, "symbol": symbol, "form": form, "filed": f["filed"],
                "total_chunks": len(chunks), "passages": passages,
                "source": "SEC EDGAR full text"}
    except Exception as exc:  # noqa: BLE001
        logger.warning("search_filings(%s) failed: %s", symbol, exc)
        return {"ok": False, "error": f"filing search failed: {exc}"}


async def diff_risk_factors(symbol: str) -> dict:
    """Diff the Risk Factors section between the company's two latest 10-Ks.

    Risk-factor language is lawyer-reviewed and sticky — when it CHANGES, the
    company is telling you something. This pulls Item 1A from the two most
    recent 10-K filings and returns the paragraphs that were added or removed,
    plus a similarity score. New risk language is a classic early-warning
    signal; quote the most material additions in your answer.

    Args:
        symbol: Stock ticker, e.g. "TSLA".
    """
    symbol = (symbol or "").strip().upper()
    if not symbol:
        return {"ok": False, "error": "symbol is required"}
    try:
        rows = await _list_filings_raw(symbol, ("10-K",), limit=2)
        if len(rows) < 2:
            return {"ok": False, "error": f"Need two 10-Ks on EDGAR for {symbol}; found {len(rows)}."}
        new_f, old_f = rows[0], rows[1]
        new_text, old_text = await asyncio.gather(
            _fetch_filing_text(new_f["cik"], new_f["accession"], new_f["primary_doc"]),
            _fetch_filing_text(old_f["cik"], old_f["accession"], old_f["primary_doc"]),
        )
        item, ends = _section_spec("10-K", "risk_factors")
        new_sec = extract_item(new_text, item, ends)
        old_sec = extract_item(old_text, item, ends)
        if not new_sec or not old_sec:
            return {"ok": False, "error": "Could not locate Item 1A in one of the filings."}
        d = diff_sections(old_sec, new_sec)
        return {"ok": True, "symbol": symbol,
                "new_filing": {"filed": new_f["filed"], "form": "10-K"},
                "old_filing": {"filed": old_f["filed"], "form": "10-K"},
                **d,
                "read": ("LOW language change — risks are steady." if d["similarity_pct"] > 85
                         else "MATERIAL language change — read the added paragraphs."),
                "source": "SEC EDGAR Item 1A diff"}
    except Exception as exc:  # noqa: BLE001
        logger.warning("diff_risk_factors(%s) failed: %s", symbol, exc)
        return {"ok": False, "error": f"risk factor diff failed: {exc}"}
