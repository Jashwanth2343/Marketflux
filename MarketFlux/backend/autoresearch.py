"""
autoresearch.py — Autonomous research loop for MarketFlux.

Inspired by Andrej Karpathy's autoresearch (github.com/karpathy/autoresearch):
  - Reads program.md for research instructions.
  - Modifies REACT_SYSTEM_PROMPT in react_agent.py (the "train.py" equivalent).
  - Runs eval_pipeline.py to measure the composite score (the "val_bpb" equivalent).
  - Keeps the change if the score improves; reverts otherwise.
  - Logs every experiment to autoresearch_log.json.

Usage:
    python autoresearch.py [--iterations N] [--log autoresearch_log.json]

Requirements:
    GEMINI_API_KEY or EMERGENT_LLM_KEY must be set in .env.
    All regular MarketFlux backend dependencies must be installed.
"""

import argparse
import asyncio
import copy
import json
import logging
import os
import re
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

import google.generativeai as genai

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("autoresearch")

# ---------------------------------------------------------------------------
# Paths (all relative to this file so the script is location-independent)
# ---------------------------------------------------------------------------
_HERE = Path(__file__).parent
REACT_AGENT_PATH = _HERE / "react_agent.py"
PROGRAM_MD_PATH = _HERE / "program.md"
DEFAULT_LOG_PATH = _HERE / "autoresearch_log.json"

# ---------------------------------------------------------------------------
# LLM helpers
# ---------------------------------------------------------------------------

def _configure_genai() -> None:
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("EMERGENT_LLM_KEY")
    if not api_key:
        raise RuntimeError(
            "No API key found. Set GEMINI_API_KEY or EMERGENT_LLM_KEY in .env."
        )
    genai.configure(api_key=api_key)


def _make_model(model_id: str = "models/gemini-2.5-flash") -> genai.GenerativeModel:
    return genai.GenerativeModel(model_id)


# ---------------------------------------------------------------------------
# Evaluation helpers (import from eval_pipeline so we reuse its logic)
# ---------------------------------------------------------------------------

async def _run_eval() -> dict:
    """
    Run the evaluation pipeline and return a summary dict with per-metric averages
    and the overall composite score.
    """
    # Import here so that edits to react_agent.py are picked up on each call.
    # We reload the module so Python re-imports the potentially modified file.
    import importlib
    import eval_pipeline

    importlib.reload(eval_pipeline)

    # eval_pipeline.main() writes eval_report.json and prints a summary.
    # We capture results by running its test cases directly.
    results = []
    for case in eval_pipeline.TEST_CASES:
        res = await eval_pipeline.run_test_case(case)
        results.append(res)

    avg_correctness = (
        sum(r["eval_scores"].get("correctness_score", 0) for r in results) / len(results)
    )
    avg_formatting = (
        sum(r["eval_scores"].get("formatting_score", 0) for r in results) / len(results)
    )
    avg_conciseness = (
        sum(r["eval_scores"].get("conciseness_score", 0) for r in results) / len(results)
    )
    composite = (avg_correctness + avg_formatting + avg_conciseness) / 3.0

    return {
        "avg_correctness": round(avg_correctness, 3),
        "avg_formatting": round(avg_formatting, 3),
        "avg_conciseness": round(avg_conciseness, 3),
        "composite": round(composite, 3),
        "raw_results": results,
    }


# ---------------------------------------------------------------------------
# Prompt-extraction helpers
# ---------------------------------------------------------------------------

_PROMPT_START = 'REACT_SYSTEM_PROMPT = """'
_PROMPT_END = '"""\n'


def _extract_system_prompt(source: str) -> str:
    """Return only the body of REACT_SYSTEM_PROMPT from the source text."""
    start = source.find(_PROMPT_START)
    if start == -1:
        raise ValueError("Could not find REACT_SYSTEM_PROMPT in react_agent.py")
    start += len(_PROMPT_START)
    end = source.find(_PROMPT_END, start)
    if end == -1:
        raise ValueError("Could not find closing triple-quote for REACT_SYSTEM_PROMPT")
    return source[start:end]


def _replace_system_prompt(source: str, new_prompt_body: str) -> str:
    """Replace the body of REACT_SYSTEM_PROMPT in the source text."""
    start = source.find(_PROMPT_START)
    end = source.find(_PROMPT_END, start + len(_PROMPT_START))
    prefix = source[: start + len(_PROMPT_START)]
    suffix = source[end:]
    return prefix + new_prompt_body + suffix


