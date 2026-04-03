"""
Portfolio Risk Engine for FundOS.

Provides hedge fund-grade portfolio risk analytics:
  - Portfolio beta vs SPY
  - Sector concentration analysis
  - Correlation matrix
  - Factor exposure (value/growth/momentum/quality)
  - Stress test scenarios
  - Position sizing recommendations
  - VaR estimate (parametric)
"""

import asyncio
import logging
import math
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

async def _get_price_history(tickers: List[str], period: str = "1y") -> Dict[str, list]:
    """Fetch price history for multiple tickers in parallel."""
    try:
        import yfinance as yf

        def _fetch_all():
            result = {}
            for t in tickers + ["SPY"]:
                try:
                    ticker = yf.Ticker(t.upper())
                    hist = ticker.history(period=period)
                    if not hist.empty:
                        result[t.upper()] = list(hist["Close"])
                except Exception:
                    pass
            return result

        return await asyncio.to_thread(_fetch_all)
    except Exception as e:
        logger.error(f"_get_price_history error: {e}")
        return {}


async def _get_ticker_info(ticker: str) -> dict:
    try:
        import yfinance as yf

        def _f():
            return yf.Ticker(ticker.upper()).info or {}

        return await asyncio.to_thread(_f)
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Core computations
# ---------------------------------------------------------------------------

def _daily_returns(prices: list) -> list:
    """Compute daily % returns from a price series."""
    if len(prices) < 2:
        return []
    return [(prices[i] - prices[i - 1]) / prices[i - 1] for i in range(1, len(prices))]


def _compute_beta(stock_returns: list, market_returns: list) -> Optional[float]:
    """Compute OLS beta of stock returns vs market returns."""
    n = min(len(stock_returns), len(market_returns))
    if n < 20:
        return None
    s = np.array(stock_returns[-n:], dtype=float)
    m = np.array(market_returns[-n:], dtype=float)
    # Remove NaN/Inf
    mask = np.isfinite(s) & np.isfinite(m)
    s, m = s[mask], m[mask]
    if len(s) < 10:
        return None
    cov = np.cov(s, m)
    if cov[1, 1] == 0:
        return None
    return round(float(cov[0, 1] / cov[1, 1]), 2)


def _compute_correlation_matrix(returns_map: Dict[str, list]) -> Dict:
    """Compute pairwise correlation matrix for a set of return series."""
    tickers = [t for t in returns_map if t != "SPY"]
    n = len(tickers)
    if n < 2:
        return {"tickers": tickers, "matrix": []}

    # Align lengths to shortest series
    min_len = min(len(returns_map[t]) for t in tickers)
    matrix_data = np.array([returns_map[t][-min_len:] for t in tickers], dtype=float)

    # Handle NaN/Inf
    matrix_data = np.nan_to_num(matrix_data, nan=0.0, posinf=0.0, neginf=0.0)

    corr = np.corrcoef(matrix_data)
    # Round and convert to list of lists
    corr_rounded = [[round(float(corr[i, j]), 3) for j in range(n)] for i in range(n)]

    return {"tickers": tickers, "matrix": corr_rounded}


def _parametric_var(returns: list, confidence: float = 0.95) -> Optional[float]:
    """
    Compute parametric VaR at given confidence level.
    Returns VaR as a % of portfolio value (positive = potential loss).
    """
    if len(returns) < 20:
        return None
    arr = np.array(returns, dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) < 10:
        return None
    mu = np.mean(arr)
    sigma = np.std(arr)
    # Approximate normal quantile for 95% confidence (z ≈ -1.645)
    z = -1.645  # 95th percentile of standard normal
    var = -(mu + z * sigma)
    return round(float(var * 100), 2)  # as percentage


def _max_drawdown(prices: list) -> float:
    """Maximum drawdown from peak."""
    if not prices:
        return 0.0
    peak = prices[0]
    max_dd = 0.0
    for p in prices:
        if p > peak:
            peak = p
        dd = (peak - p) / peak
        if dd > max_dd:
            max_dd = dd
    return round(max_dd * 100, 2)  # as percentage


# ---------------------------------------------------------------------------
# Stress test scenarios
# ---------------------------------------------------------------------------

