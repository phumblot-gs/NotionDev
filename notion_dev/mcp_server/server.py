# notion_dev/mcp_server/server.py
"""
NotionDev MCP Server - Main entry point

This server exposes NotionDev functionality to Claude Code via the
Model Context Protocol (MCP).

Usage:
    python -m notion_dev.mcp_server.server

Or via Claude Code:
    claude mcp add --transport stdio notiondev -- python -m notion_dev.mcp_server.server
"""

import os
import sys
import json
import logging
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any

try:
    from mcp.server.fastmcp import FastMCP
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    FastMCP = None

# Configure logging to stderr (stdout is reserved for MCP protocol)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

# Initialize FastMCP server (only if mcp package is available)
if MCP_AVAILABLE:
    mcp = FastMCP("notiondev")
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


def get_notion_client():
    """Get a configured NotionClient instance."""
    try:
        from ..core.config import Config
        from ..core.notion_client import NotionClient

        config = Config.load()
        return NotionClient(
            config.notion.token,
            config.notion.database_modules_id,
            config.notion.database_features_id
        )
    except Exception as e:
        logger.error(f"Failed to initialize NotionClient: {e}")
        return None


def get_asana_client():
    """Get a configured AsanaClient instance."""
    try:
        from ..core.config import Config
        from ..core.asana_client import AsanaClient

        config = Config.load()
        return AsanaClient(
            config.asana.access_token,
            config.asana.workspace_gid,
            config.asana.user_gid,
            config.asana.portfolio_gid
        )
    except Exception as e:
        logger.error(f"Failed to initialize AsanaClient: {e}")
        return None


# =============================================================================
# MCP Tools - Installation & Setup
# =============================================================================

@mcp.tool()
async def notiondev_check_installation() -> str:
    """Check if NotionDev is installed and configured properly.

    Returns the installation status and any issues found.
    """
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
    result = run_notion_dev_command(["info", "--json"])

    if result["success"]:
        return result["output"]
    else:
        return json.dumps({
            "error": result.get("error", "Failed to get info"),
            "details": result.get("output", "")
        })


@mcp.tool()
async def notiondev_work_on_ticket(task_id: str) -> str:
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
    # Run the work command with --yes flag to skip interactive prompts
    result = run_notion_dev_command(["work", task_id, "--yes"], timeout=120)

    if result["success"]:
        return f"Started working on ticket {task_id}.\n\nOutput:\n{result['output']}"
    else:
        return json.dumps({
            "error": result.get("error", "Failed to start work on ticket"),
            "details": result.get("output", ""),
            "hint": "Make sure the ticket ID is correct and you have access to it."
        })


@mcp.tool()
async def notiondev_add_comment(message: str) -> str:
    """Add a comment to the current working ticket in Asana.

    Args:
        message: The comment message to add

    Returns:
        Confirmation or error message
    """
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
    result = run_notion_dev_command(["done"])

    if result["success"]:
        return "Ticket marked as done and reassigned to creator."
    else:
        return json.dumps({
            "error": result.get("error", "Failed to mark ticket as done"),
            "details": result.get("output", "")
        })


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
    asana = get_asana_client()
    if not asana:
        return json.dumps({"error": "Failed to initialize Asana client"})

    try:
        # Prepend feature code to notes if provided
        full_notes = notes
        if feature_code:
            feature_header = f"## Feature Code\n{feature_code}\n\n"
            full_notes = feature_header + notes

        task = asana.create_task(
            name=name,
            notes=full_notes,
            project_gid=project_gid if project_gid else None,
            due_on=due_on if due_on else None
        )

        if task:
            # Build Asana URL
            project_id = task.project_gid or "0"
            asana_url = f"https://app.asana.com/0/{project_id}/{task.gid}"

            return json.dumps({
                "success": True,
                "message": f"Ticket '{name}' created successfully",
                "ticket": {
                    "id": task.gid,
                    "name": task.name,
                    "feature_code": task.feature_code,
                    "url": asana_url,
                    "due_on": task.due_on
                }
            }, indent=2)
        else:
            return json.dumps({"error": "Failed to create ticket"})

    except Exception as e:
        return json.dumps({"error": str(e)})


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
    asana = get_asana_client()
    if not asana:
        return json.dumps({"error": "Failed to initialize Asana client"})

    try:
        task = asana.update_task(
            task_gid=task_id,
            name=name if name else None,
            notes=notes if notes else None,
            append_notes=append_notes,
            due_on=due_on if due_on else None,
            assignee_gid=assignee_gid if assignee_gid else None
        )

        if task:
            # Build Asana URL
            project_id = task.project_gid or "0"
            asana_url = f"https://app.asana.com/0/{project_id}/{task.gid}"

            return json.dumps({
                "success": True,
                "message": f"Ticket '{task.name}' updated successfully",
                "ticket": {
                    "id": task.gid,
                    "name": task.name,
                    "feature_code": task.feature_code,
                    "url": asana_url,
                    "due_on": task.due_on,
                    "completed": task.completed
                }
            }, indent=2)
        else:
            return json.dumps({"error": f"Failed to update ticket {task_id}"})

    except Exception as e:
        return json.dumps({"error": str(e)})


# =============================================================================
# MCP Tools - Notion Documentation
# =============================================================================

