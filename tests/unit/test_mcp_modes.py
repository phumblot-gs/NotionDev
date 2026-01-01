# tests/unit/test_mcp_modes.py
"""Tests for MCP server modes (local vs remote).

These tests ensure that:
1. Configuration correctly identifies local vs remote mode
2. Tools are properly enabled/disabled based on mode
3. Imports work correctly in both modes
4. Remote backend functions work with mocked dependencies

IMPORTANT: Run these tests before deploying to catch import errors early!
"""

import pytest
import os
import json
from unittest.mock import patch, MagicMock, PropertyMock
from pathlib import Path


class TestServerConfig:
    """Test ServerConfig class for local and remote modes."""

    def test_default_config_is_local_mode(self):
        """Default configuration should be local (stdio) mode."""
        from notion_dev.mcp_server.config import ServerConfig, TransportMode

        config = ServerConfig()

        assert config.transport == TransportMode.STDIO
        assert config.is_local is True
        assert config.is_remote is False

    def test_remote_mode_requires_sse_and_auth(self):
        """Remote mode requires both SSE transport and auth enabled."""
        from notion_dev.mcp_server.config import ServerConfig, TransportMode

        # SSE without auth is NOT remote
        config_sse_no_auth = ServerConfig(transport=TransportMode.SSE, auth_enabled=False)
        assert config_sse_no_auth.is_remote is False

        # SSE with auth IS remote
        config_sse_with_auth = ServerConfig(transport=TransportMode.SSE, auth_enabled=True)
        assert config_sse_with_auth.is_remote is True

        # STDIO with auth is still local
        config_stdio_with_auth = ServerConfig(transport=TransportMode.STDIO, auth_enabled=True)
        assert config_stdio_with_auth.is_remote is False
        assert config_stdio_with_auth.is_local is True

    def test_local_mode_disables_remote_only_tools(self):
        """In local mode, remote-only tools should be disabled."""
        from notion_dev.mcp_server.config import ServerConfig, TransportMode

        config = ServerConfig(transport=TransportMode.STDIO)

        # Remote-only tools should be disabled
        assert config.is_tool_enabled("notiondev_read_file") is False
        assert config.is_tool_enabled("notiondev_search_code") is False
        assert config.is_tool_enabled("notiondev_list_files") is False
        assert config.is_tool_enabled("notiondev_prepare_feature_context") is False

        # Normal tools should be enabled
        assert config.is_tool_enabled("notiondev_list_tickets") is True
        assert config.is_tool_enabled("notiondev_get_module") is True

    def test_remote_mode_disables_local_only_tools(self):
        """In remote mode, local-only tools should be disabled."""
        from notion_dev.mcp_server.config import ServerConfig, TransportMode

        config = ServerConfig(transport=TransportMode.SSE, auth_enabled=True)

        # Local-only tools should be disabled
        assert config.is_tool_enabled("notiondev_check_installation") is False
        assert config.is_tool_enabled("notiondev_get_install_instructions") is False
        assert config.is_tool_enabled("notiondev_work_on_ticket") is False
        assert config.is_tool_enabled("notiondev_mark_done") is False

        # Remote-only tools should be enabled
        assert config.is_tool_enabled("notiondev_read_file") is True
        assert config.is_tool_enabled("notiondev_list_files") is True

    @patch.dict(os.environ, {
        "MCP_TRANSPORT": "sse",
        "MCP_AUTH_ENABLED": "true",
        "MCP_PORT": "9000",
    }, clear=False)
    def test_config_from_env_remote(self):
        """Test configuration from environment variables for remote mode."""
        from notion_dev.mcp_server.config import ServerConfig, TransportMode

        config = ServerConfig.from_env()

        assert config.transport == TransportMode.SSE
        assert config.auth_enabled is True
        assert config.port == 9000
        assert config.is_remote is True

    @patch.dict(os.environ, {
        "MCP_TRANSPORT": "stdio",
    }, clear=False)
    def test_config_from_env_local(self):
        """Test configuration from environment variables for local mode."""
        from notion_dev.mcp_server.config import ServerConfig, TransportMode

        config = ServerConfig.from_env()

        assert config.transport == TransportMode.STDIO
        assert config.is_local is True

    def test_config_validation_remote_mode(self):
        """Remote mode should require OAuth and service tokens."""
        from notion_dev.mcp_server.config import ServerConfig, TransportMode

        # Remote mode without required tokens should fail validation
        config = ServerConfig(
            transport=TransportMode.SSE,
            auth_enabled=True,
            # Missing: google_client_id, google_client_secret, jwt_secret, service tokens
        )

        errors = config.validate()

        assert len(errors) > 0
        assert any("GOOGLE_CLIENT_ID" in e for e in errors)
        assert any("JWT_SECRET" in e for e in errors)
        assert any("SERVICE_NOTION_TOKEN" in e for e in errors)

    def test_config_validation_local_mode_no_errors(self):
        """Local mode should have no validation errors."""
        from notion_dev.mcp_server.config import ServerConfig, TransportMode

        config = ServerConfig(transport=TransportMode.STDIO)

        errors = config.validate()

        assert len(errors) == 0


