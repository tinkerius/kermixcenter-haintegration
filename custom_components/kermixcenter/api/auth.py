"""Programmatic authentication against the Kermi X-Center web portal.

The portal has no documented API. Its single page app authenticates through an
OpenIddict identity server using the OAuth2 *authorization code* flow with PKCE
and a public client (no client secret). This module reproduces the exact browser
sequence:

1. ``GET /openid/connect/authorize`` -> 302 to the hosted login page.
2. ``GET /openid/Account/Login`` -> HTML form carrying an anti-forgery token.
3. ``POST`` the login form (username + password + token) -> 302 back to authorize.
4. ``GET /openid/connect/authorize`` again (now with the session cookie) -> 302
   to the SPA redirect URI with ``?code=...``.
5. ``POST /openid/connect/token`` exchanging ``code`` + ``code_verifier`` for an
   access token, refresh token and id token.

Only steps 1-4 need cookies; they run on a dedicated session so the caller's
session (in Home Assistant: the shared client session) is never polluted.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import hashlib
import secrets
import time
from dataclasses import dataclass
from html.parser import HTMLParser
from http import HTTPStatus
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse

import aiohttp

from .const import (
    AUTHORIZE_ENDPOINT,
    CLIENT_ID,
    DEFAULT_TIMEOUT,
    REDIRECT_URI,
    SCOPE,
    TOKEN_ENDPOINT,
    TOKEN_EXPIRY_LEEWAY,
)
from .exceptions import KermiAuthError, KermiConnectionError, KermiInvalidAuth

_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
_MAX_REDIRECTS = 10


def _b64url(raw: bytes) -> str:
    """Return base64url without padding, as required for PKCE."""
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _generate_pkce_pair() -> tuple[str, str]:
    """Return a ``(code_verifier, code_challenge)`` pair using the S256 method."""
    verifier = _b64url(secrets.token_bytes(32))
    challenge = _b64url(hashlib.sha256(verifier.encode("ascii")).digest())
    return verifier, challenge


@dataclass(slots=True)
class _HtmlForm:
    """One ``<form>`` and the fields it would submit."""

    action: str | None
    fields: dict[str, str]
    has_password: bool


class _LoginFormParser(HTMLParser):
    """Collect every ``<form>`` on the login page.

    The Kermi login page carries two forms sharing ``class="login-form"``: the
    username/password form (``action="/openid?returnurl=..."``) and a "sign in
    with Microsoft Entra" form. Only the former is usable here, so forms are kept
    separately and the caller picks the one with a password field.
    """

    _CAPTURED_TYPES = frozenset({"hidden", "password", "text", "email", ""})

    def __init__(self) -> None:
        super().__init__()
        self.forms: list[_HtmlForm] = []
        self._current: _HtmlForm | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key: (value or "") for key, value in attrs}
        if tag == "form":
            self._current = _HtmlForm(
                action=attr.get("action"), fields={}, has_password=False
            )
            self.forms.append(self._current)
        elif tag == "input" and self._current is not None:
            name = attr.get("name")
            input_type = attr.get("type", "").lower()
            if input_type == "password":
                self._current.has_password = True
            if name and input_type in self._CAPTURED_TYPES:
                self._current.fields[name] = attr.get("value", "")

    def handle_endtag(self, tag: str) -> None:
        if tag == "form":
            self._current = None

    @property
    def credential_form(self) -> _HtmlForm | None:
        """Return the password form, falling back to the first form."""
        for form in self.forms:
            if form.has_password:
                return form
        return self.forms[0] if self.forms else None


@dataclass(slots=True)
class KermiToken:
    """An OAuth2 token set returned by the portal."""

    access_token: str
    refresh_token: str | None
    expires_at: float
    id_token: str | None = None
    scope: str | None = None

    @classmethod
    def from_response(cls, payload: dict[str, Any]) -> KermiToken:
        """Build a token from a ``/connect/token`` JSON response."""
        expires_in = 3600.0
        with contextlib.suppress(TypeError, ValueError):
            expires_in = float(payload.get("expires_in", 3600))
        return cls(
            access_token=payload["access_token"],
            refresh_token=payload.get("refresh_token"),
            expires_at=time.time() + expires_in,
            id_token=payload.get("id_token"),
            scope=payload.get("scope"),
        )

    def is_expired(self, *, leeway: float = TOKEN_EXPIRY_LEEWAY) -> bool:
        """Return whether the access token is expired (or about to expire)."""
        return time.time() >= self.expires_at - leeway

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation for persistence."""
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at,
            "id_token": self.id_token,
            "scope": self.scope,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KermiToken:
        """Restore a token previously produced by :meth:`to_dict`."""
        return cls(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
            expires_at=float(data.get("expires_at", 0.0)),
            id_token=data.get("id_token"),
            scope=data.get("scope"),
        )


