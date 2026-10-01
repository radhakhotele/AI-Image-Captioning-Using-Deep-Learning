"""Thread-safe, lazy-loading Hugging Face ViT-GPT2 caption generation."""

import threading
from typing import Any

from PIL import Image


class CaptionGenerationError(RuntimeError):
    """Raised when the model cannot be loaded or generate a caption."""


class CaptionGenerator:
    """Load the pretrained model once and serialize resource-heavy inference."""

    def __init__(self, model_id: str):
        self.model_id = model_id
        self._load_lock = threading.Lock()
        self._inference_lock = threading.Lock()
        self._torch: Any = None
        self._processor: Any = None
        self._tokenizer: Any = None
        self._model: Any = None
        self._device: Any = None

    def _ensure_loaded(self) -> None:
        """Import ML packages and load weights on the first caption request."""
        if self._model is not None:
            return

        with self._load_lock:
            if self._model is not None:
                return

            try:
                import torch
                from transformers import (
                    AutoImageProcessor,
                    AutoTokenizer,
                    VisionEncoderDecoderModel,
                )

                device = torch.device(
                    "cuda" if torch.cuda.is_available() else "cpu"
                )
                processor = AutoImageProcessor.from_pretrained(
                    self.model_id, use_fast=False
                )
                tokenizer = AutoTokenizer.from_pretrained(self.model_id)
                model = VisionEncoderDecoderModel.from_pretrained(self.model_id)
                model.to(device)
                model.eval()

                self._torch = torch
                self._processor = processor
                self._tokenizer = tokenizer
                self._model = model
                self._device = device
            except Exception as exc:
                raise CaptionGenerationError(
                    "The caption model could not be loaded. Check model access "
                    "and available memory, then try again."
                ) from exc

    def generate(self, image: Image.Image) -> str:
        """Generate a concise caption for a validated Pillow image."""
        with self._inference_lock:
            self._ensure_loaded()
            try:
                image_rgb = image.convert("RGB")
                inputs = self._processor(images=image_rgb, return_tensors="pt")
                pixel_values = inputs.pixel_values.to(self._device)

                with self._torch.inference_mode():
                    output_ids = self._model.generate(
                        pixel_values,
                        max_length=32,
                        num_beams=4,
                        no_repeat_ngram_size=2,
                        early_stopping=True,
                    )

                caption = self._tokenizer.batch_decode(
                    output_ids, skip_special_tokens=True
                )[0].strip()
                if not caption:
                    raise CaptionGenerationError(
                        "The model returned an empty caption. Please try another image."
                    )
                return " ".join(caption.split())
            except CaptionGenerationError:
                raise
            except Exception as exc:
                raise CaptionGenerationError(
                    "The caption model could not process this image. Please try "
                    "another image."
                ) from exc


_generator_lock = threading.Lock()
_generator: CaptionGenerator | None = None


def generate_caption(image: Image.Image, model_id: str | None = None) -> str:
    """Use one lazily initialized process-wide model instance."""
    global _generator

    selected_model = model_id or "nlpconnect/vit-gpt2-image-captioning"
    if _generator is None or _generator.model_id != selected_model:
        with _generator_lock:
            if _generator is None or _generator.model_id != selected_model:
                _generator = CaptionGenerator(selected_model)
    return _generator.generate(image)