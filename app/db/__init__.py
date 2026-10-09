"""
Database module initialization.

Exports database components for use across the application.
"""

from .tenant import tenant_session_factory

__all__ = [
    "tenant_session_factory",
]