"""
Слой репозиториев для работы с данными
"""

from app.infrastructure.persistence.repositories.base import BaseRepository
from app.infrastructure.persistence.repositories.company import CompanyRepository
from app.infrastructure.persistence.repositories.parser import ParserRepository
from app.infrastructure.persistence.repositories.platform import PlatformRepository
from app.infrastructure.persistence.repositories.review import ReviewRepository

__all__ = [
    "BaseRepository",
    "CompanyRepository",
    "ParserRepository",
    "PlatformRepository",
    "ReviewRepository",
]
