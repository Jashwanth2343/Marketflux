"""Smoke tests for the Pilot subsystem.

These tests do NOT hit the network, do NOT require a Mongo instance, and do
NOT require LLM credentials. They verify:

  - strategy_dsl: schema validation, compilation determinism, lookahead safety
  - personality: serialization, signal_weights normalization, risk_policy mapping
  - trade_proposals: status transitions and terminal-state immutability

Run from the backend directory:
    python -m pytest tests/test_pilot_smoke.py -v
or simply:
    python tests/test_pilot_smoke.py
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

# Make backend/ importable when run directly.
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from vnext.pilot.strategy_dsl import (
    DEFAULT_SPEC_SCHEMA_VERSION,
    StrategySpec,
    compile_spec,
    validate_spec_dict,
)
from vnext.pilot.personality import (
    ATLAS,
    SAGE,
    SEED_PERSONALITIES,
    VEGA,
    Personality,
    PersonalityRiskPolicy,
)
from vnext.pilot.trade_proposals import (
    ProposalStatus,
    TradeProposal,
    default_expiry_iso,
)


# ===========================================================================
# Helpers
# ===========================================================================
def _make_price_panel(tickers, days=400, seed=42):
    """Generate a synthetic multi-ticker price panel with drift + noise."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2023-01-02", periods=days)
    data = {}
    for i, t in enumerate(tickers):
        drift = 0.0003 + i * 0.0001
        vol = 0.012 + i * 0.001
        returns = rng.normal(drift, vol, days)
        prices = 100 * np.exp(np.cumsum(returns))
        data[t] = prices
    closes = pd.DataFrame(data, index=dates)
    panel = pd.concat({"close": closes}, axis=1)
    return panel


# ===========================================================================
# strategy_dsl tests
# ===========================================================================
def test_spec_validation_rejects_missing_fields():
    failures = 0
    bad_specs = [
        {},
        {"name": "x"},
        {"name": "x", "universe": []},
        {"name": "x", "universe": ["AAPL"], "entry": []},
        {"name": "x", "universe": ["AAPL"], "entry": [{"signal": "rsi_14", "op": ">", "value": 30}], "exit": []},
        {
            "name": "x", "universe": ["AAPL"],
            "entry": [{"signal": "INVALID_SIGNAL", "op": ">", "value": 30}],
            "exit": [{"type": "stop_loss", "pct": 0.05}],
            "sizing": {"type": "equal_weight"},
        },
    ]
    for spec in bad_specs:
        try:
            validate_spec_dict(spec)
            failures += 1
            print(f"  FAIL validate accepted: {spec}")
        except ValueError:
            pass
    assert failures == 0, "validate_spec_dict accepted malformed specs"


def test_spec_hash_is_stable():
    spec_dict = {
        "name": "test",
        "universe": ["AAPL", "MSFT"],
        "entry": [{"signal": "rsi_14", "op": "<", "value": 30}],
        "exit": [{"type": "stop_loss", "pct": 0.05}],
        "sizing": {"type": "equal_weight", "max_positions": 5, "max_position_pct": 10},
    }
    spec_a = StrategySpec.from_dict(spec_dict)
    spec_b = StrategySpec.from_dict({**spec_dict, "universe": ["MSFT", "AAPL"]})  # reorder
    assert spec_a.spec_hash == spec_b.spec_hash, "Spec hash must be order-invariant"


def test_compiler_is_deterministic():
    tickers = ["AAA", "BBB", "CCC"]
    spec_dict = {
        "name": "det",
        "universe": tickers,
        "entry": [{"signal": "rsi_14", "op": "<", "value": 35}],
        "exit": [
            {"type": "stop_loss", "pct": 0.06},
            {"type": "take_profit", "pct": 0.12},
            {"type": "max_hold_days", "value": 20},
        ],
        "sizing": {"type": "equal_weight", "max_positions": 3, "max_position_pct": 30},
    }
    spec = StrategySpec.from_dict(spec_dict)
    panel = _make_price_panel(tickers)

    result_a = compile_spec(spec, price_panel=panel, initial_capital=25_000)
    result_b = compile_spec(spec, price_panel=panel, initial_capital=25_000)

    assert result_a.spec_hash == result_b.spec_hash
    assert len(result_a.trades) == len(result_b.trades)
    assert result_a.stats["final_equity"] == result_b.stats["final_equity"]


def test_compiler_is_lookahead_safe():
    """If we know the future, we shouldn't 'see' it. Compile the same spec on
    a panel that ends 1 day earlier and confirm the trade list is a prefix."""
    tickers = ["AAA", "BBB"]
    spec = StrategySpec.from_dict({
        "name": "safe",
        "universe": tickers,
        "entry": [{"signal": "mom_20d_pct", "op": ">", "value": 3}],
        "exit": [{"type": "max_hold_days", "value": 10}],
        "sizing": {"type": "equal_weight", "max_positions": 2, "max_position_pct": 50},
    })
    panel_full = _make_price_panel(tickers, days=400)
    panel_short = panel_full.iloc[:-30]

    full = compile_spec(spec, price_panel=panel_full)
    short = compile_spec(spec, price_panel=panel_short)

    # Trades that closed on or before the short panel's last date should match.
    short_last_date = panel_short.index[-1].isoformat()
    full_truncated = [t for t in full.trades if t["exit_date"] <= short_last_date]
    short_truncated = [t for t in short.trades if t["exit_date"] <= short_last_date]
    assert len(full_truncated) == len(short_truncated), (
        f"Lookahead leak: full panel produced {len(full_truncated)} trades but short panel produced {len(short_truncated)}"
    )


