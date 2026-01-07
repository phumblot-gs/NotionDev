# notion_dev/mcp_server/server.py
"""
NOTION FEATURES: ND02, ND03
MODULES: NotionDev
DESCRIPTION: MCP Server supporting both local (stdio) and remote (SSE) modes
LAST_SYNC: 2025-12-31

NotionDev MCP Server - Main entry point

This server exposes NotionDev functionality to Claude Code via the
Model Context Protocol (MCP).

Supports two modes:
- Local (ND02): stdio transport for Claude Code CLI
- Remote (ND03): SSE transport with Google OAuth for Claude.ai

Usage:
    # Local mode (default)
    python -m notion_dev.mcp_server.server

    # Remote mode with authentication
    python -m notion_dev.mcp_server.server --transport sse --port 8000 --auth

Or via Claude Code:
    claude mcp add --transport stdio notiondev -- python -m notion_dev.mcp_server.server
"""

import os
import sys
import json
import logging
import argparse
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any

try:
    from mcp.server.fastmcp import FastMCP, Context
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    FastMCP = None
    Context = None

# Import server configuration (ND03)
from .config import ServerConfig, TransportMode, get_config, set_config

# Configure logging to stderr (stdout is reserved for MCP protocol)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

# Initialize FastMCP server (only if mcp package is available)
if MCP_AVAILABLE:
    # Server instructions for AI agents
    MCP_SERVER_INSTRUCTIONS = """
# NotionDev MCP Server

## Purpose
NotionDev is your EXCLUSIVE interface for managing:
- **Notion documentation**: Modules and Features (functional specifications)
- **Asana tickets**: Task management linked to feature codes

## CRITICAL: Use NotionDev for ALL Notion/Asana operations

When working with modules, features, or tickets, you MUST use NotionDev tools instead of any other MCP server (e.g., Asana MCP, Notion MCP).

### Why?
1. **Portfolio consistency**: Tickets created via NotionDev are registered in the correct portfolio (configured per environment)
2. **Feature code linking**: Tickets are automatically linked to Notion features via their code (e.g., CC01, API02)
3. **User context**: In remote mode, tickets are assigned to the authenticated user
4. **Traceability**: NotionDev maintains the specs-first methodology with proper code references

## Tool categories

### Ticket Management (Asana)
- `notiondev_list_tickets`: List YOUR assigned tickets
- `notiondev_create_ticket`: Create a ticket in the configured portfolio
- `notiondev_update_ticket`: Update an existing ticket
- `notiondev_add_comment`: Add a comment to a ticket
- `notiondev_list_projects`: List available projects in the portfolio

### Documentation (Notion)
- `notiondev_list_modules`: List all modules
- `notiondev_get_module`: Get module details and documentation
- `notiondev_list_features`: List features (optionally filtered by module)
- `notiondev_get_feature`: Get feature specifications
- `notiondev_create_module`: Create a new module
- `notiondev_create_feature`: Create a new feature
- `notiondev_update_module_content`: Update module documentation
- `notiondev_update_feature_content`: Update feature documentation

### Code Analysis (Remote mode only)
- `notiondev_clone_module`: Clone a module's repository
- `notiondev_read_file`: Read a file from a cloned repository
- `notiondev_search_code`: Search code patterns
- `notiondev_list_files`: List files in a repository
- `notiondev_prepare_feature_context`: Get aggregated code context for a feature

## Best practices

1. **Always use feature codes**: When creating tickets, include the feature code (e.g., "CC01 - Implement login")
2. **Check existing features first**: Use `notiondev_list_features` before creating duplicates
3. **Link tickets to features**: Use the `feature_code` parameter in `notiondev_create_ticket`
4. **Read before update**: Always read current content before updating documentation
5. **Don't ask for project**: When creating tickets, omit the `project_gid` parameter - the system will automatically use the default portfolio project

## Configuration

- **Local mode**: Uses `~/.notion-dev/config.yml` for portfolio and user settings
- **Remote mode**: Uses environment variables (ASANA_PORTFOLIO_GID, etc.)

Both modes ensure tickets are created in the correct portfolio with proper user assignment.
"""
    mcp = FastMCP("notiondev", instructions=MCP_SERVER_INSTRUCTIONS)
else:
    # Create a mock mcp object with no-op decorators for when mcp package is not available
    # This allows the module to be imported without errors
    class MockMCP:
        def tool(self):
            def decorator(func):
                return func
            return decorator

        def prompt(self):
            def decorator(func):
                return func
            return decorator

        def resource(self, uri):
            def decorator(func):
                return func
            return decorator

        def run(self, transport=None):
            pass

    mcp = MockMCP()

# =============================================================================
# Helper functions
# =============================================================================

def get_config_path() -> Path:
    """Get the path to the NotionDev configuration file."""
    return Path.home() / ".notion-dev" / "config.yml"


