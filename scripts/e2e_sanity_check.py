#!/usr/bin/env python3
"""Run the deterministic, database-free review privacy sanity check."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.anonymizer import anonymize_author_name  # noqa: E402
from app.core.review_privacy import safe_review_summary  # noqa: E402
from app.services.local_review_si import analyze_review_locally  # noqa: E402
from app.services.pii import PLACEHOLDER, contains_pii, redact_text  # noqa: E402

SAMPLE = "Мой телефон 89001234567, официант хамил"
EXPECTED_SANITIZED = f"Мой телефон {PLACEHOLDER}, официант хамил"
_OK, _BAD = "\033[32mPASS\033[0m", "\033[31mFAIL\033[0m"
failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    suffix = f" ({detail})" if detail and not condition else ""
    print(f"  [{_OK if condition else _BAD}] {name}{suffix}")
    if not condition:
        failures.append(name)


def main() -> int:
    print("\nPhase A: deterministic privacy and tenant-safe outputs (no database)")

    sanitized = redact_text(SAMPLE)
    check(
        "Phone number is deterministically removed",
        sanitized == EXPECTED_SANITIZED and not contains_pii(sanitized),
        repr(sanitized),
    )
    check(
        "Sanitization is idempotent",
        redact_text(sanitized) == sanitized,
    )

    analysis = analyze_review_locally(sanitized, rating=1)
    check(
        "Local analysis returns a valid threat level",
        1 <= analysis.threat_level <= 5,
        str(analysis.threat_level),
    )
    check(
        "Analysis outputs contain no personal data",
        all(
            not contains_pii(value)
            for value in (analysis.summary, analysis.reply_draft)
        )
        and "89001234567" not in analysis.summary
        and "89001234567" not in analysis.reply_draft,
    )
    check(
        "Author identity is replaced with a constant label",
        anonymize_author_name("Иван Петров", "author-123") == "Автор отзыва",
    )
    check(
        "Persisted review summary uses only allowlisted values",
        safe_review_summary(1, analysis.sentiment, "Jane Doe")
        == "Негативный отзыв; оценка 1/5.",
    )

    if failures:
        print(f"\nFAILED: {len(failures)} -> " + "; ".join(failures))
        return 1
    print("\nAll Phase A checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
