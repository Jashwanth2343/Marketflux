"""Unit tests for sec_filings' pure text helpers — no network, no DB."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sec_filings import diff_sections, extract_item, strip_html  # noqa: E402


# ---------------------------------------------------------------------------
# strip_html
# ---------------------------------------------------------------------------
def test_strip_html_drops_tags_and_unescapes():
    raw = "<html><body><p>Revenue grew <b>12%</b> &amp; margins held.</p></body></html>"
    assert strip_html(raw) == "Revenue grew 12% & margins held."


def test_strip_html_drops_script_and_style():
    raw = "<style>.a{color:red}</style><script>alert(1)</script><p>Real text</p>"
    assert strip_html(raw) == "Real text"


def test_strip_html_block_tags_become_newlines():
    raw = "<p>Item 1A. Risk Factors</p><p>Our business faces risks.</p>"
    out = strip_html(raw)
    assert out.splitlines() == ["Item 1A. Risk Factors", "Our business faces risks."]


def test_strip_html_handles_nbsp():
    assert strip_html("<p>Item&nbsp;1A.&nbsp;Risk Factors</p>") == "Item 1A. Risk Factors"


def test_strip_html_empty():
    assert strip_html("") == ""


# ---------------------------------------------------------------------------
# extract_item — TOC-aware section extraction
# ---------------------------------------------------------------------------
def _fake_filing():
    filler = "Risk paragraph about competition and macro conditions. " * 40
    return "\n".join([
        "TABLE OF CONTENTS",
        "Item 1. Business",
        "Item 1A. Risk Factors",       # TOC row — must NOT be chosen
        "Item 1B. Unresolved Staff Comments",
        "PART I",
        "Item 1. Business",
        "We design GPUs. " * 100,
        "Item 1A. Risk Factors",       # real section
        filler,
        "Item 1B. Unresolved Staff Comments",
        "None.",
    ])


def test_extract_item_skips_toc_and_finds_real_section():
    sec = extract_item(_fake_filing(), "1A", ("1B", "2"))
    assert sec.startswith("Item 1A. Risk Factors")
    assert "competition and macro" in sec
    assert "Unresolved" not in sec


def test_extract_item_returns_empty_when_section_missing():
    assert extract_item("Item 7. MD&A\nshort text", "1A", ("1B",)) == ""


def test_extract_item_case_insensitive():
    text = "\n".join(["ITEM 1A. RISK FACTORS", "x " * 800, "ITEM 1B. OTHER"])
    sec = extract_item(text, "1A", ("1B",))
    assert sec.startswith("ITEM 1A.")


# ---------------------------------------------------------------------------
# diff_sections
# ---------------------------------------------------------------------------
def _para(seed: str) -> str:
    return (seed + " — this paragraph describes a specific business risk in detail. ") * 4


def test_diff_detects_added_and_removed_language():
    old = "\n".join([_para("Competition risk"), _para("Supply chain risk")])
    new = "\n".join([_para("Competition risk"), _para("AI regulation risk")])
    d = diff_sections(old, new)
    assert d["added_count"] >= 1
    assert d["removed_count"] >= 1
    assert any("AI regulation" in p for p in d["added"])
    assert any("Supply chain" in p for p in d["removed"])
    assert 0 <= d["similarity_pct"] <= 100


def test_diff_identical_sections_is_clean():
    text = "\n".join([_para("Competition risk"), _para("Litigation risk")])
    d = diff_sections(text, text)
    assert d["added_count"] == 0
    assert d["removed_count"] == 0
    assert d["similarity_pct"] == 100.0


def test_diff_caps_returned_snippets():
    old = "\n".join(_para(f"Old risk {i}") for i in range(20))
    new = "\n".join(_para(f"New risk {i}") for i in range(20))
    d = diff_sections(old, new, max_items=8)
    assert len(d["added"]) <= 8
    assert len(d["removed"]) <= 8
    assert d["added_count"] >= 8  # counts reflect reality even when capped
