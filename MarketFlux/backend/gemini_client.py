"""Text and chat calls on the supported google-genai SDK.

Tool-calling loops in the copilot still build google.generativeai models,
because those loops depend on that SDK's function-call part objects. Every
get_gemini_model() caller (digests, screener, chat, memos) goes through here.
"""
from __future__ import annotations

import base64
import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

_client = None


class GeminiResponse:
    def __init__(self, text: str):
        self.text = text or ""


class GeminiChatSession:
    def __init__(self, chat: Any):
        self._chat = chat

    def send_message(self, message: str, stream: bool = False):
        if stream:
            return (
                GeminiResponse(getattr(chunk, "text", None) or "")
                for chunk in self._chat.send_message_stream(message)
            )
        response = self._chat.send_message(message)
        return GeminiResponse(getattr(response, "text", None) or "")


class GeminiChatModel:
    """Drop-in for the one-shot and chat methods callers already use."""

    def __init__(self, model_id: str, system_instruction: Optional[str] = None):
        self.model_id = model_id
        self.system_instruction = system_instruction

    def generate_content(self, contents: Any) -> GeminiResponse:
        client = get_client()
        response = client.models.generate_content(
            model=self.model_id,
            contents=_normalize_contents(contents),
            config=_config(self.system_instruction),
        )
        return GeminiResponse(getattr(response, "text", None) or "")

    def start_chat(self, history: Optional[list] = None) -> GeminiChatSession:
        client = get_client()
        kwargs: dict[str, Any] = {"model": self.model_id}
        config = _config(self.system_instruction)
        if config is not None:
            kwargs["config"] = config
        converted = _history(history)
        if converted:
            kwargs["history"] = converted
        return GeminiChatSession(client.chats.create(**kwargs))


def get_client():
    global _client
    if _client is not None:
        return _client
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")
    from google import genai

    _client = genai.Client(api_key=api_key)
    return _client


def _config(system_instruction: Optional[str]):
    if not system_instruction:
        return None
    from google.genai import types

    return types.GenerateContentConfig(system_instruction=system_instruction)


def _normalize_contents(contents: Any):
    if isinstance(contents, str):
        return contents
    if not isinstance(contents, list):
        return contents
    from google.genai import types

    parts = []
    for item in contents:
        if isinstance(item, str):
            parts.append(types.Part.from_text(text=item))
        elif isinstance(item, dict) and item.get("data") and item.get("mime_type"):
            raw = item["data"]
            data = base64.b64decode(raw) if isinstance(raw, str) else raw
            parts.append(types.Part.from_bytes(data=data, mime_type=item["mime_type"]))
        else:
            parts.append(item)
    return parts


def _history(history: Optional[list]):
    if not history:
        return None
    from google.genai import types

    contents = []
    for turn in history:
        role = turn.get("role") or "user"
        if role == "assistant":
            role = "model"
        texts = []
        for part in turn.get("parts") or []:
            if isinstance(part, str):
                texts.append(part)
            elif isinstance(part, dict) and part.get("text"):
                texts.append(part["text"])
        if not texts:
            continue
        contents.append(types.Content(role=role, parts=[types.Part.from_text(text="\n".join(texts))]))
    return contents or None
