"""Ollama Gemma client using the official Ollama Python package."""
from __future__ import annotations

import json
import logging
from typing import Optional

import ollama

from config import get_settings

logger = logging.getLogger(__name__)


class OllamaClientError(Exception):
    """Raised when Ollama is unavailable or model cannot be used."""


class OllamaClient:
    """Client for communicating with a local Ollama server."""

    def __init__(self, host: Optional[str] = None, model: Optional[str] = None):
        settings = get_settings()
        self.host = host or settings.ollama_host
        self.model = model or settings.ollama_model
        self.client = ollama.Client(host=self.host)

    def list_models(self) -> list[str]:
        """Return installed model names."""
        response = self.client.list()
        return [model.model for model in response.models]

    def is_available(self) -> bool:
        """Check if Ollama is running and the configured model is installed."""
        try:
            return self.model in self.list_models()
        except Exception as exc:
            logger.error("Error checking Ollama availability: %s", exc)
            return False

    def ensure_available(self) -> None:
        """Raise a clear error if Ollama or the model is unavailable."""
        try:
            models = self.list_models()
        except Exception as exc:
            raise OllamaClientError(
                f"Cannot reach Ollama at {self.host}. Start it with: ollama serve"
            ) from exc

        if self.model not in models:
            raise OllamaClientError(
                f"Model '{self.model}' is not installed. Run: ollama pull {self.model}"
            )

    def generate(
        self,
        prompt: str,
        temperature: float = 0.0,
        timeout: int = 120,
        json_format: bool = False,
        images: Optional[list] = None,
    ) -> Optional[str]:
        """Generate a response from the local model, optionally with image input."""
        try:
            kwargs = {
                "model": self.model,
                "prompt": prompt,
                "options": {"temperature": temperature},
            }
            if json_format:
                kwargs["format"] = "json"
            if images:
                kwargs["images"] = images

            response = self.client.generate(**kwargs)
            return (response.get("response") or "").strip()
        except Exception as exc:
            logger.error("Error calling Ollama: %s", exc)
            return None

    def extract_json(
        self,
        prompt: str,
        temperature: float = 0.0,
        timeout: int = 120,
        max_retries: int = 1,
        images: Optional[list] = None,
    ) -> Optional[dict]:
        """Generate and parse JSON from Ollama with one retry on malformed output."""
        for attempt in range(max_retries + 1):
            response = self.generate(
                prompt,
                temperature=temperature,
                timeout=timeout,
                json_format=True,
                images=images,
            )
            if not response:
                return None

            try:
                if "```json" in response:
                    json_str = response.split("```json")[1].split("```")[0].strip()
                else:
                    json_str = response
                return json.loads(json_str)
            except json.JSONDecodeError as exc:
                if attempt < max_retries:
                    logger.warning("Malformed JSON (attempt %s), retrying...", attempt + 1)
                else:
                    logger.error("Failed to parse JSON: %s", exc)
                    logger.debug("Response: %s", response)
                    return None
        return None
