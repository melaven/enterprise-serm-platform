"""
ARQ Worker для фоновых задач SERM
"""

from .tasks import fetch_reviews_task
from .worker import WorkerSettings

__all__ = ["WorkerSettings", "fetch_reviews_task"]
