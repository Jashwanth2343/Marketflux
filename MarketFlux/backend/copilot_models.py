"""Selectable LLMs for the Copilot agent.

The agent runs on Gemini (native function-calling) or any OpenAI-compatible
provider (OpenRouter, NVIDIA NIM) for tool-calling. Models are gated by which
provider keys are present in the environment, so the picker only ever shows what
will actually work. IDs below were confirmed available + tool-capable on the
configured OpenRouter / NIM catalogs.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Optional

DEFAULT_KEY = "gemini-2.5-flash"


@dataclass(frozen=True)
class ModelSpec:
    key: str          # stable id used by the UI + API
    label: str        # display name
    provider: str     # "gemini" | "openrouter" | "nim"
    model_id: str     # the provider's model identifier
    note: str = ""    # short descriptor for the UI
    experimental: bool = False  # tool-calling not yet confirmed on this provider


# Order = display order. First Gemini entry is the default.
CATALOG: List[ModelSpec] = [
    ModelSpec("gemini-2.5-flash", "Gemini 2.5 Flash", "gemini", "gemini-2.5-flash", "Fast · default"),
    ModelSpec("gemini-2.5-pro", "Gemini 2.5 Pro", "gemini", "gemini-2.5-pro", "Deeper reasoning"),
    ModelSpec("gpt-4o", "GPT-4o", "openrouter", "openai/gpt-4o", "OpenAI flagship"),
    ModelSpec("gpt-4o-mini", "GPT-4o mini", "openrouter", "openai/gpt-4o-mini", "Cheap & fast"),
    ModelSpec("claude-3-haiku", "Claude 3 Haiku", "openrouter", "anthropic/claude-3-haiku", "Anthropic"),
    ModelSpec("qwen-2.5-72b", "Qwen 2.5 72B", "openrouter", "qwen/qwen-2.5-72b-instruct", "Strong reasoning"),
    ModelSpec("deepseek-chat", "DeepSeek V3", "openrouter", "deepseek/deepseek-chat", "Reasoning/financials", experimental=True),
    ModelSpec("nemotron-70b", "Nemotron 70B", "nim", "nvidia/llama-3.1-nemotron-70b-instruct", "NVIDIA", experimental=True),
]


def _provider_key(provider: str) -> Optional[str]:
    return {
        "gemini": os.getenv("GEMINI_API_KEY"),
        "openrouter": os.getenv("OPENROUTER_API_KEY"),
        "nim": os.getenv("NVIDIA_NIM_API_KEY"),
    }.get(provider)


def _provider_base_url(provider: str) -> Optional[str]:
    if provider == "openrouter":
        return (os.getenv("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1").rstrip("/")
    if provider == "nim":
        return (os.getenv("NVIDIA_NIM_BASE_URL") or "https://integrate.api.nvidia.com/v1").rstrip("/")
    return None


def available_models() -> List[dict]:
    """Models whose provider key is present — what the picker should show."""
    out = []
    for m in CATALOG:
        if _provider_key(m.provider):
            out.append({
                "key": m.key,
                "label": m.label,
                "provider": m.provider,
                "note": m.note,
                "experimental": m.experimental,
                "default": m.key == DEFAULT_KEY,
            })
    return out


@dataclass(frozen=True)
class ResolvedModel:
    key: str
    label: str
    provider: str
    model_id: str
    base_url: Optional[str]
    api_key: Optional[str]


def resolve(key: Optional[str]) -> ResolvedModel:
    """Resolve a UI key to a usable model, falling back to the default if the
    requested one is unknown or its provider key is missing."""
    spec = next((m for m in CATALOG if m.key == key), None)
    if spec is None or not _provider_key(spec.provider):
        spec = next(m for m in CATALOG if m.key == DEFAULT_KEY)
    return ResolvedModel(
        key=spec.key,
        label=spec.label,
        provider=spec.provider,
        model_id=spec.model_id,
        base_url=_provider_base_url(spec.provider),
        api_key=_provider_key(spec.provider),
    )