class TestRemoteBackendImports:
    """Test that all imports in remote_backend work correctly.

    This is critical to catch ImportError before deployment!
    """

    def test_remote_backend_can_be_imported(self):
        """Remote backend module should be importable."""
        from notion_dev.mcp_server import remote_backend

        assert hasattr(remote_backend, 'RemoteBackend')
        assert hasattr(remote_backend, 'get_remote_backend')
        assert hasattr(remote_backend, 'is_remote_mode')

    def test_get_remote_backend_function_exists(self):
        """get_remote_backend function should exist and be callable."""
        from notion_dev.mcp_server.remote_backend import get_remote_backend

        assert callable(get_remote_backend)

    def test_is_remote_mode_function_exists(self):
        """is_remote_mode function should exist and be callable."""
        from notion_dev.mcp_server.remote_backend import is_remote_mode

        assert callable(is_remote_mode)

    def test_remote_user_dataclass(self):
        """RemoteUser should be a valid dataclass."""
        from notion_dev.mcp_server.remote_backend import RemoteUser

        user = RemoteUser(email="test@example.com", name="Test User")

        assert user.email == "test@example.com"
        assert user.name == "Test User"
        assert user.asana_user_gid is None
        assert user.is_resolved is False


class TestCodeToolsImports:
    """Test that all imports in code_tools work correctly."""

    def test_code_tools_can_be_imported(self):
        """Code tools module should be importable."""
        from notion_dev.mcp_server import code_tools

        assert hasattr(code_tools, 'CodeReader')
        assert hasattr(code_tools, 'get_code_reader')

    def test_code_reader_class_exists(self):
        """CodeReader class should have all required methods."""
        from notion_dev.mcp_server.code_tools import CodeReader

        assert hasattr(CodeReader, 'get_repo_path')
        assert hasattr(CodeReader, 'read_file')
        assert hasattr(CodeReader, 'search_code')
        assert hasattr(CodeReader, 'list_files')
        assert hasattr(CodeReader, 'prepare_feature_context')

    def test_code_reader_methods_accept_repository_url(self):
        """All CodeReader methods should accept repository_url parameter."""
        from notion_dev.mcp_server.code_tools import CodeReader
        import inspect

        methods_with_repo_url = ['get_repo_path', 'read_file', 'search_code', 'list_files', 'prepare_feature_context']

        for method_name in methods_with_repo_url:
            method = getattr(CodeReader, method_name)
            sig = inspect.signature(method)
            param_names = list(sig.parameters.keys())

            assert 'repository_url' in param_names, f"{method_name} is missing repository_url parameter"


class TestServerImports:
    """Test that server.py imports work correctly in both modes.

    This is the critical test that would have caught the get_backend error!
    """

    def test_server_module_can_be_imported(self):
        """Server module should be importable without errors."""
        # This will raise ImportError if there are broken imports
        from notion_dev.mcp_server import server

        assert server is not None

    def test_server_imports_get_remote_backend_correctly(self):
        """Server should use get_remote_backend, not get_backend."""
        import ast

        server_path = Path(__file__).parent.parent.parent / "notion_dev" / "mcp_server" / "server.py"

        with open(server_path, "r") as f:
            content = f.read()

        # Check that we don't have the wrong import
        assert "from .remote_backend import get_backend" not in content, \
            "Found incorrect import 'get_backend' - should be 'get_remote_backend'"

        # The correct imports that should exist
        assert "from .remote_backend import get_remote_backend" in content or \
               "from .remote_backend import is_remote_mode, get_remote_backend" in content, \
            "Missing correct import 'get_remote_backend'"


