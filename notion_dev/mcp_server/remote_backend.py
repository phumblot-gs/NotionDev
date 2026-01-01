"""
NOTION FEATURES: ND03
MODULES: NotionDev
DESCRIPTION: Backend for remote MCP server mode - uses service tokens instead of local config
LAST_SYNC: 2025-12-31
"""

import os
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from functools import lru_cache

logger = logging.getLogger(__name__)


@dataclass
class RemoteUser:
    """Represents an authenticated user in remote mode."""
    email: str
    name: str
    asana_user_gid: Optional[str] = None

    @property
    def is_resolved(self) -> bool:
        """Check if the user's Asana identity has been resolved."""
        return self.asana_user_gid is not None


class RemoteBackend:
    """Backend for remote MCP server mode.

    Uses service account tokens (configured via environment variables)
    instead of local user config files. Maps OAuth-authenticated users
    to their Asana identities for proper ticket filtering.
    """

    def __init__(self):
        """Initialize the remote backend from environment variables."""
        from .config import get_config

        self.config = get_config()

        # Service tokens from environment
        self._notion_token = self.config.service_notion_token
        self._asana_token = self.config.service_asana_token

        # Lazy-loaded clients
        self._asana_client = None
        self._notion_client = None

        # User cache: email -> RemoteUser
        self._user_cache: Dict[str, RemoteUser] = {}

        # Current user context (set per-request)
        self._current_user: Optional[RemoteUser] = None

        # Asana workspace and portfolio from environment
        self._workspace_gid = os.environ.get("ASANA_WORKSPACE_GID", "")
        self._portfolio_gid = os.environ.get("ASANA_PORTFOLIO_GID", "")

        # Notion database IDs from environment
        self._notion_modules_db = os.environ.get("NOTION_MODULES_DATABASE_ID", "")
        self._notion_features_db = os.environ.get("NOTION_FEATURES_DATABASE_ID", "")

    @property
    def is_configured(self) -> bool:
        """Check if the remote backend is properly configured."""
        return bool(self._asana_token and self._notion_token)

    @property
    def asana_client(self):
        """Get the Asana client (lazy-loaded)."""
        if self._asana_client is None:
            if not self._asana_token:
                raise RuntimeError("SERVICE_ASANA_TOKEN not configured")

            from ..core.asana_client import AsanaClient

            # Use a dummy user_gid initially - will be overridden per-request
            self._asana_client = AsanaClient(
                access_token=self._asana_token,
                workspace_gid=self._workspace_gid,
                user_gid="",  # Will be set per-request
                portfolio_gid=self._portfolio_gid or None
            )
        return self._asana_client

    @property
    def notion_client(self):
        """Get the Notion client (lazy-loaded)."""
        if self._notion_client is None:
            if not self._notion_token:
                raise RuntimeError("SERVICE_NOTION_TOKEN not configured")

            from ..core.notion_client import NotionClient

            self._notion_client = NotionClient(
                token=self._notion_token,
                modules_db_id=self._notion_modules_db,
                features_db_id=self._notion_features_db
            )
        return self._notion_client

    def set_current_user(self, email: str, name: str) -> RemoteUser:
        """Set the current user context from OAuth.

        Args:
            email: User's email from OAuth
            name: User's display name from OAuth

        Returns:
            RemoteUser with resolved Asana identity (if found)
        """
        # Check cache first
        if email in self._user_cache:
            self._current_user = self._user_cache[email]
            logger.info(f"Using cached user: {email} -> {self._current_user.asana_user_gid}")
            return self._current_user

        # Create new user and try to resolve Asana identity
        user = RemoteUser(email=email, name=name)

        try:
            asana_user = self.asana_client.find_user_by_email(email)
            if asana_user:
                user.asana_user_gid = asana_user.get('gid')
                logger.info(f"Resolved Asana user: {email} -> {user.asana_user_gid}")
            else:
                logger.warning(f"Could not find Asana user for email: {email}")
        except Exception as e:
            logger.error(f"Error resolving Asana user for {email}: {e}")

        # Cache and set as current
        self._user_cache[email] = user
        self._current_user = user
        return user

    def clear_current_user(self):
        """Clear the current user context."""
        self._current_user = None

    @property
    def current_user(self) -> Optional[RemoteUser]:
        """Get the current user context."""
        return self._current_user

    def get_asana_client_for_user(self):
        """Get an Asana client configured for the current user.

        Returns:
            AsanaClient with user_gid set to current user's Asana ID
        """
        if not self._current_user:
            raise RuntimeError("No current user context")

        if not self._current_user.asana_user_gid:
            raise RuntimeError(f"User {self._current_user.email} has no Asana identity")

        from ..core.asana_client import AsanaClient

        return AsanaClient(
            access_token=self._asana_token,
            workspace_gid=self._workspace_gid,
            user_gid=self._current_user.asana_user_gid,
            portfolio_gid=self._portfolio_gid or None
        )

    # =========================================================================
    # High-level operations (used by MCP tools in remote mode)
    # =========================================================================

    def list_tickets(self) -> List[Dict[str, Any]]:
        """List tickets assigned to the current user.

        Returns:
            List of ticket dicts
        """
        client = self.get_asana_client_for_user()
        tasks = client.get_my_tasks()

        return [
            {
                "id": task.gid,
                "name": task.name,
                "feature_code": task.feature_code,
                "project": task.project_name,
                "completed": task.completed,
                "due_on": task.due_on,
            }
            for task in tasks
        ]

    def get_ticket(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific ticket by ID.

        Args:
            task_id: Asana task GID

        Returns:
            Ticket dict or None
        """
        task = self.asana_client.get_task(task_id)
        if not task:
            return None

        return {
            "id": task.gid,
            "name": task.name,
            "notes": task.notes,
            "feature_code": task.feature_code,
            "project": task.project_name,
            "completed": task.completed,
            "due_on": task.due_on,
            "assignee_gid": task.assignee_gid,
            "created_by_gid": task.created_by_gid,
        }

    def add_comment(self, task_id: str, message: str) -> bool:
        """Add a comment to a ticket.

        Args:
            task_id: Asana task GID
            message: Comment text

        Returns:
            True if successful
        """
        return self.asana_client.add_comment_to_task(task_id, message)

    def list_projects(self) -> List[Dict[str, Any]]:
        """List projects from the portfolio.

        Returns:
            List of project dicts
        """
        projects = self.asana_client.get_portfolio_projects()
        return [
            {
                "gid": p.gid,
                "name": p.name,
            }
            for p in projects
        ]

    def create_ticket(
        self,
        name: str,
        notes: str = "",
        project_gid: Optional[str] = None,
        due_on: Optional[str] = None,
        feature_code: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Create a new ticket.

        Args:
            name: Ticket title
            notes: Description
            project_gid: Target project (uses first portfolio project if not specified)
            due_on: Due date (YYYY-MM-DD)
            feature_code: Feature code to reference

        Returns:
            Created ticket dict or None
        """
        if not self._current_user or not self._current_user.asana_user_gid:
            logger.error("Cannot create ticket: no current user")
            return None

        # Add feature code reference to notes if provided
        if feature_code and feature_code not in notes:
            notes = f"**Feature**: {feature_code}\n\n{notes}"

        task = self.asana_client.create_task(
            name=name,
            notes=notes,
            project_gid=project_gid,
            assignee_gid=self._current_user.asana_user_gid,
            due_on=due_on
        )

        if not task:
            return None

        return {
            "id": task.gid,
            "name": task.name,
            "url": f"https://app.asana.com/0/{task.project_gid}/{task.gid}"
        }

    def update_ticket(
        self,
        task_id: str,
        name: Optional[str] = None,
        notes: Optional[str] = None,
        append_notes: bool = False,
        due_on: Optional[str] = None,
        assignee_gid: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Update an existing ticket.

        Args:
            task_id: Asana task GID
            name: New title
            notes: New notes
            append_notes: If True, append to existing notes
            due_on: New due date
            assignee_gid: New assignee

        Returns:
            Updated ticket dict or None
        """
        task = self.asana_client.update_task(
            task_gid=task_id,
            name=name,
            notes=notes,
            append_notes=append_notes,
            due_on=due_on,
            assignee_gid=assignee_gid
        )

        if not task:
            return None

        return self.get_ticket(task_id)

    def get_info(self) -> Dict[str, Any]:
        """Get server and user info.

        Returns:
            Info dict
        """
        info = {
            "mode": "remote",
            "configured": self.is_configured,
        }

        if self._current_user:
            info["user"] = {
                "email": self._current_user.email,
                "name": self._current_user.name,
                "asana_resolved": self._current_user.is_resolved,
                "asana_user_gid": self._current_user.asana_user_gid,
            }

        # Test connections
        if self.is_configured:
            try:
                connection_test = self.asana_client.test_connection()
                info["asana"] = {
                    "connected": connection_test.get("success", False),
                    "workspace": connection_test.get("workspace"),
                    "portfolio": connection_test.get("portfolio"),
                }
            except Exception as e:
                info["asana"] = {"connected": False, "error": str(e)}

        return info

    # =========================================================================
    # Notion operations
    # =========================================================================

    def list_modules(self) -> List[Dict[str, Any]]:
        """List all modules from Notion."""
        modules = self.notion_client.get_modules()
        return [
            {
                "code_prefix": m.code_prefix,
                "name": m.name,
                "description": m.description,
                "application": m.application,
            }
            for m in modules
        ]

    def get_module(self, code_prefix: str) -> Optional[Dict[str, Any]]:
        """Get a specific module by code prefix."""
        module = self.notion_client.get_module_by_prefix(code_prefix)
        if not module:
            return None

        return {
            "code_prefix": module.code_prefix,
            "name": module.name,
            "description": module.description,
            "application": module.application,
            "content": module.content,
        }

    def list_features(self, module_prefix: Optional[str] = None) -> List[Dict[str, Any]]:
        """List features, optionally filtered by module."""
        if module_prefix:
            features = self.notion_client.get_features_by_module(module_prefix)
        else:
            features = self.notion_client.get_all_features()

        return [
            {
                "code": f.code,
                "name": f.name,
                "module_prefix": f.module_prefix,
            }
            for f in features
        ]

    def get_feature(self, code: str) -> Optional[Dict[str, Any]]:
        """Get a specific feature by code."""
        feature = self.notion_client.get_feature_by_code(code)
        if not feature:
            return None

        return {
            "code": feature.code,
            "name": feature.name,
            "module_prefix": feature.module_prefix,
            "content": feature.content,
        }


# Global instance (lazy-loaded)
_remote_backend: Optional[RemoteBackend] = None


def get_remote_backend() -> RemoteBackend:
    """Get the global remote backend instance."""
    global _remote_backend
    if _remote_backend is None:
        _remote_backend = RemoteBackend()
    return _remote_backend


def is_remote_mode() -> bool:
    """Check if we're running in remote mode."""
    from .config import get_config
    return get_config().is_remote
