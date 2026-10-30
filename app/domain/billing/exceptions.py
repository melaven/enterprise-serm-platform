"""Domain exceptions for subscription and usage-based billing."""


class BillingException(Exception):
    """Base exception for billing rules."""


class SubscriptionInactiveError(BillingException):
    """Raised when a tenant does not have an active subscription."""


class QuotaExceededError(BillingException):
    """Raised when a tenant has exhausted its included token allowance."""