def is_notion_dev_installed() -> bool:
    """Check if notion-dev CLI is installed and accessible."""
    try:
        result = subprocess.run(
            ["notion-dev", "--help"],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def is_notion_dev_configured() -> bool:
    """Check if notion-dev is properly configured."""
    config_path = get_config_path()
    if not config_path.exists():
        return False

    # Try to run a simple command to verify configuration
    try:
        result = subprocess.run(
            ["notion-dev", "info", "--json"],
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.returncode == 0
    except subprocess.SubprocessError:
        return False


def run_notion_dev_command(args: List[str], timeout: int = 60) -> Dict[str, Any]:
    """Run a notion-dev CLI command and return the result.

    Args:
        args: Command arguments (e.g., ["tickets", "--json"])
        timeout: Command timeout in seconds

    Returns:
        Dict with 'success', 'output', and optionally 'error' keys
    """
    try:
        result = subprocess.run(
            ["notion-dev"] + args,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=os.getcwd()
        )

        if result.returncode == 0:
            return {
                "success": True,
                "output": result.stdout.strip()
            }
        else:
            return {
                "success": False,
                "output": result.stdout.strip(),
                "error": result.stderr.strip()
            }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": f"Command timed out after {timeout} seconds"
        }
    except FileNotFoundError:
        return {
            "success": False,
            "error": "notion-dev command not found. Please install it first."
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def run_cli_command(args: List[str], timeout: int = 60) -> dict:
    """Execute a notion-dev CLI command and return parsed JSON output.

    Args:
        args: List of command arguments (without 'notion-dev' prefix)
        timeout: Command timeout in seconds

    Returns:
        Parsed JSON output from the CLI command
    """
    try:
        # Always add --json flag for machine-readable output
        full_args = ["notion-dev"] + args
        if "--json" not in args:
            full_args.append("--json")

        logger.info(f"Running CLI command: {' '.join(full_args)}")

        result = subprocess.run(
            full_args,
            capture_output=True,
            text=True,
            timeout=timeout
        )

        if result.returncode != 0:
            logger.error(f"CLI command failed: {result.stderr}")
            # Try to parse error from stdout first (some commands output JSON errors)
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError:
                return {"error": result.stderr or f"Command failed with code {result.returncode}"}

        # Parse JSON output
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse CLI output: {e}")
            logger.error(f"Raw output: {result.stdout}")
            return {"error": f"Failed to parse CLI output: {str(e)}", "raw_output": result.stdout}

    except subprocess.TimeoutExpired:
        return {"error": f"Command timed out after {timeout} seconds"}
    except Exception as e:
        logger.error(f"Error running CLI command: {e}")
        return {"error": str(e)}


def get_github_client():
    """Get a configured GitHubClient instance."""
    try:
        from ..core.config import Config
        from ..core.github_client import GitHubClient

        config = Config.load()
        return GitHubClient(
            token=config.github.token if hasattr(config, 'github') and config.github else None,
            clone_dir=config.github.clone_dir if hasattr(config, 'github') and config.github else "/tmp/notiondev",
            shallow_clone=config.github.shallow_clone if hasattr(config, 'github') and config.github else True
        )
    except Exception as e:
        logger.error(f"Failed to initialize GitHubClient: {e}")
        return None


# =============================================================================
# MCP Tools - Installation & Setup
# =============================================================================

@mcp.tool()
async def notiondev_check_installation() -> str:
    """Check if NotionDev is installed and configured properly.

    Returns the installation status and any issues found.
    """
    # This tool is disabled in remote mode
    config = get_config()
    if config.is_remote:
        return json.dumps({
            "error": "This tool is not available in remote mode",
            "message": "notiondev_check_installation is only available when running locally via Claude Code CLI"
        })

    issues = []
    status = {
        "installed": False,
        "configured": False,
        "config_path": str(get_config_path()),
        "issues": []
    }

    # Check installation
    if is_notion_dev_installed():
        status["installed"] = True
    else:
        issues.append("notion-dev CLI is not installed or not in PATH")

    # Check configuration
    if status["installed"]:
        if get_config_path().exists():
            if is_notion_dev_configured():
                status["configured"] = True
            else:
                issues.append("Configuration exists but is invalid or incomplete")
        else:
            issues.append(f"Configuration file not found at {status['config_path']}")

    status["issues"] = issues

    if status["installed"] and status["configured"]:
        return json.dumps({
            **status,
            "message": "NotionDev is installed and configured correctly!"
        }, indent=2)
    else:
        return json.dumps({
            **status,
            "message": "NotionDev needs setup. See issues for details."
        }, indent=2)


@mcp.tool()
async def notiondev_get_install_instructions() -> str:
    """Get detailed instructions for installing and configuring NotionDev.

    Returns step-by-step installation guide.
    """
    # This tool is disabled in remote mode
    config = get_config()
    if config.is_remote:
        return json.dumps({
            "error": "This tool is not available in remote mode",
            "message": "notiondev_get_install_instructions is only available when running locally via Claude Code CLI"
        })

    instructions = """
# NotionDev Installation Guide

## Step 1: Install the package

```bash
pip install notion-dev
```

Or install from source:
```bash
git clone https://github.com/phumblot-gs/NotionDev.git
cd NotionDev
pip install -e .
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
  portfolio_gid: "YOUR_PORTFOLIO_GID"  # Optional
```

## Step 4: Get your API tokens

### Notion Token:
1. Go to https://www.notion.so/my-integrations
2. Create a new integration named "NotionDev"
3. Copy the "Internal Integration Secret" (starts with `secret_`)
4. Share your Modules and Features databases with the integration

### Notion Database IDs:
- Open your database in Notion
- Copy the ID from the URL: `notion.so/workspace/{DATABASE_ID}?v=...`

### Asana Token:
1. Go to https://app.asana.com/0/my-apps
2. Create a "Personal Access Token"
3. Copy the generated token

### Asana IDs:
- Workspace GID: Found in Asana URL or via API
- User GID: Your user ID in Asana
- Portfolio GID: Optional, for filtering tickets by portfolio

## Step 5: Test the installation

```bash
notion-dev info
notion-dev tickets
```

## Notion Database Structure Required

### Modules Database:
- `name` (Title): Module name
- `description` (Text): Short description
- `status` (Select): Draft, Review, Validated, Obsolete
- `application` (Select): Backend, Frontend, Service
- `code_prefix` (Text): 2-3 character prefix (e.g., CC, API)

### Features Database:
- `code` (Text): Unique code (e.g., CC01, API02)
- `name` (Title): Feature name
- `status` (Select): Draft, Review, Validated, Obsolete
- `module` (Relation): Link to parent module
- `plan` (Multi-select): Subscription plans
- `user_rights` (Multi-select): Access rights
"""
    return instructions


# =============================================================================
# MCP Tools - Ticket Management
# =============================================================================

@mcp.tool()
async def notiondev_list_tickets() -> str:
    """List all Asana tickets assigned to the current user.

    Returns JSON with ticket information including ID, name, feature code, and status.
    """
    # Check if we're in remote mode
    from .remote_backend import is_remote_mode, get_remote_backend

    if is_remote_mode():
        try:
            backend = get_remote_backend()
            tickets = backend.list_tickets()
            return json.dumps(tickets, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Remote backend error: {e}")
            return json.dumps({
                "error": str(e),
                "hint": "Make sure you're authenticated and your email is linked to an Asana account"
            })

    # Local mode: use CLI
    result = run_notion_dev_command(["tickets", "--json"])

    if result["success"]:
        return result["output"]
    else:
        return json.dumps({
            "error": result.get("error", "Failed to fetch tickets"),
            "details": result.get("output", "")
        })


@mcp.tool()
async def notiondev_get_info() -> str:
    """Get current project and task information.

    Returns JSON with project details and current working ticket if any.
    """
    # Check if we're in remote mode
    from .remote_backend import is_remote_mode, get_remote_backend

    if is_remote_mode():
        try:
            backend = get_remote_backend()
            info = backend.get_info()
            return json.dumps(info, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Remote backend error: {e}")
            return json.dumps({"error": str(e)})

    # Local mode: use CLI
    result = run_notion_dev_command(["info", "--json"])

    if result["success"]:
        return result["output"]
    else:
        return json.dumps({
            "error": result.get("error", "Failed to get info"),
            "details": result.get("output", "")
        })


@mcp.tool()
async def notiondev_work_on_ticket(task_id: str, ctx: Context = None) -> str:
    """Start working on a specific Asana ticket.

    This will:
    - Load the ticket from Asana
    - Fetch the associated feature documentation from Notion
    - Export the context to AGENTS.md
    - Add a comment to the Asana ticket

    Args:
        task_id: The Asana task ID to work on

    Returns:
        Status message with ticket and feature information
    """
    # This tool is disabled in remote mode
    config = get_config()
    if config.is_remote:
        return json.dumps({
            "error": "This tool is not available in remote mode",
            "message": "notiondev_work_on_ticket is only available when running locally via Claude Code CLI",
            "hint": "Use notiondev_get_feature to get feature documentation instead"
        })

    # Use CLI command with --yes --json to get structured output
    result = run_cli_command(["work", task_id, "--yes"], timeout=120)
    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool()
async def notiondev_add_comment(message: str, task_id: str = "") -> str:
    """Add a comment to the current working ticket in Asana.

    Args:
        message: The comment message to add
        task_id: (Remote mode only) The task ID to comment on

    Returns:
        Confirmation or error message
    """
    from .remote_backend import is_remote_mode, get_remote_backend

    if is_remote_mode():
        if not task_id:
            return json.dumps({
                "error": "task_id is required in remote mode",
                "hint": "Provide the task_id parameter"
            })
        try:
            backend = get_remote_backend()
            success = backend.add_comment(task_id, message)
            if success:
                return f"Comment added successfully: \"{message}\""
            else:
                return json.dumps({"error": "Failed to add comment"})
        except Exception as e:
            return json.dumps({"error": str(e)})

    # Local mode: use CLI
    result = run_notion_dev_command(["comment", message])

    if result["success"]:
        return f"Comment added successfully: \"{message}\""
    else:
        return json.dumps({
            "error": result.get("error", "Failed to add comment"),
            "details": result.get("output", ""),
            "hint": "Make sure you have a current working ticket (use notiondev_work_on_ticket first)"
        })


@mcp.tool()
async def notiondev_mark_done() -> str:
    """Mark the current ticket as done and reassign to creator.

    This will:
    - Add a completion comment to the ticket
    - Reassign the ticket to its creator
    - Clear the current working ticket

    Returns:
        Confirmation or error message
    """
    # This tool is disabled in remote mode
    config = get_config()
    if config.is_remote:
        return json.dumps({
            "error": "This tool is not available in remote mode",
            "message": "notiondev_mark_done is only available when running locally via Claude Code CLI"
        })

    result = run_notion_dev_command(["done"])

    if result["success"]:
        return "Ticket marked as done and reassigned to creator."
    else:
        return json.dumps({
            "error": result.get("error", "Failed to mark ticket as done"),
            "details": result.get("output", "")
        })


# =============================================================================
# MCP Tools - Asana Projects
# =============================================================================

@mcp.tool()
async def notiondev_list_projects() -> str:
    """List available Asana projects from the configured portfolio.

    Use this to find the correct project_gid when creating tickets.

    Returns:
        JSON array of projects with their IDs and names
    """
    from .remote_backend import is_remote_mode, get_remote_backend

    if is_remote_mode():
        try:
            backend = get_remote_backend()
            projects = backend.list_projects()
            return json.dumps(projects, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})

    # Local mode: use CLI
    result = run_cli_command(["projects"])
    return json.dumps(result, indent=2)


# =============================================================================
# MCP Tools - Ticket Creation & Update
# =============================================================================

@mcp.tool()
async def notiondev_create_ticket(
    name: str,
    notes: str = "",
    feature_code: str = "",
    project_gid: str = "",
    due_on: str = ""
) -> str:
    """Create a new ticket in Asana.

    Args:
        name: Ticket title (required). Should include feature code, e.g., "CC01 - Implement login"
        notes: Ticket description in markdown format
        feature_code: Feature code to reference (e.g., 'CC01'). Will be added to notes if provided.
        project_gid: Target project ID. If not provided, uses first project from portfolio.
        due_on: Due date in YYYY-MM-DD format

    Returns:
        JSON with created ticket details including ID and URL
    """
    from .remote_backend import is_remote_mode, get_remote_backend

    if is_remote_mode():
        try:
            backend = get_remote_backend()
            ticket = backend.create_ticket(
                name=name,
                notes=notes,
                project_gid=project_gid or None,
                due_on=due_on or None,
                feature_code=feature_code or None
            )
            if ticket:
                return json.dumps(ticket, indent=2)
            else:
                return json.dumps({"error": "Failed to create ticket"})
        except Exception as e:
            return json.dumps({"error": str(e)})

    # Local mode: use CLI
    args = ["create-ticket", "--name", name]

    if feature_code:
        args.extend(["--feature", feature_code])
    if notes:
        args.extend(["--notes", notes])
    if project_gid:
        args.extend(["--project", project_gid])
    if due_on:
        args.extend(["--due", due_on])

    result = run_cli_command(args)
    return json.dumps(result, indent=2)


@mcp.tool()
async def notiondev_update_ticket(
    task_id: str,
    name: str = "",
    notes: str = "",
    append_notes: bool = False,
    due_on: str = "",
    assignee_gid: str = ""
) -> str:
    """Update an existing ticket in Asana.

    Args:
        task_id: The Asana task ID to update (required)
        name: New ticket title (optional)
        notes: New notes content in markdown format (optional)
        append_notes: If true, append to existing notes instead of replacing
        due_on: New due date in YYYY-MM-DD format (optional)
        assignee_gid: New assignee user ID (optional)

    Returns:
        JSON with updated ticket details
    """
    from .remote_backend import is_remote_mode, get_remote_backend

    if is_remote_mode():
        try:
            backend = get_remote_backend()
            ticket = backend.update_ticket(
                task_id=task_id,
                name=name or None,
                notes=notes or None,
                append_notes=append_notes,
                due_on=due_on or None,
                assignee_gid=assignee_gid or None
            )
            if ticket:
                return json.dumps(ticket, indent=2)
            else:
                return json.dumps({"error": "Failed to update ticket"})
        except Exception as e:
            return json.dumps({"error": str(e)})

    # Local mode: use CLI
    args = ["update-ticket", task_id]

    if name:
        args.extend(["--name", name])
    if notes:
        args.extend(["--notes", notes])
    if append_notes:
        args.append("--append")
    if due_on:
        args.extend(["--due", due_on])
    if assignee_gid:
        args.extend(["--assignee", assignee_gid])

    result = run_cli_command(args)
    return json.dumps(result, indent=2)


# =============================================================================
# MCP Tools - Notion Documentation
# =============================================================================

@mcp.tool()
async def notiondev_list_modules() -> str:
    """List all modules in the Notion database.

    Returns JSON array of modules with their properties.
    """
    from .remote_backend import is_remote_mode, get_remote_backend

    if is_remote_mode():
        try:
            backend = get_remote_backend()
            modules = backend.list_modules()
            return json.dumps(modules, indent=2, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)})

    # Local mode: use CLI
    result = run_cli_command(["modules"])
    return json.dumps(result, indent=2)


@mcp.tool()
async def notiondev_get_module(code_prefix: str) -> str:
    """Get detailed information about a specific module.

    Args:
        code_prefix: The module's code prefix (e.g., 'CC', 'API')

    Returns:
        Module details including full documentation content
    """
    from .remote_backend import is_remote_mode, get_remote_backend

    if is_remote_mode():
        try:
            backend = get_remote_backend()
            module = backend.get_module(code_prefix)
            if module:
                return json.dumps(module, indent=2, ensure_ascii=False)
            else:
                return json.dumps({"error": f"Module '{code_prefix}' not found"})
        except Exception as e:
            return json.dumps({"error": str(e)})

    # Local mode: use CLI
    result = run_cli_command(["module", code_prefix])
    return json.dumps(result, indent=2)


@mcp.tool()
async def notiondev_list_features(module_prefix: str = None) -> str:
    """List features, optionally filtered by module.

    Args:
        module_prefix: Optional module prefix to filter features (e.g., 'CC')

    Returns:
        JSON array of features
    """
    from .remote_backend import is_remote_mode, get_remote_backend

    if is_remote_mode():
        try:
            backend = get_remote_backend()
            features = backend.list_features(module_prefix)
            return json.dumps(features, indent=2, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)})

    # Local mode: use CLI
    args = ["features"]
    if module_prefix:
        args.extend(["--module", module_prefix])
    result = run_cli_command(args)
    return json.dumps(result, indent=2)


