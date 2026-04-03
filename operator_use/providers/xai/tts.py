"""xAI Grok TTS provider via custom /v1/tts endpoint."""

import os
import logging
from typing import Optional

import httpx

from operator_use.providers.base import BaseTTS

XAI_BASE_URL = "https://api.x.ai/v1"
logger = logging.getLogger(__name__)


class TTSXai(BaseTTS):
    """
    xAI Grok Text-to-Speech provider.

    Uses the xAI TTS API endpoint for high-quality speech synthesis.

    Supported voices: eve (default), ara, rex, sal, leo.
    Supported languages: 20+ via BCP-47 codes (en, zh, pt-BR, etc.) or "auto".

    Args:
        model: The TTS model to use (default: "grok-tts").
        voice: The voice to use for synthesis (default: "eve").
            Options: eve, ara, rex, sal, leo.
        api_key: xAI API key. Falls back to XAI_API_KEY env variable.
        language: Language code for synthesis (default: "auto").
        response_format: Audio format for the output (default: "mp3").
        timeout: Request timeout in seconds.

    Example:
        ```python
        from operator_use.providers.xai import TTSXai

        tts = TTSXai(voice="ara")
        tts.synthesize("Hello from xAI!", "output.mp3")
        ```
    """

    VOICES = ("eve", "ara", "rex", "sal", "leo")

    def __init__(
        self,
        model: str = "grok-tts",
        voice: str = "eve",
        api_key: Optional[str] = None,
        language: str = "auto",
        response_format: str = "mp3",
        timeout: float = 120.0,
    ):
        self._model = model
        self.voice = voice
        self.language = language
        self.response_format = response_format
        self.api_key = api_key or os.environ.get("XAI_API_KEY") or ""
        self.timeout = timeout

    @property
    def model(self) -> str:
        return self._model

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _payload(self, text: str) -> dict:
        return {
            "text": text,
            "voice_id": self.voice,
            "language": self.language,
        }

    def synthesize(self, text: str, output_path: str) -> None:
        """Synthesize text into an audio file using the xAI TTS API.

        Args:
            text: The text to convert to speech.
            output_path: Path where the generated audio file will be saved.
        """
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                f"{XAI_BASE_URL}/tts",
                headers=self._headers(),
                json=self._payload(text),
            )
            response.raise_for_status()
            with open(output_path, "wb") as f:
                f.write(response.content)
        logger.debug(f"[TTSXai] Audio saved to {output_path}")

    async def asynthesize(self, text: str, output_path: str) -> None:
        """Asynchronously synthesize text into an audio file using the xAI TTS API.

        Args:
            text: The text to convert to speech.
            output_path: Path where the generated audio file will be saved.
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{XAI_BASE_URL}/tts",
                headers=self._headers(),
                json=self._payload(text),
            )
            response.raise_for_status()
            with open(output_path, "wb") as f:
                f.write(response.content)
        logger.debug(f"[TTSXai] Async audio saved to {output_path}")
