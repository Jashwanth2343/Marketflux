# MarketFlux Autoresearch Program

## Mission
You are an autonomous research agent for MarketFlux, an AI-powered investment research platform.
Your job is to improve the quality of the MarketFlux AI assistant's responses by iterating on
`REACT_SYSTEM_PROMPT` inside `react_agent.py`.

## The Target File
**`react_agent.py`** — contains `REACT_SYSTEM_PROMPT`, a multi-section system prompt that instructs
the AI agent how to behave. This is the only string you should modify.

## Metric
Run `eval_pipeline.py` after each change. The evaluation produces three scores per test case:
- **correctness_score** (1–5): Does the response accurately address the user's intent?
- **formatting_score** (1–5): Did the response follow the formatting rules?
- **conciseness_score** (1–5): Did the response avoid irrelevant data?

The single scalar to maximize is the **composite score**:
```
composite = (avg_correctness + avg_formatting + avg_conciseness) / 3
```
Higher is better (max 5.0). Accept a change if and only if `new_composite > baseline_composite`.

## What You May Modify
- Only `REACT_SYSTEM_PROMPT` in `react_agent.py`.
- Do NOT change any function signatures, tool definitions, model IDs, or other Python logic.
- Do NOT import new packages.

## Research Strategy
Each iteration should make one small, focused change. Good ideas to explore:

1. **Tighten response-length rules** — the evaluator penalises over-verbose answers. Make the length
   rule for each query type crisper and more enforceable.
2. **Clarify table usage** — specify exactly which query types require a table vs. plain prose.
3. **Disclaimer placement** — the disclaimer is currently appended too broadly; tighten the
   condition so it only appears for deep analysis.
4. **Macro query handling** — strengthen the instruction to always quote exact live index numbers.
5. **Tone calibration** — more Goldman Sachs, less generic chatbot.
6. **Tool-call efficiency** — add guidance to avoid redundant tool calls for simple queries.

## Experiment Log
Every attempt is recorded in `autoresearch_log.json` with:
- `iteration`: experiment number
- `change_description`: one-line summary of what was changed
- `baseline_composite`: score before the change
- `new_composite`: score after the change
- `accepted`: true/false
- `timestamp`: ISO-8601

## Stopping Condition
The loop runs for a fixed number of iterations (configurable via `--iterations`). Review
`autoresearch_log.json` each morning to understand which changes the agent discovered.

## Example prompt to kick off a new experiment
```
Read program.md, then look at the current REACT_SYSTEM_PROMPT in react_agent.py.
Propose one small, targeted improvement. Apply it, run the eval, and report the score delta.
```
