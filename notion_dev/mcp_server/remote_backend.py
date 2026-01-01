"""
NOTION FEATURES: ND03
MODULES: NotionDev
DESCRIPTION: Backend for remote MCP server mode - uses service tokens instead of local config
LAST_SYNC: 2025-12-31
"""

import os
import logging
from contextvars import ContextVar
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from functools import lru_cache

logger = logging.getLogger(__name__)

# Context variable for current user - isolated per async task/request
# This ensures each SSE connection has its own user context
_current_user_context: ContextVar[Optional["RemoteUser"]] = ContextVar(
    "current_user_context", default=None
)


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

        # User cache: email -> RemoteUser (shared across all sessions for efficiency)
        self._user_cache: Dict[str, RemoteUser] = {}

        # NOTE: Current user is now stored in _current_user_context (ContextVar)
        # to ensure isolation between concurrent SSE connections.
        # The old self._current_user is removed.

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

        This uses a ContextVar to ensure isolation between concurrent
        SSE connections. Each async task/request gets its own user context.

        Args:
            email: User's email from OAuth
            name: User's display name from OAuth

        Returns:
            RemoteUser with resolved Asana identity (if found)
        """
        # Check cache first (shared cache is fine - it's read-only user data)
        if email in self._user_cache:
            user = self._user_cache[email]
            _current_user_context.set(user)
            logger.info(f"Using cached user: {email} -> {user.asana_user_gid}")
            return user

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

        # Cache for future requests and set in current context
        self._user_cache[email] = user
        _current_user_context.set(user)
        return user

    def clear_current_user(self):
        """Clear the current user context for this async task."""
        _current_user_context.set(None)

    @property
    def current_user(self) -> Optional[RemoteUser]:
        """Get the current user context for this async task.

        Returns the user set by set_current_user() in the current
        async context. Different SSE connections will have different users.
        """
        return _current_user_context.get()

    def get_asana_client_for_user(self):
        """Get an Asana client configured for the current user.

        Returns:
            AsanaClient with user_gid set to current user's Asana ID

        Raises:
            RuntimeError: If no user context is set or user has no Asana identity
        """
        current_user = self.current_user
        if not current_user:
            raise RuntimeError("No current user context - call set_current_user() first")

        if not current_user.asana_user_gid:
            raise RuntimeError(f"User {current_user.email} has no Asana identity")

        from ..core.asana_client import AsanaClient

        return AsanaClient(
            access_token=self._asana_token,
            workspace_gid=self._workspace_gid,
            user_gid=current_user.asana_user_gid,
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
        current_user = self.current_user
        if not current_user or not current_user.asana_user_gid:
            logger.error("Cannot create ticket: no current user")
            return None

        # Add feature code reference to notes if provided
        if feature_code and feature_code not in notes:
            notes = f"**Feature**: {feature_code}\n\n{notes}"

        task = self.asana_client.create_task(
            name=name,
            notes=notes,
            project_gid=project_gid,
            assignee_gid=current_user.asana_user_gid,
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

        current_user = self.current_user
        if current_user:
            info["user"] = {
                "email": current_user.email,
                "name": current_user.name,
                "asana_resolved": current_user.is_resolved,
                "asana_user_gid": current_user.asana_user_gid,
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
            "repository_url": module.repository_url,
            "branch": module.branch,
            "code_path": module.code_path,
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
                "module_name": f.module_name,
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
            "module_name": feature.module_name,
            "content": feature.content,
        }

    # =========================================================================
    # Repository operations (for remote mode)
    # =========================================================================

    def clone_module(self, code_prefix: str, force: bool = False) -> Dict[str, Any]:
        """Clone a module's repository for code analysis.

        Args:
            code_prefix: Module code prefix (e.g., 'ND', 'CC')
            force: If True, remove existing clone and re-clone

        Returns:
            Dict with clone status and path
        """
        # Get module info from Notion
        module = self.get_module(code_prefix)
        if not module:
            return {"error": f"Module '{code_prefix}' not found"}

        repository_url = module.get("repository_url")
        if not repository_url:
            return {
                "error": f"Module '{module['name']}' does not have a repository_url configured",
                "hint": "Add the repository_url property to the module in Notion"
            }

        branch = module.get("branch")
        code_path = module.get("code_path")

        # Use GitHubClient for clone operations
        from ..core.github_client import GitHubClient

        # Get clone directory from config
        clone_dir = self.config.repos_cache_dir

        github = GitHubClient(
            token=os.environ.get("GITHUB_TOKEN"),  # Optional, for private repos
            clone_dir=clone_dir,
            shallow_clone=True
        )

        try:
            result = github.clone_repository(
                repo_url=repository_url,
                branch=branch,
                force=force
            )

            if result["success"]:
                response = {
                    "success": True,
                    "message": f"Repository cloned successfully for module '{module['name']}'",
                    "module": {
                        "name": module["name"],
                        "code_prefix": code_prefix,
                        "repository_url": repository_url,
                        "branch": branch or "default"
                    },
                    "clone": {
                        "path": result["path"],
                        "code_path": code_path
                    },
                    "important": (
                        "The repository is cloned on the MCP server, NOT in your local environment. "
                        "You CANNOT access it via shell/bash commands. "
                        "Use these NotionDev tools to interact with the code:"
                    ),
                    "available_tools": [
                        "notiondev_list_files - List files in the repository",
                        "notiondev_read_file - Read file contents",
                        "notiondev_search_code - Search for patterns in code",
                        "notiondev_prepare_feature_context - Get aggregated context for a feature"
                    ]
                }

                if code_path:
                    full_code_path = os.path.join(result["path"], code_path)
                    response["clone"]["full_code_path"] = full_code_path

                return response
            else:
                return {
                    "error": result.get("error", "Clone failed"),
                    "repository_url": repository_url
                }

        except Exception as e:
            logger.error(f"Clone error for {code_prefix}: {e}")
            return {"error": str(e)}

    def get_cloned_repo_info(self, code_prefix: str) -> Dict[str, Any]:
        """Get information about a cloned repository.

        Args:
            code_prefix: Module code prefix

        Returns:
            Dict with repository info or error
        """
        module = self.get_module(code_prefix)
        if not module:
            return {"error": f"Module '{code_prefix}' not found"}

        repository_url = module.get("repository_url")
        if not repository_url:
            return {
                "error": f"Module '{module['name']}' does not have a repository_url configured"
            }

        from ..core.github_client import GitHubClient

        clone_dir = self.config.repos_cache_dir
        github = GitHubClient(clone_dir=clone_dir)

        # Get the local path for this repo
        local_path = github._get_repo_local_path(repository_url)
        info = github.get_repository_info(local_path)

        if not info.get("exists"):
            return {
                "error": f"Repository not cloned for module '{module['name']}'",
                "hint": f"Use notiondev_clone_module('{code_prefix}') to clone first"
            }

        return {
            "module": {
                "name": module["name"],
                "code_prefix": code_prefix
            },
            "repository": {
                "path": info["path"],
                "branch": info["branch"],
                "remote_url": info["remote_url"],
                "last_commit": info["last_commit"],
                "code_path": module.get("code_path"),
            },
            "note": (
                "This path is on the MCP server. Use notiondev_list_files, "
                "notiondev_read_file, or notiondev_search_code to access code. "
                "Shell/bash commands will NOT work."
            )
        }

    # =========================================================================
    # Notion write operations (for remote mode)
    # =========================================================================

    def create_module(
        self,
        name: str,
        description: str,
        code_prefix: str,
        application: str = "Backend",
        content_markdown: str = ""
    ) -> Optional[Dict[str, Any]]:
        """Create a new module in Notion.

        Args:
            name: Module name
            description: Short description
            code_prefix: 2-3 character code prefix
            application: One of 'Backend', 'Frontend', 'Service'
            content_markdown: Documentation content

        Returns:
            Created module dict or None
        """
        module = self.notion_client.create_module(
            name=name,
            description=description,
            code_prefix=code_prefix,
            application=application,
            content_markdown=content_markdown
        )

        if not module:
            return None

        return {
            "code_prefix": module.code_prefix,
            "name": module.name,
            "description": module.description,
            "application": module.application,
            "notion_id": module.notion_id,
        }

    def create_feature(
        self,
        name: str,
        module_prefix: str,
        content_markdown: str = "",
        plan: str = "",
        user_rights: str = ""
    ) -> Optional[Dict[str, Any]]:
        """Create a new feature in Notion.

        Args:
            name: Feature name
            module_prefix: Parent module's code prefix
            content_markdown: Documentation content
            plan: Comma-separated plans
            user_rights: Comma-separated user rights

        Returns:
            Created feature dict or None
        """
        # Parse plan and user_rights
        plan_list = [p.strip() for p in plan.split(",") if p.strip()] if plan else []
        rights_list = [r.strip() for r in user_rights.split(",") if r.strip()] if user_rights else []

        # NotionClient.create_feature now handles module lookup and code generation
        feature = self.notion_client.create_feature(
            name=name,
            module_prefix=module_prefix,
            plan=plan_list,
            user_rights=rights_list,
            content_markdown=content_markdown
        )

        if not feature:
            return None

        return {
            "code": feature.code,
            "name": feature.name,
            "module_name": feature.module_name,
            "notion_id": feature.notion_id,
        }

    def update_module_content(
        self,
        code_prefix: str,
        content_markdown: str,
        replace: bool = True
    ) -> Dict[str, Any]:
        """Update a module's content.

        Args:
            code_prefix: Module code prefix
            content_markdown: New content
            replace: If True, replace. If False, append.

        Returns:
            Success dict or error dict
        """
        success = self.notion_client.update_module_content(
            code_prefix=code_prefix,
            content_markdown=content_markdown,
            replace=replace
        )

        if success:
            return {"success": True, "message": f"Module {code_prefix} content updated"}
        else:
            return {"error": f"Failed to update module {code_prefix} content"}

    def update_feature_content(
        self,
        code: str,
        content_markdown: str,
        replace: bool = True
    ) -> Dict[str, Any]:
        """Update a feature's content.

        Args:
            code: Feature code
            content_markdown: New content
            replace: If True, replace. If False, append.

        Returns:
            Success dict or error dict
        """
        success = self.notion_client.update_feature_content(
            code=code,
            content_markdown=content_markdown,
            replace=replace
        )

        if success:
            return {"success": True, "message": f"Feature {code} content updated"}
        else:
            return {"error": f"Failed to update feature {code} content"}


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