@mcp.tool()
async def notiondev_list_modules() -> str:
    """List all modules in the Notion database.

    Returns JSON array of modules with their properties.
    """
    notion = get_notion_client()
    if not notion:
        return json.dumps({"error": "Failed to initialize Notion client"})

    try:
        modules = notion.list_modules()
        return json.dumps([
            {
                "id": m.notion_id,
                "name": m.name,
                "description": m.description,
                "code_prefix": m.code_prefix,
                "application": m.application,
                "status": m.status
            }
            for m in modules
        ], indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def notiondev_get_module(code_prefix: str) -> str:
    """Get detailed information about a specific module.

    Args:
        code_prefix: The module's code prefix (e.g., 'CC', 'API')

    Returns:
        Module details including full documentation content
    """
    notion = get_notion_client()
    if not notion:
        return json.dumps({"error": "Failed to initialize Notion client"})

    try:
        module = notion.get_module_by_prefix(code_prefix)
        if not module:
            return json.dumps({"error": f"Module with prefix '{code_prefix}' not found"})

        return json.dumps({
            "id": module.notion_id,
            "name": module.name,
            "description": module.description,
            "code_prefix": module.code_prefix,
            "application": module.application,
            "status": module.status,
            "content": module.content
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def notiondev_list_features(module_prefix: str = None) -> str:
    """List features, optionally filtered by module.

    Args:
        module_prefix: Optional module prefix to filter features (e.g., 'CC')

    Returns:
        JSON array of features
    """
    notion = get_notion_client()
    if not notion:
        return json.dumps({"error": "Failed to initialize Notion client"})

    try:
        if module_prefix:
            module = notion.get_module_by_prefix(module_prefix)
            if not module:
                return json.dumps({"error": f"Module with prefix '{module_prefix}' not found"})
            features = notion.list_features_for_module(module.notion_id)
        else:
            features = notion.search_features()

        return json.dumps([
            {
                "code": f.code,
                "name": f.name,
                "module": f.module_name,
                "status": f.status,
                "plan": f.plan,
                "user_rights": f.user_rights
            }
            for f in features
        ], indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def notiondev_get_feature(code: str) -> str:
    """Get detailed information about a specific feature.

    Args:
        code: The feature code (e.g., 'CC01', 'API02')

    Returns:
        Feature details including full documentation content
    """
    notion = get_notion_client()
    if not notion:
        return json.dumps({"error": "Failed to initialize Notion client"})

    try:
        feature = notion.get_feature(code)
        if not feature:
            return json.dumps({"error": f"Feature '{code}' not found"})

        return json.dumps({
            "code": feature.code,
            "name": feature.name,
            "module": feature.module_name,
            "status": feature.status,
            "plan": feature.plan,
            "user_rights": feature.user_rights,
            "content": feature.content,
            "module_content": feature.module.content if feature.module else None
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


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
    notion = get_notion_client()
    if not notion:
        return json.dumps({"error": "Failed to initialize Notion client"})

    try:
        module = notion.create_module(
            name=name,
            description=description,
            code_prefix=code_prefix,
            application=application,
            status="Draft",
            content_markdown=content_markdown
        )

        if module:
            return json.dumps({
                "success": True,
                "message": f"Module '{name}' created successfully",
                "module": {
                    "id": module.notion_id,
                    "name": module.name,
                    "code_prefix": module.code_prefix,
                    "application": module.application,
                    "status": module.status
                }
            }, indent=2)
        else:
            return json.dumps({"error": "Failed to create module"})
    except Exception as e:
        return json.dumps({"error": str(e)})


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
    notion = get_notion_client()
    if not notion:
        return json.dumps({"error": "Failed to initialize Notion client"})

    try:
        # Get module by prefix
        module = notion.get_module_by_prefix(module_prefix)
        if not module:
            return json.dumps({"error": f"Module with prefix '{module_prefix}' not found"})

        # Generate next feature code
        code = notion.get_next_feature_code(module.notion_id)

        # Parse plan and user_rights
        plan_list = [p.strip() for p in plan.split(',') if p.strip()] if plan else []
        rights_list = [r.strip() for r in user_rights.split(',') if r.strip()] if user_rights else []

        feature = notion.create_feature(
            code=code,
            name=name,
            module_id=module.notion_id,
            status="Draft",
            plan=plan_list,
            user_rights=rights_list,
            content_markdown=content_markdown
        )

        if feature:
            return json.dumps({
                "success": True,
                "message": f"Feature '{code} - {name}' created successfully",
                "feature": {
                    "code": feature.code,
                    "name": feature.name,
                    "module": feature.module_name,
                    "status": feature.status,
                    "plan": feature.plan,
                    "user_rights": feature.user_rights
                }
            }, indent=2)
        else:
            return json.dumps({"error": "Failed to create feature"})
    except Exception as e:
        return json.dumps({"error": str(e)})


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
    notion = get_notion_client()
    if not notion:
        return json.dumps({"error": "Failed to initialize Notion client"})

    try:
        module = notion.get_module_by_prefix(code_prefix)
        if not module:
            return json.dumps({"error": f"Module with prefix '{code_prefix}' not found"})

        success = notion.update_page_content(
            module.notion_id,
            content_markdown,
            replace=replace
        )

        if success:
            return json.dumps({
                "success": True,
                "message": f"Module '{module.name}' content updated successfully"
            })
        else:
            return json.dumps({"error": "Failed to update module content"})
    except Exception as e:
        return json.dumps({"error": str(e)})


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
    notion = get_notion_client()
    if not notion:
        return json.dumps({"error": "Failed to initialize Notion client"})

    try:
        feature = notion.get_feature(code)
        if not feature:
            return json.dumps({"error": f"Feature '{code}' not found"})

        success = notion.update_page_content(
            feature.notion_id,
            content_markdown,
            replace=replace
        )

        if success:
            return json.dumps({
                "success": True,
                "message": f"Feature '{code}' content updated successfully"
            })
        else:
            return json.dumps({"error": "Failed to update feature content"})
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

    logger.info("Starting NotionDev MCP Server...")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
