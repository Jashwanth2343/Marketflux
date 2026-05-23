"""Sandboxed Python execution tool for the Copilot agent.

Gives the agent a quantitative scratchpad: it can write Python (numpy / pandas /
scipy / math / statistics) to compute things the fixed tools can't — position
sizing, Sharpe/Sortino, correlations, portfolio optimization, ad-hoc backtests,
custom screens.

SAFETY. The code is LLM-authored and the agent reads untrusted web/news content,
so this is hardened in depth:
  1. AST allowlist — only safe modules import; file/network/system modules,
     dunder-attribute escapes, and dangerous builtins (open/eval/exec/getattr…)
     are rejected before anything runs.
  2. Isolated subprocess — `python -I` with a CLEAN env (no APCA/GEMINI/Mongo
     secrets present), a throwaway temp cwd, a CPU rlimit, and a wall-clock
     timeout. Even a sandbox escape finds no secrets in the environment.
  3. Output is capped.
"""
from __future__ import annotations

import ast
import logging
import os
import subprocess
import sys
import tempfile

logger = logging.getLogger(__name__)

# Top-level modules the sandboxed code may import.
ALLOWED_MODULES = {
    "math", "cmath", "statistics", "random", "decimal", "fractions",
    "datetime", "json", "re", "itertools", "functools", "collections",
    "numpy", "pandas", "scipy",
}

# Builtins/names that enable file, eval, or sandbox-escape access.
BLOCKED_NAMES = {
    "open", "eval", "exec", "compile", "__import__", "input", "breakpoint",
    "globals", "locals", "vars", "getattr", "setattr", "delattr",
    "memoryview", "help", "exit", "quit", "object",
}

TIMEOUT_SECONDS = 12
MAX_OUTPUT_CHARS = 6000

_PRELUDE = (
    "import math, statistics, json, datetime\n"
    "import numpy as np\n"
    "import pandas as pd\n"
    "pd.set_option('display.width', 120)\n"
    "pd.set_option('display.max_columns', 30)\n"
)


def _validate(code: str) -> str | None:
    """Return an error string if the code uses something disallowed, else None."""
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return f"SyntaxError: {exc.msg} (line {exc.lineno})"

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top not in ALLOWED_MODULES:
                    return f"Import of '{alias.name}' is not allowed in the sandbox."
        elif isinstance(node, ast.ImportFrom):
            top = (node.module or "").split(".")[0]
            if top not in ALLOWED_MODULES:
                return f"Import from '{node.module}' is not allowed in the sandbox."
        elif isinstance(node, ast.Attribute):
            if node.attr.startswith("__") and node.attr.endswith("__"):
                return f"Access to dunder attribute '{node.attr}' is not allowed."
        elif isinstance(node, ast.Name):
            if node.id in BLOCKED_NAMES:
                return f"Use of '{node.id}' is not allowed in the sandbox."
    return None


def _limit_resources():  # pragma: no cover - runs in child process
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
    except Exception:
        pass


def run_python(code: str) -> dict:
    """Run Python in a secure sandbox for quantitative analysis and return its
    printed output. numpy (as np), pandas (as pd), math, statistics, json and
    datetime are pre-imported — you do NOT need to import them. scipy is also
    available.

    Use this for any calculation the other tools can't do directly: position
    sizing (e.g. Kelly, fixed-fractional), Sharpe/Sortino, correlations, expected
    value, portfolio weights/optimization, simple simulations, or crunching
    numbers you gathered from research tools. PRINT the results you want to see —
    only stdout is returned.

    The sandbox has NO file, network, or system access (no os/sys/requests/open).
    Keep code self-contained: embed the numbers you need as literals.

    Args:
        code: Python source to execute. Print what you want returned.
    """
    if not code or not code.strip():
        return {"ok": False, "error": "No code provided."}

    violation = _validate(code)
    if violation:
        return {"ok": False, "error": violation}

    safe_env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "PYTHONIOENCODING": "utf-8",
        "OPENBLAS_NUM_THREADS": "2",
        "OMP_NUM_THREADS": "2",
        "MPLBACKEND": "Agg",
        "HOME": tempfile.gettempdir(),
    }

    program = _PRELUDE + "\n" + code
    try:
        with tempfile.TemporaryDirectory() as tmp:
            proc = subprocess.run(
                [sys.executable, "-I", "-c", program],
                env=safe_env,
                cwd=tmp,
                capture_output=True,
                text=True,
                timeout=TIMEOUT_SECONDS,
                preexec_fn=_limit_resources if os.name == "posix" else None,
            )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"Execution timed out after {TIMEOUT_SECONDS}s."}
    except Exception as exc:
        logger.error(f"run_python failed to launch: {exc}")
        return {"ok": False, "error": f"Sandbox error: {exc}"}

    stdout = (proc.stdout or "")[:MAX_OUTPUT_CHARS]
    stderr = (proc.stderr or "").strip()

    if proc.returncode != 0:
        # Surface the last line of the traceback — most useful to the model.
        tail = stderr.splitlines()[-1] if stderr else "non-zero exit"
        return {"ok": False, "error": tail, "stdout": stdout}

    if not stdout.strip():
        return {"ok": True, "stdout": "", "note": "Code ran but printed nothing — use print() to return values."}
    return {"ok": True, "stdout": stdout}