@mcp.tool()
async def notiondev_get_feature(code: str) -> str:
    """Get detailed information about a specific feature.

    Args:
        code: The feature code (e.g., 'CC01', 'API02')

    Returns:
        Feature details including full documentation content
    """
    from .remote_backend import is_remote_mode, get_remote_backend

    if is_remote_mode():
        try:
            backend = get_remote_backend()
            feature = backend.get_feature(code)
            if feature:
                return json.dumps(feature, indent=2, ensure_ascii=False)
            else:
                return json.dumps({"error": f"Feature '{code}' not found"})
        except Exception as e:
            return json.dumps({"error": str(e)})

    # Local mode: use CLI
    result = run_cli_command(["feature", code])
    return json.dumps(result, indent=2)


@mcp.tool()
async def notiondev_create_module(
    name: str,
    description: str,
    code_prefix: str,
    application: str = "Backend",
    content_markdown: str = ""
) -> str:
    """Create a new module in Notion.

    Args:
        name: Module name
        description: Short description of the module
        code_prefix: 2-3 character code prefix (e.g., 'CC', 'API', 'USR')
        application: One of 'Backend', 'Frontend', 'Service'
        content_markdown: Full documentation content in markdown format

    Returns:
        Created module details or error
    """
    from .remote_backend import is_remote_mode, get_remote_backend

    if is_remote_mode():
        try:
            backend = get_remote_backend()
            module = backend.create_module(
                name=name,
                description=description,
                code_prefix=code_prefix,
                application=application,
                content_markdown=content_markdown
            )
            if module:
                return json.dumps(module, indent=2)
            else:
                return json.dumps({"error": "Failed to create module"})
        except Exception as e:
            return json.dumps({"error": str(e)})

    # Local mode: use CLI
    args = [
        "create-module",
        "--name", name,
        "--prefix", code_prefix,
        "--description", description,
        "--application", application
    ]
    if content_markdown:
        args.extend(["--content", content_markdown])

    result = run_cli_command(args)
    return json.dumps(result, indent=2)


@mcp.tool()
async def notiondev_create_feature(
    name: str,
    module_prefix: str,
    content_markdown: str = "",
    plan: str = "",
    user_rights: str = ""
) -> str:
    """Create a new feature in Notion.

    The feature code will be automatically generated based on the module prefix.

    Args:
        name: Feature name
        module_prefix: Parent module's code prefix (e.g., 'CC')
        content_markdown: Full documentation content in markdown format
        plan: Comma-separated subscription plans (e.g., 'free,premium')
        user_rights: Comma-separated user rights (e.g., 'admin,user')

    Returns:
        Created feature details or error
    """
    from .remote_backend import is_remote_mode, get_remote_backend

    if is_remote_mode():
        try:
            backend = get_remote_backend()
            feature = backend.create_feature(
                name=name,
                module_prefix=module_prefix,
                content_markdown=content_markdown,
                plan=plan,
                user_rights=user_rights
            )
            if feature:
                return json.dumps(feature, indent=2)
            else:
                return json.dumps({"error": f"Failed to create feature. Module '{module_prefix}' may not exist."})
        except Exception as e:
            return json.dumps({"error": str(e)})

    # Local mode: use CLI
    args = [
        "create-feature",
        "--name", name,
        "--module", module_prefix
    ]
    if content_markdown:
        args.extend(["--content", content_markdown])
    if plan:
        args.extend(["--plan", plan])
    if user_rights:
        args.extend(["--rights", user_rights])

    result = run_cli_command(args)
    return json.dumps(result, indent=2)


@mcp.tool()
async def notiondev_update_module_content(
    code_prefix: str,
    content_markdown: str,
    replace: bool = True
) -> str:
    """Update a module's documentation content.

    Args:
        code_prefix: The module's code prefix (e.g., 'CC')
        content_markdown: New content in markdown format
        replace: If True, replace all content. If False, append.

    Returns:
        Success or error message
    """
    from .remote_backend import is_remote_mode, get_remote_backend

    if is_remote_mode():
        try:
            backend = get_remote_backend()
            result = backend.update_module_content(
                code_prefix=code_prefix,
                content_markdown=content_markdown,
                replace=replace
            )
            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})

    # Local mode: use CLI
    args = ["update-module", code_prefix, "--content", content_markdown]
    if not replace:
        args.append("--append")

    result = run_cli_command(args)
    return json.dumps(result, indent=2)


