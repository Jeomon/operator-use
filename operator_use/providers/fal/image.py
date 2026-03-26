import logging
import os
import urllib.request
from typing import Optional

from operator_use.providers.base import BaseImage

logger = logging.getLogger(__name__)


class ImageFal(BaseImage):
    """fal.ai image generation provider.

    Uses the fal-client SDK to run FLUX and other models on fal.ai infrastructure.
    Requires the `fal-client` package: pip install fal-client

    Args:
        model: The fal model ID to use (default: "fal-ai/flux/schnell").
            Popular options:
              "fal-ai/flux/schnell"       (fastest, 4 steps)
              "fal-ai/flux/dev"           (higher quality)
              "fal-ai/flux-pro"           (best quality, paid)
              "fal-ai/flux-pro/v1.1"      (latest pro)
              "fal-ai/flux-lora"          (LoRA support)
              "fal-ai/stable-diffusion-v3-medium"
        image_size: Output image size preset (default: "landscape_4_3").
            Options: "square_hd", "square", "portrait_4_3", "portrait_16_9",
                     "landscape_4_3", "landscape_16_9".
        num_inference_steps: Steps for generation (default: 4 for schnell).
        api_key: fal.ai API key. Falls back to FAL_KEY env variable.

    Example:
        ```python
        from operator_use.providers.fal import ImageFal

        provider = ImageFal(model="fal-ai/flux/schnell")
        provider.generate("a red panda coding on a laptop", "output.png")
        ```
    """

    def __init__(
        self,
        model: str = "fal-ai/flux/schnell",
        image_size: str = "landscape_4_3",
        num_inference_steps: int = 4,
        api_key: Optional[str] = None,
    ):
        self._model = model
        self.image_size = image_size
        self.num_inference_steps = num_inference_steps
        self.api_key = api_key or os.environ.get("FAL_KEY")
        if self.api_key:
            os.environ["FAL_KEY"] = self.api_key

    @property
    def model(self) -> str:
        return self._model

    def _build_arguments(self, prompt: str, **kwargs) -> dict:
        return {
            "prompt": prompt,
            "image_size": kwargs.get("image_size", self.image_size),
            "num_inference_steps": kwargs.get("num_inference_steps", self.num_inference_steps),
            "num_images": 1,
            "enable_safety_checker": True,
        }

    def generate(self, prompt: str, output_path: str, **kwargs) -> None:
        """Generate an image and save it to output_path.

        Args:
            prompt: Text description of the image to generate.
            output_path: Path where the image will be saved.
            **kwargs: Override image_size or num_inference_steps for this call.
        """
        try:
            import fal_client
        except ImportError:
            raise ImportError("fal-client is required: pip install fal-client")

        result = fal_client.run(self._model, arguments=self._build_arguments(prompt, **kwargs))
        url = result["images"][0]["url"]
        urllib.request.urlretrieve(url, output_path)
        logger.debug(f"[ImageFal] Image saved to {output_path}")

    async def agenerate(self, prompt: str, output_path: str, **kwargs) -> None:
        """Asynchronously generate an image and save it to output_path.

        Args:
            prompt: Text description of the image to generate.
            output_path: Path where the image will be saved.
            **kwargs: Override image_size or num_inference_steps for this call.
        """
        try:
            import fal_client
        except ImportError:
            raise ImportError("fal-client is required: pip install fal-client")

        import aiohttp as _aiohttp

        result = await fal_client.run_async(
            self._model, arguments=self._build_arguments(prompt, **kwargs)
        )
        url = result["images"][0]["url"]
        async with _aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                resp.raise_for_status()
                data = await resp.read()
        with open(output_path, "wb") as f:
            f.write(data)
        logger.debug(f"[ImageFal] Async image saved to {output_path}")
