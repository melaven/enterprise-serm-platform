"""Compatibility imports for ARQ worker settings."""

from app.infrastructure.queue.worker.worker import (
    BulkWorkerSettings,
    CriticalWorkerSettings,
    LegacyWorkerSettings,
    WorkerSettings,
)

__all__ = [
    "BulkWorkerSettings",
    "CriticalWorkerSettings",
    "LegacyWorkerSettings",
    "WorkerSettings",
]