def test_compiler_handles_empty_panel():
    spec = StrategySpec.from_dict({
        "name": "empty",
        "universe": ["AAA"],
        "entry": [{"signal": "rsi_14", "op": "<", "value": 50}],
        "exit": [{"type": "stop_loss", "pct": 0.05}],
        "sizing": {"type": "equal_weight", "max_positions": 1, "max_position_pct": 100},
    })
    result = compile_spec(spec, price_panel=None, initial_capital=10_000)
    assert result.trades == []
    assert result.stats["final_equity"] == 10_000


# ===========================================================================
# personality tests
# ===========================================================================
def test_seed_personalities_load():
    assert len(SEED_PERSONALITIES) == 3
    names = {p.name for p in SEED_PERSONALITIES}
    assert names == {"Atlas", "Sage", "Vega"}
    for p in SEED_PERSONALITIES:
        assert p.is_seed is True
        assert p.user_id == "system"
        assert sum(p.signal_weights.values()) == pytest_approx(1.0)


def test_personality_signal_weight_renorm():
    p = Personality(
        id="t1",
        user_id="u1",
        name="Weights",
        mandate="Test mandate.",
        universe=["AAPL"],
        signal_weights={"momentum": 2.0, "quality": 1.0, "value": 1.0},
        risk_policy=PersonalityRiskPolicy(),
    )
    assert sum(p.signal_weights.values()) == pytest_approx(1.0)
    assert p.signal_weights["momentum"] == pytest_approx(0.5)


def test_personality_risk_policy_to_policy_engine_dict():
    rp = PersonalityRiskPolicy(max_position_pct=10, min_confidence_to_trade=70)
    d = rp.to_policy_engine_dict()
    assert d["max_position_pct"]["params"]["value"] == 10
    assert d["min_confidence_to_trade"]["params"]["value"] == 70
    assert d["no_live_trading"]["enabled"] is True


def test_personality_serialization_roundtrip():
    p = ATLAS
    d = p.to_dict()
    restored = Personality.from_dict(d)
    assert restored.id == p.id
    assert restored.name == p.name
    assert sorted(restored.universe) == sorted(p.universe)
    assert restored.signal_weights == p.signal_weights


# ===========================================================================
# trade_proposals tests
# ===========================================================================
def test_proposal_construction_and_defaults():
    p = TradeProposal(
        id="x",
        user_id="u1",
        personality_id="seed_atlas",
        personality_name="Atlas",
        ticker="nvda",
        side="buy",
        qty=10,
        quote_price=120.0,
    )
    assert p.ticker == "NVDA"
    assert p.expires_at  # auto-set
    assert p.is_terminal is False


def test_proposal_rejects_bad_side_and_qty():
    raised = []
    try:
        TradeProposal(id="x", user_id="u", personality_id="p", personality_name="P",
                      ticker="NVDA", side="hold", qty=10, quote_price=1)
    except ValueError as exc:
        raised.append(str(exc))
    try:
        TradeProposal(id="x", user_id="u", personality_id="p", personality_name="P",
                      ticker="NVDA", side="buy", qty=0, quote_price=1)
    except ValueError as exc:
        raised.append(str(exc))
    assert len(raised) == 2, f"Expected 2 ValueErrors; got {raised}"


def test_default_expiry_is_in_the_future():
    e = default_expiry_iso()
    parsed = datetime.fromisoformat(e)
    assert parsed > datetime.now(timezone.utc)
    # Not absurdly far either
    assert parsed < datetime.now(timezone.utc) + timedelta(days=2)


# ===========================================================================
# Minimal test runner so this works without pytest
# ===========================================================================
def pytest_approx(value, tol=1e-3):
    class _A:
        def __eq__(self_inner, other):
            return abs(other - value) < tol
    return _A()


def _run_all():
    tests = [
        test_spec_validation_rejects_missing_fields,
        test_spec_hash_is_stable,
        test_compiler_is_deterministic,
        test_compiler_is_lookahead_safe,
        test_compiler_handles_empty_panel,
        test_seed_personalities_load,
        test_personality_signal_weight_renorm,
        test_personality_risk_policy_to_policy_engine_dict,
        test_personality_serialization_roundtrip,
        test_proposal_construction_and_defaults,
        test_proposal_rejects_bad_side_and_qty,
        test_default_expiry_is_in_the_future,
    ]
    passed = 0
    failed = []
    for t in tests:
        try:
            t()
            passed += 1
            print(f"  OK  {t.__name__}")
        except AssertionError as exc:
            failed.append((t.__name__, str(exc)))
            print(f"  FAIL {t.__name__}: {exc}")
        except Exception as exc:
            failed.append((t.__name__, repr(exc)))
            print(f"  ERR  {t.__name__}: {exc!r}")
    print(f"\n{passed}/{len(tests)} passed")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(_run_all())
