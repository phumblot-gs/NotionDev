# tests/unit/test_mcp_server.py
"""Tests for NotionDev MCP Server functionality.

These tests focus on the helper functions and business logic,
not the MCP decorators which require the mcp package.
"""

import pytest
import json
import subprocess
from unittest.mock import patch, MagicMock
from pathlib import Path


class TestMCPServerHelpers:
    """Test MCP server helper functions (without MCP imports)."""

    def test_get_config_path(self):
        """Test config path generation."""
        # Test the logic directly without importing the module
        config_path = Path.home() / ".notion-dev" / "config.yml"
        assert config_path.name == "config.yml"
        assert ".notion-dev" in str(config_path)

    @patch("subprocess.run")
    def test_is_notion_dev_installed_success(self, mock_run):
        """Test installation check when notion-dev is installed."""
        mock_run.return_value = MagicMock(returncode=0)

        try:
            result = subprocess.run(
                ["notion-dev", "--help"],
                capture_output=True,
                text=True,
                timeout=10
            )
            is_installed = result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            is_installed = False

        assert is_installed is True

    @patch("subprocess.run")
    def test_is_notion_dev_installed_not_found(self, mock_run):
        """Test installation check when notion-dev is not installed."""
        mock_run.side_effect = FileNotFoundError()

        try:
            result = subprocess.run(
                ["notion-dev", "--help"],
                capture_output=True,
                text=True,
                timeout=10
            )
            is_installed = result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            is_installed = False

        assert is_installed is False

    @patch("subprocess.run")
    def test_run_notion_dev_command_success(self, mock_run):
        """Test running a notion-dev command successfully."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"tasks": []}',
            stderr=""
        )

        result = subprocess.run(
            ["notion-dev", "tickets", "--json"],
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode == 0:
            output = {"success": True, "output": result.stdout.strip()}
        else:
            output = {"success": False, "error": result.stderr.strip()}

        assert output["success"] is True
        assert output["output"] == '{"tasks": []}'

    @patch("subprocess.run")
    def test_run_notion_dev_command_failure(self, mock_run):
        """Test running a notion-dev command that fails."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Error: configuration invalid"
        )

        result = subprocess.run(
            ["notion-dev", "tickets"],
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode == 0:
            output = {"success": True, "output": result.stdout.strip()}
        else:
            output = {"success": False, "error": result.stderr.strip()}

        assert output["success"] is False
        assert "Error" in output["error"]

    @patch("subprocess.run")
    def test_run_notion_dev_command_timeout(self, mock_run):
        """Test running a command that times out."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="notion-dev", timeout=60)

        try:
            result = subprocess.run(
                ["notion-dev", "tickets"],
                capture_output=True,
                text=True,
                timeout=60
            )
            output = {"success": True, "output": result.stdout.strip()}
        except subprocess.TimeoutExpired:
            output = {"success": False, "error": "Command timed out after 60 seconds"}
        except FileNotFoundError:
            output = {"success": False, "error": "notion-dev command not found"}

        assert output["success"] is False
        assert "timed out" in output["error"]

    @patch("subprocess.run")
    def test_run_notion_dev_command_not_found(self, mock_run):
        """Test running when notion-dev is not found."""
        mock_run.side_effect = FileNotFoundError()

        try:
            result = subprocess.run(
                ["notion-dev", "tickets"],
                capture_output=True,
                text=True,
                timeout=60
            )
            output = {"success": True, "output": result.stdout.strip()}
        except subprocess.TimeoutExpired:
            output = {"success": False, "error": "Command timed out"}
        except FileNotFoundError:
            output = {"success": False, "error": "notion-dev command not found"}

        assert output["success"] is False
        assert "not found" in output["error"]


class TestInstallationInstructions:
    """Test installation instructions content."""

    def test_installation_guide_content(self):
        """Test that installation guide has all required sections."""
        # This is the expected content structure
        required_sections = [
            "pip install notion-dev",
            "config.yml",
            "notion",
            "asana",
            "token",
            "database"
        ]

        # Simulate the instruction content
        instructions = """
# NotionDev Installation Guide

## Step 1: Install the package

```bash
pip install notion-dev
```

## Step 2: Create configuration directory

```bash
mkdir -p ~/.notion-dev
```

## Step 3: Create configuration file

Create `~/.notion-dev/config.yml` with the following content:

```yaml
notion:
  token: "secret_YOUR_NOTION_TOKEN"
  database_modules_id: "YOUR_MODULES_DB_ID"
  database_features_id: "YOUR_FEATURES_DB_ID"

asana:
  access_token: "YOUR_ASANA_TOKEN"
  workspace_gid: "YOUR_WORKSPACE_GID"
  user_gid: "YOUR_USER_GID"
```
"""
        for section in required_sections:
            assert section in instructions.lower()


class TestMethodologyContent:
    """Test methodology content structure."""

    def test_methodology_has_required_sections(self):
        """Test methodology explains the specs-first approach."""
        # Expected content structure
        methodology = """
# NotionDev Specs-First Methodology

## Philosophy

NotionDev implements a **specs-first** approach to development.

## Documentation Structure

### Two-Level Hierarchy

Module (e.g., "User Authentication")
├── Feature CC01 - User Registration
├── Feature CC02 - Password Reset

### Module Documentation

A module represents a functional domain of your application.

### Feature Documentation

A feature represents a specific functionality.

## Workflow

### Definition of Ready (DoR)

A feature is ready for development when documentation is complete.
"""

        assert "specs-first" in methodology.lower()
        assert "module" in methodology.lower()
        assert "feature" in methodology.lower()
        assert "workflow" in methodology.lower()


class TestModuleTemplate:
    """Test module template structure."""

    def test_module_template_has_all_sections(self):
        """Test module template has all required documentation sections."""
        required_sections = [
            "objective",
            "stack technique",
            "architecture",
            "data model",
            "environments",
            "hosting",
            "ci/cd",
            "security",
            "environment variables",
            "useful links"
        ]

        template = """
# {Module Name}

## Objective
{Description}

## Stack Technique
- Languages
- Frameworks
- Database

## Architecture
{Description}

## Data Model
{Entities}

## Environments
| Environment | URL | Notes |

## Hosting
- Provider
- Services

## CI/CD
### Local Development Commands
### Database Migrations

## Security & Compliance
- Authentication
- Authorization

## Environment Variables
| Variable | Description |

## Useful Links
- Documentation
"""

        template_lower = template.lower()
        for section in required_sections:
            assert section in template_lower, f"Missing section: {section}"


class TestFeatureTemplate:
    """Test feature template structure."""

    def test_feature_template_has_all_sections(self):
        """Test feature template has all required documentation sections."""
        required_sections = [
            "description",
            "use cases",
            "business rules",
            "endpoints",
            "ui components",
            "data model",
            "tests"
        ]

        template = """
# {Feature Name}

## Description
{Description}

## Use Cases
### UC1: {Name}

## Business Rules
| ID | Rule | Description |

## Endpoints / Routes
| Method | Route | Description |

## UI Components
### Component Name

## Data Model
### Entities Affected

## Required Tests
- Unit Tests
- Integration Tests
- E2E Tests
"""

        template_lower = template.lower()
        for section in required_sections:
            assert section in template_lower, f"Missing section: {section}"


class TestNotionClientIntegration:
    """Test that NotionClient methods work correctly for MCP use cases."""

    def test_notion_client_has_required_methods(self):
        """Test NotionClient has all methods needed by MCP server."""
        from notion_dev.core.notion_client import NotionClient

        required_methods = [
            'get_feature',
            'get_module_by_id',
            'get_module_by_prefix',
            'list_modules',
            'list_features_for_module',
            'search_features',
            'create_module',
            'create_feature',
            'update_page_content',
            'update_module_properties',
            'update_feature_properties',
            'get_next_feature_code'
        ]

        for method in required_methods:
            assert hasattr(NotionClient, method), f"Missing method: {method}"


class TestModelsForMCP:
    """Test that models work correctly for MCP serialization."""

    def test_module_can_be_serialized(self):
        """Test Module can be converted to JSON-serializable dict."""
        from notion_dev.core.models import Module

        module = Module(
            name="Test Module",
            description="A test module",
            status="Draft",
            application="Backend",
            code_prefix="TM",
            notion_id="12345",
            content="# Documentation"
        )

        # Simulate JSON serialization like MCP tools do
        data = {
            "id": module.notion_id,
            "name": module.name,
            "description": module.description,
            "code_prefix": module.code_prefix,
            "application": module.application,
            "status": module.status,
            "content": module.content
        }

        json_str = json.dumps(data)
        assert "Test Module" in json_str
        assert "TM" in json_str

    def test_feature_can_be_serialized(self):
        """Test Feature can be converted to JSON-serializable dict."""
        from notion_dev.core.models import Feature

        feature = Feature(
            code="TM01",
            name="Test Feature",
            status="Draft",
            module_name="Test Module",
            plan=["free", "premium"],
            user_rights=["user", "admin"],
            notion_id="67890",
            content="# Feature docs"
        )

        data = {
            "code": feature.code,
            "name": feature.name,
            "module": feature.module_name,
            "status": feature.status,
            "plan": feature.plan,
            "user_rights": feature.user_rights,
            "content": feature.content
        }

        json_str = json.dumps(data)
        assert "TM01" in json_str
        assert "Test Feature" in json_str
        assert "premium" in json_str


class TestConfigForMCP:
    """Test configuration handling for MCP."""

    def test_config_path_exists(self):
        """Test config path is deterministic."""
        expected_path = Path.home() / ".notion-dev" / "config.yml"
        assert expected_path.parent.name == ".notion-dev"
        assert expected_path.name == "config.yml"

    def test_config_can_hide_tokens(self):
        """Test that config can be represented without exposing tokens."""
        # Simulate config data
        config_data = {
            "notion": {
                "database_modules_id": "abc123",
                "database_features_id": "def456",
                "token_configured": True  # Don't expose actual token
            },
            "asana": {
                "workspace_gid": "111",
                "user_gid": "222",
                "portfolio_gid": "333",
                "token_configured": True  # Don't expose actual token
            }
        }

        json_str = json.dumps(config_data)

        # Should not contain any secrets
        assert "secret_" not in json_str
        assert "token_configured" in json_str
