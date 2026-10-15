import json
import math
from collections import Counter
from pathlib import Path
from uuid import uuid4

from scripts.seed_db import _fake_embedding, generate_seed_data, write_mock_json


def test_generated_demo_data_is_stable_and_has_all_sentiments() -> None:
    tenant_id = uuid4()
    first = generate_seed_data(tenant_id)
    second = generate_seed_data(tenant_id)

    assert first == second
    assert len(first["platforms"]) == 3
    assert len(first["reviews"]) == 120
    assert len(first["platform_statistics"]) == 3
    assert len({review["id"] for review in first["reviews"]}) == 120
    assert Counter(review["sentiment"] for review in first["reviews"]) == {
        "POSITIVE": 45,
        "NEUTRAL": 30,
        "NEGATIVE": 45,
    }
    assert all(review["tenant_id"] == str(tenant_id) for review in first["reviews"])


def test_fake_embeddings_are_deterministic_nonzero_and_unit_length() -> None:
    first = _fake_embedding("demo review")
    second = _fake_embedding("demo review")

    assert first == second
    assert len(first) == 1536
    assert all(math.isfinite(value) for value in first)
    assert math.isclose(
        math.sqrt(sum(value * value for value in first)), 1.0, abs_tol=1e-8
    )


def test_frontend_json_is_written_as_utf8_json(tmp_path: Path) -> None:
    destination = tmp_path / "mock_reputation_data.json"
    data = generate_seed_data()

    write_mock_json(data, destination)

    assert json.loads(destination.read_text(encoding="utf-8")) == data
