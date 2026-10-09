"""
Слой репозиториев для работы с данными
"""

from .base import BaseRepository
from .company import CompanyRepository
from .parser import ParserRepository
from .platform import PlatformRepository
from .review import ReviewRepository

__all__ = [
    "BaseRepository",
    "CompanyRepository",
    "ParserRepository", 
    "PlatformRepository",
    "ReviewRepository"
]