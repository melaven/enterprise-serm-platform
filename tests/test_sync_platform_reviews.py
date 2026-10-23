import asyncio
from uuid import uuid4

import pytest

from app.services.worker.tasks import fetch_platform_reviews, fetch_reviews_task


@pytest.mark.parametrize(
    "task,args",
    [
        (fetch_reviews_task, ({}, uuid4(), "2gis", "https://public.example/reviews")),
        (fetch_platform_reviews, ({}, uuid4(), "google_business")),
    ],
)
def test_legacy_scraping_tasks_are_disabled(task, args) -> None:
    with pytest.raises(RuntimeError, match="disabled"):
        asyncio.run(task(*args))
