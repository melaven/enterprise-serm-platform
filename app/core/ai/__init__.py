"""AI-конвейер SentiGuard: генерация черновиков ответов на отзывы."""

from app.core.ai.errors import (
    LLMError,
    LLMOutputRejected,
    LLMPermanentError,
    LLMTransientError,
)
from app.core.ai.generator import AIResponseGenerator
from app.core.ai.providers import (
    AnthropicProvider,
    LLMProvider,
    OpenAICompatibleProvider,
    build_provider,
)
from app.core.ai.schemas import (
    DraftBatch,
    DraftVariant,
    GeneratedDraft,
    GenerationResult,
    GenerationSource,
    ReviewLike,
    ReviewSnapshot,
    TenantContext,
)

__all__ = [
    "AIResponseGenerator",
    "AnthropicProvider",
    "DraftBatch",
    "DraftVariant",
    "GeneratedDraft",
    "GenerationResult",
    "GenerationSource",
    "LLMError",
    "LLMOutputRejected",
    "LLMPermanentError",
    "LLMProvider",
    "LLMTransientError",
    "OpenAICompatibleProvider",
    "ReviewLike",
    "ReviewSnapshot",
    "TenantContext",
    "build_provider",
]
