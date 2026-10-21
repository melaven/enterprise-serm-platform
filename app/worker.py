"""Legacy ARQ entry point with review-processing jobs disabled."""

from arq import WorkerSettings

from app.core.redis import get_redis_settings


class WorkerSettings(WorkerSettings):
    redis_settings = get_redis_settings()
    functions = []
