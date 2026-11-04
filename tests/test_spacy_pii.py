"""
Tests for SpaCy-based PII sanitization.

Tests NER-based entity detection and async event loop protection.
"""

import pytest
from app.core.spacy_pii import SpacyPIISanitizer, ENTITY_PLACEHOLDERS


@pytest.mark.asyncio
async def test_spacy_sanitizer_initialization():
    """Test that the SpaCy sanitizer can be initialized and shut down."""
    sanitizer = SpacyPIISanitizer(model_name="en_core_web_sm", max_workers=1)
    
    try:
        await sanitizer.initialize()
        assert sanitizer._initialized
        assert sanitizer.executor is not None
    finally:
        await sanitizer.shutdown()
        assert not sanitizer._initialized


@pytest.mark.asyncio
async def test_spacy_sanitize_empty_text():
    """Test sanitizing empty text."""
    sanitizer = SpacyPIISanitizer(model_name="en_core_web_sm", max_workers=1)
    
    try:
        await sanitizer.initialize()
        result, count = await sanitizer.sanitize("")
        assert result == ""
        assert count == 0
    finally:
        await sanitizer.shutdown()


@pytest.mark.asyncio
async def test_spacy_sanitize_no_pii():
    """Test sanitizing text without PII."""
    sanitizer = SpacyPIISanitizer(model_name="en_core_web_sm", max_workers=1)
    
    try:
        await sanitizer.initialize()
        text = "This is a simple review about good service."
        result, count = await sanitizer.sanitize(text)
        # Should not change text if no entities detected
        assert count == 0
    finally:
        await sanitizer.shutdown()


@pytest.mark.asyncio
async def test_spacy_sanitize_person():
    """Test sanitizing text with person names."""
    sanitizer = SpacyPIISanitizer(model_name="en_core_web_sm", max_workers=1)
    
    try:
        await sanitizer.initialize()
        text = "John Smith visited our restaurant yesterday."
        result, count = await sanitizer.sanitize(text)
        assert count > 0
        assert "[REDACTED_PERSON]" in result
        assert "John" not in result
        assert "Smith" not in result
    finally:
        await sanitizer.shutdown()


@pytest.mark.asyncio
async def test_spacy_sanitize_organization():
    """Test sanitizing text with organization names."""
    sanitizer = SpacyPIISanitizer(model_name="en_core_web_sm", max_workers=1)
    
    try:
        await sanitizer.initialize()
        text = "I work at Google Inc."
        result, count = await sanitizer.sanitize(text)
        assert count > 0
        assert "[REDACTED_ORG]" in result
    finally:
        await sanitizer.shutdown()


@pytest.mark.asyncio
async def test_spacy_sanitize_location():
    """Test sanitizing text with location names."""
    sanitizer = SpacyPIISanitizer(model_name="en_core_web_sm", max_workers=1)
    
    try:
        await sanitizer.initialize()
        text = "I visited Paris last summer."
        result, count = await sanitizer.sanitize(text)
        assert count > 0
        assert "[REDACTED_LOCATION]" in result
    finally:
        await sanitizer.shutdown()


@pytest.mark.asyncio
async def test_spacy_sanitize_text_convenience():
    """Test the convenience method that returns only sanitized text."""
    sanitizer = SpacyPIISanitizer(model_name="en_core_web_sm", max_workers=1)
    
    try:
        await sanitizer.initialize()
        text = "John called us from Moscow."
        result = await sanitizer.sanitize_text(text)
        assert isinstance(result, str)
        assert "[REDACTED_" in result
    finally:
        await sanitizer.shutdown()


@pytest.mark.asyncio
async def test_spacy_contains_pii():
    """Test the contains_pii method."""
    sanitizer = SpacyPIISanitizer(model_name="en_core_web_sm", max_workers=1)
    
    try:
        await sanitizer.initialize()
        
        # Text with PII
        text_with_pii = "My name is John Doe."
        assert await sanitizer.contains_pii(text_with_pii) is True
        
        # Text without PII
        text_without_pii = "The service was excellent."
        assert await sanitizer.contains_pii(text_without_pii) is False
    finally:
        await sanitizer.shutdown()


@pytest.mark.asyncio
async def test_spacy_error_not_initialized():
    """Test that error is raised when using uninitialized sanitizer."""
    sanitizer = SpacyPIISanitizer(model_name="en_core_web_sm", max_workers=1)
    
    with pytest.raises(RuntimeError, match="not initialized"):
        await sanitizer.sanitize("test text")


@pytest.mark.asyncio
async def test_event_loop_protection():
    """Test that the sanitizer doesn't block the event loop."""
    import asyncio
    
    sanitizer = SpacyPIISanitizer(model_name="en_core_web_sm", max_workers=1)
    
    try:
        await sanitizer.initialize()
        
        # Create a concurrent task that should not be blocked
        async def concurrent_task():
            await asyncio.sleep(0.1)
            return "concurrent completed"
        
        # Run sanitization and concurrent task in parallel
        text = "John Smith works at Apple in California."
        results = await asyncio.gather(
            sanitizer.sanitize(text),
            concurrent_task(),
        )
        
        sanitized_text, count = results[0]
        concurrent_result = results[1]
        
        assert count > 0
        assert concurrent_result == "concurrent completed"
        # If the event loop was blocked, the concurrent task would fail
    finally:
        await sanitizer.shutdown()