class TestCodeReaderWithMockedRepo:
    """Test CodeReader functionality with mocked repositories."""

    @pytest.fixture
    def temp_repo(self, tmp_path):
        """Create a temporary repository structure."""
        repo_dir = tmp_path / "test_repo"
        repo_dir.mkdir()

        # Create some test files
        (repo_dir / "main.py").write_text("""# NOTION FEATURES: TEST01
# MODULES: TestModule
def main():
    print("Hello, World!")
""")

        (repo_dir / "utils.py").write_text("""# NOTION FEATURES: TEST01
def helper():
    # TEST01 related code
    return True
""")

        (repo_dir / "README.md").write_text("# Test Repository")

        # Create a subdirectory
        (repo_dir / "src").mkdir()
        (repo_dir / "src" / "app.py").write_text("""def app():
    pass
""")

        return repo_dir

    def test_get_repo_path_returns_none_for_missing_repo(self, tmp_path):
        """Should return None if repository doesn't exist."""
        from notion_dev.mcp_server.code_tools import CodeReader

        reader = CodeReader(repos_base_dir=str(tmp_path))

        result = reader.get_repo_path("NONEXISTENT")

        assert result is None

    def test_get_repo_path_finds_repo_by_prefix(self, temp_repo, tmp_path):
        """Should find repository by module prefix."""
        from notion_dev.mcp_server.code_tools import CodeReader

        # Create repos base with the temp_repo inside
        repos_base = tmp_path / "repos"
        repos_base.mkdir()
        # Rename temp_repo to match a module prefix
        import shutil
        final_repo = repos_base / "TEST"
        shutil.copytree(temp_repo, final_repo)

        reader = CodeReader(repos_base_dir=str(repos_base))

        result = reader.get_repo_path("TEST")

        assert result is not None
        assert result == final_repo

    def test_read_file_success(self, temp_repo, tmp_path):
        """Should read file contents successfully."""
        from notion_dev.mcp_server.code_tools import CodeReader

        repos_base = tmp_path / "repos"
        repos_base.mkdir()
        import shutil
        final_repo = repos_base / "TEST"
        shutil.copytree(temp_repo, final_repo)

        reader = CodeReader(repos_base_dir=str(repos_base))

        result = reader.read_file("TEST", "main.py")

        assert result.get("success") is True
        assert "NOTION FEATURES: TEST01" in result["content"]
        assert result["total_lines"] >= 3  # At least a few lines

    def test_read_file_error_for_missing_repo(self, tmp_path):
        """Should return error if repository not cloned."""
        from notion_dev.mcp_server.code_tools import CodeReader

        reader = CodeReader(repos_base_dir=str(tmp_path))

        result = reader.read_file("NONEXISTENT", "main.py")

        assert "error" in result
        assert "not cloned" in result["error"]

    def test_search_code_finds_pattern(self, temp_repo, tmp_path):
        """Should find code matching pattern."""
        from notion_dev.mcp_server.code_tools import CodeReader

        repos_base = tmp_path / "repos"
        repos_base.mkdir()
        import shutil
        final_repo = repos_base / "TEST"
        shutil.copytree(temp_repo, final_repo)

        reader = CodeReader(repos_base_dir=str(repos_base))

        # Search for "def" which should exist in .py files
        result = reader.search_code("TEST", "def ")

        assert result.get("success") is True
        # At least one match expected
        assert result["files_searched"] >= 1

    def test_list_files_returns_file_list(self, temp_repo, tmp_path):
        """Should list files in repository."""
        from notion_dev.mcp_server.code_tools import CodeReader

        repos_base = tmp_path / "repos"
        repos_base.mkdir()
        import shutil
        final_repo = repos_base / "TEST"
        shutil.copytree(temp_repo, final_repo)

        reader = CodeReader(repos_base_dir=str(repos_base))

        result = reader.list_files("TEST", "**/*.py")

        assert result.get("success") is True
        assert result["total_files"] >= 1  # At least one .py file
        # Check we got some Python files
        file_paths = [f["path"] for f in result["files"]]
        assert any(f.endswith(".py") for f in file_paths)

    def test_prepare_feature_context(self, temp_repo, tmp_path):
        """Should prepare aggregated context for a feature."""
        from notion_dev.mcp_server.code_tools import CodeReader

        repos_base = tmp_path / "repos"
        repos_base.mkdir()
        import shutil
        final_repo = repos_base / "TEST"
        shutil.copytree(temp_repo, final_repo)

        reader = CodeReader(repos_base_dir=str(repos_base))

        result = reader.prepare_feature_context("TEST", "TEST01")

        assert result.get("success") is True
        assert result["feature_code"] == "TEST01"
        # Function should return successfully even with no primary files
        assert "primary_files" in result
        assert "secondary_files" in result


