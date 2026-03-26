import asyncio
import logging
import os
from typing import Optional

from operator_use.providers.base import BaseImage

logger = logging.getLogger(__name__)


class ImageGoogle(BaseImage):
    """Google Imagen image generation provider.

    Uses the Google GenAI SDK (Imagen 3) to generate images from text prompts.

    Args:
        model: The Imagen model to use (default: "imagen-3.0-generate-002").
        api_key: Google API key. Falls back to GEMINI_API_KEY env variable.
        negative_prompt: Optional description of what to exclude from the image.

    Example:
        ```python
        from operator_use.providers.google import ImageGoogle

        provider = ImageGoogle()
        provider.generate("a red panda coding on a laptop", "output.png")
        ```
    """

    def __init__(
        self,
        model: str = "imagen-3.0-generate-002",
        api_key: Optional[str] = None,
        negative_prompt: Optional[str] = None,
    ):
        self._model = model
        self.negative_prompt = negative_prompt
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")

    @property
    def model(self) -> str:
        return self._model

    def _make_client(self):
        from google import genai
        return genai.Client(api_key=self.api_key)

    def generate(self, prompt: str, output_path: str, **kwargs) -> None:
        """Generate an image and save it to output_path.

        Args:
            prompt: Text description of the image to generate.
            output_path: Path where the PNG image will be saved.
            **kwargs: Override negative_prompt for this call.
        """
        from google import genai

        client = self._make_client()
        config = genai.types.GenerateImagesConfig(
            number_of_images=1,
            output_mime_type="image/png",
            negative_prompt=kwargs.get("negative_prompt", self.negative_prompt),
        )
        response = client.models.generate_images(
            model=self._model,
            prompt=prompt,
            config=config,
        )
        image_data = response.generated_images[0].image.image_data
        with open(output_path, "wb") as f:
            f.write(image_data)
        logger.debug(f"[ImageGoogle] Image saved to {output_path}")

    async def agenerate(self, prompt: str, output_path: str, **kwargs) -> None:
        """Asynchronously generate an image and save it to output_path.

        Args:
            prompt: Text description of the image to generate.
            output_path: Path where the PNG image will be saved.
            **kwargs: Override negative_prompt for this call.
        """
        await asyncio.to_thread(self.generate, prompt, output_path, **kwargs)
