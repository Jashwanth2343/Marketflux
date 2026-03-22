from __future__ import annotations

import json
import logging
import os
import re
import asyncio
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

from .usage_logging import build_usage_event

logger = logging.getLogger(__name__)

_MODEL_EXCLUDE_HINTS = {"embed", "embedding", "vision", "audio", "image"}
@dataclass(slots=True)
class _ResolvedModel:
    provider: str
    base_url: str
    api_key: str
    model_id: str
    model_info: Dict[str, Any]


class StrategyLLMRouter:
    """Provider-flexible router for the Fund OS agent swarm."""

    def __init__(self) -> None:
        self.openrouter_api_key = os.getenv("OPENROUTER_API_KEY", "")
        self.openrouter_base_url = (os.getenv("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1").rstrip("/")
        self.openrouter_model_override = (os.getenv("FUNDOS_OPENROUTER_FALLBACK_MODEL") or os.getenv("OPENROUTER_REASONING_MODEL") or "").strip()

        self.nim_api_key = os.getenv("NVIDIA_NIM_API_KEY", "")
        self.nim_base_url = (os.getenv("NVIDIA_NIM_BASE_URL") or "https://integrate.api.nvidia.com/v1").rstrip("/")
        self.nim_reasoning_override = (os.getenv("FUNDOS_NIM_REASONING_MODEL") or os.getenv("NVIDIA_NIM_REASONING_MODEL") or "").strip()
        self.nim_fast_override = (os.getenv("FUNDOS_NIM_FAST_MODEL") or os.getenv("NVIDIA_NIM_FAST_MODEL") or "").strip()

        self._catalog_cache: Dict[str, List[Dict[str, Any]]] = {}
        self._resolved_models: Dict[str, _ResolvedModel] = {}
        self.last_usage_event: Optional[Dict[str, Any]] = None
        self.usage_events: List[Dict[str, Any]] = []

    @property
    def configured(self) -> bool:
        return bool(self.nim_api_key or self.openrouter_api_key)

    def provider_plan(self) -> Dict[str, Any]:
        reasoning = self._resolved_models.get("reasoning")
        fast = self._resolved_models.get("fast")
        if reasoning or fast:
            primary = reasoning or fast
            return {
                "provider": primary.provider,
                "base_url": primary.base_url,
                "reasoning_model": reasoning.model_id if reasoning else None,
                "fast_model": fast.model_id if fast else None,
                "cost_profile": "discovered",
                "catalog_status": "resolved",
            }

        if self.nim_api_key:
            return {
                "provider": "nvidia_nim",
                "base_url": self.nim_base_url,
                "reasoning_model": self.nim_reasoning_override or None,
                "fast_model": self.nim_fast_override or None,
                "cost_profile": "discovering",
                "catalog_status": "pending_discovery",
            }
        if self.openrouter_api_key:
            return {
                "provider": "openrouter",
                "base_url": self.openrouter_base_url,
                "reasoning_model": self.openrouter_model_override or None,
                "fast_model": self.openrouter_model_override or None,
                "cost_profile": "discovering",
                "catalog_status": "pending_discovery",
            }
        return {
            "provider": "unconfigured",
            "reasoning_model": None,
            "fast_model": None,
            "cost_profile": "configuration-required",
            "catalog_status": "unconfigured",
        }

    def _normalize_model_list(self, data: Any) -> List[Dict[str, Any]]:
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if isinstance(data, dict):
            for key in ("data", "models", "items"):
                value = data.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
        return []

    def _model_id(self, model: Dict[str, Any]) -> str:
        return str(model.get("id") or model.get("model") or model.get("name") or "").strip()

    def _pricing(self, model: Dict[str, Any]) -> Dict[str, Any]:
        pricing = model.get("pricing")
        return pricing if isinstance(pricing, dict) else {}

    def _is_embedded_model(self, model_id: str) -> bool:
        lowered = model_id.lower()
        return any(hint in lowered for hint in _MODEL_EXCLUDE_HINTS)

    def _size_score(self, model_id: str) -> float:
        match = re.search(r"(\d+(?:\.\d+)?)\s*b", model_id.lower())
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                return 999.0
        return 999.0

    def _has_free_pricing(self, model: Dict[str, Any]) -> bool:
        pricing = self._pricing(model)
        prompt = pricing.get("prompt")
        completion = pricing.get("completion")
        try:
            return float(prompt or 0) == 0 and float(completion or 0) == 0
        except (TypeError, ValueError):
            return False

    def _score_model(self, model: Dict[str, Any], *, provider: str, kind: str) -> float:
        model_id = self._model_id(model)
        lowered = model_id.lower()
        if not model_id or self._is_embedded_model(model_id):
            return float("-inf")

        score = 0.0
        if self._has_free_pricing(model):
            score += 1000.0

        if "nemotron" in lowered:
            score += 180.0
        if "llama" in lowered:
            score += 120.0
        if "mistral" in lowered:
            score += 95.0
        if "qwen" in lowered:
            score += 90.0
        if "gpt" in lowered:
            score += 80.0

        if kind == "reasoning":
            if any(token in lowered for token in ("reason", "think", "instruct", "chat")):
                score += 60.0
        else:
            if any(token in lowered for token in ("mini", "nano", "small", "flash", "fast")):
                score += 60.0

        if provider == "openrouter" and "free" in lowered:
            score += 50.0

        score -= min(self._size_score(model_id), 999.0) * 10.0
        return score

    def _select_model(self, models: List[Dict[str, Any]], *, provider: str, kind: str, override: str = "") -> Optional[Dict[str, Any]]:
        if override:
            for model in models:
                if self._model_id(model) == override:
                    return model
            logger.warning("Fund OS %s override model not found in live catalog: %s", provider, override)

        ranked = sorted(
            (model for model in models if self._score_model(model, provider=provider, kind=kind) != float("-inf")),
            key=lambda model: self._score_model(model, provider=provider, kind=kind),
            reverse=True,
        )
        return ranked[0] if ranked else None

    async def _fetch_model_catalog(self, *, provider: str, base_url: str, api_key: str) -> List[Dict[str, Any]]:
        if not api_key:
            return []

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{base_url}/models", headers=headers)
            response.raise_for_status()
            return self._normalize_model_list(response.json())

    async def refresh_provider_catalogs(self) -> Dict[str, List[Dict[str, Any]]]:
        catalogs: Dict[str, List[Dict[str, Any]]] = {}
        tasks = []
        if self.nim_api_key:
            tasks.append(("nvidia_nim", self.nim_base_url, self.nim_api_key))
        if self.openrouter_api_key:
            tasks.append(("openrouter", self.openrouter_base_url, self.openrouter_api_key))

        async def _load(provider: str, base_url: str, api_key: str) -> tuple[str, List[Dict[str, Any]]]:
            try:
                models = await self._fetch_model_catalog(provider=provider, base_url=base_url, api_key=api_key)
                return provider, models
            except Exception as exc:
                logger.warning("Fund OS provider catalog discovery failed for %s: %s", provider, exc)
                return provider, []

        results = await asyncio.gather(*[_load(provider, base_url, api_key) for provider, base_url, api_key in tasks]) if tasks else []
        for provider, models in results:
            catalogs[provider] = models
            self._catalog_cache[provider] = models
        return catalogs

    async def _resolve_model(self, *, kind: str) -> _ResolvedModel:
        if kind in self._resolved_models:
            return self._resolved_models[kind]

        if not self._catalog_cache:
            await self.refresh_provider_catalogs()

        nim_models = self._catalog_cache.get("nvidia_nim", [])
        openrouter_models = self._catalog_cache.get("openrouter", [])

        if self.nim_api_key and nim_models:
            override = self.nim_reasoning_override if kind == "reasoning" else self.nim_fast_override
            selected = self._select_model(nim_models, provider="nvidia_nim", kind=kind, override=override)
            if selected:
                resolved = _ResolvedModel(
                    provider="nvidia_nim",
                    base_url=self.nim_base_url,
                    api_key=self.nim_api_key,
                    model_id=self._model_id(selected),
                    model_info=selected,
                )
                self._resolved_models[kind] = resolved
                return resolved

        if self.openrouter_api_key and openrouter_models:
            override = self.openrouter_model_override
            selected = self._select_model(openrouter_models, provider="openrouter", kind=kind, override=override)
            if selected:
                resolved = _ResolvedModel(
                    provider="openrouter",
                    base_url=self.openrouter_base_url,
                    api_key=self.openrouter_api_key,
                    model_id=self._model_id(selected),
                    model_info=selected,
                )
                self._resolved_models[kind] = resolved
                return resolved

        if self.nim_api_key and not nim_models and self.openrouter_api_key and not openrouter_models:
            raise RuntimeError("No models returned by either NVIDIA NIM or OpenRouter live catalogs.")

        raise RuntimeError("No compatible model could be resolved from live provider catalogs.")

    def _headers_for_provider(self, provider: str, api_key: str) -> Dict[str, str]:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        if provider == "openrouter":
            headers["HTTP-Referer"] = "https://marketflux.local"
            headers["X-Title"] = "MarketFlux Fund OS"
        return headers

    async def complete(
        self,
        *,
        messages: List[Dict[str, str]],
        reasoning: bool = True,
        max_tokens: int = 1400,
        temperature: float = 0.2,
        request_purpose: str = "strategy_terminal",
        session_id: Optional[str] = None,
        owner_user_id: Optional[str] = None,
    ) -> str:
        selection = await self._resolve_model(kind="reasoning" if reasoning else "fast")
        headers = self._headers_for_provider(selection.provider, selection.api_key)
        payload = {
            "model": selection.model_id,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(f"{selection.base_url}/chat/completions", headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError("LLM response did not include choices.")
        message = choices[0].get("message") or {}
        content = message.get("content")
        if isinstance(content, list):
            parts = []
            for item in content:
                if item.get("type") == "text":
                    parts.append(item.get("text", ""))
            text = "".join(parts).strip()
        else:
            text = str(content or "").strip()

        usage_event = build_usage_event(
            provider=selection.provider,
            model_id=selection.model_id,
            request_purpose=request_purpose,
            payload=data,
            model_info=selection.model_info,
            session_id=session_id,
            owner_user_id=owner_user_id,
        )
        self.last_usage_event = usage_event
        self.usage_events.append(usage_event)
        logger.info("fundos.model_usage %s", json.dumps(usage_event, sort_keys=True, default=str))
        return text

    async def complete_json(
        self,
        *,
        messages: List[Dict[str, str]],
        reasoning: bool = True,
        max_tokens: int = 1400,
        temperature: float = 0.15,
        request_purpose: str = "strategy_terminal",
        session_id: Optional[str] = None,
        owner_user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        text = await self.complete(
            messages=messages,
            reasoning=reasoning,
            max_tokens=max_tokens,
            temperature=temperature,
            request_purpose=request_purpose,
            session_id=session_id,
            owner_user_id=owner_user_id,
        )
        if not text:
            return {"raw": "", "parse_error": "empty_response"}

        cleaned = text.strip()
        if "```" in cleaned:
            parts = cleaned.split("```")
            for part in parts:
                candidate = part.strip()
                if candidate.startswith("json"):
                    candidate = candidate[4:].strip()
                if candidate.startswith("{") and candidate.endswith("}"):
                    cleaned = candidate
                    break

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(cleaned[start : end + 1])
                except json.JSONDecodeError:
                    pass
            return {"raw": text, "parse_error": "invalid_json"}
