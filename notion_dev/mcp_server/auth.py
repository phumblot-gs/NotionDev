"""
NOTION FEATURES: ND03
MODULES: NotionDev
DESCRIPTION: Google OAuth authentication middleware for remote MCP server
LAST_SYNC: 2025-12-31
"""

import os
import sys
import json
import time
import logging
import hashlib
import secrets
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

# Try to import JWT library
try:
    import jwt
    JWT_AVAILABLE = True
except ImportError:
    JWT_AVAILABLE = False
    jwt = None

# Try to import httpx for async HTTP requests
try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    httpx = None


@dataclass
class UserInfo:
    """Authenticated user information from Google OAuth."""
    email: str
    name: str
    picture: Optional[str] = None
    domain: Optional[str] = None

    @property
    def is_service_account(self) -> bool:
        """Check if this is a service account."""
        return self.email.startswith("charles@") or self.email.startswith("charly@")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "email": self.email,
            "name": self.name,
            "picture": self.picture,
            "domain": self.domain,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserInfo":
        """Create from dictionary."""
        return cls(
            email=data["email"],
            name=data.get("name", data["email"]),
            picture=data.get("picture"),
            domain=data.get("domain"),
        )


class OAuthError(Exception):
    """OAuth authentication error."""
    pass


class GoogleOAuthProvider:
    """Google OAuth 2.0 provider for authentication.

    Implements the authorization code flow:
    1. Redirect user to Google login
    2. Google redirects back with authorization code
    3. Exchange code for tokens
    4. Verify ID token and extract user info
    """

    GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
    GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
    GOOGLE_CERTS_URL = "https://www.googleapis.com/oauth2/v3/certs"

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        allowed_domain: Optional[str] = None,
    ):
        """Initialize Google OAuth provider.

        Args:
            client_id: Google OAuth client ID
            client_secret: Google OAuth client secret
            redirect_uri: Callback URL after authentication
            allowed_domain: If set, only allow emails from this domain
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.allowed_domain = allowed_domain

        # State management for CSRF protection
        self._pending_states: Dict[str, float] = {}
        self._state_ttl = 600  # 10 minutes

    def get_authorization_url(self, state: Optional[str] = None) -> str:
        """Generate the Google OAuth authorization URL.

        Args:
            state: Optional state parameter for CSRF protection

        Returns:
            URL to redirect the user to
        """
        if state is None:
            state = secrets.token_urlsafe(32)

        # Store state with timestamp
        self._pending_states[state] = time.time()
        self._cleanup_expired_states()

        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
        }

        # Restrict to domain if configured
        if self.allowed_domain:
            params["hd"] = self.allowed_domain

        return f"{self.GOOGLE_AUTH_URL}?{urlencode(params)}"

    def verify_state(self, state: str) -> bool:
        """Verify that the state parameter is valid.

        Args:
            state: State parameter from callback

        Returns:
            True if state is valid
        """
        self._cleanup_expired_states()

        if state in self._pending_states:
            del self._pending_states[state]
            return True
        return False

    async def exchange_code(self, code: str) -> Dict[str, Any]:
        """Exchange authorization code for tokens.

        Args:
            code: Authorization code from callback

        Returns:
            Token response containing access_token, id_token, etc.

        Raises:
            OAuthError: If exchange fails
        """
        if not HTTPX_AVAILABLE:
            raise OAuthError("httpx package not installed")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.GOOGLE_TOKEN_URL,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": self.redirect_uri,
                },
            )

            if response.status_code != 200:
                logger.error(f"Token exchange failed: {response.text}")
                raise OAuthError(f"Token exchange failed: {response.status_code}")

            return response.json()

    async def get_user_info(self, access_token: str) -> UserInfo:
        """Get user information from Google.

        Args:
            access_token: OAuth access token

        Returns:
            UserInfo object with user details

        Raises:
            OAuthError: If request fails or domain not allowed
        """
        if not HTTPX_AVAILABLE:
            raise OAuthError("httpx package not installed")

        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )

            if response.status_code != 200:
                logger.error(f"Failed to get user info: {response.text}")
                raise OAuthError(f"Failed to get user info: {response.status_code}")

            data = response.json()

        email = data.get("email", "")
        domain = email.split("@")[1] if "@" in email else None

        # Verify domain if restriction is configured
        if self.allowed_domain and domain != self.allowed_domain:
            logger.warning(f"Domain not allowed: {domain} (expected {self.allowed_domain})")
            raise OAuthError(f"Email domain '{domain}' is not allowed")

        return UserInfo(
            email=email,
            name=data.get("name", email),
            picture=data.get("picture"),
            domain=domain,
        )

    def _cleanup_expired_states(self) -> None:
        """Remove expired state entries."""
        now = time.time()
        expired = [
            state for state, timestamp in self._pending_states.items()
            if now - timestamp > self._state_ttl
        ]
        for state in expired:
            del self._pending_states[state]


class JWTManager:
    """JWT token manager for session management.

    Creates and validates JWT tokens for authenticated users.
    """

    def __init__(
        self,
        secret: str,
        expiration_hours: int = 1,
        algorithm: str = "HS256",
    ):
        """Initialize JWT manager.

        Args:
            secret: Secret key for signing tokens
            expiration_hours: Token lifetime in hours
            algorithm: JWT signing algorithm
        """
        if not JWT_AVAILABLE:
            raise ImportError("PyJWT package not installed. Run: pip install PyJWT")

        self.secret = secret
        self.expiration_hours = expiration_hours
        self.algorithm = algorithm

    def create_token(self, user: UserInfo) -> str:
        """Create a JWT token for a user.

        Args:
            user: Authenticated user info

        Returns:
            Signed JWT token string
        """
        now = datetime.utcnow()
        payload = {
            "sub": user.email,
            "name": user.name,
            "domain": user.domain,
            "iat": now,
            "exp": now + timedelta(hours=self.expiration_hours),
        }

        return jwt.encode(payload, self.secret, algorithm=self.algorithm)

    def verify_token(self, token: str) -> Optional[UserInfo]:
        """Verify and decode a JWT token.

        Args:
            token: JWT token string

        Returns:
            UserInfo if valid, None otherwise
        """
        try:
            payload = jwt.decode(token, self.secret, algorithms=[self.algorithm])

            return UserInfo(
                email=payload["sub"],
                name=payload.get("name", payload["sub"]),
                domain=payload.get("domain"),
            )
        except jwt.ExpiredSignatureError:
            logger.warning("Token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            return None

    def refresh_token(self, token: str) -> Optional[str]:
        """Refresh an existing token if still valid.

        Args:
            token: Current JWT token

        Returns:
            New token if current is valid, None otherwise
        """
        user = self.verify_token(token)
        if user:
            return self.create_token(user)
        return None


# Context variable for per-request user isolation in async environments
_auth_current_user_context: ContextVar[Optional[UserInfo]] = ContextVar(
    "auth_current_user_context", default=None
)


class AuthMiddleware:
    """Authentication middleware for the MCP server.

    Handles:
    - OAuth login flow
    - JWT token verification
    - User context injection

    Note: Uses contextvars for async-safe per-request user isolation.
    """

    def __init__(
        self,
        google_client_id: str,
        google_client_secret: str,
        redirect_uri: str,
        jwt_secret: str,
        allowed_domain: Optional[str] = None,
        jwt_expiration_hours: int = 1,
    ):
        """Initialize auth middleware.

        Args:
            google_client_id: Google OAuth client ID
            google_client_secret: Google OAuth client secret
            redirect_uri: OAuth callback URL
            jwt_secret: Secret for JWT signing
            allowed_domain: Restrict to this email domain
            jwt_expiration_hours: JWT token lifetime
        """
        self.oauth = GoogleOAuthProvider(
            client_id=google_client_id,
            client_secret=google_client_secret,
            redirect_uri=redirect_uri,
            allowed_domain=allowed_domain,
        )

        self.jwt = JWTManager(
            secret=jwt_secret,
            expiration_hours=jwt_expiration_hours,
        )
        # Note: _current_user is removed in favor of contextvars

    @property
    def current_user(self) -> Optional[UserInfo]:
        """Get the current authenticated user (from context)."""
        return _auth_current_user_context.get()

    def get_login_url(self) -> str:
        """Get the Google OAuth login URL.

        Returns:
            URL to redirect user to for login
        """
        return self.oauth.get_authorization_url()

    async def handle_callback(self, code: str, state: str) -> str:
        """Handle OAuth callback and create session.

        Args:
            code: Authorization code from Google
            state: State parameter for CSRF verification

        Returns:
            JWT token for the session

        Raises:
            OAuthError: If authentication fails
        """
        # Verify state
        if not self.oauth.verify_state(state):
            raise OAuthError("Invalid state parameter")

        # Exchange code for tokens
        tokens = await self.oauth.exchange_code(code)

        # Get user info
        user = await self.oauth.get_user_info(tokens["access_token"])

        logger.info(f"User authenticated: {user.email}")

        # Create JWT session token
        return self.jwt.create_token(user)

    def verify_request(self, token: str) -> bool:
        """Verify a request and set current user in context.

        Args:
            token: JWT token from request

        Returns:
            True if authenticated
        """
        user = self.jwt.verify_token(token)
        if user:
            _auth_current_user_context.set(user)
            return True

        _auth_current_user_context.set(None)
        return False

    def clear_user(self) -> None:
        """Clear the current user context."""
        _auth_current_user_context.set(None)

    def get_user_for_logging(self) -> str:
        """Get user identifier for logging purposes.

        Returns:
            User email or "anonymous"
        """
        current_user = self.current_user
        if current_user:
            return current_user.email
        return "anonymous"


def create_auth_middleware_from_config() -> Optional[AuthMiddleware]:
    """Create auth middleware from server configuration.

    Returns:
        AuthMiddleware instance or None if not configured
    """
    from .config import get_config

    config = get_config()

    if not config.auth_enabled:
        return None

    if not all([
        config.google_client_id,
        config.google_client_secret,
        config.jwt_secret,
    ]):
        logger.warning("Auth enabled but missing configuration")
        return None

    # Determine redirect URI based on environment
    base_url = os.environ.get("MCP_BASE_URL", f"http://localhost:{config.port}")
    redirect_uri = f"{base_url}/auth/callback"

    return AuthMiddleware(
        google_client_id=config.google_client_id,
        google_client_secret=config.google_client_secret,
        redirect_uri=redirect_uri,
        jwt_secret=config.jwt_secret,
        allowed_domain=config.allowed_email_domain,
        jwt_expiration_hours=config.jwt_expiration_hours,
    )
