"""
PII Sanitizer Service — Production-ready NER-based PII masking

This service uses spaCy NER to detect and mask Personally Identifiable Information
in review text. Heavy CPU-bound spaCy processing is offloaded to a ProcessPoolExecutor
to prevent blocking the FastAPI async event loop.

Architecture:
- ProcessPoolExecutor: Isolates CPU-bound NER work in separate processes
- Singleton pattern: Ensures single model instance per application
- Async interface: Non-blocking via asyncio.run_in_executor
- Graceful shutdown: Proper executor cleanup on application shutdown

Usage:
    sanitizer = PIISanitizer.get_instance()
    masked_text = await sanitizer.sanitize_async(original_text)
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ProcessPoolExecutor
from functools import partial
from typing import Final

import spacy
from spacy.language import Language

# ============================================================================
# Module-level function for ProcessPoolExecutor (must be picklable)
# ============================================================================

_MODEL_NAME: Final[str] = "ru_core_news_sm"
_MASK_NAME: Final[str] = "[ИМЯ СКРЫТО]"
_MASK_LOCATION: Final[str] = "[ЛОКАЦИЯ СКРЫТА]"


def _load_spacy_model() -> Language:
    """
    Load spaCy model in the worker process.
    This function runs in each worker process separately.
    """
    try:
        return spacy.load(_MODEL_NAME)
    except OSError:
        # Fallback: download model if not present
        from spacy.cli import download

        download(_MODEL_NAME)
        return spacy.load(_MODEL_NAME)


def _sanitize_text_sync(text: str, nlp: Language) -> str:
    """
    Synchronous function to sanitize text using spaCy NER.
    This runs in a separate process to avoid blocking the event loop.

    Args:
        text: Input text to sanitize
        nlp: Loaded spaCy Language model

    Returns:
        Sanitized text with PII masked
    """
    if not text or not text.strip():
        return text

    doc = nlp(text)
    sanitized_text = text

    # Process entities in reverse order to preserve string indices
    for ent in reversed(doc.ents):
        if ent.label_ == "PER":
            sanitized_text = (
                sanitized_text[: ent.start_char]
                + _MASK_NAME
                + sanitized_text[ent.end_char :]
            )
        elif ent.label_ == "LOC":
            sanitized_text = (
                sanitized_text[: ent.start_char]
                + _MASK_LOCATION
                + sanitized_text[ent.end_char :]
            )

    return sanitized_text


# ============================================================================
# Singleton Service Class
# ============================================================================


class PIISanitizer:
    """
    Singleton service for PII sanitization using spaCy NER.

    Features:
    - ProcessPoolExecutor for CPU-bound NER processing
    - Async interface via run_in_executor
    - Lazy model loading
    - Graceful shutdown support

    Example:
        sanitizer = PIISanitizer.get_instance()
        masked = await sanitizer.sanitize_async("Иван из Москвы")
        # Returns: "[ИМЯ СКРЫТО] из [ЛОКАЦИЯ СКРЫТА]"
    """

    _instance: PIISanitizer | None = None
    _lock: asyncio.Lock = asyncio.Lock()

    def __init__(self) -> None:
        """Initialize the sanitizer (use get_instance() instead)."""
        self._executor: ProcessPoolExecutor | None = None
        self._model_loaded: bool = False
        self._nlp: Language | None = None

    @classmethod
    async def get_instance(cls) -> PIISanitizer:
        """
        Get or create the singleton instance.
        Thread-safe via asyncio.Lock.
        """
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
                    await cls._instance._initialize()
        return cls._instance

    async def _initialize(self) -> None:
        """
        Initialize the ProcessPoolExecutor and load spaCy model.
        Runs once per application lifetime.
        """
        if self._executor is not None:
            return

        # Create process pool (one worker per CPU core)
        self._executor = ProcessPoolExecutor(max_workers=1)

        # Load model in main process for initialization validation
        # Note: Each worker will load its own copy
        try:
            self._nlp = await asyncio.get_running_loop().run_in_executor(
                self._executor, _load_spacy_model
            )
            self._model_loaded = True
        except Exception as e:
            if self._executor:
                self._executor.shutdown(wait=True)
                self._executor = None
            raise RuntimeError(f"Failed to load spaCy model: {e}") from e

    async def sanitize_async(self, text: str) -> str:
        """
        Asynchronously sanitize text by masking PII entities.

        Offloads CPU-bound NER processing to ProcessPoolExecutor
        to prevent blocking the FastAPI event loop.

        Args:
            text: Input text to sanitize

        Returns:
            Sanitized text with PII masked

        Raises:
            RuntimeError: If sanitizer is not initialized
        """
        if self._executor is None or not self._model_loaded:
            raise RuntimeError(
                "PIISanitizer is not initialized. Call get_instance() first."
            )

        if not text or not text.strip():
            return text

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self._executor, partial(_sanitize_text_sync, text, self._nlp)
        )

    async def shutdown(self) -> None:
        """
        Gracefully shutdown the ProcessPoolExecutor.
        Call this during application shutdown (FastAPI lifespan).
        """
        if self._executor is not None:
            self._executor.shutdown(wait=True)
            self._executor = None
            self._model_loaded = False
            self._nlp = None

    @classmethod
    async def reset(cls) -> None:
        """
        Reset the singleton instance (useful for testing).
        """
        if cls._instance is not None:
            await cls._instance.shutdown()
            cls._instance = None


# ============================================================================
# Convenience Functions
# ============================================================================


async def sanitize_text(text: str) -> str:
    """
    Convenience function to sanitize text using the singleton sanitizer.

    Example:
        masked = await sanitize_text("Иван из Москвы")
    """
    sanitizer = await PIISanitizer.get_instance()
    return await sanitizer.sanitize_async(text)
