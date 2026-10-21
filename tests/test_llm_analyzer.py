import asyncio
from typing import Any

import pytest
from pydantic import BaseModel

from app.services.llm_analyzer import GenerationResult, LLMReviewAnalyzer


class RecordingClient:
    model = "test"

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def generate_json(
        self, *, system_instruction: str, prompt: str, schema: type[BaseModel]
    ) -> GenerationResult:
        self.calls.append(
            {
                "system_instruction": system_instruction,
                "prompt": prompt,
                "schema": schema,
            }
        )
        return GenerationResult(json_text="{}", tokens_used=0)


def test_review_analyzer_fails_closed_before_sending_text() -> None:
    client = RecordingClient()

    with pytest.raises(RuntimeError, match="disabled"):
        asyncio.run(LLMReviewAnalyzer(client).analyze("private review text"))

    assert client.calls == []
