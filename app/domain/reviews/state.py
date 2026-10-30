from enum import Enum


class ReviewState(str, Enum):
    """States for the review lifecycle finite state machine."""

    NEW = "new"
    ANALYZING = "analyzing"
    ANALYSIS_FAILED = "analysis_failed"
    AUTO_APPROVED = "auto_approved"
    DRAFT_PENDING = "draft_pending"
    ESCALATED = "escalated"
    IGNORED = "ignored"
    APPROVED = "approved"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    PUBLISH_FAILED = "publish_failed"
