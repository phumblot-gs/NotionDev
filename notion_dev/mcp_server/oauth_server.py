"""
NOTION FEATURES: ND03
MODULES: NotionDev
DESCRIPTION: OAuth 2.0 Authorization Server implementation for MCP (RFC 8414, RFC 7591)
LAST_SYNC: 2025-12-31

Implements the OAuth 2.0 flow required by Claude.ai for MCP server integration:
- RFC 8414: Authorization Server Metadata
- RFC 7591: Dynamic Client Registration
- OAuth 2.0 with PKCE (RFC 7636)
"""

import os
import sys
import json
import time
import logging
import secrets
import hashlib
import base64
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from urllib.parse import urlencode, parse_qs, urlparse

logger = logging.getLogger(__name__)

# Try to import JWT library
try:
    import jwt
    JWT_AVAILABLE = True
except ImportError:
    JWT_AVAILABLE = False
    jwt = None


@dataclass
class OAuthClient:
    """Registered OAuth client."""
    client_id: str
    client_secret: Optional[str]
    client_name: str
    redirect_uris: List[str]
    grant_types: List[str]
    response_types: List[str]
    scope: str
    token_endpoint_auth_method: str
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to registration response."""
        return {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "client_name": self.client_name,
            "redirect_uris": self.redirect_uris,
            "grant_types": self.grant_types,
            "response_types": self.response_types,
            "scope": self.scope,
            "token_endpoint_auth_method": self.token_endpoint_auth_method,
            "client_id_issued_at": int(self.created_at),
        }


@dataclass
class AuthorizationCode:
    """Authorization code for OAuth flow."""
    code: str
    client_id: str
    redirect_uri: str
    scope: str
    code_challenge: str
    code_challenge_method: str
    user_email: str
    user_name: str
    expires_at: float
    used: bool = False


@dataclass
class AccessToken:
    """OAuth access token."""
    token: str
    client_id: str
    user_email: str
    user_name: str
    scope: str
    expires_at: float


class MCPOAuthServer:
    """OAuth 2.0 Authorization Server for MCP.

    Implements the OAuth flow required by Claude.ai:
    1. /.well-known/oauth-authorization-server - Server metadata
    2. /.well-known/oauth-protected-resource - Protected resource metadata
    3. /register - Dynamic client registration (RFC 7591)
    4. /authorize - Authorization endpoint with PKCE
    5. /token - Token endpoint
    """

    def __init__(
        self,
        issuer: str,
        jwt_secret: str,
        google_client_id: str,
        google_client_secret: str,
        allowed_domain: Optional[str] = None,
        allowed_emails: Optional[List[str]] = None,
        token_expiration_seconds: int = 3600,
    ):
        """Initialize OAuth server.

        Args:
            issuer: Base URL of the MCP server (e.g., https://notiondev.fly.dev)
            jwt_secret: Secret for signing tokens
            google_client_id: Google OAuth client ID for user authentication
            google_client_secret: Google OAuth client secret
            allowed_domain: Optional domain restriction for Google login
            allowed_emails: Optional list of specific emails allowed
            token_expiration_seconds: Access token lifetime
        """
        self.issuer = issuer.rstrip("/")
        self.jwt_secret = jwt_secret
        self.google_client_id = google_client_id
        self.google_client_secret = google_client_secret
        self.allowed_domain = allowed_domain
        self.allowed_emails = [e.lower() for e in (allowed_emails or [])]
        self.token_expiration_seconds = token_expiration_seconds

        # In-memory storage (consider Redis for production scale)
        self._clients: Dict[str, OAuthClient] = {}
        self._auth_codes: Dict[str, AuthorizationCode] = {}
        self._access_tokens: Dict[str, AccessToken] = {}
        self._pending_auth: Dict[str, Dict[str, Any]] = {}  # state -> auth request info

        # Code/token expiration
        self._code_expiration_seconds = 600  # 10 minutes

    def get_metadata(self) -> Dict[str, Any]:
        """Get OAuth 2.0 Authorization Server Metadata (RFC 8414)."""
        return {
            "issuer": self.issuer,
            "authorization_endpoint": f"{self.issuer}/authorize",
            "token_endpoint": f"{self.issuer}/token",
            "registration_endpoint": f"{self.issuer}/register",
            "scopes_supported": ["mcp:tools", "mcp:resources", "mcp:prompts"],
            "response_types_supported": ["code"],
            "response_modes_supported": ["query"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "token_endpoint_auth_methods_supported": ["client_secret_basic", "client_secret_post", "none"],
            "code_challenge_methods_supported": ["S256"],
            "service_documentation": f"{self.issuer}/docs",
        }

    def get_protected_resource_metadata(self) -> Dict[str, Any]:
        """Get OAuth 2.0 Protected Resource Metadata."""
        return {
            "resource": f"{self.issuer}/sse",
            "authorization_servers": [self.issuer],
            "scopes_supported": ["mcp:tools", "mcp:resources", "mcp:prompts"],
            "bearer_methods_supported": ["header"],
        }

    def register_client(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Register a new OAuth client (RFC 7591).

        Args:
            request_data: Client registration request

        Returns:
            Client registration response

        Raises:
            ValueError: If registration request is invalid
        """
        # Validate required fields
        redirect_uris = request_data.get("redirect_uris", [])
        if not redirect_uris:
            raise ValueError("redirect_uris is required")

        # Validate redirect URIs
        for uri in redirect_uris:
            parsed = urlparse(uri)
            # Allow localhost for development, require HTTPS otherwise
            if parsed.scheme not in ("http", "https"):
                raise ValueError(f"Invalid redirect URI scheme: {uri}")
            if parsed.scheme == "http" and parsed.hostname not in ("localhost", "127.0.0.1"):
                raise ValueError(f"HTTP only allowed for localhost: {uri}")

        # Generate client credentials
        client_id = secrets.token_urlsafe(32)

        # Client secret is optional for public clients
        token_endpoint_auth_method = request_data.get("token_endpoint_auth_method", "none")
        client_secret = None
        if token_endpoint_auth_method != "none":
            client_secret = secrets.token_urlsafe(48)

        # Create client
        client = OAuthClient(
            client_id=client_id,
            client_secret=client_secret,
            client_name=request_data.get("client_name", "MCP Client"),
            redirect_uris=redirect_uris,
            grant_types=request_data.get("grant_types", ["authorization_code"]),
            response_types=request_data.get("response_types", ["code"]),
            scope=request_data.get("scope", "mcp:tools mcp:resources mcp:prompts"),
            token_endpoint_auth_method=token_endpoint_auth_method,
        )

        # Store client
        self._clients[client_id] = client

        logger.info(f"Registered new OAuth client: {client_id} ({client.client_name})")

        return client.to_dict()

    def create_authorization_url(
        self,
        client_id: str,
        redirect_uri: str,
        scope: str,
        state: str,
        code_challenge: str,
        code_challenge_method: str,
    ) -> str:
        """Create Google OAuth authorization URL.

        We use Google as the identity provider, then issue our own tokens.

        Args:
            client_id: OAuth client ID
            redirect_uri: Client's redirect URI
            scope: Requested scope
            state: Client's state parameter
            code_challenge: PKCE code challenge
            code_challenge_method: PKCE method (S256)

        Returns:
            Google OAuth URL to redirect user to

        Raises:
            ValueError: If request is invalid
        """
        # Validate client
        client = self._clients.get(client_id)
        if not client:
            raise ValueError("invalid_client")

        # Validate redirect URI
        if redirect_uri not in client.redirect_uris:
            raise ValueError("invalid_redirect_uri")

        # Validate PKCE
        if code_challenge_method != "S256":
            raise ValueError("invalid_request: only S256 code_challenge_method supported")

        # Store auth request info
        internal_state = secrets.token_urlsafe(32)
        self._pending_auth[internal_state] = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": scope,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": code_challenge_method,
            "created_at": time.time(),
        }

        # Build Google OAuth URL
        params = {
            "client_id": self.google_client_id,
            "redirect_uri": f"{self.issuer}/oauth/google/callback",
            "response_type": "code",
            "scope": "openid email profile",
            "state": internal_state,
            "access_type": "offline",
            "prompt": "consent",
        }

        if self.allowed_domain:
            params["hd"] = self.allowed_domain

        return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"

    async def handle_google_callback(
        self,
        code: str,
        state: str,
    ) -> str:
        """Handle Google OAuth callback.

        Args:
            code: Google authorization code
            state: Internal state parameter

        Returns:
            Redirect URL with authorization code for the MCP client

        Raises:
            ValueError: If callback is invalid
        """
        # Validate state
        auth_info = self._pending_auth.pop(state, None)
        if not auth_info:
            raise ValueError("invalid_state")

        # Check expiration (10 minutes)
        if time.time() - auth_info["created_at"] > 600:
            raise ValueError("authorization_expired")

        # Exchange Google code for tokens
        try:
            import httpx
            async with httpx.AsyncClient() as http_client:
                response = await http_client.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "client_id": self.google_client_id,
                        "client_secret": self.google_client_secret,
                        "code": code,
                        "grant_type": "authorization_code",
                        "redirect_uri": f"{self.issuer}/oauth/google/callback",
                    },
                )

                if response.status_code != 200:
                    logger.error(f"Google token exchange failed: {response.text}")
                    raise ValueError("google_auth_failed")

                tokens = response.json()

                # Get user info
                user_response = await http_client.get(
                    "https://www.googleapis.com/oauth2/v2/userinfo",
                    headers={"Authorization": f"Bearer {tokens['access_token']}"},
                )

                if user_response.status_code != 200:
                    raise ValueError("failed_to_get_user_info")

                user_info = user_response.json()

        except ImportError:
            raise ValueError("httpx not installed")

        # Extract user info
        user_email = user_info.get("email", "").lower()
        user_name = user_info.get("name", user_email)
        user_domain = user_email.split("@")[1] if "@" in user_email else None

        # Validate domain if restricted
        if self.allowed_domain and user_domain != self.allowed_domain:
            logger.warning(f"Domain not allowed: {user_domain} (expected {self.allowed_domain})")
            raise ValueError(f"domain_not_allowed: {user_domain}")

        # Validate specific emails if configured
        if self.allowed_emails and user_email not in self.allowed_emails:
            logger.warning(f"Email not in allowed list: {user_email}")
            raise ValueError("email_not_allowed")

        logger.info(f"Google auth successful for: {user_email}")

        # Create authorization code
        auth_code = secrets.token_urlsafe(32)
        self._auth_codes[auth_code] = AuthorizationCode(
            code=auth_code,
            client_id=auth_info["client_id"],
            redirect_uri=auth_info["redirect_uri"],
            scope=auth_info["scope"],
            code_challenge=auth_info["code_challenge"],
            code_challenge_method=auth_info["code_challenge_method"],
            user_email=user_email,
            user_name=user_name,
            expires_at=time.time() + self._code_expiration_seconds,
        )

        # Build redirect URL for MCP client
        redirect_params = {
            "code": auth_code,
            "state": auth_info["state"],
        }

        redirect_uri = auth_info["redirect_uri"]
        separator = "&" if "?" in redirect_uri else "?"
        return f"{redirect_uri}{separator}{urlencode(redirect_params)}"

    def exchange_code_for_token(
        self,
        grant_type: str,
        code: str,
        redirect_uri: str,
        client_id: str,
        code_verifier: str,
    ) -> Dict[str, Any]:
        """Exchange authorization code for access token.

        Args:
            grant_type: Must be "authorization_code"
            code: Authorization code
            redirect_uri: Must match original request
            client_id: OAuth client ID
            code_verifier: PKCE code verifier

        Returns:
            Token response

        Raises:
            ValueError: If request is invalid
        """
        if grant_type != "authorization_code":
            raise ValueError("unsupported_grant_type")

        # Get and validate auth code
        auth_code = self._auth_codes.get(code)
        if not auth_code:
            raise ValueError("invalid_grant: code not found")

        if auth_code.used:
            raise ValueError("invalid_grant: code already used")

        if time.time() > auth_code.expires_at:
            raise ValueError("invalid_grant: code expired")

        if auth_code.client_id != client_id:
            raise ValueError("invalid_grant: client_id mismatch")

        if auth_code.redirect_uri != redirect_uri:
            raise ValueError("invalid_grant: redirect_uri mismatch")

        # Verify PKCE code challenge
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode()).digest()
        ).decode().rstrip("=")

        if code_challenge != auth_code.code_challenge:
            raise ValueError("invalid_grant: code_verifier invalid")

        # Mark code as used
        auth_code.used = True

        # Generate access token
        access_token = self._create_access_token(
            client_id=client_id,
            user_email=auth_code.user_email,
            user_name=auth_code.user_name,
            scope=auth_code.scope,
        )

        return {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": self.token_expiration_seconds,
            "scope": auth_code.scope,
        }

    def _create_access_token(
        self,
        client_id: str,
        user_email: str,
        user_name: str,
        scope: str,
    ) -> str:
        """Create a JWT access token."""
        if not JWT_AVAILABLE:
            # Fallback to opaque token
            token = secrets.token_urlsafe(48)
            self._access_tokens[token] = AccessToken(
                token=token,
                client_id=client_id,
                user_email=user_email,
                user_name=user_name,
                scope=scope,
                expires_at=time.time() + self.token_expiration_seconds,
            )
            return token

        # Create JWT token
        now = datetime.utcnow()
        payload = {
            "iss": self.issuer,
            "sub": user_email,
            "name": user_name,
            "client_id": client_id,
            "scope": scope,
            "iat": now,
            "exp": now + timedelta(seconds=self.token_expiration_seconds),
        }

        return jwt.encode(payload, self.jwt_secret, algorithm="HS256")

    def verify_access_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify an access token and return user info.

        Args:
            token: Bearer token

        Returns:
            User info dict or None if invalid
        """
        # Try JWT first
        if JWT_AVAILABLE:
            try:
                payload = jwt.decode(token, self.jwt_secret, algorithms=["HS256"])
                return {
                    "email": payload["sub"],
                    "name": payload.get("name", payload["sub"]),
                    "client_id": payload.get("client_id"),
                    "scope": payload.get("scope"),
                }
            except jwt.ExpiredSignatureError:
                logger.warning("Token expired")
                return None
            except jwt.InvalidTokenError as e:
                logger.warning(f"Invalid token: {e}")
                # Fall through to check opaque tokens

        # Check opaque tokens
        stored = self._access_tokens.get(token)
        if stored:
            if time.time() > stored.expires_at:
                del self._access_tokens[token]
                return None
            return {
                "email": stored.user_email,
                "name": stored.user_name,
                "client_id": stored.client_id,
                "scope": stored.scope,
            }

        return None

    def cleanup_expired(self) -> None:
        """Remove expired codes and tokens."""
        now = time.time()

        # Clean auth codes
        expired_codes = [k for k, v in self._auth_codes.items() if now > v.expires_at]
        for code in expired_codes:
            del self._auth_codes[code]

        # Clean access tokens (only opaque ones)
        expired_tokens = [k for k, v in self._access_tokens.items() if now > v.expires_at]
        for token in expired_tokens:
            del self._access_tokens[token]

        # Clean pending auth
        expired_auth = [k for k, v in self._pending_auth.items() if now - v["created_at"] > 600]
        for state in expired_auth:
            del self._pending_auth[state]


# Global instance
_oauth_server: Optional[MCPOAuthServer] = None


def get_oauth_server() -> Optional[MCPOAuthServer]:
    """Get the global OAuth server instance."""
    return _oauth_server


def init_oauth_server(
    issuer: str,
    jwt_secret: str,
    google_client_id: str,
    google_client_secret: str,
    allowed_domain: Optional[str] = None,
    allowed_emails: Optional[List[str]] = None,
    token_expiration_seconds: int = 3600,
) -> MCPOAuthServer:
    """Initialize the global OAuth server."""
    global _oauth_server
    _oauth_server = MCPOAuthServer(
        issuer=issuer,
        jwt_secret=jwt_secret,
        google_client_id=google_client_id,
        google_client_secret=google_client_secret,
        allowed_domain=allowed_domain,
        allowed_emails=allowed_emails,
        token_expiration_seconds=token_expiration_seconds,
    )
    return _oauth_server