# ---------------------------------------------------------------------------
# LLM-powered proposal generator
# ---------------------------------------------------------------------------

_PROPOSE_PROMPT = """\
You are an expert AI agent helping to improve the MarketFlux financial assistant.

== RESEARCH PROGRAM ==
{program_md}

== CURRENT REACT_SYSTEM_PROMPT ==
{current_prompt}

== LAST EVAL SCORES ==
Composite: {composite}/5.0
  avg_correctness : {avg_correctness}/5.0
  avg_formatting  : {avg_formatting}/5.0
  avg_conciseness : {avg_conciseness}/5.0

== PREVIOUS ATTEMPTS (last 5) ==
{previous_attempts}

== YOUR TASK ==
Propose ONE small, targeted improvement to REACT_SYSTEM_PROMPT that is most likely to raise the
composite score. Focus on the weakest metric above.

Rules:
- Change only the text of the prompt, not Python code outside the string.
- Make a single, coherent edit (add/remove/reword a rule or example).
- Do NOT make the prompt dramatically longer — clarity beats length.

Output ONLY a JSON object with exactly two keys:
{{
  "change_description": "<one-line summary of what you changed and why>",
  "new_prompt": "<the complete new REACT_SYSTEM_PROMPT body (everything that will sit between the triple-quotes)>"
}}
Do not include any text outside the JSON object.
"""


def _build_previous_attempts_text(log: list, n: int = 5) -> str:
    if not log:
        return "None yet."
    recent = log[-n:]
    lines = []
    for entry in recent:
        status = "✅ ACCEPTED" if entry.get("accepted") else "❌ REJECTED"
        lines.append(
            f"  Iter {entry['iteration']}: {status} | "
            f"Δ={entry.get('new_composite', 0) - entry.get('baseline_composite', 0):+.3f} | "
            f"{entry.get('change_description', '')}"
        )
    return "\n".join(lines)


async def _propose_change(
    program_md: str,
    current_prompt: str,
    last_scores: dict,
    experiment_log: list,
    model: genai.GenerativeModel,
) -> dict:
    """Ask the LLM to propose an improved system prompt. Returns the parsed JSON."""
    prompt_text = _PROPOSE_PROMPT.format(
        program_md=program_md,
        current_prompt=current_prompt,
        composite=last_scores.get("composite", 0),
        avg_correctness=last_scores.get("avg_correctness", 0),
        avg_formatting=last_scores.get("avg_formatting", 0),
        avg_conciseness=last_scores.get("avg_conciseness", 0),
        previous_attempts=_build_previous_attempts_text(experiment_log),
    )
    logger.info("Asking LLM for improvement proposal...")
    response = model.generate_content(
        prompt_text,
        generation_config={"response_mime_type": "application/json"},
    )
    raw = response.text.strip()
    # Strip possible markdown fences
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return json.loads(raw)


# ---------------------------------------------------------------------------
# Experiment log helpers
# ---------------------------------------------------------------------------

def _load_log(path: Path) -> list:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            return []
    return []


def _save_log(path: Path, log: list) -> None:
    path.write_text(json.dumps(log, indent=2))


# ---------------------------------------------------------------------------
# Main research loop
# ---------------------------------------------------------------------------

