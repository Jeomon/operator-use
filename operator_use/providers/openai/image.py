import base64
import logging
import os
from typing import Optional

import aiohttp
from openai import AsyncOpenAI, OpenAI

from operator_use.providers.base import BaseImage

logger = logging.getLogger(__name__)


class ImageOpenAI(BaseImage):
    """OpenAI Image Generation provider.

    Supports DALL-E 3, DALL-E 2, and gpt-image-1 via the OpenAI Images API.

    Args:
        model: The image model to use (default: "dall-e-3").
            Options: "dall-e-3", "dall-e-2", "gpt-image-1".
        size: Image dimensions (default: "1024x1024").
            DALL-E 3: "1024x1024", "1024x1792", "1792x1024".
            DALL-E 2: "256x256", "512x512", "1024x1024".
        quality: Image quality (default: "standard").
            DALL-E 3 / gpt-image-1: "standard", "hd".
        style: Image style for DALL-E 3 (default: "vivid").
            Options: "vivid", "natural".
        api_key: OpenAI API key. Falls back to OPENAI_API_KEY env variable.
        base_url: Optional base URL override. Falls back to OPENAI_BASE_URL env variable.

    Example:
        ```python
        from operator_use.providers.openai import ImageOpenAI

        provider = ImageOpenAI(model="dall-e-3", size="1024x1024", quality="hd")
        provider.generate("a red panda coding on a laptop", "output.png")
        ```
    """

    def __init__(
        self,
        model: str = "dall-e-3",
        size: str = "1024x1024",
        quality: str = "standard",
        style: str = "vivid",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self._model = model
        self.size = size
        self.quality = quality
        self.style = style
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.base_url = base_url or os.environ.get("OPENAI_BASE_URL")

        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        self.aclient = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)

    @property
    def model(self) -> str:
        return self._model

    def generate(self, prompt: str, output_path: str, **kwargs) -> None:
        """Generate an image and save it to output_path.

        Args:
            prompt: Text description of the image to generate.
            output_path: Path where the PNG image will be saved.
            **kwargs: Override size, quality, or style for this call.
        """
        params = dict(
            model=self._model,
            prompt=prompt,
            size=kwargs.get("size", self.size),
            quality=kwargs.get("quality", self.quality),
            n=1,
            response_format="b64_json",
        )
        if self._model == "dall-e-3":
            params["style"] = kwargs.get("style", self.style)

        response = self.client.images.generate(**params)
        image_data = base64.b64decode(response.data[0].b64_json)
        with open(output_path, "wb") as f:
            f.write(image_data)
        logger.debug(f"[ImageOpenAI] Image saved to {output_path}")

    async def agenerate(self, prompt: str, output_path: str, **kwargs) -> None:
        """Asynchronously generate an image and save it to output_path.

        Args:
            prompt: Text description of the image to generate.
            output_path: Path where the PNG image will be saved.
            **kwargs: Override size, quality, or style for this call.
        """
        params = dict(
            model=self._model,
            prompt=prompt,
            size=kwargs.get("size", self.size),
            quality=kwargs.get("quality", self.quality),
            n=1,
            response_format="b64_json",
        )
        if self._model == "dall-e-3":
            params["style"] = kwargs.get("style", self.style)

        response = await self.aclient.images.generate(**params)
        image_data = base64.b64decode(response.data[0].b64_json)
        with open(output_path, "wb") as f:
            f.write(image_data)
        logger.debug(f"[ImageOpenAI] Async image saved to {output_path}")
