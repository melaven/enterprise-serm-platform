"""Publication lifecycle for moderated review replies."""

from enum import StrEnum


class ReplyPublicationStatus(StrEnum):
    QUEUED_OUTBOX = "queued_outbox"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    PUBLISH_FAILED = "publish_failed"
