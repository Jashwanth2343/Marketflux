"""Unit tests for the copilot's parallel read-tool fan-out."""
import asyncio
import time

import pytest

import copilot_agent as ca


def _patch_helpers(monkeypatch, exec_fn):
    monkeypatch.setattr(ca, "_exec_tool", exec_fn)
    monkeypatch.setattr(ca, "_tool_label", lambda n, a: n)
    monkeypatch.setattr(ca, "_sanitize", lambda a: a)
    monkeypatch.setattr(ca, "_result_summary", lambda n, r: n)
    monkeypatch.setattr(ca, "_insight_payload", lambda n, r: None)


def _run(batch, emit, results):
    async def go():
        async for _ in ca._run_read_tools_parallel(batch, None, "u", True, emit, results):
            pass
    asyncio.run(go())


def test_events_pair_and_results_fill_slots(monkeypatch):
    async def fake_exec(name, args, db, user_id, confirm):
        await asyncio.sleep(0.01)
        return {"ok": True, "tool": name, "args": args}

    _patch_helpers(monkeypatch, fake_exec)
    events = []

    def emit(ev_type, **data):
        events.append((ev_type, data.get("name")))
        return ev_type

    results = {}
    _run([(0, "get_quote", {"symbol": "AAPL"}), (1, "get_news", {})], emit, results)

    # All tool_call events come before any tool_result.
    assert events[:2] == [("tool_call", "get_quote"), ("tool_call", "get_news")]
    assert sorted(events[2:]) == [("tool_result", "get_news"), ("tool_result", "get_quote")]
    assert results[0]["tool"] == "get_quote"
    assert results[1]["tool"] == "get_news"


def test_duplicate_names_emit_results_in_reverse_call_order(monkeypatch):
    async def fake_exec(name, args, db, user_id, confirm):
        return {"ok": True, "symbol": args["symbol"]}

    _patch_helpers(monkeypatch, fake_exec)
    order = []

    def emit(ev_type, **data):
        if ev_type == "tool_result":
            order.append(data["name"])
        return ev_type

    results = {}
    _run([(0, "get_quote", {"symbol": "AAPL"}), (1, "get_quote", {"symbol": "MSFT"})],
         emit, results)
    # Reverse emission pairs each result with the client's newest pending entry.
    assert results[0]["symbol"] == "AAPL" and results[1]["symbol"] == "MSFT"
    assert order == ["get_quote", "get_quote"]


def test_tools_actually_run_concurrently(monkeypatch):
    async def slow_exec(name, args, db, user_id, confirm):
        await asyncio.sleep(0.05)
        return {"ok": True}

    _patch_helpers(monkeypatch, slow_exec)
    results = {}
    start = time.monotonic()
    _run([(i, f"tool_{i}", {}) for i in range(4)], lambda t, **d: t, results)
    elapsed = time.monotonic() - start
    # 4 × 50ms sequentially would be ≥200ms; concurrent should be well under.
    assert elapsed < 0.15, f"tools did not fan out concurrently ({elapsed:.3f}s)"
    assert len(results) == 4


def test_exception_becomes_error_result(monkeypatch):
    async def flaky_exec(name, args, db, user_id, confirm):
        if name == "boom":
            raise RuntimeError("provider down")
        return {"ok": True}

    _patch_helpers(monkeypatch, flaky_exec)
    results = {}
    _run([(0, "boom", {}), (1, "fine", {})], lambda t, **d: t, results)
    assert results[0] == {"ok": False, "error": "provider down"}
    assert results[1] == {"ok": True}


def test_sequential_tools_listed():
    # Execution tools and the stateful python scratchpad must never fan out.
    assert "place_order" in ca._SEQUENTIAL_TOOLS
    assert "close_position" in ca._SEQUENTIAL_TOOLS
    assert "cancel_all_open_orders" in ca._SEQUENTIAL_TOOLS
    assert "run_python" in ca._SEQUENTIAL_TOOLS
