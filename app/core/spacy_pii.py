"""
SpaCy-based PII Sanitizer using Named Entity Recognition (NER).

Replaces regex-based sanitization with NLP-based entity detection for better accuracy.
Handles PERSON, ORG, LOC, PHONE, EMAIL, and other PII entities.

CRITICAL: SpaCy is CPU-bound and synchronous. All NER operations are offloaded
to a ProcessPoolExecutor to prevent blocking the FastAPI event loop.
"""

import asyncio
import logging
from concurrent.futures import ProcessPoolExecutor
from functools import partial
from typing import Final

import spacy
from spacy.language import Language

logger = logging.getLogger(__name__)

# Entity label to placeholder mapping
ENTITY_PLACEHOLDERS: Final[dict[str, str]] = {
    "PERSON": "[REDACTED_PERSON]",
    "ORG": "[REDACTED_ORG]",
    "GPE": "[REDACTED_LOCATION]",  # Geopolitical Entity (countries, cities)
    "LOC": "[REDACTED_LOCATION]",  # Location (mountains, rivers, etc.)
    "EMAIL": "[REDACTED_EMAIL]",
    "PHONE": "[REDACTED_PHONE]",
    "CARDINAL": "[REDACTED_NUMBER]",  # Numbers (use carefully)
    "DATE": "[REDACTED_DATE]",
    "URL": "[REDACTED_URL]",
    "PER": "[REDACTED_PERSON]",  # Named person
    "NORP": "[REDACTED_NORP]",  # Nationalities, religious, political groups
}


def _load_spacy_model(model_name: str) -> Language:
    """
    Load SpaCy model. Called in worker process to avoid GIL contention.

    This function runs in a separate process to ensure thread safety and
    avoid the Global Interpreter Lock (GIL) blocking async operations.
    """
    try:
        return spacy.load(model_name)
    except OSError:
        # Model not found, download it
        import subprocess
        import sys

        logger.warning(f"SpaCy model '{model_name}' not found, downloading...")
        subprocess.check_call(
            [sys.executable, "-m", "spacy", "download", model_name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return spacy.load(model_name)


def _sanitize_text_sync(text: str, model_name: str) -> tuple[str, int]:
    """
    Synchronous PII sanitization using SpaCy NER.

    This function runs in a separate process and is NOT async-safe.
    Must be called via ProcessPoolExecutor.

    Args:
        text: Input text to sanitize
        model_name: SpaCy model name (e.g., 'ru_core_news_sm', 'en_core_web_sm')

    Returns:
        Tuple of (sanitized_text, number_of_replacements)
    """
    # Load model (cached in process)
    if not hasattr(_sanitize_text_sync, "_model"):
        _sanitize_text_sync._model = _load_spacy_model(model_name)  # type: ignore

    nlp = _sanitize_text_sync._model  # type: ignore
    doc = nlp(text)

    # Collect replacements in reverse order to preserve indices
    replacements = []
    for ent in reversed(doc.ents):
        if ent.label_ in ENTITY_PLACEHOLDERS:
            replacements.append(
                (ent.start_char, ent.end_char, ENTITY_PLACEHOLDERS[ent.label_])
            )

    # Apply replacements
    if not replacements:
        return text, 0

    # Build sanitized text
    text_list = list(text)
    for start, end, placeholder in replacements:
        text_list[start:end] = list(placeholder)

    sanitized = "".join(text_list)
    return sanitized, len(replacements)


class SpacyPIISanitizer:
    """
    Async wrapper for SpaCy-based PII sanitization.

    Manages ProcessPoolExecutor and provides async interface for NER operations.
    Protects the FastAPI event loop by offloading CPU-bound SpaCy work to separate processes.
    """

    def __init__(
        self,
        model_name: str = "ru_core_news_sm",
        max_workers: int = 2,
    ):
        """
        Initialize the SpaCy PII sanitizer.

        Args:
            model_name: SpaCy model to use (ru_core_news_sm for Russian, en_core_web_sm for English)
            max_workers: Number of worker processes for parallel NER processing
        """
        self.model_name = model_name
        self.max_workers = max_workers
        self.executor: ProcessPoolExecutor | None = None
        self._initialized = False

    async def initialize(self) -> None:
        """
        Initialize the ProcessPoolExecutor.

        Should be called in FastAPI lifespan context manager.
        Loads the SpaCy model in each worker process to minimize cold start latency.
        """
        if self._initialized:
            return

        self.executor = ProcessPoolExecutor(max_workers=self.max_workers)

        # Warm up by loading the model in one worker
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                self.executor, partial(_load_spacy_model, self.model_name)
            )
            logger.info(
                "SpaCy PII sanitizer initialized (model=%s, workers=%s)",
                self.model_name,
                self.max_workers,
            )
        except Exception as e:
            logger.error("Failed to initialize SpaCy PII sanitizer: %s", e)
            raise

        self._initialized = True

    async def shutdown(self) -> None:
        """
        Shutdown the ProcessPoolExecutor.

        Should be called in FastAPI lifespan context manager cleanup.
        """
        if self.executor:
            self.executor.shutdown(wait=True)
            self.executor = None
            self._initialized = False
            logger.info("SpaCy PII sanitizer shutdown complete")

    async def sanitize(self, text: str) -> tuple[str, int]:
        """
        Sanitize text by replacing PII entities with placeholders.

        This is an async wrapper that offloads the CPU-bound SpaCy NER work
        to a ProcessPoolExecutor, preventing event loop blocking.

        Args:
            text: Input text to sanitize

        Returns:
            Tuple of (sanitized_text, number_of_replacements)

        Raises:
            RuntimeError: If sanitizer not initialized
        """
        if not self._initialized or self.executor is None:
            raise RuntimeError(
                "SpaCy PII sanitizer not initialized. Call initialize() first."
            )

        if not text or not text.strip():
            return "", 0

        # Offload to ProcessPoolExecutor to avoid blocking event loop
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            self.executor, partial(_sanitize_text_sync, text, self.model_name)
        )

        return result

    async def sanitize_text(self, text: str) -> str:
        """
        Convenience method that returns only the sanitized text.

        Args:
            text: Input text to sanitize

        Returns:
            Sanitized text
        """
        sanitized, _ = await self.sanitize(text)
        return sanitized

    async def contains_pii(self, text: str) -> bool:
        """
        Check if text contains PII entities.

        Args:
            text: Input text to check

        Returns:
            True if PII entities are detected, False otherwise
        """
        if not text or not text.strip():
            return False

        sanitized, count = await self.sanitize(text)
        return count > 0


# Global instance for FastAPI app state
_default_sanitizer: SpacyPIISanitizer | None = None


def get_spacy_sanitizer() -> SpacyPIISanitizer:
    """
    Get the global SpaCy PII sanitizer instance.

    The instance should be initialized in FastAPI lifespan:
        from app.core.spacy_pii import get_spacy_sanitizer
        sanitizer = get_spacy_sanitizer()
        await sanitizer.initialize()

    Returns:
        Global SpacyPIISanitizer instance
    """
    global _default_sanitizer
    if _default_sanitizer is None:
        _default_sanitizer = SpacyPIISanitizer()
    return _default_sanitizer
