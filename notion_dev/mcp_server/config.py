"""
NOTION FEATURES: ND03
MODULES: NotionDev
DESCRIPTION: Configuration management for MCP server modes (local stdio / remote SSE)
LAST_SYNC: 2025-12-31
"""

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List


class TransportMode(Enum):
    """Transport modes for MCP server."""
    STDIO = "stdio"
    SSE = "sse"


@dataclass
class ServerConfig:
    """Configuration for the MCP server.

    Supports two modes:
    - Local (stdio): For Claude Code CLI integration (ND02)
    - Remote (SSE): For Claude.ai web interface with OAuth (ND03)
    """

    # Transport settings
    transport: TransportMode = TransportMode.STDIO
    port: int = 8000
    host: str = "0.0.0.0"

    # Authentication settings (only for remote mode)
    auth_enabled: bool = False
    google_client_id: Optional[str] = None
    google_client_secret: Optional[str] = None
    allowed_email_domain: Optional[str] = None
    allowed_emails: List[str] = field(default_factory=list)  # Specific emails allowed
    jwt_secret: Optional[str] = None
    jwt_expiration_hours: int = 1

    # Service account tokens (for remote mode)
    service_notion_token: Optional[str] = None
    service_asana_token: Optional[str] = None

    # Repository cache settings (for remote mode)
    repos_cache_dir: str = "/data/repos"
    repos_cache_ttl_hours: int = 1

    # Tools configuration
    disabled_tools_remote: List[str] = field(default_factory=lambda: [
        "notiondev_check_installation",
        "notiondev_get_install_instructions",
        "notiondev_work_on_ticket",
        "notiondev_mark_done",
    ])

    remote_only_tools: List[str] = field(default_factory=lambda: [
        "notiondev_read_file",
        "notiondev_search_code",
        "notiondev_list_files",
        "notiondev_prepare_feature_context",
    ])

    @property
    def is_remote(self) -> bool:
        """Check if running in remote mode (SSE with auth)."""
        return self.transport == TransportMode.SSE and self.auth_enabled

    @property
    def is_local(self) -> bool:
        """Check if running in local mode (stdio)."""
        return self.transport == TransportMode.STDIO

    def is_tool_enabled(self, tool_name: str) -> bool:
        """Check if a tool should be enabled based on current mode.

        Args:
            tool_name: Name of the MCP tool

        Returns:
            True if the tool should be available
        """
        if self.is_remote:
            # In remote mode, disable local-only tools
            if tool_name in self.disabled_tools_remote:
                return False
            return True
        else:
            # In local mode, disable remote-only tools
            if tool_name in self.remote_only_tools:
                return False
            return True

    @classmethod
    def from_env(cls) -> "ServerConfig":
        """Create configuration from environment variables.

        Environment variables:
            MCP_TRANSPORT: "stdio" or "sse" (default: stdio)
            MCP_PORT: Server port for SSE mode (default: 8000)
            MCP_HOST: Server host for SSE mode (default: 0.0.0.0)
            MCP_AUTH_ENABLED: "true" or "false" (default: false)
            GOOGLE_CLIENT_ID: Google OAuth client ID
            GOOGLE_CLIENT_SECRET: Google OAuth client secret
            ALLOWED_EMAIL_DOMAIN: Restrict login to this domain (e.g., grand-shooting.com)
            ALLOWED_EMAILS: Comma-separated list of specific emails allowed (e.g., "user@example.com,admin@example.com")
            JWT_SECRET: Secret for signing JWT tokens
            JWT_EXPIRATION_HOURS: JWT token lifetime (default: 1)
            SERVICE_NOTION_TOKEN: Notion token for service account
            SERVICE_ASANA_TOKEN: Asana PAT for service account
            REPOS_CACHE_DIR: Directory for cloned repos (default: /data/repos)
            REPOS_CACHE_TTL_HOURS: TTL for cached repos (default: 1)
        """
        transport_str = os.environ.get("MCP_TRANSPORT", "stdio").lower()
        transport = TransportMode.SSE if transport_str == "sse" else TransportMode.STDIO

        # Parse allowed emails from comma-separated string
        allowed_emails_str = os.environ.get("ALLOWED_EMAILS", "")
        allowed_emails = [e.strip().lower() for e in allowed_emails_str.split(",") if e.strip()]

        return cls(
            transport=transport,
            port=int(os.environ.get("MCP_PORT", "8000")),
            host=os.environ.get("MCP_HOST", "0.0.0.0"),
            auth_enabled=os.environ.get("MCP_AUTH_ENABLED", "false").lower() == "true",
            google_client_id=os.environ.get("GOOGLE_CLIENT_ID"),
            google_client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
            allowed_email_domain=os.environ.get("ALLOWED_EMAIL_DOMAIN"),
            allowed_emails=allowed_emails,
            jwt_secret=os.environ.get("JWT_SECRET"),
            jwt_expiration_hours=int(os.environ.get("JWT_EXPIRATION_HOURS", "1")),
            service_notion_token=os.environ.get("SERVICE_NOTION_TOKEN"),
            service_asana_token=os.environ.get("SERVICE_ASANA_TOKEN"),
            repos_cache_dir=os.environ.get("REPOS_CACHE_DIR", "/data/repos"),
            repos_cache_ttl_hours=int(os.environ.get("REPOS_CACHE_TTL_HOURS", "1")),
        )

    @classmethod
    def from_args(
        cls,
        transport: str = "stdio",
        port: int = 8000,
        host: str = "0.0.0.0",
        auth: bool = False,
    ) -> "ServerConfig":
        """Create configuration from CLI arguments, with env vars as fallback.

        Args:
            transport: "stdio" or "sse"
            port: Server port for SSE mode
            host: Server host for SSE mode
            auth: Enable authentication

        Returns:
            ServerConfig instance
        """
        # Start with environment-based config
        config = cls.from_env()

        # Override with CLI arguments
        config.transport = TransportMode.SSE if transport == "sse" else TransportMode.STDIO
        config.port = port
        config.host = host

        # Auth can be enabled via CLI or env
        if auth:
            config.auth_enabled = True

        return config

    def validate(self) -> List[str]:
        """Validate the configuration.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        if self.is_remote:
            # Remote mode requires OAuth configuration
            if not self.google_client_id:
                errors.append("GOOGLE_CLIENT_ID is required for remote mode")
            if not self.google_client_secret:
                errors.append("GOOGLE_CLIENT_SECRET is required for remote mode")
            if not self.jwt_secret:
                errors.append("JWT_SECRET is required for remote mode")
            if not self.service_notion_token:
                errors.append("SERVICE_NOTION_TOKEN is required for remote mode")
            if not self.service_asana_token:
                errors.append("SERVICE_ASANA_TOKEN is required for remote mode")

        return errors

    def __repr__(self) -> str:
        """String representation (hides secrets)."""
        return (
            f"ServerConfig("
            f"transport={self.transport.value}, "
            f"port={self.port}, "
            f"auth_enabled={self.auth_enabled}, "
            f"allowed_domain={self.allowed_email_domain}"
            f")"
        )


# Global configuration instance
_config: Optional[ServerConfig] = None


def get_config() -> ServerConfig:
    """Get the global server configuration.

    Returns:
        The current ServerConfig instance
    """
    global _config
    if _config is None:
        _config = ServerConfig.from_env()
    return _config


def set_config(config: ServerConfig) -> None:
    """Set the global server configuration.

    Args:
        config: ServerConfig instance to use
    """
    global _config
    _config = config
