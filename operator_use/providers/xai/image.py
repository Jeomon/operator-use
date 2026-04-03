"""xAI Grok Imagine image generation — OpenAI-compatible API."""

import os
from typing import Optional

from operator_use.providers.openai.image import ImageOpenAI

XAI_BASE_URL = "https://api.x.ai/v1"


class ImageXai(ImageOpenAI):
    """
    xAI Grok Imagine Image Generation provider.

    Uses the xAI OpenAI-compatible images/generations endpoint.

    Supported models:
    - "grok-imagine-image" (default, recommended)
    - "grok-imagine-image-pro" (higher quality)

    Args:
        model: The image model to use (default: "grok-imagine-image").
        size: Image dimensions (default: "auto").
        quality: Image quality (default: "auto").
            Note: xAI currently does not support quality/size/style parameters.
        style: Image style (default: "vivid").
            Note: xAI currently does not support style parameter.
        api_key: xAI API key. Falls back to XAI_API_KEY env variable.
        base_url: Optional base URL override. Falls back to XAI_API_BASE env variable.

    Example:
        ```python
        from operator_use.providers.xai import ImageXai

        provider = ImageXai()
        provider.generate("a red panda coding on a laptop", "output.png")
        ```
    """

    def __init__(
        self,
        model: str = "grok-imagine-image",
        size: str = "auto",
        quality: str = "auto",
        style: str = "vivid",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        super().__init__(
            model=model,
            size=size,
            quality=quality,
            style=style,
            api_key=api_key or os.environ.get("XAI_API_KEY"),
            base_url=base_url or os.environ.get("XAI_API_BASE") or XAI_BASE_URL,
        )

    def _build_generate_params(self, prompt: str, **kwargs) -> dict:
        """Build request parameters for xAI image generation.

        xAI image API only supports model + prompt (no quality/size/style yet).
        """
        return {
            "model": self._model,
            "prompt": prompt,
            "n": 1,
            "response_format": "b64_json",
        }