@mcp.tool()
async def notiondev_update_feature_content(
    code: str,
    content_markdown: str,
    replace: bool = True
) -> str:
    """Update a feature's documentation content.

    Args:
        code: The feature code (e.g., 'CC01')
        content_markdown: New content in markdown format
        replace: If True, replace all content. If False, append.

    Returns:
        Success or error message
    """
    from .remote_backend import is_remote_mode, get_remote_backend

    if is_remote_mode():
        try:
            backend = get_remote_backend()
            result = backend.update_feature_content(
                code=code,
                content_markdown=content_markdown,
                replace=replace
            )
            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})

    # Local mode: use CLI
    args = ["update-feature", code, "--content", content_markdown]
    if not replace:
        args.append("--append")

    result = run_cli_command(args)
    return json.dumps(result, indent=2)


# =============================================================================
# MCP Tools - GitHub Integration
# =============================================================================

@mcp.tool()
async def notiondev_clone_module(
    module_prefix: str,
    force: bool = False
) -> str:
    """Clone a module's repository to local filesystem for code analysis.

    This tool reads the repository_url from the Notion module and clones it
    to a local directory for AI-assisted code analysis.

    The module must have repository_url property set in Notion.

    Args:
        module_prefix: The module's code prefix (e.g., 'CC', 'API')
        force: If True, remove existing clone and re-clone fresh

    Returns:
        JSON with clone status and local path
    """
    # Check if we're in remote mode
    config = get_config()
    if config.is_remote:
        # Use RemoteBackend for remote mode
        from .remote_backend import get_remote_backend
        backend = get_remote_backend()
        result = backend.clone_module(module_prefix, force)
        return json.dumps(result, indent=2)

    # Local mode: use CLI and local config
    # Get module info via CLI
    module_result = run_cli_command(["module", module_prefix])
    if "error" in module_result:
        return json.dumps(module_result, indent=2)

    module_data = module_result.get("module", {})
    repository_url = module_data.get("repository_url")
    branch = module_data.get("branch")
    code_path = module_data.get("code_path")
    module_name = module_data.get("name", module_prefix)

    if not repository_url:
        return json.dumps({
            "error": f"Module '{module_name}' does not have a repository_url configured",
            "hint": "Add the repository_url property to the module in Notion"
        })

    # Use GitHub client to clone (still needed for actual git operations)
    github = get_github_client()
    if not github:
        return json.dumps({"error": "Failed to initialize GitHub client"})

    try:
        result = github.clone_repository(
            repo_url=repository_url,
            branch=branch,
            force=force
        )

        if result["success"]:
            response = {
                "success": True,
                "message": f"Repository cloned successfully for module '{module_name}'",
                "module": {
                    "name": module_name,
                    "code_prefix": module_prefix,
                    "repository_url": repository_url,
                    "branch": branch or "default"
                },
                "clone": {
                    "path": result["path"],
                    "code_path": code_path
                }
            }

            if code_path:
                full_code_path = os.path.join(result["path"], code_path)
                response["clone"]["full_code_path"] = full_code_path
                response["hint"] = f"Code is located at: {full_code_path}"
            else:
                response["hint"] = f"Repository cloned to: {result['path']}"

            return json.dumps(response, indent=2)
        else:
            return json.dumps({
                "error": result.get("error", "Clone failed"),
                "repository_url": repository_url
            })

    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def notiondev_get_cloned_repo_info(module_prefix: str) -> str:
    """Get information about a cloned repository for a module.

    Args:
        module_prefix: The module's code prefix (e.g., 'CC', 'API')

    Returns:
        JSON with repository information including path, branch, and last commit
    """
    # Check if we're in remote mode
    config = get_config()
    if config.is_remote:
        # Use RemoteBackend for remote mode
        from .remote_backend import get_remote_backend
        backend = get_remote_backend()
        result = backend.get_cloned_repo_info(module_prefix)
        return json.dumps(result, indent=2)

    # Local mode: use CLI and local config
    # Get module info via CLI
    module_result = run_cli_command(["module", module_prefix])
    if "error" in module_result:
        return json.dumps(module_result, indent=2)

    module_data = module_result.get("module", {})
    repository_url = module_data.get("repository_url")
    code_path = module_data.get("code_path")
    module_name = module_data.get("name", module_prefix)

    if not repository_url:
        return json.dumps({
            "error": f"Module '{module_name}' does not have a repository_url configured"
        })

    github = get_github_client()
    if not github:
        return json.dumps({"error": "Failed to initialize GitHub client"})

    try:
        # Get the local path for this repository
        local_path = github._get_repo_local_path(repository_url)

        # Get repository info
        info = github.get_repository_info(local_path)

        if not info["exists"]:
            return json.dumps({
                "error": "Repository not cloned",
                "hint": f"Use notiondev_clone_module('{module_prefix}') to clone first"
            })

        return json.dumps({
            "module": {
                "name": module_name,
                "code_prefix": module_prefix
            },
            "repository": {
                "path": info["path"],
                "branch": info["branch"],
                "remote_url": info["remote_url"],
                "last_commit": info["last_commit"],
                "code_path": code_path,
                "full_code_path": os.path.join(info["path"], code_path) if code_path else info["path"]
            }
        }, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def notiondev_cleanup_cloned_repos() -> str:
    """Remove all cloned repositories to free up disk space.

    Returns:
        JSON with number of repositories removed
    """
    github = get_github_client()
    if not github:
        return json.dumps({"error": "Failed to initialize GitHub client"})

    try:
        count = github.cleanup_all()
        return json.dumps({
            "success": True,
            "message": f"Removed {count} cloned repositories",
            "clone_dir": github.clone_dir
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


# =============================================================================
# MCP Prompts - Methodology & Templates
# =============================================================================

@mcp.prompt()
async def notiondev_methodology() -> str:
    """Get an explanation of the NotionDev specs-first methodology.

    Use this prompt to understand how to organize documentation
    in Notion with modules and features.
    """
    return """# NotionDev Specs-First Methodology

## Philosophy

NotionDev implements a **specs-first** approach to development where all functional
specifications are documented in Notion BEFORE coding begins. This ensures:

1. **Clear requirements** - Developers know exactly what to build
2. **AI context** - AI assistants receive complete specifications
3. **Traceability** - Code can be traced back to specifications
4. **No regressions** - AI agents are instructed not to modify code for other features

## Documentation Structure

### Two-Level Hierarchy

```
Module (e.g., "User Authentication")
├── Feature CC01 - User Registration
├── Feature CC02 - Password Reset
├── Feature CC03 - OAuth Integration
└── ...
```

### Module Documentation

A module represents a functional domain of your application. Each module MUST include:

1. **Objective** - What this module does
2. **Stack Technique** - Languages, frameworks, databases
3. **Architecture** - How components interact
4. **Data Model** - Entities and relationships
5. **Environments** - Dev, staging, prod URLs
6. **Hosting** - Cloud provider, services
7. **CI/CD** - Commands for local dev, tests, migrations
8. **Security & Compliance** - Auth, authorization, GDPR
9. **Environment Variables** - Required configuration
10. **External Dependencies** - Third-party services
11. **Useful Links** - External documentation

### Feature Documentation

A feature represents a specific functionality. Each feature MUST include:

1. **Description** - What the feature does
2. **Use Cases** - User stories and scenarios
3. **Business Rules** - Logic and constraints
4. **Endpoints/Routes** - API or UI routes
5. **UI Components** - Frontend elements (if applicable)
6. **Data Model** - Entities affected
7. **Required Tests** - Unit, integration, E2E

## Workflow

### Definition of Ready (DoR)

A feature is ready for development when:
- [ ] Documentation is complete in Notion
- [ ] Status is "Validated" (or "Review" for minor features)
- [ ] An Asana ticket exists with the feature code
- [ ] The ticket is assigned to a developer

### Development Cycle

1. **Select ticket**: `notion-dev tickets`
2. **Start work**: `notion-dev work TASK-ID`
   - Loads specs from Notion
   - Exports to AGENTS.md
   - Comments on Asana ticket
3. **Develop**: Code with AI assistant (context is in AGENTS.md)
4. **Update**: Document any changes back to Notion
5. **Complete**: `notion-dev done`
   - Comments on ticket
   - Reassigns to creator for review

### Feature Codes

Each feature has a unique code:
- Format: `{MODULE_PREFIX}{NUMBER}` (e.g., CC01, API02)
- Module prefix: 2-3 uppercase letters
- Number: 2 digits, zero-padded

The feature code is used:
- In Asana ticket titles/descriptions
- In code file headers for traceability
- To link documentation to implementation

## Code Traceability

Generated AGENTS.md includes instructions for AI to add headers:

```python
# NOTION FEATURES: CC01
# MODULES: User Authentication
# DESCRIPTION: User registration endpoint
# LAST_SYNC: 2025-01-15

def register_user():
    ...
```

This enables:
- Tracking which features are implemented where
- Preventing accidental modification of other features
- Code review verification against specs

## Best Practices

1. **Document first, code later** - Never start coding without specs
2. **Keep docs updated** - Sync changes back to Notion
3. **One feature per ticket** - Clear scope and traceability
4. **Use feature codes** - Always reference in commits and code
5. **Review regularly** - Mark obsolete features appropriately
"""


@mcp.prompt()
async def notiondev_module_template() -> str:
    """Get the documentation template for a new module.

    Use this template when creating module documentation in Notion.
    """
    return """# Module Documentation Template

Copy and customize this template for your module documentation in Notion.

---

# {Module Name}

## Objective

{Describe the main purpose and goals of this module. What problem does it solve?}

## Stack Technique

- **Languages**: {e.g., Python 3.11, TypeScript 5.x}
- **Frameworks**: {e.g., FastAPI 0.100+, React 18}
- **Database**: {e.g., PostgreSQL 15, Redis 7}
- **Other**: {e.g., Celery, RabbitMQ, Elasticsearch}

## Architecture

{Describe the architecture of this module:
- Main components and their responsibilities
- How they interact
- External integrations
- Include diagrams if helpful}

## Data Model

{Describe the main entities:

### Entity Name
| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| ... | ... | ... |

### Relationships
- Entity A → Entity B: {relationship description}
}

## Environments

| Environment | URL | Notes |
|-------------|-----|-------|
| Development | http://localhost:8000 | Local development |
| Staging | https://staging.example.com | Pre-production testing |
| Production | https://api.example.com | Live environment |

## Hosting

- **Provider**: {e.g., AWS, GCP, Azure, OVH}
- **Services**: {e.g., ECS, Cloud Run, EC2, VPS}
- **CDN**: {e.g., CloudFront, Cloudflare}
- **Storage**: {e.g., S3, GCS}

## CI/CD

### Local Development Commands

```bash
# Start the development server
{command}

# Run tests
{command}

# Run linting
{command}

# Build for production
{command}
```

### Database Migrations

{Describe the migration protocol:
1. How to create migrations
2. How to apply locally
3. How to apply in production
4. Rollback procedures}

### Pipeline

{Describe the CI/CD pipeline:
- Triggers (push, PR, manual)
- Stages (build, test, deploy)
- Environment promotion}

## Security & Compliance

- **Authentication**: {e.g., JWT, OAuth2, API Keys}
- **Authorization**: {e.g., RBAC, ABAC, policies}
- **Data Protection**: {e.g., encryption at rest/transit}
- **Compliance**: {e.g., GDPR, SOC2, HIPAA}
- **Secrets Management**: {e.g., AWS Secrets Manager, Vault}

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| DATABASE_URL | Database connection string | postgresql://... |
| SECRET_KEY | Application secret | {random string} |
| ... | ... | ... |

## External Dependencies

| Service | Purpose | Documentation |
|---------|---------|---------------|
| Stripe | Payments | https://stripe.com/docs |
| SendGrid | Email | https://docs.sendgrid.com |
| ... | ... | ... |

## Useful Links

- [Framework Documentation](url)
- [API Reference](url)
- [Internal Wiki](url)
"""


@mcp.prompt()
async def notiondev_feature_template() -> str:
    """Get the documentation template for a new feature.

    Use this template when creating feature documentation in Notion.
    """
    return """# Feature Documentation Template

Copy and customize this template for your feature documentation in Notion.

---

# {Feature Name}

## Description

{Provide a clear, concise description of what this feature does from a user perspective.}

## Use Cases

### UC1: {Use Case Name}
**Actor**: {User role}
**Preconditions**: {What must be true before}
**Flow**:
1. User does X
2. System responds with Y
3. ...
**Postconditions**: {What is true after}

### UC2: {Another Use Case}
...

## Business Rules

| ID | Rule | Description |
|----|------|-------------|
| BR1 | {Rule name} | {Detailed description} |
| BR2 | {Rule name} | {Detailed description} |
| ... | ... | ... |

## Endpoints / Routes

### API Endpoints (if backend)

| Method | Route | Description | Auth |
|--------|-------|-------------|------|
| GET | /api/v1/resource | List resources | Required |
| POST | /api/v1/resource | Create resource | Required |
| GET | /api/v1/resource/:id | Get resource | Required |
| PUT | /api/v1/resource/:id | Update resource | Required |
| DELETE | /api/v1/resource/:id | Delete resource | Admin |

### Request/Response Examples

**POST /api/v1/resource**
```json
// Request
{
  "name": "Example",
  "value": 123
}

// Response 201
{
  "id": "uuid",
  "name": "Example",
  "value": 123,
  "created_at": "2025-01-15T10:00:00Z"
}
```

### UI Routes (if frontend)

| Route | Component | Description |
|-------|-----------|-------------|
| /dashboard | Dashboard | Main dashboard view |
| /resource/:id | ResourceDetail | Detail view |
| ... | ... | ... |

## UI Components

### Component Name
- **Purpose**: {What it does}
- **Props**: {Input properties}
- **Events**: {Events emitted}
- **Mockup**: {Link to design or description}

## Data Model

### Entities Affected

| Entity | Changes |
|--------|---------|
| Resource | New fields: X, Y |
| User | New relation to Resource |

### New Fields

| Entity | Field | Type | Description |
|--------|-------|------|-------------|
| Resource | status | enum | active, inactive, pending |
| ... | ... | ... | ... |

## Required Tests

### Unit Tests
- [ ] Test case 1: {description}
- [ ] Test case 2: {description}

### Integration Tests
- [ ] API endpoint returns correct data
- [ ] Database operations work correctly

### E2E Tests
- [ ] User can complete flow from start to finish
- [ ] Error states are handled correctly

## Dependencies

### Feature Dependencies
- Requires: {Feature codes that must be implemented first}
- Blocks: {Feature codes that depend on this}

### External Dependencies
- {Third-party service or API if needed}

## Notes

{Any additional notes, considerations, or technical debt to address later}
"""


@mcp.prompt()
async def notiondev_init_project() -> str:
    """Start the interactive project initialization workflow.

    This prompt guides you through documenting an existing project
    in Notion with modules and features.
    """
    return """# Project Documentation Initialization

I'll help you document your existing project in Notion. This is an interactive process
where I'll analyze your codebase and ask questions to build comprehensive documentation.

## Process Overview

1. **Code Analysis** - I'll read your project structure and existing documentation
2. **Initial Draft** - Generate a "naive" documentation based on what I observe
3. **Project Understanding** - Questions about objectives and architecture
4. **Functional Details** - Questions about features and user flows
5. **Technical Stack** - Confirm technologies and infrastructure
6. **Module Definition** - Define modules with complete information
7. **Feature List** - Identify and document features
8. **Notion Creation** - Create the documentation in Notion

## Let's Begin!

To start, I need to understand your project. Please answer the following:

### Step 1: Basic Information

1. **What is the name of your project?**

2. **In one sentence, what does your project do?**

3. **Who are the main users of this application?**

4. **Is this project a Backend, Frontend, or Service (or multiple)?**

---

Once you answer these questions, I'll analyze your codebase and continue with more specific questions.

**Note**: During this process, I'll use the following tools:
- Read files to understand your code structure
- `notiondev_create_module` to create modules in Notion
- `notiondev_create_feature` to create features in Notion

Ready? Please answer the questions above to begin!
"""


# =============================================================================
# MCP Tools - Code Reading (ND03 - Remote mode only)
# =============================================================================

@mcp.tool()
async def notiondev_read_file(
    module_prefix: str,
    file_path: str,
    start_line: int = 1,
    end_line: Optional[int] = None,
) -> str:
    """Read the contents of a file in a cloned repository.

    This tool is available in remote mode for Product Owners to analyze code.

    Args:
        module_prefix: Module code prefix (e.g., 'CC', 'API')
        file_path: Relative path to file within the repository
        start_line: First line to read (1-indexed, default: 1)
        end_line: Last line to read (None for all lines)

    Returns:
        JSON with file content and metadata
    """
    config = get_config()
    if not config.is_tool_enabled("notiondev_read_file"):
        return json.dumps({
            "error": "This tool is only available in remote mode",
            "hint": "Use standard file reading tools in local mode"
        })

    # Get module from Notion to retrieve repository_url
    from .remote_backend import get_remote_backend
    backend = get_remote_backend()
    module = backend.get_module(module_prefix)
    repository_url = module.get("repository_url") if module else None

    from .code_tools import get_code_reader
    reader = get_code_reader()
    result = reader.read_file(module_prefix, file_path, start_line, end_line, repository_url)
    return json.dumps(result, indent=2)


@mcp.tool()
async def notiondev_search_code(
    module_prefix: str,
    pattern: str,
    glob: str = "**/*",
    max_results: int = 50,
    context_lines: int = 2,
) -> str:
    """Search for a pattern in the code of a module.

    This tool is available in remote mode for Product Owners to analyze code.

    Args:
        module_prefix: Module code prefix (e.g., 'CC', 'API')
        pattern: Regex pattern to search for
        glob: File glob pattern to filter files (default: all files)
        max_results: Maximum number of matches to return (default: 50)
        context_lines: Number of context lines before/after match (default: 2)

    Returns:
        JSON with search results including file paths, line numbers, and context
    """
    config = get_config()
    if not config.is_tool_enabled("notiondev_search_code"):
        return json.dumps({
            "error": "This tool is only available in remote mode",
            "hint": "Use standard grep/search tools in local mode"
        })

    # Get module from Notion to retrieve repository_url
    from .remote_backend import get_remote_backend
    backend = get_remote_backend()
    module = backend.get_module(module_prefix)
    repository_url = module.get("repository_url") if module else None

    from .code_tools import get_code_reader
    reader = get_code_reader()
    result = reader.search_code(module_prefix, pattern, glob, max_results, context_lines, repository_url)
    return json.dumps(result, indent=2)


@mcp.tool()
async def notiondev_list_files(
    module_prefix: str,
    glob_pattern: str = "**/*",
    include_size: bool = False,
    max_files: int = 500,
) -> str:
    """List files in a module's repository.

    This tool is available in remote mode for Product Owners to explore code structure.

    Args:
        module_prefix: Module code prefix (e.g., 'CC', 'API')
        glob_pattern: Glob pattern to filter files (default: all files)
        include_size: Include file sizes in results (default: false)
        max_files: Maximum number of files to return (default: 500)

    Returns:
        JSON with file listing
    """
    config = get_config()
    if not config.is_tool_enabled("notiondev_list_files"):
        return json.dumps({
            "error": "This tool is only available in remote mode",
            "hint": "Use standard ls/find tools in local mode"
        })

    # Get module from Notion to retrieve repository_url
    from .remote_backend import get_remote_backend
    backend = get_remote_backend()
    module = backend.get_module(module_prefix)
    repository_url = module.get("repository_url") if module else None

    from .code_tools import get_code_reader
    reader = get_code_reader()
    result = reader.list_files(module_prefix, glob_pattern, include_size, max_files, repository_url)
    return json.dumps(result, indent=2)


@mcp.tool()
async def notiondev_prepare_feature_context(
    module_prefix: str,
    feature_code: str,
    max_total_lines: int = 2000,
) -> str:
    """Prepare aggregated code context for a feature.

    This tool intelligently gathers relevant code for a feature:
    1. Searches for files containing the feature code in headers
    2. Identifies related imports and dependencies
    3. Creates a summary suitable for AI analysis

    This is the primary tool for Product Owners to understand feature implementation.

    Args:
        module_prefix: Module code prefix (e.g., 'CC', 'API')
        feature_code: Feature code (e.g., 'CC01', 'API02')
        max_total_lines: Maximum total lines to include (default: 2000)

    Returns:
        JSON with aggregated context including:
        - primary_files: Files with feature header
        - secondary_files: Files referencing the feature
        - tree_summary: Directory structure
        - suggestions: Recommendations for further analysis
    """
    config = get_config()
    if not config.is_tool_enabled("notiondev_prepare_feature_context"):
        return json.dumps({
            "error": "This tool is only available in remote mode",
            "hint": "Use notiondev_work_on_ticket in local mode for similar functionality"
        })

    # Get module from Notion to retrieve repository_url
    from .remote_backend import get_remote_backend
    backend = get_remote_backend()
    module = backend.get_module(module_prefix)
    repository_url = module.get("repository_url") if module else None

    from .code_tools import get_code_reader
    reader = get_code_reader()
    result = reader.prepare_feature_context(module_prefix, feature_code, max_total_lines, repository_url)
    return json.dumps(result, indent=2)


# =============================================================================
# MCP Resources - Configuration & State
# =============================================================================

@mcp.resource("notiondev://config")
async def get_config_resource() -> str:
    """Get the current NotionDev configuration (without sensitive tokens)."""
    try:
        from ..core.config import Config
        config = Config.load()

        return json.dumps({
            "notion": {
                "database_modules_id": config.notion.database_modules_id,
                "database_features_id": config.notion.database_features_id,
                "token_configured": bool(config.notion.token)
            },
            "asana": {
                "workspace_gid": config.asana.workspace_gid,
                "user_gid": config.asana.user_gid,
                "portfolio_gid": config.asana.portfolio_gid,
                "token_configured": bool(config.asana.access_token)
            },
            "config_path": str(get_config_path())
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.resource("notiondev://current-task")
async def get_current_task_resource() -> str:
    """Get information about the current working task."""
    result = run_notion_dev_command(["info", "--json"])

    if result["success"]:
        try:
            data = json.loads(result["output"])
            return json.dumps(data.get("current_task") or {"message": "No current task"}, indent=2)
        except json.JSONDecodeError:
            return json.dumps({"error": "Invalid JSON response"})
    else:
        return json.dumps({"error": result.get("error", "Failed to get current task")})


@mcp.resource("notiondev://methodology")
async def get_methodology_resource() -> str:
    """Get the specs-first methodology documentation."""
    # Return the same content as the prompt
    return await notiondev_methodology()


# =============================================================================
# Main entry point
# =============================================================================

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="NotionDev MCP Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Local mode (default) - for Claude Code CLI
  python -m notion_dev.mcp_server.server

  # Remote mode - for Claude.ai web interface
  python -m notion_dev.mcp_server.server --transport sse --port 8000 --auth

Environment variables (for remote mode):
  GOOGLE_CLIENT_ID       Google OAuth client ID
  GOOGLE_CLIENT_SECRET   Google OAuth client secret
  JWT_SECRET             Secret for JWT token signing
  ALLOWED_EMAIL_DOMAIN   Restrict login to this domain
  SERVICE_NOTION_TOKEN   Notion token for service account
  SERVICE_ASANA_TOKEN    Asana PAT for service account
        """
    )

    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="Transport mode: stdio (local) or sse (remote). Default: stdio"
    )

    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for SSE transport. Default: 8000"
    )

    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind for SSE transport. Default: 0.0.0.0"
    )

    parser.add_argument(
        "--auth",
        action="store_true",
        help="Enable Google OAuth authentication (required for remote mode)"
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )

    return parser.parse_args()


def main():
    """Run the MCP server."""
    if not MCP_AVAILABLE:
        print("ERROR: The 'mcp' package is not installed.", file=sys.stderr)
        print("", file=sys.stderr)
        print("The MCP package requires Python 3.10 or higher.", file=sys.stderr)
        print("Your current Python version: {}".format(sys.version.split()[0]), file=sys.stderr)
        print("", file=sys.stderr)
        print("To install the MCP package:", file=sys.stderr)
        print("  1. Upgrade to Python 3.10+ (recommended: Python 3.11 or 3.12)", file=sys.stderr)
        print("  2. Then run: pip install notion-dev[mcp]", file=sys.stderr)
        print("", file=sys.stderr)
        print("Alternatively, you can use notion-dev CLI directly:", file=sys.stderr)
        print("  notion-dev --help", file=sys.stderr)
        sys.exit(1)

    # Parse command line arguments
    args = parse_args()

    # Configure logging level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")

    # Initialize server configuration
    config = ServerConfig.from_args(
        transport=args.transport,
        port=args.port,
        host=args.host,
        auth=args.auth,
    )
    set_config(config)

    # Validate configuration for remote mode
    if config.is_remote:
        errors = config.validate()
        if errors:
            print("ERROR: Invalid configuration for remote mode:", file=sys.stderr)
            for error in errors:
                print(f"  - {error}", file=sys.stderr)
            print("", file=sys.stderr)
            print("Set the required environment variables and try again.", file=sys.stderr)
            sys.exit(1)

    logger.info(f"Starting NotionDev MCP Server in {config.transport.value} mode...")
    logger.info(f"Configuration: {config}")

    if config.transport == TransportMode.STDIO:
        # Local mode: stdio transport
        logger.info("Running in local mode (stdio transport)")
        mcp.run(transport="stdio")
    else:
        # Remote mode: SSE transport with authentication
        logger.info(f"Running in remote mode (SSE transport on {config.host}:{config.port})")
        logger.info(f"Auth enabled: {config.auth_enabled}")
        if config.allowed_email_domain:
            logger.info(f"Allowed domain: {config.allowed_email_domain}")

        # Initialize remote backend
        from .remote_backend import get_remote_backend
        try:
            backend = get_remote_backend()
            if backend.is_configured:
                logger.info("Remote backend initialized successfully")
                # Test connection
                info = backend.get_info()
                logger.info(f"Backend info: {info}")
            else:
                logger.warning("Remote backend not fully configured - missing service tokens")
        except Exception as e:
            logger.error(f"Failed to initialize remote backend: {e}")

        # Initialize OAuth middleware if auth is enabled
        auth_middleware = None
        if config.auth_enabled:
            from .auth import create_auth_middleware_from_config
            auth_middleware = create_auth_middleware_from_config()
            if auth_middleware:
                logger.info("OAuth authentication enabled")
            else:
                logger.warning("Auth enabled but OAuth middleware not configured")

        # For SSE mode, we need to use uvicorn directly with the FastMCP app
        # since mcp.run() doesn't accept host/port parameters
        import uvicorn
        from mcp.server.sse import SseServerTransport
        from starlette.applications import Starlette
        from starlette.routing import Route, Mount
        from starlette.responses import JSONResponse, HTMLResponse, RedirectResponse

        # Create the SSE transport
        sse = SseServerTransport("/messages/")

        # Helper to verify JWT token from request
        def get_user_from_token(request):
            """Extract and verify user from JWT token.

            Supports both:
            - Legacy auth middleware tokens
            - New OAuth server tokens (RFC 8414)
            """
            token = None

            # Try Authorization header (RFC 6750)
            auth_header = request.headers.get("authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]

            # Try cookie (legacy)
            if not token:
                token = request.cookies.get("notiondev_token")

            # Try query parameter (for SSE connections)
            if not token:
                token = request.query_params.get("token")

            if not token:
                return None

            # Try new OAuth server first (if available)
            from .oauth_server import get_oauth_server
            oauth = get_oauth_server()
            if oauth:
                user_info = oauth.verify_access_token(token)
                if user_info:
                    # Return a UserInfo-like object
                    from .auth import UserInfo
                    return UserInfo(
                        email=user_info["email"],
                        name=user_info["name"],
                    )

            # Fall back to legacy auth middleware
            if auth_middleware and auth_middleware.verify_request(token):
                return auth_middleware.current_user

            return None

        # Create handler for SSE endpoint
        async def handle_sse(request):
            from .remote_backend import get_remote_backend

            # If auth is enabled, verify the user
            user = get_user_from_token(request)

            if config.auth_enabled and not user:
                # Redirect to login if not authenticated
                return RedirectResponse(url="/auth/login", status_code=302)

            # Set user context in backend
            if user:
                try:
                    backend = get_remote_backend()
                    remote_user = backend.set_current_user(user.email, user.name)
                    logger.info(f"Set current user: {remote_user.email} (Asana: {remote_user.asana_user_gid})")
                except Exception as e:
                    logger.error(f"Failed to set user context: {e}")
            else:
                # Try headers/query params as fallback (for testing)
                user_email = request.headers.get("x-user-email") or request.query_params.get("user_email")
                user_name = request.headers.get("x-user-name", "Claude User")
                if user_email:
                    try:
                        backend = get_remote_backend()
                        remote_user = backend.set_current_user(user_email, user_name)
                        logger.info(f"Set current user (fallback): {remote_user.email}")
                    except Exception as e:
                        logger.error(f"Failed to set user context: {e}")

            async with sse.connect_sse(
                request.scope, request.receive, request._send
            ) as streams:
                await mcp._mcp_server.run(
                    streams[0], streams[1], mcp._mcp_server.create_initialization_options()
                )

        # Create handler for messages endpoint
        async def handle_messages(request):
            from .remote_backend import get_remote_backend

            # If auth is enabled, verify the user (same logic as handle_sse)
            user = get_user_from_token(request)

            if config.auth_enabled and not user:
                return JSONResponse({"error": "Unauthorized"}, status_code=401)

            # Set user context in backend
            if user:
                try:
                    backend = get_remote_backend()
                    remote_user = backend.set_current_user(user.email, user.name)
                    logger.info(f"Set current user (messages): {remote_user.email} (Asana: {remote_user.asana_user_gid})")
                except Exception as e:
                    logger.error(f"Failed to set user context: {e}")
            else:
                # Try headers/query params as fallback (for testing)
                user_email = request.headers.get("x-user-email") or request.query_params.get("user_email")
                user_name = request.headers.get("x-user-name", "Claude User")
                if user_email:
                    try:
                        backend = get_remote_backend()
                        remote_user = backend.set_current_user(user_email, user_name)
                        logger.info(f"Set current user (messages fallback): {remote_user.email}")
                    except Exception as e:
                        logger.error(f"Failed to set user context: {e}")

            await sse.handle_post_message(request.scope, request.receive, request._send)

        # Create health check endpoint
        async def health_check(request):
            from .remote_backend import get_remote_backend
            try:
                backend = get_remote_backend()
                info = backend.get_info()
                return JSONResponse({
                    "status": "ok",
                    "server": "notiondev-mcp",
                    "mode": "remote",
                    "configured": info.get("configured", False),
                    "asana_connected": info.get("asana", {}).get("connected", False),
                    "auth_enabled": config.auth_enabled
                })
            except Exception as e:
                return JSONResponse({
                    "status": "ok",
                    "server": "notiondev-mcp",
                    "mode": "remote",
                    "error": str(e)
                })

        # OAuth login page
        async def auth_login(request):
            if not auth_middleware:
                return JSONResponse({"error": "OAuth not configured"}, status_code=500)

            login_url = auth_middleware.get_login_url()
            # Return a simple HTML page that redirects to Google
            return HTMLResponse(f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>NotionDev - Login</title>
                <meta http-equiv="refresh" content="0;url={login_url}">
                <style>
                    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                           display: flex; justify-content: center; align-items: center; height: 100vh;
                           margin: 0; background: #f5f5f5; }}
                    .container {{ text-align: center; padding: 40px; background: white; border-radius: 8px;
                                 box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                    a {{ color: #4285f4; text-decoration: none; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h2>NotionDev MCP Server</h2>
                    <p>Redirecting to Google login...</p>
                    <p><a href="{login_url}">Click here if not redirected</a></p>
                </div>
            </body>
            </html>
            """)

        # OAuth callback
        async def auth_callback(request):
            if not auth_middleware:
                return JSONResponse({"error": "OAuth not configured"}, status_code=500)

            code = request.query_params.get("code")
            state = request.query_params.get("state")

            if not code or not state:
                return JSONResponse({"error": "Missing code or state"}, status_code=400)

            try:
                from .auth import OAuthError
                token = await auth_middleware.handle_callback(code, state)

                # Return HTML with token that can be used for SSE connection
                return HTMLResponse(f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>NotionDev - Authenticated</title>
                    <style>
                        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                               display: flex; justify-content: center; align-items: center; height: 100vh;
                               margin: 0; background: #f5f5f5; }}
                        .container {{ text-align: center; padding: 40px; background: white; border-radius: 8px;
                                     box-shadow: 0 2px 4px rgba(0,0,0,0.1); max-width: 600px; }}
                        .token {{ background: #f0f0f0; padding: 10px; border-radius: 4px;
                                 word-break: break-all; font-family: monospace; font-size: 12px;
                                 margin: 20px 0; }}
                        .success {{ color: #28a745; }}
                        code {{ background: #e9ecef; padding: 2px 6px; border-radius: 3px; }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <h2 class="success">Authentication Successful!</h2>
                        <p>Welcome to NotionDev MCP Server</p>
                        <p>Your session token (valid for {config.jwt_expiration_hours} hour):</p>
                        <div class="token">{token}</div>
                        <p><strong>To use with Claude.ai:</strong></p>
                        <p>Add the SSE URL with your token:</p>
                        <code>/sse?token={token[:20]}...</code>
                        <p style="margin-top: 20px; color: #666; font-size: 14px;">
                            You can close this window and configure the MCP server in Claude.ai settings.
                        </p>
                    </div>
                </body>
                </html>
                """, headers={"Set-Cookie": f"notiondev_token={token}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=3600"})

            except Exception as e:
                logger.error(f"OAuth callback error: {e}")
                return HTMLResponse(f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>NotionDev - Error</title>
                    <style>
                        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                               display: flex; justify-content: center; align-items: center; height: 100vh;
                               margin: 0; background: #f5f5f5; }}
                        .container {{ text-align: center; padding: 40px; background: white; border-radius: 8px;
                                     box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                        .error {{ color: #dc3545; }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <h2 class="error">Authentication Failed</h2>
                        <p>{str(e)}</p>
                        <p><a href="/auth/login">Try again</a></p>
                    </div>
                </body>
                </html>
                """, status_code=400)

        # User info endpoint
        async def auth_me(request):
            user = get_user_from_token(request)
            if user:
                return JSONResponse(user.to_dict())
            return JSONResponse({"error": "Not authenticated"}, status_code=401)

        # =====================================================================
        # OAuth 2.0 endpoints (RFC 8414, RFC 7591) for Claude.ai compatibility
        # =====================================================================

        # Initialize OAuth server if auth is enabled
        oauth_server = None
        if config.auth_enabled:
            from .oauth_server import init_oauth_server

            # Determine base URL
            base_url = os.environ.get("MCP_BASE_URL", f"http://localhost:{config.port}")

            oauth_server = init_oauth_server(
                issuer=base_url,
                jwt_secret=config.jwt_secret,
                google_client_id=config.google_client_id,
                google_client_secret=config.google_client_secret,
                allowed_domain=config.allowed_email_domain,
                allowed_emails=config.allowed_emails,
                token_expiration_seconds=config.jwt_expiration_hours * 3600,
            )
            logger.info(f"OAuth server initialized with issuer: {base_url}")

        # OAuth metadata endpoint (RFC 8414)
        async def oauth_metadata(request):
            if not oauth_server:
                return JSONResponse({"error": "OAuth not configured"}, status_code=500)
            return JSONResponse(oauth_server.get_metadata())

        # Protected resource metadata
        async def oauth_protected_resource(request):
            if not oauth_server:
                return JSONResponse({"error": "OAuth not configured"}, status_code=500)
            return JSONResponse(oauth_server.get_protected_resource_metadata())

        # Dynamic client registration (RFC 7591)
        async def oauth_register(request):
            if not oauth_server:
                return JSONResponse({"error": "OAuth not configured"}, status_code=500)

            try:
                body = await request.json()
                result = oauth_server.register_client(body)
                return JSONResponse(result, status_code=201)
            except json.JSONDecodeError:
                return JSONResponse({"error": "invalid_request", "error_description": "Invalid JSON"}, status_code=400)
            except ValueError as e:
                return JSONResponse({"error": "invalid_client_metadata", "error_description": str(e)}, status_code=400)
            except Exception as e:
                logger.error(f"Registration error: {e}")
                return JSONResponse({"error": "server_error", "error_description": str(e)}, status_code=500)

        # Authorization endpoint
        async def oauth_authorize(request):
            if not oauth_server:
                return JSONResponse({"error": "OAuth not configured"}, status_code=500)

            try:
                # Get query parameters
                client_id = request.query_params.get("client_id")
                redirect_uri = request.query_params.get("redirect_uri")
                scope = request.query_params.get("scope", "mcp:tools")
                state = request.query_params.get("state")
                code_challenge = request.query_params.get("code_challenge")
                code_challenge_method = request.query_params.get("code_challenge_method", "S256")
                response_type = request.query_params.get("response_type")

                if response_type != "code":
                    return JSONResponse({
                        "error": "unsupported_response_type",
                        "error_description": "Only 'code' response_type is supported"
                    }, status_code=400)

                if not all([client_id, redirect_uri, code_challenge]):
                    return JSONResponse({
                        "error": "invalid_request",
                        "error_description": "Missing required parameters"
                    }, status_code=400)

                # Create Google OAuth URL
                auth_url = oauth_server.create_authorization_url(
                    client_id=client_id,
                    redirect_uri=redirect_uri,
                    scope=scope,
                    state=state or "",
                    code_challenge=code_challenge,
                    code_challenge_method=code_challenge_method,
                )

                return RedirectResponse(url=auth_url, status_code=302)

            except ValueError as e:
                error_msg = str(e)
                if "invalid_client" in error_msg:
                    return JSONResponse({"error": "invalid_client"}, status_code=401)
                elif "invalid_redirect_uri" in error_msg:
                    return JSONResponse({"error": "invalid_redirect_uri"}, status_code=400)
                else:
                    return JSONResponse({"error": "invalid_request", "error_description": error_msg}, status_code=400)
            except Exception as e:
                logger.error(f"Authorization error: {e}")
                return JSONResponse({"error": "server_error"}, status_code=500)

        # Google OAuth callback (internal)
        async def oauth_google_callback(request):
            if not oauth_server:
                return JSONResponse({"error": "OAuth not configured"}, status_code=500)

            code = request.query_params.get("code")
            state = request.query_params.get("state")
            error = request.query_params.get("error")

            if error:
                logger.error(f"Google OAuth error: {error}")
                return HTMLResponse(f"""
                <!DOCTYPE html>
                <html>
                <head><title>Authentication Failed</title></head>
                <body>
                    <h1>Authentication Failed</h1>
                    <p>Error: {error}</p>
                </body>
                </html>
                """, status_code=400)

            if not code or not state:
                return JSONResponse({"error": "invalid_request"}, status_code=400)

            try:
                redirect_url = await oauth_server.handle_google_callback(code, state)
                return RedirectResponse(url=redirect_url, status_code=302)

            except ValueError as e:
                error_msg = str(e)
                logger.error(f"Google callback error: {error_msg}")

                # Show user-friendly error page
                if "domain_not_allowed" in error_msg:
                    message = "Your email domain is not authorized to access this application."
                elif "email_not_allowed" in error_msg:
                    message = "Your email address is not authorized to access this application."
                else:
                    message = f"Authentication failed: {error_msg}"

                return HTMLResponse(f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Authentication Failed</title>
                    <style>
                        body {{ font-family: -apple-system, sans-serif; display: flex;
                               justify-content: center; align-items: center; height: 100vh;
                               margin: 0; background: #f5f5f5; }}
                        .container {{ text-align: center; padding: 40px; background: white;
                                     border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                        .error {{ color: #dc3545; }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <h2 class="error">Authentication Failed</h2>
                        <p>{message}</p>
                    </div>
                </body>
                </html>
                """, status_code=403)
            except Exception as e:
                logger.error(f"Unexpected error in Google callback: {e}")
                return JSONResponse({"error": "server_error"}, status_code=500)

        # Token endpoint
        async def oauth_token(request):
            if not oauth_server:
                return JSONResponse({"error": "OAuth not configured"}, status_code=500)

            try:
                # Parse form data
                form = await request.form()
                grant_type = form.get("grant_type")
                code = form.get("code")
                redirect_uri = form.get("redirect_uri")
                client_id = form.get("client_id")
                code_verifier = form.get("code_verifier")

                if not all([grant_type, code, redirect_uri, client_id, code_verifier]):
                    return JSONResponse({
                        "error": "invalid_request",
                        "error_description": "Missing required parameters"
                    }, status_code=400)

                result = oauth_server.exchange_code_for_token(
                    grant_type=grant_type,
                    code=code,
                    redirect_uri=redirect_uri,
                    client_id=client_id,
                    code_verifier=code_verifier,
                )

                return JSONResponse(result)

            except ValueError as e:
                error_msg = str(e)
                if "invalid_grant" in error_msg:
                    return JSONResponse({"error": "invalid_grant", "error_description": error_msg}, status_code=400)
                elif "unsupported_grant_type" in error_msg:
                    return JSONResponse({"error": "unsupported_grant_type"}, status_code=400)
                else:
                    return JSONResponse({"error": "invalid_request", "error_description": error_msg}, status_code=400)
            except Exception as e:
                logger.error(f"Token error: {e}")
                return JSONResponse({"error": "server_error"}, status_code=500)

        # Build routes
        routes = [
            Route("/health", health_check, methods=["GET"]),
            Route("/sse", handle_sse, methods=["GET"]),
            Route("/messages/", handle_messages, methods=["POST"]),
        ]

        # Add OAuth 2.0 routes (required by Claude.ai)
        if config.auth_enabled:
            routes.extend([
                # OAuth 2.0 metadata (RFC 8414)
                Route("/.well-known/oauth-authorization-server", oauth_metadata, methods=["GET"]),
                Route("/.well-known/oauth-authorization-server/sse", oauth_metadata, methods=["GET"]),
                Route("/.well-known/oauth-protected-resource", oauth_protected_resource, methods=["GET"]),
                Route("/.well-known/oauth-protected-resource/sse", oauth_protected_resource, methods=["GET"]),
                # Dynamic Client Registration (RFC 7591)
                Route("/register", oauth_register, methods=["POST"]),
                # Authorization flow
                Route("/authorize", oauth_authorize, methods=["GET"]),
                Route("/oauth/google/callback", oauth_google_callback, methods=["GET"]),
                Route("/token", oauth_token, methods=["POST"]),
                # Legacy auth routes (kept for backwards compatibility)
                Route("/auth/login", auth_login, methods=["GET"]),
                Route("/auth/callback", auth_callback, methods=["GET"]),
                Route("/auth/me", auth_me, methods=["GET"]),
            ])

        # Create Starlette app with routes
        app = Starlette(routes=routes)

        # Run with uvicorn
        uvicorn.run(app, host=config.host, port=config.port, log_level="info")


if __name__ == "__main__":
    main()
