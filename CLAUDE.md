# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NotionDev is a Python CLI tool that integrates Notion, Asana, and Git for developers. It streamlines development workflows by automatically loading feature specifications from Notion into the IDE (specifically Cursor) while synchronizing with Asana tickets.

## Commands

### Running the CLI in Development Mode

```bash
# Run from project root
python -m notion_dev.cli.main

# Or with arguments
python -m notion_dev.cli.main tickets
python -m notion_dev.cli.main work TASK-123456789
```

### Installing for Testing

```bash
# Use the installation script
chmod +x install_notion_dev.sh
./install_notion_dev.sh

# Test the installation
~/notion-dev-install/test_config.sh
```

### Key CLI Commands

- `info` - Show current project information
- `tickets` - List Asana tickets (with optional portfolio filtering)
- `work` - Start working on a specific ticket
- `context` - Generate AI context for a feature
- `interactive` - Interactive mode

## Architecture

### Directory Structure

```
notion_dev/
├── __init__.py          # Package initialization with embedded setup.py
├── cli/
│   └── main.py          # Click CLI commands and rich terminal UI
├── core/
│   ├── asana_client.py  # Custom Asana API client using requests
│   ├── config.py        # YAML configuration with dataclasses
│   ├── context_builder.py # AI context generation for Cursor
│   ├── models.py        # Data models (Module, Feature, AsanaTask, AsanaProject)
│   └── notion_client.py # Notion API client wrapper
└── requirements.txt     # Python dependencies
```

### Key Design Patterns

1. **Configuration Management**: Uses YAML configuration stored in `~/.notion-dev/config.yml` with automatic project detection based on working directory. Project-specific cache stored in `.notion-dev/` folders.

2. **API Clients**: 
   - `AsanaClient` - Custom implementation using requests library (NOT the official SDK due to compatibility issues)
   - `NotionClient` - Wrapper around official notion-client SDK
   - Both clients handle authentication and provide typed responses

3. **Data Models**: All data structures use Python dataclasses for type safety and validation

4. **Multi-project Support**: Automatically detects current project from working directory and switches context

5. **Workflow Integration**: Links Asana tickets → Notion features → AI context → Code with automatic header generation for traceability

### Important Implementation Details

- The Asana client uses direct HTTP requests instead of the official SDK due to version compatibility issues
- Feature codes follow patterns like AU01, DA02, API03 (prefix + number)
- Headers are automatically generated in code files for traceability
- Context files are exported to `.cursor/` directory for IDE integration

## Dependencies

Main dependencies (from requirements.txt):
- `click>=8.1.7` - CLI framework
- `rich>=13.7.0` - Terminal formatting
- `notion-client>=2.2.1` - Notion API
- `requests>=2.31.0` - HTTP requests (for Asana)
- `pyyaml>=6.0.1` - Configuration
- `gitpython>=3.1.40` - Git integration

## Configuration Required

The tool requires API tokens for both Notion and Asana, plus database IDs for Notion:
- Notion token (starts with `secret_`)
- Notion database IDs for "Modules" and "Features"
- Asana personal access token
- Asana workspace and user GIDs

## Testing

Currently no formal test framework is implemented. Testing is done via:
- Installation script includes `test_config.sh` for configuration validation
- Manual testing of CLI commands