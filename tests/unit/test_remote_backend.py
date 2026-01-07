# tests/unit/test_remote_backend.py
"""Tests for NotionDev Remote Backend and ASGI apps.

These tests verify the remote mode functionality used by Claude.ai.
"""

import pytest
import json
from unittest.mock import patch, MagicMock, AsyncMock
import os


class TestRemoteBackendConfiguration:
    """Test remote backend configuration and initialization."""

    def test_remote_backend_reads_env_vars(self):
        """Test that RemoteBackend reads configuration from environment variables."""
        with patch.dict(os.environ, {
            'SERVICE_NOTION_TOKEN': 'test_notion_token',
            'SERVICE_ASANA_TOKEN': 'test_asana_token',
            'NOTION_MODULES_DATABASE_ID': 'modules_db_id',
            'NOTION_FEATURES_DATABASE_ID': 'features_db_id',
            'ASANA_WORKSPACE_GID': 'workspace_123',
            'ASANA_PORTFOLIO_GID': 'portfolio_456',
            'ASANA_DEFAULT_PROJECT_GID': 'project_789',
        }):
            # Import after setting env vars
            from notion_dev.mcp_server.remote_backend import RemoteBackend

            backend = RemoteBackend()

            assert backend._notion_token == 'test_notion_token'
            assert backend._asana_token == 'test_asana_token'
            assert backend._modules_db_id == 'modules_db_id'
            assert backend._features_db_id == 'features_db_id'
            assert backend._workspace_gid == 'workspace_123'
            assert backend._portfolio_gid == 'portfolio_456'
            assert backend._default_project_gid == 'project_789'

    def test_remote_backend_default_project_used_in_asana_client(self):
        """Test that default_project_gid is passed to AsanaClient."""
        with patch.dict(os.environ, {
            'SERVICE_NOTION_TOKEN': 'test_token',
            'SERVICE_ASANA_TOKEN': 'test_asana',
            'NOTION_MODULES_DATABASE_ID': 'mod_db',
            'NOTION_FEATURES_DATABASE_ID': 'feat_db',
            'ASANA_WORKSPACE_GID': 'ws_123',
            'ASANA_DEFAULT_PROJECT_GID': 'default_proj_123',
        }):
            from notion_dev.mcp_server.remote_backend import RemoteBackend

            backend = RemoteBackend()

            # Access the asana_client property to trigger creation
            with patch('notion_dev.mcp_server.remote_backend.AsanaClient') as mock_asana:
                mock_asana.return_value = MagicMock()
                _ = backend.asana_client

                # Verify AsanaClient was called with default_project_gid
                mock_asana.assert_called_once()
                call_kwargs = mock_asana.call_args
                assert call_kwargs.kwargs.get('default_project_gid') == 'default_proj_123'


class TestAsanaClientCreateTask:
    """Test AsanaClient.create_task with default project handling."""

    def test_create_task_uses_default_project_when_no_project_specified(self):
        """Test that create_task uses default_project_gid when project_gid is not specified."""
        from notion_dev.core.asana_client import AsanaClient

        with patch('notion_dev.core.asana_client.requests') as mock_requests:
            # Mock the workspace test
            mock_requests.get.return_value = MagicMock(
                status_code=200,
                json=lambda: {'data': {'name': 'Test User'}}
            )

            client = AsanaClient(
                access_token='test_token',
                workspace_gid='ws_123',
                user_gid='user_123',
                portfolio_gid='portfolio_123',
                default_project_gid='default_proj_456'
            )

            # Mock the create task request
            mock_requests.post.return_value = MagicMock(
                status_code=201,
                raise_for_status=lambda: None,
                json=lambda: {
                    'data': {
                        'gid': 'task_123',
                        'name': 'Test Task',
                        'notes': 'Test notes',
                        'permalink_url': 'https://app.asana.com/0/task_123'
                    }
                }
            )

            # Create task without specifying project_gid
            task = client.create_task(name='Test Task', notes='Test notes')

            # Verify the POST was made with default project
            mock_requests.post.assert_called_once()
            call_args = mock_requests.post.call_args
            request_data = call_args.kwargs.get('json', {}).get('data', {})

            # The default project should be used
            assert 'projects' in request_data
            assert 'default_proj_456' in request_data['projects']

    def test_create_task_uses_explicit_project_over_default(self):
        """Test that explicit project_gid takes precedence over default."""
        from notion_dev.core.asana_client import AsanaClient

        with patch('notion_dev.core.asana_client.requests') as mock_requests:
            mock_requests.get.return_value = MagicMock(
                status_code=200,
                json=lambda: {'data': {'name': 'Test User'}}
            )

            client = AsanaClient(
                access_token='test_token',
                workspace_gid='ws_123',
                user_gid='user_123',
                default_project_gid='default_proj_456'
            )

            mock_requests.post.return_value = MagicMock(
                status_code=201,
                raise_for_status=lambda: None,
                json=lambda: {
                    'data': {
                        'gid': 'task_123',
                        'name': 'Test Task',
                        'notes': 'Test notes',
                        'permalink_url': 'https://app.asana.com/0/task_123'
                    }
                }
            )

            # Create task WITH explicit project_gid
            task = client.create_task(
                name='Test Task',
                notes='Test notes',
                project_gid='explicit_proj_789'
            )

            # Verify the explicit project was used, not the default
            call_args = mock_requests.post.call_args
            request_data = call_args.kwargs.get('json', {}).get('data', {})

            assert 'projects' in request_data
            assert 'explicit_proj_789' in request_data['projects']
            assert 'default_proj_456' not in request_data['projects']


