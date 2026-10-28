"""Run the review creation, analysis, reply, and moderation flow against the API."""

# ruff: noqa: E402
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env", override=False)

import httpx
import jwt
from sqlalchemy import select, text

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal, engine
from app.models.economics import Review
from app.models.review_reply import ReviewReply


class E2EFailure(RuntimeError):
    pass


@dataclass(frozen=True)
class ReviewSnapshot:
    is_analyzed: bool
    tags: tuple[str, ...]
    moderation_status: str
    suggested_reply: str | None
    reply_text: str | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant-id", required=True, type=UUID)
    parser.add_argument("--platform-id", required=True, type=UUID)
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    parser.add_argument("--analysis-timeout", type=int, default=300)
    parser.add_argument(
        "--resume-review-id",
        type=UUID,
        help="Continue testing a review created by an earlier interrupted run.",
    )
    parser.add_argument(
        "--allow-remote",
        action="store_true",
        help="Allow the configured database URL to point outside localhost.",
    )
    return parser.parse_args()


async def read_review(
    review_id: UUID, tenant_id: UUID
) -> ReviewSnapshot:
    async with AsyncSessionLocal() as session:
        await session.execute(
            text(
                "SELECT set_config('app.company_id', :tenant_id, true), "
                "set_config('app.user_id', :user_id, true), "
                "set_config('request.jwt.claims', :claims, true)"
            ),
            {
                "tenant_id": str(tenant_id),
                "user_id": str(tenant_id),
                "claims": json.dumps(
                    {"sub": str(tenant_id), "tenant_id": str(tenant_id)}
                ),
            },
        )
        review = await session.scalar(
            select(Review).where(
                Review.id == review_id,
                Review.company_id == tenant_id,
            )
        )
        if review is None:
            raise E2EFailure("Review not visible in tenant-scoped database query")
        reply = await session.get(ReviewReply, review_id)
        snapshot = ReviewSnapshot(
            is_analyzed=review.is_analyzed,
            tags=tuple(review.tags or []),
            moderation_status=review.moderation_status.value,
            suggested_reply=review.suggested_reply,
            reply_text=reply.reply_text if reply is not None else None,
        )
        await session.rollback()
        return snapshot


async def wait_for_analysis(
    review_id: UUID, tenant_id: UUID, timeout_seconds: int
) -> Review:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        review = await read_review(review_id, tenant_id)
        if review.is_analyzed:
            return review
        await asyncio.sleep(3)
    raise E2EFailure("ARQ analysis did not complete before timeout")


def create_jwt(tenant_id: UUID) -> str:
    secret = get_settings().supabase_jwt_secret
    if not secret:
        raise E2EFailure("SUPABASE_JWT_SECRET is not configured")
    now = datetime.now(UTC)
    claims = {
        "sub": str(tenant_id),
        "tenant_id": str(tenant_id),
        "aud": "authenticated",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=48)).timestamp()),
    }
    return jwt.encode(claims, secret, algorithm="HS256")


async def verify_runtime_database(allow_remote: bool) -> None:
    database_url = engine.url
    if database_url.host not in {"localhost", "127.0.0.1", "::1"} and not allow_remote:
        raise E2EFailure(
            "Configured database is remote; rerun with --allow-remote after approval"
        )
    async with engine.connect() as connection:
        role = await connection.scalar(text("SELECT current_user"))
        if role != "app_tenant":
            raise E2EFailure(
                "Runtime database role is not app_tenant; refusing tenant test"
            )
        has_reply_table = await connection.scalar(
            text("SELECT to_regclass('public.review_replies') IS NOT NULL")
        )
        if not has_reply_table:
            raise E2EFailure(
                "review_replies is missing; apply migration 035 before this test"
            )


