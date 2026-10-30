"""Иерархия ошибок скрейперов. Воркер решает по типу, повторять ли задачу."""


class ScraperError(Exception):
    """Базовая ошибка скрейпера."""


class ScraperTransientError(ScraperError):
    """Временный сбой (таймаут, сеть, 5xx): задачу стоит повторить позже."""


class ScraperBlockedError(ScraperTransientError):
    """Площадка отдала 401/403/429/капчу. Повтор позже (другой UA/IP) может помочь."""


class ScraperPermanentError(ScraperError):
    """Повтор бесполезен: страница не найдена, URL чужой, вёрстка изменилась."""