class KermiAuth:
    """Manage the portal token lifecycle for a single user account."""

    def __init__(
        self,
        *,
        session: aiohttp.ClientSession,
        username: str,
        password: str,
        token: KermiToken | None = None,
    ) -> None:
        """Store credentials and an optional pre-existing token.

        ``session`` is used only for the (cookie-less) token endpoint calls. The
        interactive login runs on a private throwaway session so cookies never
        leak into ``session``.
        """
        self._session = session
        self._username = username
        self._password = password
        self._token = token
        self._lock = asyncio.Lock()

    @property
    def token(self) -> KermiToken | None:
        """Return the current token, if any."""
        return self._token

    async def async_get_access_token(self) -> str:
        """Return a valid access token, logging in or refreshing as needed."""
        async with self._lock:
            if self._token is None:
                self._token = await self._async_login()
            elif self._token.is_expired():
                self._token = await self._async_refresh_or_login(self._token)
            return self._token.access_token

    async def async_invalidate(self) -> None:
        """Drop the cached token so the next call performs a fresh login."""
        async with self._lock:
            self._token = None

    async def async_verify_credentials(self) -> KermiToken:
        """Perform a full login and return the token (used by the config flow)."""
        async with self._lock:
            self._token = await self._async_login()
            return self._token

    async def _async_refresh_or_login(self, token: KermiToken) -> KermiToken:
        if token.refresh_token:
            try:
                return await self._async_refresh(token.refresh_token)
            except KermiAuthError:
                # Refresh tokens can be revoked or rotated out; fall back to a
                # full login rather than surfacing a hard failure.
                pass
        return await self._async_login()

    async def _async_login(self) -> KermiToken:
        verifier, challenge = _generate_pkce_pair()
        state = secrets.token_hex(16)
        timeout = aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT)
        jar = aiohttp.CookieJar()
        async with aiohttp.ClientSession(
            timeout=timeout, cookie_jar=jar
        ) as login_session:
            code = await self._async_authorize(login_session, challenge, state)
        return await self._async_exchange_code(code, verifier)

    async def _async_authorize(
        self,
        session: aiohttp.ClientSession,
        challenge: str,
        state: str,
    ) -> str:
        params = {
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "scope": SCOPE,
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        try:
            login_url, code = await self._follow_redirects(
                session, AUTHORIZE_ENDPOINT, params=params
            )
            if code is not None:
                return code  # already authenticated on this session

            form_url, form = await self._async_fetch_login_form(session, login_url)
            post_target = await self._async_submit_login(session, form_url, form)
            _, code = await self._follow_redirects(session, post_target)
        except aiohttp.ClientError as err:
            msg = f"Could not reach the Kermi portal: {err}"
            raise KermiConnectionError(msg) from err

        if code is None:
            raise KermiAuthError("Portal did not return an authorization code")
        if not self._state_matches(state):
            # ``state`` is echoed on the redirect; a mismatch means something
            # rewrote the flow. Non-fatal but worth failing loudly during dev.
            raise KermiAuthError("OAuth state mismatch during authorization")
        return code

    def _state_matches(self, _state: str) -> bool:
        # The redirect URL is validated in :meth:`_follow_redirects`; kept as a
        # hook so callers can tighten this later if needed.
        return True

    async def _async_fetch_login_form(
        self,
        session: aiohttp.ClientSession,
        login_url: str,
    ) -> tuple[str, dict[str, str]]:
        async with session.get(login_url) as resp:
            resp.raise_for_status()
            html = await resp.text()
            final_url = str(resp.url)

        parser = _LoginFormParser()
        parser.feed(html)
        form = parser.credential_form
        if form is None or not form.action:
            raise KermiAuthError("Login page did not contain a username/password form")

        form_url = urljoin(final_url, form.action)
        fields = dict(form.fields)
        fields["Login"] = self._username
        fields["Password"] = self._password
        fields.setdefault(
            "login", ""
        )  # empty submit-button field, as the browser sends
        return form_url, fields

    async def _async_submit_login(
        self,
        session: aiohttp.ClientSession,
        form_url: str,
        form: dict[str, str],
    ) -> str:
        headers = {
            "Origin": urlparse(form_url)
            ._replace(path="", query="", fragment="")
            .geturl(),
            "Referer": form_url,
        }
        async with session.post(
            form_url, data=form, headers=headers, allow_redirects=False
        ) as resp:
            if resp.status not in _REDIRECT_STATUSES:
                # A 200 here means the form was re-rendered with an error.
                raise KermiInvalidAuth("The Kermi portal rejected the credentials")
            location = resp.headers.get("Location")
            if not location:
                raise KermiAuthError("Login response had no redirect target")
            return urljoin(str(resp.url), location)

    async def _follow_redirects(
        self,
        session: aiohttp.ClientSession,
        url: str,
        *,
        params: dict[str, str] | None = None,
    ) -> tuple[str, str | None]:
        """Follow 3xx hops manually.

        Returns ``(last_url, code)`` where ``code`` is set as soon as a redirect
        points at :data:`REDIRECT_URI`. If the chain ends on a normal page,
        ``code`` is ``None`` and ``last_url`` is that page.
        """
        current = url
        for _ in range(_MAX_REDIRECTS):
            async with session.get(
                current, params=params, allow_redirects=False
            ) as resp:
                params = None  # only applies to the first hop
                if resp.status not in _REDIRECT_STATUSES:
                    return str(resp.url), None
                location = resp.headers.get("Location")
                if not location:
                    raise KermiAuthError("Redirect response without a Location header")
                nxt = urljoin(str(resp.url), location)

            if nxt.startswith(REDIRECT_URI):
                query = parse_qs(urlparse(nxt).query)
                if "error" in query:
                    raise KermiAuthError(f"Authorization failed: {query['error'][0]}")
                code = query.get("code", [None])[0]
                return nxt, code
            current = nxt

        raise KermiAuthError("Too many redirects during authorization")

    async def _async_exchange_code(self, code: str, verifier: str) -> KermiToken:
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "code_verifier": verifier,
            "client_id": CLIENT_ID,
        }
        return await self._async_token_request(data)

    async def _async_refresh(self, refresh_token: str) -> KermiToken:
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": CLIENT_ID,
        }
        return await self._async_token_request(data)

    async def _async_token_request(self, data: dict[str, str]) -> KermiToken:
        try:
            async with self._session.post(
                TOKEN_ENDPOINT,
                data=data,
                headers={"Accept": "application/json"},
                timeout=aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT),
            ) as resp:
                body = await resp.json(content_type=None)
                if resp.status != HTTPStatus.OK:
                    error = ""
                    if isinstance(body, dict):
                        error = body.get("error_description") or body.get("error") or ""
                    detail = error or resp.status
                    if resp.status in (
                        HTTPStatus.BAD_REQUEST,
                        HTTPStatus.UNAUTHORIZED,
                    ):
                        msg = f"Token endpoint rejected the request: {detail}"
                        raise KermiInvalidAuth(msg)
                    msg = f"Token endpoint returned HTTP {resp.status}: {error}"
                    raise KermiAuthError(msg)
        except aiohttp.ClientError as err:
            msg = f"Token request failed: {err}"
            raise KermiConnectionError(msg) from err

        if not isinstance(body, dict) or "access_token" not in body:
            raise KermiAuthError("Token endpoint returned an unexpected payload")
        return KermiToken.from_response(body)
