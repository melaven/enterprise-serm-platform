import sys
import os
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app.database import get_db
try:
    from app.database import supabase
except ImportError:
    pass

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Any, cast

from fastapi.concurrency import run_in_threadpool
from postgrest.exceptions import APIError as PostgrestAPIError
from app.app.schemas.reviews import ReviewWebhook
from app.app.services.llm import generate_review_response


router = APIRouter(prefix="/api/v1/reviews", tags=["reviews"])


@router.post("/webhook", status_code=status.HTTP_201_CREATED)
async def receive_review(payload: ReviewWebhook) -> dict[str, Any]:
    insert_data = {
        "company_id": payload.company_id,
        "platform_id": payload.platform_id,
        "external_review_id": payload.external_review_id,
        "author_name": payload.author_name,
        "rating": payload.rating,
        "review_text": payload.review_text,
        "sentiment": "negative" if payload.rating <= 3 else "unknown",
        "processing_status": "new",
    }

    try:
        response = await run_in_threadpool(
            lambda: supabase.table("reviews_log")
            .insert(insert_data)
            .execute()
        )
    except PostgrestAPIError as exc:
        # PostgreSQL unique_violation. Это надежнее, чем искать слово
        # "duplicate" в тексте ошибки.
        if getattr(exc, "code", None) == "23505":
            return {
                "message": "Review already exists",
                "external_review_id": payload.external_review_id,
            }

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save review",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected database error",
        ) from exc

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Review was not returned after insert",
        )

    review_row = cast(dict[str, Any], response.data[0])
    review_id = review_row["id"]

    if payload.rating > 3:
        return {
            "message": "Review accepted",
            "review_id": review_id,
            "negative": False,
        }

    try:
        ai_response = await generate_review_response(
            review_text=payload.review_text,
            rating=payload.rating,
        )

        update_data = {
            "sentiment": "negative",
            "processing_status": "response_generated",
            "ai_response": ai_response,
        }

        await run_in_threadpool(
            lambda: supabase.table("reviews_log")
            .update(update_data)
            .eq("id", review_id)
            .execute()
        )
    except Exception as exc:
        # Сам отзыв уже сохранен. Фиксируем ошибку, чтобы его можно было
        # повторно обработать отдельным worker/retry endpoint.
        try:
            await run_in_threadpool(
                lambda: supabase.table("reviews_log")
                .update(
                    {
                        "sentiment": "negative",
                        "processing_status": "failed",
                        "error_message": str(exc)[:2_000],
                    }
                )
                .eq("id", review_id)
                .execute()
            )
        except Exception:
            # Ошибка обновления не должна скрывать исходную ошибку обработки.
            pass

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Review saved, but response generation failed",
        ) from exc

    return {
        "message": "Negative review accepted and response generated",
        "review_id": review_id,
        "negative": True,
        "processing_status": "response_generated",
    }