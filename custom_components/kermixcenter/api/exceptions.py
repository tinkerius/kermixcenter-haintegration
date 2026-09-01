"""Exceptions raised by the Kermi X-Center API client."""

from __future__ import annotations


class KermiError(Exception):
    """Base class for every error raised by this package."""


class KermiConnectionError(KermiError):
    """Raised when the portal cannot be reached or returns an unexpected reply."""


class KermiAuthError(KermiError):
    """Raised when authentication against the portal fails."""


class KermiInvalidAuth(KermiAuthError):
    """Raised specifically when the username or password is rejected."""


class KermiApiError(KermiError):
    """Raised when the API answers with a non-zero ``StatusCode``."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        """Keep the portal ``StatusCode`` alongside the message."""
        super().__init__(message)
        self.status_code = status_code
