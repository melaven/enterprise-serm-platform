from enum import Enum


class RiskLevel(str, Enum):
    SAFE = "safe"
    WARNING = "warning"
    CRITICAL_RISK = "critical_risk"


class ResponseStrategyType(str, Enum):
    LEGAL_STRICT = "legal_strict"
    APPEASEMENT = "appeasement"
    INFO_REQUEST = "info_request"
