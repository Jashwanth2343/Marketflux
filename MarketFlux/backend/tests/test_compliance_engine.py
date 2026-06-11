"""Unit tests for the pre-trade compliance & risk-control engine.

Pure logic, no I/O — these run fast and deterministically. Runnable under pytest
or directly (``python tests/test_compliance_engine.py``).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import compliance_engine as ce  # noqa: E402

ACCT = {"equity": "100000", "cash": "40000", "buying_power": "80000"}
POSITIONS = [
    {"symbol": "NVDA", "qty": "50", "market_value": "15000",
     "unrealized_pl": "1200", "avg_entry_price": "276"},
]


def _check(report, rule):
    return next((c for c in report["checks"] if c["rule"] == rule), None)


def test_clean_buy_passes():
    r = ce.pre_trade_check(symbol="AAPL", side="buy", quantity=10, est_price=200,
                           account=ACCT, positions=POSITIONS)
    assert r["decision"] == ce.PASS
    assert r["ok"] is True
    assert _check(r, "concentration")["status"] == "pass"


def test_concentration_blocks():
    # 150 * 300 = 45k; + 15k held = 60k → 60% of 100k equity → over 30% ceiling.
    r = ce.pre_trade_check(symbol="NVDA", side="buy", quantity=150, est_price=300,
                           account=ACCT, positions=POSITIONS)
    assert r["decision"] == ce.BLOCK
    assert r["ok"] is False
    assert _check(r, "concentration")["status"] == "block"
    assert r["projected_weight_pct"] == 60.0


def test_buying_power_blocks():
    r = ce.pre_trade_check(symbol="MSFT", side="buy", quantity=1000, est_price=400,
                           account=ACCT, positions=[])
    assert r["decision"] == ce.BLOCK
    assert _check(r, "buying_power")["status"] == "block"


def test_notional_cap_blocks():
    r = ce.pre_trade_check(symbol="AVGO", side="buy", quantity=500, est_price=200,
                           account=ACCT, positions=[])
    assert _check(r, "notional_cap")["status"] == "block"


def test_short_sale_warns():
    r = ce.pre_trade_check(symbol="NVDA", side="sell", quantity=80, est_price=300,
                           account=ACCT, positions=POSITIONS)
    assert r["decision"] == ce.WARN
    assert r["ok"] is True  # warn is non-blocking
    assert _check(r, "short_sale")["status"] == "warn"


def test_long_sale_passes_no_short():
    r = ce.pre_trade_check(symbol="NVDA", side="sell", quantity=50, est_price=300,
                           account=ACCT, positions=POSITIONS)
    assert _check(r, "short_sale")["status"] == "pass"


def test_pdt_floor_warns_on_small_account():
    r = ce.pre_trade_check(symbol="AAPL", side="buy", quantity=5, est_price=200,
                           account={"equity": "10000", "buying_power": "10000"}, positions=[])
    assert _check(r, "pattern_day_trader")["status"] == "warn"


def test_penny_stock_warns():
    r = ce.pre_trade_check(symbol="PENNY", side="buy", quantity=100, est_price=0.50,
                           account=ACCT, positions=[])
    assert _check(r, "liquidity")["status"] == "warn"


def test_invalid_quantity_blocks_early():
    r = ce.pre_trade_check(symbol="AAPL", side="buy", quantity=0, est_price=200,
                           account=ACCT, positions=[])
    assert r["decision"] == ce.BLOCK
    assert _check(r, "order_sanity")["status"] == "block"


def test_missing_account_fails_open_no_false_block():
    # No account info → concentration/buying-power can't be evaluated; must not block.
    r = ce.pre_trade_check(symbol="AAPL", side="buy", quantity=10, est_price=200,
                           account={}, positions=[])
    assert r["decision"] in (ce.PASS, ce.WARN)
    assert r["ok"] is True


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for t in tests:
        t()
        print(f"  ok  {t.__name__}")
        passed += 1
    print(f"\n{passed}/{len(tests)} compliance tests passed.")
