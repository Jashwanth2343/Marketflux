"""Unit tests for the pure cores of the new intelligence tools.

Covers the deterministic logic — regime classification and trade projection —
without any network/LLM. Runnable under pytest or directly.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import market_regime as mr  # noqa: E402
import copilot_intelligence_tools as intel  # noqa: E402

_UP = [100 + i * 0.2 for i in range(260)]
_DOWN = [160 - i * 0.2 for i in range(260)]
ACCT = {"equity": "100000", "cash": "40000", "buying_power": "80000"}
POS = [{"symbol": "NVDA", "qty": "50", "market_value": "15000", "unrealized_pl": "1200"}]


# --- regime --------------------------------------------------------------
def test_regime_risk_on():
    r = mr.classify_regime(_UP, 12.0, 80.0)
    assert r["risk_state"] == "risk-on"
    assert r["spy_trend"] == "uptrend"
    assert r["suggested_gross_exposure"] == "90-100%"


def test_regime_risk_off():
    r = mr.classify_regime(_DOWN, 34.0, 25.0)
    assert r["risk_state"] == "risk-off"
    assert r["spy_trend"] == "downtrend"
    assert r["vix_band"] == "stressed"


def test_regime_handles_missing_data():
    r = mr.classify_regime([100, 101], None, None)
    assert r["spy_trend"] == "unknown"
    assert r["vix_band"] == "unknown"
    assert "regime_label" in r


# --- trade projection ----------------------------------------------------
def test_project_buy_add():
    p = intel.project_trade(ACCT, POS, "NVDA", "buy", 50, 300)
    assert p["before"]["weight_pct"] == 15.0
    assert p["after"]["weight_pct"] == 30.0
    assert p["after"]["cash"] == 25000.0
    assert p["largest_position_after"]["symbol"] == "NVDA"


def test_project_partial_sell():
    p = intel.project_trade(ACCT, POS, "NVDA", "sell", 25, 300)
    assert p["after"]["weight_pct"] == 7.5
    assert p["after"]["cash"] == 47500.0


def test_project_new_name_buying_power():
    p = intel.project_trade(ACCT, POS, "AAPL", "buy", 100, 200)
    assert p["after"]["weight_pct"] == 20.0
    assert p["after"]["buying_power"] == 60000.0


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests:
        t()
        print(f"  ok  {t.__name__}")
    print(f"\n{len(tests)}/{len(tests)} intelligence-tool tests passed.")
