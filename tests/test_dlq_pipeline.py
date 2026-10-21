import pytest

from app.services.worker.analysis_tasks import process_reviews_batch


@pytest.mark.asyncio
async def test_background_review_text_analysis_fails_closed() -> None:
    with pytest.raises(RuntimeError, match="disabled"):
        await process_reviews_batch({}, "tenant", ["review"])