class TestRemoteBackendWithMocks:
    """Test RemoteBackend with mocked Notion and Asana clients."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration for remote mode."""
        from notion_dev.mcp_server.config import ServerConfig, TransportMode

        return ServerConfig(
            transport=TransportMode.SSE,
            auth_enabled=True,
            service_notion_token="test_notion_token",
            service_asana_token="test_asana_token",
            repos_cache_dir="/tmp/test_repos",
        )

    @patch.dict(os.environ, {
        "SERVICE_NOTION_TOKEN": "test_notion_token",
        "SERVICE_ASANA_TOKEN": "test_asana_token",
        "ASANA_WORKSPACE_GID": "test_workspace",
        "ASANA_PORTFOLIO_GID": "test_portfolio",
        "NOTION_MODULES_DATABASE_ID": "test_modules_db",
        "NOTION_FEATURES_DATABASE_ID": "test_features_db",
    }, clear=False)
    def test_remote_backend_is_configured(self, mock_config):
        """RemoteBackend should be properly configured."""
        from notion_dev.mcp_server.remote_backend import RemoteBackend
        from notion_dev.mcp_server.config import set_config

        set_config(mock_config)

        backend = RemoteBackend()

        assert backend.is_configured is True

    def test_remote_backend_set_current_user(self):
        """Should set and cache user."""
        from notion_dev.mcp_server.remote_backend import RemoteBackend, RemoteUser

        with patch.object(RemoteBackend, 'asana_client', new_callable=PropertyMock) as mock_asana:
            mock_asana.return_value.find_user_by_email.return_value = {"gid": "12345"}

            backend = RemoteBackend()
            user = backend.set_current_user("test@example.com", "Test User")

            assert user.email == "test@example.com"
            assert user.name == "Test User"
            assert user.asana_user_gid == "12345"
            assert backend.current_user == user

    def test_get_module_returns_repository_url(self):
        """get_module should return repository_url for code tools."""
        from notion_dev.mcp_server.remote_backend import RemoteBackend
        from notion_dev.core.models import Module

        mock_module = Module(
            name="Test Module",
            description="A test module",
            status="validated",
            application="Backend",
            code_prefix="TM",
            notion_id="12345",
            repository_url="https://github.com/test/repo",
            branch="main",
        )

        with patch.object(RemoteBackend, 'notion_client', new_callable=PropertyMock) as mock_notion:
            mock_notion.return_value.get_module_by_prefix.return_value = mock_module

            backend = RemoteBackend()
            result = backend.get_module("TM")

            assert result is not None
            assert result["repository_url"] == "https://github.com/test/repo"
            assert result["branch"] == "main"


class TestMCPToolsIntegration:
    """Integration tests for MCP tools behavior in different modes."""

    @patch('notion_dev.mcp_server.config._config', None)
    def test_reset_config_between_tests(self):
        """Ensure config is reset between tests."""
        from notion_dev.mcp_server.config import get_config, set_config, ServerConfig

        # Reset global config
        set_config(ServerConfig())

        config = get_config()
        assert config is not None

    def test_tool_enabled_check_in_code(self):
        """Test that is_tool_enabled is used correctly in tools."""
        import ast

        server_path = Path(__file__).parent.parent.parent / "notion_dev" / "mcp_server" / "server.py"

        with open(server_path, "r") as f:
            content = f.read()

        # These remote-only tools should check is_tool_enabled
        remote_tools = [
            "notiondev_read_file",
            "notiondev_search_code",
            "notiondev_list_files",
            "notiondev_prepare_feature_context",
        ]

        for tool in remote_tools:
            # Check that the tool function checks is_tool_enabled
            assert f'is_tool_enabled("{tool}")' in content, \
                f"Tool {tool} should check is_tool_enabled"


