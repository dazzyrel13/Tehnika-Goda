"""Shared default for ADMIN_URL_PREFIX when env is unset (local/tests only)."""

# Override in .env for every real deploy. Never ship this value to production.
DEFAULT_ADMIN_URL_PREFIX = "local-admin/"
