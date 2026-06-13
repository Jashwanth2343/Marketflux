"""Copilot eval harness — runs the golden-query set against the live agent.

Usage (from MarketFlux/backend, with the venv):
    ./venv/bin/python -m evals.run_evals --smoke      # 3 quick cases
    ./venv/bin/python -m evals.run_evals              # full set
    ./venv/bin/python -m evals.run_evals --case live-quote

Every case runs in research mode (no execution tools) with db=None, so evals
never touch Mongo, never stage trades, and never write memory. Results land in
evals/out/report.json (gitignored) and print as a table. Exit code 1 if any
case fails — usable as a CI gate once keys are available there.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))
load_dotenv(BACKEND_DIR / ".env")

GOLDEN = Path(__file__).resolve().parent / "golden.json"
OUT_DIR = Path(__file__).resolve().parent / "out"


async def run_case(case: dict) -> dict:
    """Run one golden query through the agent and grade it."""
    from copilot_agent import run_copilot_agent

    start = time.monotonic()
    final_text_parts: list[str] = []
    tools_used: list[str] = []
    stream_error = None

    try:
        async with asyncio.timeout(case.get("max_latency_s", 90) + 30):
            async for raw in run_copilot_agent(
                message=case["query"], db=None, user_id="eval",
                session_id=f"eval-{case['id']}", confirm=True, mode="research",
            ):
                for line in raw.splitlines():
                    if not line.startswith("data: "):
                        continue
                    try:
                        ev = json.loads(line[6:])
                    except json.JSONDecodeError:
                        continue
                    if ev.get("type") == "token":
                        final_text_parts.append(ev.get("content", ""))
                    elif ev.get("type") == "tool_call":
                        tools_used.append(ev.get("name", "?"))
                    elif ev.get("type") == "done" and ev.get("error"):
                        stream_error = ev["error"]
    except (TimeoutError, asyncio.TimeoutError):
        stream_error = "hard timeout"
    except Exception as exc:  # noqa: BLE001 — a crash is itself an eval result
        stream_error = f"crashed: {exc}"

    latency = time.monotonic() - start
    text = "".join(final_text_parts)
    checks: dict[str, bool] = {}

    checks["completed"] = stream_error is None and bool(text.strip())
    if "max_latency_s" in case:
        checks["latency"] = latency <= case["max_latency_s"]
    if "expect_contains_any" in case:
        checks["contains_any"] = any(s.lower() in text.lower() for s in case["expect_contains_any"])
    if "expect_contains_all" in case:
        checks["contains_all"] = all(s.lower() in text.lower() for s in case["expect_contains_all"])
    if "expect_regex" in case:
        checks["regex"] = bool(re.search(case["expect_regex"], text))
    if case.get("expect_tool_used"):
        checks["tool_used"] = len(tools_used) > 0
    if "min_response_chars" in case:
        checks["min_length"] = len(text) >= case["min_response_chars"]

    return {
        "id": case["id"],
        "passed": all(checks.values()),
        "checks": checks,
        "latency_s": round(latency, 1),
        "tools_used": tools_used,
        "error": stream_error,
        "response_preview": text[:240],
    }


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true", help="run only the smoke subset")
    parser.add_argument("--case", help="run a single case by id")
    args = parser.parse_args()

    spec = json.loads(GOLDEN.read_text())
    cases = spec["cases"]
    if args.case:
        cases = [c for c in cases if c["id"] == args.case]
        if not cases:
            print(f"no case named {args.case!r}"); return 2
    elif args.smoke:
        cases = [c for c in cases if c.get("smoke")]

    print(f"Running {len(cases)} eval case(s) — research mode, db=None\n")
    results = []
    for case in cases:  # sequential: avoids yfinance burst throttling
        r = await run_case(case)
        results.append(r)
        mark = "PASS" if r["passed"] else "FAIL"
        failed = [k for k, v in r["checks"].items() if not v]
        detail = f"  failed: {', '.join(failed)}" if failed else ""
        err = f"  error: {r['error']}" if r["error"] else ""
        print(f"[{mark}] {r['id']:24} {r['latency_s']:6.1f}s  tools={len(r['tools_used'])}{detail}{err}")

    passed = sum(1 for r in results if r["passed"])
    print(f"\n{passed}/{len(results)} passed")

    OUT_DIR.mkdir(exist_ok=True)
    report_path = OUT_DIR / "report.json"
    report_path.write_text(json.dumps({
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "passed": passed, "total": len(results), "results": results,
    }, indent=2))
    print(f"report: {report_path}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