class TestGitHubClientNamingConvention:
    """Test that CodeReader uses GitHubClient naming convention correctly."""

    def test_get_repo_path_uses_github_naming(self, tmp_path):
        """Should find repo using GitHubClient naming convention."""
        from notion_dev.mcp_server.code_tools import CodeReader

        # Create a repo with GitHubClient naming convention
        repos_base = tmp_path / "repos"
        repos_base.mkdir()
        repo_dir = repos_base / "owner_reponame"
        repo_dir.mkdir()
        (repo_dir / "test.py").write_text("# test file")

        reader = CodeReader(repos_base_dir=str(repos_base))

        # Mock GitHubClient._get_repo_local_path to return our test path
        with patch('notion_dev.core.github_client.GitHubClient._get_repo_local_path') as mock_path:
            mock_path.return_value = str(repo_dir)

            result = reader.get_repo_path("ND", repository_url="https://github.com/owner/reponame")

            assert result is not None
            assert result == repo_dir


class TestConcurrentUserSessions:
    """Test that contextvars properly isolate concurrent user sessions."""

    def test_contextvars_isolate_users_in_remote_backend(self):
        """Each async task should have its own user context."""
        import asyncio
        from notion_dev.mcp_server.remote_backend import (
            RemoteBackend, _current_user_context
        )

        backend = RemoteBackend()

        results = {}

        async def simulate_request(user_email: str, delay: float):
            """Simulate a request that sets user then reads it after a delay."""
            with patch.object(RemoteBackend, 'asana_client', new_callable=PropertyMock) as mock_asana:
                mock_asana.return_value.find_user_by_email.return_value = {"gid": user_email}

                # Set user for this request
                backend.set_current_user(user_email, f"User {user_email}")

                # Simulate some async work
                await asyncio.sleep(delay)

                # Read back the user - should still be our user
                current = backend.current_user
                results[user_email] = current.email if current else None

        async def run_concurrent():
            # Run two requests concurrently
            await asyncio.gather(
                simulate_request("user1@example.com", 0.1),
                simulate_request("user2@example.com", 0.05),
            )

        asyncio.run(run_concurrent())

        # Each task should have seen its own user
        assert results["user1@example.com"] == "user1@example.com"
        assert results["user2@example.com"] == "user2@example.com"

    def test_contextvars_isolate_users_in_auth_middleware(self):
        """AuthMiddleware should use contextvars for user isolation."""
        import asyncio
        from notion_dev.mcp_server.auth import (
            AuthMiddleware, _auth_current_user_context, UserInfo
        )

        results = {}

        async def simulate_auth_request(user_email: str, delay: float):
            """Simulate setting user via context variable."""
            user = UserInfo(email=user_email, name=f"User {user_email}")
            _auth_current_user_context.set(user)

            await asyncio.sleep(delay)

            current = _auth_current_user_context.get()
            results[user_email] = current.email if current else None

        async def run_concurrent():
            await asyncio.gather(
                simulate_auth_request("auth1@example.com", 0.1),
                simulate_auth_request("auth2@example.com", 0.05),
            )

        asyncio.run(run_concurrent())

        assert results["auth1@example.com"] == "auth1@example.com"
        assert results["auth2@example.com"] == "auth2@example.com"

    def test_clear_user_only_affects_current_context(self):
        """Clearing user in one context should not affect another."""
        import asyncio
        from notion_dev.mcp_server.remote_backend import (
            RemoteBackend, _current_user_context
        )

        backend = RemoteBackend()
        results = {}

        async def task_that_clears(user_email: str):
            with patch.object(RemoteBackend, 'asana_client', new_callable=PropertyMock) as mock_asana:
                mock_asana.return_value.find_user_by_email.return_value = {"gid": user_email}

                backend.set_current_user(user_email, f"User {user_email}")
                await asyncio.sleep(0.05)
                backend.clear_current_user()
                results[f"{user_email}_after_clear"] = backend.current_user

        async def task_that_keeps(user_email: str):
            with patch.object(RemoteBackend, 'asana_client', new_callable=PropertyMock) as mock_asana:
                mock_asana.return_value.find_user_by_email.return_value = {"gid": user_email}

                backend.set_current_user(user_email, f"User {user_email}")
                await asyncio.sleep(0.1)  # Wait for other task to clear
                current = backend.current_user
                results[f"{user_email}_kept"] = current.email if current else None

        async def run_concurrent():
            await asyncio.gather(
                task_that_clears("clear@example.com"),
                task_that_keeps("keep@example.com"),
            )

        asyncio.run(run_concurrent())

        # User that cleared should be None
        assert results["clear@example.com_after_clear"] is None
        # User that kept should still have their user
        assert results["keep@example.com_kept"] == "keep@example.com"


# Run with: pytest tests/unit/test_mcp_modes.py -v