STRESS_SCENARIOS = [
    {
        "name": "Rate Spike +100bps",
        "description": "Fed raises rates unexpectedly by 100bps",
        "factor_impacts": {"growth": -0.15, "value": +0.03, "quality": -0.05, "beta_multiplier": 1.2},
    },
    {
        "name": "Market Crash -20%",
        "description": "S&P 500 drops 20% (bear market)",
        "factor_impacts": {"growth": -0.25, "value": -0.15, "quality": -0.10, "beta_multiplier": 1.0},
    },
    {
        "name": "Recession Scenario",
        "description": "GDP contracts 2%, unemployment rises to 6%",
        "factor_impacts": {"growth": -0.30, "value": -0.10, "quality": -0.08, "beta_multiplier": 1.1},
    },
    {
        "name": "USD Surge +10%",
        "description": "Dollar strengthens 10% (risk-off / safe haven demand)",
        "factor_impacts": {"growth": -0.08, "value": -0.03, "quality": +0.02, "beta_multiplier": 0.9},
    },
    {
        "name": "Inflation Spike",
        "description": "CPI rises to 7% — stagflation risk",
        "factor_impacts": {"growth": -0.20, "value": +0.08, "quality": -0.05, "beta_multiplier": 1.3},
    },
    {
        "name": "Tech Sector Selloff -30%",
        "description": "Technology sector P/E compression, valuation reset",
        "factor_impacts": {"growth": -0.35, "value": +0.05, "quality": -0.05, "beta_multiplier": 1.4},
    },
]


def _estimate_factor_exposure(info: dict) -> Dict[str, float]:
    """
    Estimate factor exposure (value/growth/quality) from fundamentals.
    Returns scores in [-1, +1].
    """
    pe = info.get("trailingPE", 15) or 15
    pb = info.get("priceToBook", 2) or 2
    rev_growth = info.get("revenueGrowth", 0) or 0
    roe = info.get("returnOnEquity", 0) or 0
    de = info.get("debtToEquity", 50) or 50

    # Growth factor: high PE, high revenue growth
    growth = min(1.0, max(-1.0, (rev_growth * 3) + ((pe - 20) / 30)))

    # Value factor: low PE, low PB
    value = min(1.0, max(-1.0, (20 - pe) / 15 + (3 - pb) / 3))

    # Quality factor: high ROE, low D/E
    quality = min(1.0, max(-1.0, (roe * 4) - (de / 100)))

    return {
        "growth": round(float(growth), 2),
        "value": round(float(value), 2),
        "quality": round(float(quality), 2),
    }


def _run_stress_test(holdings: List[Dict], portfolio_value: float,
                     betas: Dict[str, float], factor_exposures: Dict[str, Dict]) -> List[Dict]:
    """Run stress test scenarios on the portfolio."""
    results = []
    for scenario in STRESS_SCENARIOS:
        impacts = scenario["factor_impacts"]
        beta_mult = impacts.get("beta_multiplier", 1.0)

        total_pct_loss = 0.0
        for h in holdings:
            sym = h["ticker"].upper()
            weight = h.get("weight", 0)
            beta = betas.get(sym, 1.0) or 1.0
            factors = factor_exposures.get(sym, {"growth": 0, "value": 0, "quality": 0})

            # Factor contribution to loss
            factor_loss = (
                factors.get("growth", 0) * impacts.get("growth", 0)
                + factors.get("value", 0) * impacts.get("value", 0)
                + factors.get("quality", 0) * impacts.get("quality", 0)
            )

            # Beta contribution
            if "Market Crash" in scenario["name"] or "Recession" in scenario["name"]:
                beta_contrib = beta * beta_mult * -0.20
            elif "Rate Spike" in scenario["name"]:
                beta_contrib = beta * beta_mult * -0.08
            elif "Tech Sector" in scenario["name"]:
                beta_contrib = beta * beta_mult * -0.15
            else:
                beta_contrib = beta * beta_mult * -0.05

            position_loss = (factor_loss + beta_contrib) * weight
            total_pct_loss += position_loss

        total_pct_loss = max(-0.95, total_pct_loss)  # cap at -95%
        dollar_loss = portfolio_value * total_pct_loss

        results.append({
            "scenario": scenario["name"],
            "description": scenario["description"],
            "portfolio_pct_change": round(total_pct_loss * 100, 1),
            "portfolio_dollar_change": round(dollar_loss, 0),
        })

    return results


# ---------------------------------------------------------------------------
# Position sizing recommendations
# ---------------------------------------------------------------------------