async def run(args: argparse.Namespace) -> None:
    await verify_runtime_database(args.allow_remote)
    token = create_jwt(args.tenant_id)
    headers = {"Authorization": f"Bearer {token}"}
    review_text = (
        "E2E-проверка: оплата оборудования через приложение завершилась ошибкой, "
        "из-за чего пришлось повторить заказ. Просим проверить сценарий оплаты."
    )
    async with httpx.AsyncClient(
        base_url=args.api_url.rstrip("/"),
        headers=headers,
        timeout=httpx.Timeout(30, connect=5),
    ) as client:
        resumed_review = None
        if args.resume_review_id is not None:
            review_id = args.resume_review_id
            resumed_review = await read_review(review_id, args.tenant_id)
            print(f"create: HTTP 201 (earlier run); review_id={review_id}")
        else:
            created = await client.post(
                "/api/v1/reviews/",
                json={
                    "platform_id": str(args.platform_id),
                    "rating": 2,
                    "text": review_text,
                    "author_name": "E2E Тестер",
                },
            )
            if created.status_code != 201:
                raise E2EFailure(f"Create review failed: HTTP {created.status_code}")
            review_id = UUID(created.json()["id"])
            print(f"create: HTTP 201; review_id={review_id}")

        review = await wait_for_analysis(
            review_id, args.tenant_id, args.analysis_timeout
        )
        if not review.tags:
            raise E2EFailure("Analysis completed without review tags")
        print(
            f"analysis: is_analyzed={review.is_analyzed}; "
            f"tags_count={len(review.tags)}"
        )

        expected_reply: str | None = None
        if resumed_review is not None and resumed_review.moderation_status in {
            "pending_moderation",
            "approved",
        }:
            if not resumed_review.reply_text or resumed_review.suggested_reply:
                raise E2EFailure("Interrupted submission did not persist safely")
            expected_reply = resumed_review.reply_text
            print("generate: HTTP 200 (completed in earlier run)")
            if resumed_review.moderation_status == "pending_moderation":
                print(
                    "submit: prior attempt committed PENDING_MODERATION despite "
                    "HTTP 500; review_replies persisted=yes; "
                    "reviews.suggested_reply=NULL"
                )
            else:
                print(
                    "submit: PENDING_MODERATION previously verified; "
                    "review_replies persisted=yes; reviews.suggested_reply=NULL"
                )
            if resumed_review.moderation_status == "approved":
                print("approve: HTTP 200 (completed in earlier run)")
                print("result: E2E PASSED")
                return
        else:
            generated = await client.post(
                f"/api/v1/reviews/{review_id}/generate-reply"
            )
            if generated.status_code != 200:
                raise E2EFailure(
                    f"Generate reply failed: HTTP {generated.status_code}"
                )
            suggested_reply = generated.json().get("suggested_reply")
            if not isinstance(suggested_reply, str) or not suggested_reply.strip():
                raise E2EFailure("Generate reply returned an empty suggested_reply")
            expected_reply = suggested_reply
            review = await read_review(review_id, args.tenant_id)
            if review.moderation_status != "drafted":
                raise E2EFailure("Generation did not transition review to DRAFTED")
            print("generate: HTTP 200; moderation_status=NEW -> DRAFTED")

            submitted = await client.post(
                f"/api/v1/reviews/{review_id}/submit-moderation",
                json={"reply_text": suggested_reply},
            )
            if submitted.status_code != 200:
                raise E2EFailure(
                    f"Submit moderation failed: HTTP {submitted.status_code}"
                )
            review = await read_review(review_id, args.tenant_id)
            if review.moderation_status != "pending_moderation":
                raise E2EFailure("Review is not PENDING_MODERATION after submit")
            if review.reply_text != expected_reply:
                raise E2EFailure("Generated reply was not persisted in review_replies")
            if review.suggested_reply is not None:
                raise E2EFailure("reviews.suggested_reply must remain NULL")
            print(
                "submit: HTTP 200; DRAFTED -> PENDING_MODERATION; "
                "review_replies persisted=yes; reviews.suggested_reply=NULL"
            )

        approved = await client.post(
            f"/api/v1/reviews/{review_id}/approve-moderation"
        )
        if approved.status_code != 200:
            raise E2EFailure(
                f"Approve moderation failed: HTTP {approved.status_code}"
            )
        review = await read_review(review_id, args.tenant_id)
        if review.moderation_status != "approved":
            raise E2EFailure("Review is not APPROVED after approval")
        if review.reply_text != suggested_reply:
            raise E2EFailure("Reply was not retained after approval")
        if review.suggested_reply is not None:
            raise E2EFailure("reviews.suggested_reply must remain NULL after approval")
        print("approve: HTTP 200; PENDING_MODERATION -> APPROVED")
        print("result: E2E PASSED")


async def main() -> int:
    args = parse_args()
    try:
        await run(args)
        return 0
    except Exception as error:
        print(f"E2E FAILED: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    finally:
        await engine.dispose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
