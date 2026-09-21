"""Robust Gemini API client wrapper.

Handles the free tier gracefully: retries transient failures, offers a lite
model for lightweight work, and never leaks keys into logs.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Optional

from google import genai
from google.genai import types as genai_types

from app.core.config import get_settings

logger = logging.getLogger("legallens.ai")

_RESOURCE_EXHAUSTED = (429, 500, 503)
RETRY_BACKOFF_SECONDS = (1, 2, 4)


class GeminiUnavailableError(RuntimeError):
    """Raised when Gemini cannot be used (no key or persistent failure)."""


class GeminiClient:
    def __init__(self, model: Optional[str] = None, lite_model: Optional[str] = None):
        settings = get_settings()
        self.model = model or settings.gemini_model
        self.lite_model = lite_model or settings.gemini_lite_model
        self.api_key = settings.gemini_api_key
        self._client: Optional[genai.Client] = None

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def _get_client(self) -> genai.Client:
        if not self.available:
            raise GeminiUnavailableError("Gemini API key is not configured")
        if self._client is None:
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def generate_text(
        self,
        prompt: str,
        *,
        system_instruction: str | None = None,
        model: Optional[str] = None,
        max_output_tokens: int = 2048,
        temperature: float = 0.2,
        response_schema: Optional[Any] = None,
        retries: int = 2,
    ) -> str:
        """Generate text with bounded retries on transient errors."""
        client = self._get_client()
        model = model or self.model
        config_kwargs: dict[str, Any] = {
            "max_output_tokens": max_output_tokens,
            "temperature": temperature,
            # gemini-3.x models think by default. For grounded extraction we want
            # the final answer as text/JSON: disable thoughts (faster + cheaper).
            "thinking_config": genai_types.ThinkingConfig(include_thoughts=False),
        }
        if system_instruction:
            config_kwargs["system_instruction"] = system_instruction
        if response_schema is not None:
            config_kwargs["response_mime_type"] = "application/json"
            config_kwargs["response_schema"] = response_schema
        config = genai_types.GenerateContentConfig(**config_kwargs)

        attempt = 0
        while True:
            try:
                response = client.models.generate_content(
                    model=model, contents=prompt, config=config
                )
                return response.text or ""
            except GeminiUnavailableError:
                raise
            except Exception as exc:  # network, quota, malformed
                status = getattr(exc, "status_code", None)
                if status in _RESOURCE_EXHAUSTED or (status is None and attempt < retries):
                    if attempt >= retries:
                        raise
                    time.sleep(RETRY_BACKOFF_SECONDS[attempt])
                    attempt += 1
                    continue
                logger.warning("Gemini generate_text failed: %s", exc.__class__.__name__)
                raise

    def generate_structured(
        self,
        prompt: str,
        response_schema: Any,
        *,
        system_instruction: str | None = None,
        model: Optional[str] = None,
        max_output_tokens: int = 4096,
        temperature: float = 0.1,
    ) -> dict:
        """Ask Gemini for a structured JSON object matching `response_schema`.

        The schema is a plain dict so we stay provider-agnostic and easy to test.
        """
        text = self.generate_text(
            prompt,
            system_instruction=system_instruction,
            model=model,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
            response_schema=response_schema,
        )
        return parse_json_object(text)

    def generate_json_for(self, prompt: str, pydantic_model: type[Any], **kwargs) -> Any:
        """Generate a response and validate it against a Pydantic model."""
        schema = model_schema(pydantic_model)
        raw = self.generate_structured(prompt, schema, **kwargs)
        return pydantic_model.model_validate(raw)


def model_schema(model: type[Any]) -> dict:
    """Convert a Pydantic model to a Gemini-compatible JSON schema dict."""
    try:
        schema = model.model_json_schema()
    except Exception:
        schema = model.schema()
    return strip_json_schema(schema)


def strip_json_schema(schema: dict) -> dict:
    """Remove JSON-Schema keywords unsupported by Gemini's structured output."""
    drops = {"title", "default"}
    out: dict[str, Any] = {}
    for key, value in schema.items():
        if key in drops:
            continue
        if key == "properties" and isinstance(value, dict):
            out[key] = {k: strip_json_schema(v) for k, v in value.items()}
        elif key == "items" and isinstance(value, dict):
            out[key] = strip_json_schema(value)
        elif key == "allOf" and isinstance(value, list):
            for part in value:
                out.update(strip_json_schema(part))
        elif key == "$defs" and isinstance(value, dict):
            renamed = {k.replace(" ", "-"): strip_json_schema(v) for k, v in value.items()}
            out[key] = renamed
        else:
            out[key] = value
    return out


def parse_json_object(text: str) -> dict:
    """Extract and parse a JSON object from Gemini output, tolerating fences."""
    if not text:
        raise ValueError("empty LLM response")
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    start = text.find("{")
    if start == -1:
        raise ValueError("no JSON object found in LLM response")
    candidate = text[start:]
    try:
        result = json.loads(candidate)
    except json.JSONDecodeError:
        # Try to find a balanced closing brace region.
        depth = 0
        for i, ch in enumerate(candidate):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    result = json.loads(candidate[: i + 1])
                    break
        else:
            raise ValueError("malformed JSON in LLM response")
    if not isinstance(result, dict):
        raise ValueError("LLM response was not a JSON object")
    return result