def _position_sizing_recommendation(beta: float, var_pct: Optional[float], max_dd: float) -> Dict:
    """
    Kelly-inspired position sizing guidance.
    """
    # Risk score 0-10
    risk_score = 0
    if beta:
        risk_score += min(4, beta * 2)
    if var_pct:
        risk_score += min(3, var_pct * 10)
    risk_score += min(3, max_dd / 15)

    if risk_score <= 3:
        label = "LOW RISK"
        max_position_pct = 10
        suggested_pct = 7
        color = "#3FB950"
    elif risk_score <= 6:
        label = "MODERATE RISK"
        max_position_pct = 7
        suggested_pct = 4
        color = "#F0A500"
    else:
        label = "HIGH RISK"
        max_position_pct = 4
        suggested_pct = 2
        color = "#F85149"

    stop_loss_pct = round(max(5, max_dd * 0.5), 1)

    return {
        "label": label,
        "risk_score": round(risk_score, 1),
        "max_position_pct": max_position_pct,
        "suggested_position_pct": suggested_pct,
        "stop_loss_pct": stop_loss_pct,
        "color": color,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def analyze_portfolio_risk(holdings: List[Dict], db=None) -> Dict:
    """
    Comprehensive portfolio risk analysis.

    holdings: List of {"ticker": "AAPL", "shares": 10, "avg_price": 150.0}

    Returns:
        {
          "portfolio_value": float,
          "holdings_detail": [...],
          "portfolio_beta": float,
          "sector_concentration": {...},
          "correlation_matrix": {...},
          "var_95": float,
          "max_drawdown": float,
          "stress_tests": [...],
          "factor_exposure": {...},
          "risk_summary": str,
          "analyzed_at": str,
        }
    """
    if not holdings:
        return {"error": "No holdings provided"}

    tickers = [h["ticker"].upper() for h in holdings]

    # Fetch price history and info in parallel
    price_history, *infos = await asyncio.gather(
        _get_price_history(tickers),
        *[_get_ticker_info(t) for t in tickers],
    )

    info_map = {t.upper(): info for t, info in zip(tickers, infos)}

    # Calculate current portfolio value and weights
    holdings_detail = []
    total_value = 0.0
    for h in holdings:
        sym = h["ticker"].upper()
        info = info_map.get(sym, {})
        cur_price = info.get("regularMarketPrice") or info.get("currentPrice") or h.get("avg_price", 0)
        cur_price = float(cur_price) if cur_price else float(h.get("avg_price", 0))
        shares = float(h.get("shares", 0))
        position_value = cur_price * shares
        total_value += position_value

        holdings_detail.append({
            "ticker": sym,
            "shares": shares,
            "avg_price": float(h.get("avg_price", 0)),
            "current_price": cur_price,
            "position_value": position_value,
            "pnl_pct": round((cur_price - float(h.get("avg_price", 1))) / float(h.get("avg_price", 1)) * 100, 2) if h.get("avg_price") else 0,
            "sector": info.get("sector", "Unknown"),
            "beta": info.get("beta") or 1.0,
        })

    portfolio_value = total_value if total_value > 0 else 1.0

    # Add weights
    for hd in holdings_detail:
        hd["weight"] = round(hd["position_value"] / portfolio_value, 4)

    # Compute returns
    spy_prices = price_history.get("SPY", [])
    spy_returns = _daily_returns(spy_prices)
    returns_map = {}
    betas = {}
    vars_95 = {}
    max_dds = {}
    factor_exposures = {}

    for hd in holdings_detail:
        sym = hd["ticker"]
        prices = price_history.get(sym, [])
        if prices:
            rets = _daily_returns(prices)
            returns_map[sym] = rets
            beta = _compute_beta(rets, spy_returns)
            betas[sym] = beta or hd["beta"]
            vars_95[sym] = _parametric_var(rets)
            max_dds[sym] = _max_drawdown(prices)
        else:
            betas[sym] = hd["beta"]
            max_dds[sym] = 0.0

        factor_exposures[sym] = _estimate_factor_exposure(info_map.get(sym, {}))

    # Portfolio beta (weighted average)
    portfolio_beta = round(sum(hd["weight"] * betas.get(hd["ticker"], 1.0) for hd in holdings_detail), 2)

    # Portfolio VaR: combine return series weighted
    portfolio_var = None
    if returns_map and spy_returns:
        min_len = min(len(r) for r in returns_map.values())
        if min_len > 20:
            port_returns = np.zeros(min_len)
            for hd in holdings_detail:
                sym = hd["ticker"]
                if sym in returns_map:
                    rets_arr = np.array(returns_map[sym][-min_len:], dtype=float)
                    port_returns += hd["weight"] * rets_arr
            portfolio_var = _parametric_var(list(port_returns))

    # Portfolio max drawdown using SPY as proxy weighted by beta
    portfolio_max_dd = sum(
        hd["weight"] * max_dds.get(hd["ticker"], 0) for hd in holdings_detail
    )

    # Sector concentration
    sector_map: Dict[str, float] = {}
    for hd in holdings_detail:
        sec = hd.get("sector", "Unknown")
        sector_map[sec] = sector_map.get(sec, 0) + hd["weight"]
    sector_concentration = {k: round(v * 100, 1) for k, v in sorted(sector_map.items(), key=lambda x: -x[1])}

    # Herfindahl-Hirschman concentration index
    hhi = sum(w ** 2 for w in [hd["weight"] for hd in holdings_detail])
    if hhi > 0.25:
        concentration_warning = "HIGH concentration risk — top holdings dominate portfolio"
    elif hhi > 0.15:
        concentration_warning = "MODERATE concentration — consider broadening diversification"
    else:
        concentration_warning = "Well diversified portfolio"

    # Factor exposure (portfolio weighted)
    port_factor = {"growth": 0.0, "value": 0.0, "quality": 0.0}
    for hd in holdings_detail:
        sym = hd["ticker"]
        fe = factor_exposures.get(sym, {})
        for f in port_factor:
            port_factor[f] += hd["weight"] * fe.get(f, 0)
    port_factor = {k: round(v, 2) for k, v in port_factor.items()}

    # Correlation matrix
    corr_matrix = _compute_correlation_matrix(returns_map)

    # Stress tests
    stress_results = _run_stress_test(holdings_detail, portfolio_value, betas, factor_exposures)

    # Position sizing for each holding
    for hd in holdings_detail:
        sym = hd["ticker"]
        sizing = _position_sizing_recommendation(
            betas.get(sym, 1.0),
            vars_95.get(sym),
            max_dds.get(sym, 0),
        )
        hd["risk_sizing"] = sizing

    # Risk summary narrative
    worst_stress = min(stress_results, key=lambda x: x["portfolio_pct_change"]) if stress_results else {}
    risk_summary = (
        f"Portfolio beta: {portfolio_beta:.2f}. "
        f"Estimated 95% 1-day VaR: {portfolio_var:.2f}% of portfolio. "
        f"Max drawdown (12m): {portfolio_max_dd:.1f}%. "
        f"{concentration_warning}. "
        f"Worst stress scenario: {worst_stress.get('scenario', 'N/A')} ({worst_stress.get('portfolio_pct_change', 0):+.1f}%). "
        f"Factor tilt: {'Growth-heavy' if port_factor['growth'] > 0.2 else 'Value-leaning' if port_factor['value'] > 0.2 else 'Balanced'} "
        f"({'Quality premium' if port_factor['quality'] > 0.1 else 'Quality discount'})."
    ) if portfolio_var else (
        f"Portfolio beta: {portfolio_beta:.2f}. "
        f"{concentration_warning}. "
        f"Factor tilt: Growth={port_factor['growth']}, Value={port_factor['value']}, Quality={port_factor['quality']}."
    )

    return {
        "portfolio_value": round(portfolio_value, 2),
        "holdings_detail": holdings_detail,
        "portfolio_beta": portfolio_beta,
        "sector_concentration": sector_concentration,
        "concentration_warning": concentration_warning,
        "correlation_matrix": corr_matrix,
        "var_95": portfolio_var,
        "max_drawdown": round(portfolio_max_dd, 2),
        "stress_tests": stress_results,
        "factor_exposure": port_factor,
        "risk_summary": risk_summary,
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
    }


async def analyze_single_stock_risk(ticker: str) -> Dict:
    """
    Risk profile for a single ticker.
    """
    ticker = ticker.upper().strip()

    price_history, info = await asyncio.gather(
        _get_price_history([ticker]),
        _get_ticker_info(ticker),
    )

    prices = price_history.get(ticker, [])
    spy_prices = price_history.get("SPY", [])

    rets = _daily_returns(prices)
    spy_rets = _daily_returns(spy_prices)

    beta = _compute_beta(rets, spy_rets)
    var_95 = _parametric_var(rets)
    max_dd = _max_drawdown(prices)
    factor_exp = _estimate_factor_exposure(info)
    sizing = _position_sizing_recommendation(beta or 1.0, var_95, max_dd)

    # Volatility (annualised)
    if rets:
        ann_vol = round(float(np.std(rets)) * math.sqrt(252) * 100, 1)
    else:
        ann_vol = None

    return {
        "ticker": ticker,
        "beta": beta,
        "var_95_daily_pct": var_95,
        "max_drawdown_pct": max_dd,
        "annualised_volatility_pct": ann_vol,
        "factor_exposure": factor_exp,
        "sizing_recommendation": sizing,
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
    }
