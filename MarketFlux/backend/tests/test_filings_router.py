"""HTTP-layer unit tests for filings_router — no network, mocked sec_filings."""
import os
import sys
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from filings_router import build_filings_router

app = FastAPI()
app.include_router(build_filings_router())
client = TestClient(app)


# ---------------------------------------------------------------------------
# Symbol validation
# ---------------------------------------------------------------------------
def test_invalid_symbol_returns_422():
    res = client.get("/api/filings/../../etc/passwd")
    assert res.status_code in (404, 422)

def test_invalid_symbol_with_spaces_returns_422():
    res = client.get("/api/filings/AAPL MSFT")
    assert res.status_code in (404, 422)

def test_symbol_too_long_returns_422():
    res = client.get("/api/filings/TOOLONGSYMBOL")
    assert res.status_code == 422


# ---------------------------------------------------------------------------
# Happy-path passthrough
# ---------------------------------------------------------------------------
@patch("filings_router.sec_filings.get_recent_filings", new_callable=AsyncMock)
def test_filings_list_ok(mock_fn):
    mock_fn.return_value = {"ok": True, "filings": [{"accession": "0001"}]}
    res = client.get("/api/filings/AAPL")
    assert res.status_code == 200
    assert res.json()["ok"] is True
    mock_fn.assert_awaited_once_with("AAPL")


@patch("filings_router.sec_filings.diff_risk_factors", new_callable=AsyncMock)
def test_risk_diff_ok(mock_fn):
    mock_fn.return_value = {"ok": True, "diff": "..."}
    res = client.get("/api/filings/MSFT/risk-diff")
    assert res.status_code == 200


@patch("filings_router.sec_filings.search_filings", new_callable=AsyncMock)
def test_search_ok(mock_fn):
    mock_fn.return_value = {"ok": True, "results": []}
    res = client.get("/api/filings/TSLA/search?q=revenue")
    assert res.status_code == 200


# ---------------------------------------------------------------------------
# Error-path: 404 for known "not found" messages
# ---------------------------------------------------------------------------
@patch("filings_router.sec_filings.get_recent_filings", new_callable=AsyncMock)
def test_known_not_found_returns_404(mock_fn):
    mock_fn.return_value = {"ok": False, "error": "No EDGAR filings found for XYZ"}
    res = client.get("/api/filings/XYZ")
    assert res.status_code == 404


@patch("filings_router.sec_filings.diff_risk_factors", new_callable=AsyncMock)
def test_need_two_10k_returns_404(mock_fn):
    mock_fn.return_value = {"ok": False, "error": "Need two 10-Ks to diff"}
    res = client.get("/api/filings/XYZ/risk-diff")
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# Error-path: 503 for unknown/transient upstream errors
# ---------------------------------------------------------------------------
@patch("filings_router.sec_filings.get_recent_filings", new_callable=AsyncMock)
def test_transient_error_returns_503(mock_fn):
    mock_fn.return_value = {"ok": False, "error": "Connection reset by peer"}
    res = client.get("/api/filings/AAPL")
    assert res.status_code == 503


@patch("filings_router.sec_filings.search_filings", new_callable=AsyncMock)
def test_unknown_search_error_returns_503(mock_fn):
    mock_fn.return_value = {"ok": False, "error": "Timeout reading EDGAR response"}
    res = client.get("/api/filings/AAPL/search?q=revenue risk")
    assert res.status_code == 503


# ---------------------------------------------------------------------------
# Query param validation
# ---------------------------------------------------------------------------
def test_search_requires_q():
    res = client.get("/api/filings/AAPL/search")
    assert res.status_code == 422

def test_search_q_too_short_returns_422():
    res = client.get("/api/filings/AAPL/search?q=x")
    assert res.status_code == 422
