"""Ollama Gemma client."""
import json
import logging
from typing import Optional
import requests
from config import get_settings

logger = logging.getLogger(__name__)


class OllamaClient:
    """Client for communicating with Ollama."""

    def __init__(self, host: Optional[str] = None, model: Optional[str] = None):
        """Initialize Ollama client."""
        settings = get_settings()
        self.host = host or settings.ollama_host
        self.model = model or settings.ollama_model
        self.endpoint = f"{self.host}/api/generate"

    def is_available(self) -> bool:
        """Check if Ollama is running and model is available."""
        try:
            response = requests.get(
                f"{self.host}/api/tags",
                timeout=5,
            )
            if response.status_code != 200:
                return False
            
            data = response.json()
            models = [m.get("name") for m in data.get("models", [])]
            return self.model in models
        except Exception as e:
            logger.error(f"Error checking Ollama availability: {e}")
            return False

    def generate(
        self,
        prompt: str,
        temperature: float = 0.0,
        timeout: int = 120,
    ) -> Optional[str]:
        """
        Generate response from Ollama.
        
        Args:
            prompt: Input prompt
            temperature: Temperature for generation (0 = deterministic)
            timeout: Request timeout in seconds
        
        Returns:
            Generated response or None on error
        """
        try:
            response = requests.post(
                self.endpoint,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "temperature": temperature,
                    "stream": False,
                },
                timeout=timeout,
            )
            
            if response.status_code != 200:
                logger.error(f"Ollama error {response.status_code}: {response.text}")
                return None
            
            data = response.json()
            return data.get("response", "").strip()
        
        except requests.exceptions.Timeout:
            logger.error(f"Ollama request timeout (>{timeout}s)")
            return None
        except Exception as e:
            logger.error(f"Error calling Ollama: {e}")
            return None

    def extract_json(
        self,
        prompt: str,
        temperature: float = 0.0,
        timeout: int = 120,
        max_retries: int = 1,
    ) -> Optional[dict]:
        """
        Generate JSON response from Ollama.
        
        Args:
            prompt: Input prompt
            temperature: Temperature for generation
            timeout: Request timeout
            max_retries: Max retries on malformed JSON
        
        Returns:
            Parsed JSON dict or None on error
        """
        for attempt in range(max_retries + 1):
            response = self.generate(prompt, temperature, timeout)
            
            if not response:
                return None
            
            try:
                # Try to extract JSON from response
                # Sometimes the model includes explanatory text
                if "```json" in response:
                    json_str = response.split("```json")[1].split("```")[0].strip()
                else:
                    json_str = response
                
                return json.loads(json_str)
            
            except json.JSONDecodeError as e:
                if attempt < max_retries:
                    logger.warning(f"Malformed JSON (attempt {attempt + 1}), retrying...")
                else:
                    logger.error(f"Failed to parse JSON: {e}")
                    logger.debug(f"Response: {response}")
                    return None
        
        return None
