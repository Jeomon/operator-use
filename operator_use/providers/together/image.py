import logging
import os
import urllib.request
from typing import Optional

from operator_use.providers.base import BaseImage

logger = logging.getLogger(__name__)

TOGETHER_BASE_URL = "https://api.together.xyz/v1"


class ImageTogether(BaseImage):
    """Together AI image generation provider.

    Uses the Together AI Images API (OpenAI-compatible) to generate images.
    Supports FLUX.1 and other open-weight models hosted on Together.

    Args:
        model: The model to use (default: "black-forest-labs/FLUX.1-schnell-Free").
            Popular options:
              "black-forest-labs/FLUX.1-schnell-Free"  (free tier)
              "black-forest-labs/FLUX.1-schnell"
              "black-forest-labs/FLUX.1-dev"
              "black-forest-labs/FLUX.1.1-pro"
              "stabilityai/stable-diffusion-xl-base-1.0"
        width: Image width in pixels (default: 1024).
        height: Image height in pixels (default: 1024).
        steps: Number of inference steps (default: 4 for schnell, 28+ for dev/pro).
        api_key: Together AI API key. Falls back to TOGETHER_API_KEY env variable.

    Example:
        ```python
        from operator_use.providers.together import ImageTogether

        provider = ImageTogether(model="black-forest-labs/FLUX.1-schnell-Free")
        provider.generate("a red panda coding on a laptop", "output.png")
        ```
    """

    def __init__(
        self,
        model: str = "black-forest-labs/FLUX.1-schnell-Free",
        width: int = 1024,
        height: int = 1024,
        steps: int = 4,
        api_key: Optional[str] = None,
    ):
        self._model = model
        self.width = width
        self.height = height
        self.steps = steps
        self.api_key = api_key or os.environ.get("TOGETHER_API_KEY")

    @property
    def model(self) -> str:
        return self._model

    def _make_clients(self):
        from openai import AsyncOpenAI, OpenAI
        client = OpenAI(api_key=self.api_key, base_url=TOGETHER_BASE_URL)
        aclient = AsyncOpenAI(api_key=self.api_key, base_url=TOGETHER_BASE_URL)
        return client, aclient

    def generate(self, prompt: str, output_path: str, **kwargs) -> None:
        """Generate an image and save it to output_path.

        Args:
            prompt: Text description of the image to generate.
            output_path: Path where the image will be saved.
            **kwargs: Override width, height, or steps for this call.
        """
        client, _ = self._make_clients()
        response = client.images.generate(
            model=self._model,
            prompt=prompt,
            n=1,
            extra_body={
                "width": kwargs.get("width", self.width),
                "height": kwargs.get("height", self.height),
                "steps": kwargs.get("steps", self.steps),
            },
        )
        url = response.data[0].url
        urllib.request.urlretrieve(url, output_path)
        logger.debug(f"[ImageTogether] Image saved to {output_path}")

    async def agenerate(self, prompt: str, output_path: str, **kwargs) -> None:
        """Asynchronously generate an image and save it to output_path.

        Args:
            prompt: Text description of the image to generate.
            output_path: Path where the image will be saved.
            **kwargs: Override width, height, or steps for this call.
        """
        import aiohttp as _aiohttp

        _, aclient = self._make_clients()
        response = await aclient.images.generate(
            model=self._model,
            prompt=prompt,
            n=1,
            extra_body={
                "width": kwargs.get("width", self.width),
                "height": kwargs.get("height", self.height),
                "steps": kwargs.get("steps", self.steps),
            },
        )
        url = response.data[0].url
        async with _aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                resp.raise_for_status()
                data = await resp.read()
        with open(output_path, "wb") as f:
            f.write(data)
        logger.debug(f"[ImageTogether] Async image saved to {output_path}")