class TestUserContextIsolation:
    """Test user context isolation with contextvars."""

    def test_user_context_is_isolated_per_request(self):
        """Test that user context is properly isolated using contextvars."""
        from notion_dev.mcp_server.remote_backend import (
            _current_user_context,
            RemoteUser
        )

        # Create two different users
        user1 = RemoteUser(
            email='user1@example.com',
            name='User One',
            asana_user_gid='asana_user_1'
        )
        user2 = RemoteUser(
            email='user2@example.com',
            name='User Two',
            asana_user_gid='asana_user_2'
        )

        # Set context for user1
        token1 = _current_user_context.set(user1)
        assert _current_user_context.get().email == 'user1@example.com'

        # Reset and set context for user2
        _current_user_context.reset(token1)
        token2 = _current_user_context.set(user2)
        assert _current_user_context.get().email == 'user2@example.com'

        # Cleanup
        _current_user_context.reset(token2)


class TestServerConfiguration:
    """Test MCP server configuration."""

    def test_server_config_from_args_remote_mode(self):
        """Test ServerConfig initialization for remote mode."""
        from notion_dev.mcp_server.config import ServerConfig, TransportMode

        config = ServerConfig.from_args(
            transport='sse',
            port=8080,
            host='0.0.0.0',
            auth=True
        )

        assert config.transport == TransportMode.SSE
        assert config.port == 8080
        assert config.host == '0.0.0.0'
        assert config.auth_enabled is True
        assert config.is_remote is True

    def test_server_config_from_args_local_mode(self):
        """Test ServerConfig initialization for local mode."""
        from notion_dev.mcp_server.config import ServerConfig, TransportMode

        config = ServerConfig.from_args(
            transport='stdio',
            port=8000,
            host='localhost',
            auth=False
        )

        assert config.transport == TransportMode.STDIO
        assert config.is_remote is False


class TestRemoteBackendCreateTicket:
    """Test the create_ticket flow in remote backend."""

    def test_create_ticket_returns_dict_on_success(self):
        """Test that create_ticket returns a proper dict on success."""
        with patch.dict(os.environ, {
            'SERVICE_NOTION_TOKEN': 'test_token',
            'SERVICE_ASANA_TOKEN': 'test_asana',
            'NOTION_MODULES_DATABASE_ID': 'mod_db',
            'NOTION_FEATURES_DATABASE_ID': 'feat_db',
            'ASANA_WORKSPACE_GID': 'ws_123',
            'ASANA_DEFAULT_PROJECT_GID': 'default_proj',
        }):
            from notion_dev.mcp_server.remote_backend import RemoteBackend, RemoteUser, _current_user_context

            backend = RemoteBackend()

            # Set user context
            user = RemoteUser(
                email='test@example.com',
                name='Test User',
                asana_user_gid='user_123'
            )
            token = _current_user_context.set(user)

            try:
                # Mock the AsanaClient
                with patch.object(backend, 'get_asana_client_for_user') as mock_get_client:
                    mock_client = MagicMock()
                    mock_client.create_task.return_value = MagicMock(
                        gid='task_123',
                        name='Test Ticket',
                        url='https://app.asana.com/0/task_123'
                    )
                    mock_get_client.return_value = mock_client

                    result = backend.create_ticket(
                        name='Test Ticket',
                        notes='Test notes'
                    )

                    assert result is not None
                    assert 'id' in result or 'gid' in result or result.get('name') == 'Test Ticket'
            finally:
                _current_user_context.reset(token)

    def test_create_ticket_returns_none_on_failure(self):
        """Test that create_ticket returns None when Asana API fails."""
        with patch.dict(os.environ, {
            'SERVICE_NOTION_TOKEN': 'test_token',
            'SERVICE_ASANA_TOKEN': 'test_asana',
            'NOTION_MODULES_DATABASE_ID': 'mod_db',
            'NOTION_FEATURES_DATABASE_ID': 'feat_db',
            'ASANA_WORKSPACE_GID': 'ws_123',
        }):
            from notion_dev.mcp_server.remote_backend import RemoteBackend, RemoteUser, _current_user_context

            backend = RemoteBackend()

            # Set user context
            user = RemoteUser(
                email='test@example.com',
                name='Test User',
                asana_user_gid='user_123'
            )
            token = _current_user_context.set(user)

            try:
                with patch.object(backend, 'get_asana_client_for_user') as mock_get_client:
                    mock_client = MagicMock()
                    mock_client.create_task.return_value = None  # Simulate failure
                    mock_get_client.return_value = mock_client

                    result = backend.create_ticket(
                        name='Test Ticket',
                        notes='Test notes'
                    )

                    assert result is None
            finally:
                _current_user_context.reset(token)