async def research_loop(iterations: int, log_path: Path) -> None:
    _configure_genai()
    model = _make_model()

    program_md = PROGRAM_MD_PATH.read_text()
    experiment_log = _load_log(log_path)

    logger.info("=" * 60)
    logger.info("MARKETFLUX AUTORESEARCH")
    logger.info(f"Iterations planned : {iterations}")
    logger.info(f"Log file           : {log_path}")
    logger.info("=" * 60)

    # --- Baseline evaluation ---
    logger.info("Running baseline evaluation…")
    baseline_scores = await _run_eval()
    logger.info(
        f"Baseline composite: {baseline_scores['composite']:.3f}/5.0  "
        f"(correctness={baseline_scores['avg_correctness']}, "
        f"formatting={baseline_scores['avg_formatting']}, "
        f"conciseness={baseline_scores['avg_conciseness']})"
    )

    best_composite = baseline_scores["composite"]
    current_source = REACT_AGENT_PATH.read_text()

    for iteration in range(1, iterations + 1):
        logger.info("-" * 60)
        logger.info(f"ITERATION {iteration}/{iterations}  (best so far: {best_composite:.3f})")

        current_prompt = _extract_system_prompt(current_source)

        # --- Propose change ---
        try:
            proposal = await _propose_change(
                program_md,
                current_prompt,
                baseline_scores,
                experiment_log,
                model,
            )
        except Exception as e:
            logger.error(f"Proposal failed: {e}")
            experiment_log.append(
                {
                    "iteration": iteration,
                    "change_description": f"[PROPOSAL ERROR] {e}",
                    "baseline_composite": best_composite,
                    "new_composite": None,
                    "accepted": False,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
            _save_log(log_path, experiment_log)
            continue

        change_description = proposal.get("change_description", "no description")
        new_prompt_body = proposal.get("new_prompt", "")

        if not new_prompt_body.strip():
            logger.warning("LLM returned empty prompt body — skipping iteration.")
            continue

        logger.info(f"Proposal: {change_description}")

        # --- Apply change ---
        new_source = _replace_system_prompt(current_source, new_prompt_body)
        REACT_AGENT_PATH.write_text(new_source)

        # --- Evaluate ---
        logger.info("Running evaluation with new prompt…")
        try:
            new_scores = await _run_eval()
        except Exception as e:
            logger.error(f"Evaluation crashed: {e} — reverting.")
            REACT_AGENT_PATH.write_text(current_source)
            experiment_log.append(
                {
                    "iteration": iteration,
                    "change_description": change_description,
                    "baseline_composite": best_composite,
                    "new_composite": None,
                    "accepted": False,
                    "error": str(e),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
            _save_log(log_path, experiment_log)
            continue

        new_composite = new_scores["composite"]
        delta = new_composite - best_composite
        accepted = new_composite > best_composite

        logger.info(
            f"Result: composite={new_composite:.3f}  Δ={delta:+.3f}  "
            f"{'✅ ACCEPTED' if accepted else '❌ REJECTED'}"
        )

        # Snapshot scores before any mutation so log entries are always correct.
        old_composite = best_composite
        old_scores = {k: v for k, v in baseline_scores.items() if k != "raw_results"}

        if accepted:
            # Keep the new source as the new baseline
            current_source = new_source
            best_composite = new_composite
            baseline_scores = new_scores
        else:
            # Revert the file to the previous version
            REACT_AGENT_PATH.write_text(current_source)

        experiment_log.append(
            {
                "iteration": iteration,
                "change_description": change_description,
                "baseline_composite": old_composite,
                "new_composite": new_composite,
                "scores_before": old_scores,
                "scores_after": {k: v for k, v in new_scores.items() if k != "raw_results"},
                "accepted": accepted,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        _save_log(log_path, experiment_log)

    # --- Final summary ---
    logger.info("=" * 60)
    logger.info("AUTORESEARCH COMPLETE")
    logger.info(f"Best composite score achieved: {best_composite:.3f}/5.0")
    accepted_count = sum(1 for e in experiment_log[-iterations:] if e.get("accepted"))
    logger.info(f"Accepted changes: {accepted_count}/{iterations}")
    logger.info(f"Full experiment log: {log_path}")
    logger.info("=" * 60)


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=textwrap.dedent(
            """
            MarketFlux Autoresearch — autonomous improvement loop for the AI agent.

            Runs for --iterations rounds. Each round:
              1. Asks Gemini to propose an improvement to REACT_SYSTEM_PROMPT.
              2. Applies the change to react_agent.py.
              3. Runs eval_pipeline.py to measure quality.
              4. Keeps the change if the composite score improved; reverts otherwise.
              5. Logs everything to --log.
            """
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=10,
        help="Number of experiment iterations to run (default: 10).",
    )
    parser.add_argument(
        "--log",
        type=Path,
        default=DEFAULT_LOG_PATH,
        help="Path to the JSON experiment log file (default: autoresearch_log.json).",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    # Change directory to the backend folder so relative imports work correctly.
    os.chdir(_HERE)
    sys.path.insert(0, str(_HERE))

    asyncio.run(research_loop(iterations=args.iterations, log_path=args.log))
