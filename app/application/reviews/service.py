from typing import Any, Protocol
from uuid import UUID

from fastapi import status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.economics import (
    AssistantReviewSchema,
    ReplyModerationStatus,
    ReviewStatus,
)
from app.core.exceptions import BusinessLogicError, NotFoundError, SERMException
from app.core.logger import get_correlation_id
from app.core.review_privacy import safe_review_summary
from app.core.security import decrypt_token, encrypt_token
from app.domain.reviews.state import ReviewState
from app.infrastructure.persistence.models.economics import Platform, Review
from app.infrastructure.persistence.models.review_analysis_payload import (
    ReviewAnalysisPayload,
)
from app.infrastructure.persistence.models.review_reply import ReviewReply


class ReviewQueue(Protocol):
    async def enqueue_job(
        self, function_name: str, *args: object, **kwargs: object
    ) -> Any: ...


class ReviewReplyAnalyzer(Protocol):
    async def generate_reply(
        self, review_text: str, tags: list[str], rating: int
    ) -> str: ...

    async def close(self) -> None: ...


class ReviewApplicationService:
    """Application use cases for review ingestion and response moderation."""

    def __init__(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        arq_pool: ReviewQueue | None = None,
        analyzer: ReviewReplyAnalyzer | None = None,
    ) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.arq_pool = arq_pool
        self.analyzer = analyzer

    async def create_review(
        self,
        platform_id: UUID,
        rating: int,
        text: str,
        review_status: ReviewStatus = ReviewStatus.NEW,
        financial_impact: float = 0.0,
    ) -> Review:
        if self.arq_pool is None:
            raise SERMException(
                "Review processing queue is unavailable",
                status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        if not text.strip() or len(text) > 10000:
            raise SERMException(
                "Review text must contain 1 to 10000 characters",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        platform = await self.session.scalar(
            select(Platform).where(
                Platform.id == platform_id,
                Platform.company_id == self.tenant_id,
            )
        )
        if platform is None:
            raise NotFoundError("Platform", str(platform_id))

        initial_sentiment = (
            "POSITIVE" if rating >= 4 else "NEUTRAL" if rating == 3 else "NEGATIVE"
        )
        review = Review(
            company_id=self.tenant_id,
            platform_id=platform_id,
            author_name="Автор отзыва",
            rating=rating,
            text=safe_review_summary(rating, initial_sentiment),
            status=review_status,
            state=ReviewState.NEW,
            financial_impact=financial_impact,
        )
        self.session.add(review)
        await self.session.flush()
        self.session.add(
            ReviewAnalysisPayload(
                review_id=review.id,
                company_id=self.tenant_id,
                encrypted_text=encrypt_token(text),
            )
        )
        await self.session.flush()
        await self.session.refresh(review)
        await self.session.commit()

        # Get correlation ID from context to propagate to worker
        correlation_id = get_correlation_id()

        await self.arq_pool.enqueue_job(
            "process_review_task",
            str(review.id),
            str(self.tenant_id),
            correlation_id=correlation_id,
            _job_id=f"process-review-{review.id}",
        )
        return review

    async def list_assistant_reviews(
        self,
        review_filter: str,
        branch_id: UUID | None,
        limit: int,
        offset: int,
    ) -> list[AssistantReviewSchema]:
        filters = [Review.company_id == self.tenant_id]
        if branch_id is not None:
            filters.append(Review.branch_id == branch_id)
        if review_filter == "negative":
            filters.append(Review.sentiment == "NEGATIVE")
        elif review_filter == "unanswered":
            filters.append(
                Review.moderation_status.in_(
                    [ReplyModerationStatus.NEW, ReplyModerationStatus.DRAFTED]
                )
            )

        result = await self.session.execute(
            select(Review, ReviewReply.reply_text)
            .outerjoin(ReviewReply, ReviewReply.review_id == Review.id)
            .where(and_(*filters))
            .order_by(Review.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [
            AssistantReviewSchema(
                id=review.id,
                platform=review.platform,
                text=review.text,
                rating=review.rating,
                created_at=review.created_at,
                sentiment=review.sentiment,
                status=review.moderation_status,
                has_reply=bool(reply_text or review.auto_reply),
                reply_text=reply_text,
            )
            for review, reply_text in result.all()
        ]

    async def generate_reply(self, review_id: UUID) -> str:
        review = await self._get_review(review_id)
        if not review.is_analyzed:
            raise SERMException(
                "Review analysis is not complete", status.HTTP_409_CONFLICT
            )

        payload = await self.session.scalar(
            select(ReviewAnalysisPayload).where(
                ReviewAnalysisPayload.review_id == review_id,
                ReviewAnalysisPayload.company_id == self.tenant_id,
            )
        )
        if payload is None:
            raise SERMException(
                "Encrypted review text is no longer available",
                status.HTTP_409_CONFLICT,
            )

        if self.analyzer is None:
            raise SERMException(
                "Review reply analyzer is unavailable",
                status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        suggested_reply = await self.analyzer.generate_reply(
            decrypt_token(payload.encrypted_text),
            review.tags or [],
            review.rating,
        )
        if review.moderation_status == ReplyModerationStatus.NEW:
            review.moderation_status = ReplyModerationStatus.DRAFTED
        return suggested_reply

    async def submit_moderation(
        self, review_id: UUID, reply_text: str
    ) -> AssistantReviewSchema:
        review = await self._get_review(review_id)
        if review.moderation_status != ReplyModerationStatus.DRAFTED:
            raise BusinessLogicError(
                "Moderation can only be submitted from drafted status"
            )

        await self._save_reply(review, reply_text)
        review.moderation_status = ReplyModerationStatus.PENDING_MODERATION
        return await self._assistant_review(review)

    async def approve_moderation(self, review_id: UUID) -> AssistantReviewSchema:
        review = await self._get_review(review_id)
        if review.moderation_status != ReplyModerationStatus.PENDING_MODERATION:
            raise BusinessLogicError("Only replies pending moderation can be approved")
        if await self.session.get(ReviewReply, review_id) is None:
            raise BusinessLogicError("Cannot approve a review without a reply")

        review.moderation_status = ReplyModerationStatus.APPROVED
        return await self._assistant_review(review)

    async def update_status(
        self,
        review_id: UUID,
        new_status: ReviewStatus,
        si_response: str | None,
    ) -> tuple[Review, bool]:
        review = await self._get_review(review_id)
        review.status = new_status
        if si_response is not None:
            await self._save_reply(review, si_response)
            return review, True

        reply = await self.session.get(ReviewReply, review.id)
        return review, reply is not None

    async def _get_review(self, review_id: UUID) -> Review:
        review = await self.session.scalar(
            select(Review).where(
                and_(
                    Review.id == review_id,
                    Review.company_id == self.tenant_id,
                )
            )
        )
        if review is None:
            raise NotFoundError("Review", str(review_id))
        return review

    async def _save_reply(self, review: Review, reply_text: str) -> ReviewReply:
        reply = await self.session.get(ReviewReply, review.id)
        if reply is None:
            reply = ReviewReply(
                review_id=review.id,
                company_id=self.tenant_id,
                reply_text=reply_text,
            )
            self.session.add(reply)
        else:
            reply.reply_text = reply_text
        return reply

    async def _assistant_review(self, review: Review) -> AssistantReviewSchema:
        reply = await self.session.get(ReviewReply, review.id)
        return AssistantReviewSchema(
            id=review.id,
            platform=review.platform,
            text=review.text,
            rating=review.rating,
            created_at=review.created_at,
            sentiment=review.sentiment,
            status=review.moderation_status,
            has_reply=bool(reply or review.auto_reply),
            reply_text=reply.reply_text if reply is not None else None,
        )
