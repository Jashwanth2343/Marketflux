"""Unit tests for the conviction ledger's pure grading math.

These cover the deterministic core — return/alpha computation, grade bands,
and the open-thesis evaluation state machine — with no IO or DB.
"""
import os
import sys

from pytest import approx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from conviction_ledger import (  # noqa: E402
    alpha_pp,
    evaluate_open_thesis,
    grade_from_alpha,
    thesis_return_pct,
    window_return_pct,
)


# ---------------------------------------------------------------------------
# thesis_return_pct
# ---------------------------------------------------------------------------
def test_long_return_up():
    assert thesis_return_pct(100.0, 110.0, "long") == approx(10.0)


def test_long_return_down():
    assert thesis_return_pct(100.0, 90.0, "long") == approx(-10.0)


def test_short_return_profits_when_price_falls():
    assert thesis_return_pct(100.0, 90.0, "short") == approx(10.0)


def test_short_return_loses_when_price_rises():
    assert thesis_return_pct(100.0, 110.0, "short") == approx(-10.0)


def test_zero_entry_price_is_safe():
    assert thesis_return_pct(0.0, 110.0, "long") == 0.0


# ---------------------------------------------------------------------------
# alpha_pp — benchmark sign-flips for shorts
# ---------------------------------------------------------------------------
def test_long_alpha_subtracts_benchmark():
    assert alpha_pp(10.0, 4.0, "long") == approx(6.0)


def test_short_alpha_flips_benchmark():
    # Short made +10% while SPY fell 4%: shorting the market made +4%,
    # so the short's edge is 10 - 4 = 6pp, not 10 - (-4) = 14pp.
    assert alpha_pp(10.0, -4.0, "short") == approx(6.0)


def test_short_in_rising_tape_gets_credit():
    # Short broke even while SPY rose 5%: shorting the market lost 5pp,
    # so flat is actually +5pp of alpha.
    assert alpha_pp(0.0, 5.0, "short") == approx(5.0)


# ---------------------------------------------------------------------------
# grade_from_alpha — band boundaries (>= +5 A, >= +1 B, > -1 C, > -5 D, else F)
# ---------------------------------------------------------------------------
def test_grade_bands():
    assert grade_from_alpha(7.2) == "A"
    assert grade_from_alpha(5.0) == "A"      # boundary inclusive to A
    assert grade_from_alpha(4.99) == "B"
    assert grade_from_alpha(1.0) == "B"      # boundary inclusive to B
    assert grade_from_alpha(0.0) == "C"
    assert grade_from_alpha(-0.99) == "C"
    assert grade_from_alpha(-1.0) == "D"     # boundary goes to D
    assert grade_from_alpha(-4.99) == "D"
    assert grade_from_alpha(-5.0) == "F"     # boundary goes to F
    assert grade_from_alpha(-12.0) == "F"


# ---------------------------------------------------------------------------
# evaluate_open_thesis
# ---------------------------------------------------------------------------
def _thesis(**kw):
    base = {
        "direction": "long",
        "entry_date": "2026-01-02",
        "entry_price": 100.0,
        "price_target": None,
        "invalidation_price": None,
        "invalidation_date": "2026-04-02",
    }
    base.update(kw)
    return base


CLOSES = [
    ("2026-01-02", 100.0),
    ("2026-01-05", 104.0),
    ("2026-01-06", 98.0),
    ("2026-01-07", 112.0),
    ("2026-01-08", 95.0),
]


def test_target_hit_long():
    t = _thesis(price_target=110.0)
    d = evaluate_open_thesis(t, CLOSES, as_of="2026-01-08")
    assert d == {"action": "close", "reason": "target",
                 "close_date": "2026-01-07", "close_price": 112.0}


def test_invalidation_before_target_wins_by_date_order():
    # Stop at 99 trips on 01-06 BEFORE the 01-07 target print.
    t = _thesis(price_target=110.0, invalidation_price=99.0)
    d = evaluate_open_thesis(t, CLOSES, as_of="2026-01-08")
    assert d["reason"] == "invalidation_price"
    assert d["close_date"] == "2026-01-06"
    assert d["close_price"] == 98.0


def test_short_target_is_a_lower_price():
    t = _thesis(direction="short", price_target=96.0)
    d = evaluate_open_thesis(t, CLOSES, as_of="2026-01-08")
    assert d["reason"] == "target"
    assert d["close_date"] == "2026-01-08"
    assert d["close_price"] == 95.0


def test_short_invalidation_is_a_higher_price():
    t = _thesis(direction="short", invalidation_price=105.0)
    d = evaluate_open_thesis(t, CLOSES, as_of="2026-01-08")
    assert d["reason"] == "invalidation_price"
    assert d["close_date"] == "2026-01-07"  # 112 close breaches the 105 stop


def test_expiry_closes_at_last_close_on_or_before_invalidation_date():
    t = _thesis(invalidation_date="2026-01-07")
    d = evaluate_open_thesis(t, CLOSES, as_of="2026-01-08")
    assert d["reason"] == "expiry"
    assert d["close_date"] == "2026-01-07"
    assert d["close_price"] == 112.0


def test_no_trigger_means_mark_to_market():
    t = _thesis()
    d = evaluate_open_thesis(t, CLOSES, as_of="2026-01-08")
    assert d == {"action": "update", "current_price": 95.0}


def test_no_price_data_skips():
    t = _thesis()
    d = evaluate_open_thesis(t, [], as_of="2026-01-08")
    assert d["action"] == "skip"


def test_future_closes_beyond_as_of_are_ignored():
    t = _thesis(price_target=110.0)
    d = evaluate_open_thesis(t, CLOSES, as_of="2026-01-06")
    assert d["action"] == "update"
    assert d["current_price"] == 98.0


# ---------------------------------------------------------------------------
# window_return_pct
# ---------------------------------------------------------------------------
def test_window_return_basic():
    assert window_return_pct(CLOSES, "2026-01-02", "2026-01-08") == approx(-5.0)


def test_window_return_with_entry_anchor():
    # Anchoring at an explicit entry price overrides the first close.
    assert window_return_pct(CLOSES, "2026-01-02", "2026-01-07", entry_price=80.0) == approx(40.0)


def test_window_return_empty_window():
    assert window_return_pct(CLOSES, "2026-02-01", "2026-02-10") == 0.0
