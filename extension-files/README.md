# NotionDev for Cursor

Integrate Notion, Asana and Git workflows directly in Cursor IDE.

## Features

- 📋 **Asana Tasks View**: See all your assigned tasks in the sidebar
- 🎯 **Quick Task Selection**: Click on any task to start working on it
- 📝 **Current Task Info**: View detailed information about your current task
- 💬 **Add Comments**: Comment on Asana tickets directly from Cursor
- ✅ **Mark Done**: Complete tasks and reassign to requester
- 🔄 **Auto-refresh**: Automatically updates task status every 5 minutes
- 🔗 **Quick Links**: Open tasks in Asana or Notion with one click

## Requirements

- **NotionDev CLI**: Install with `pip install notion-dev` (version 1.0.3 or higher)
- **API Tokens**: Notion and Asana API access tokens
- **Cursor IDE**: Version 0.30.0 or higher

## Installation

1. Install the NotionDev CLI:
   ```bash
   pip install notion-dev
   ```

2. Install this extension from the VS Code Marketplace or Cursor Extensions

3. Configure the extension (see Configuration section)

## Configuration

On first use, the extension will prompt you to configure your API tokens. You can also configure manually:

1. Open Command Palette (`Cmd+Shift+P` on Mac, `Ctrl+Shift+P` on Windows/Linux)
2. Run `NotionDev: Configure`
3. Enter your tokens and IDs when prompted

### Required Configuration

- **Notion API Token**: Get from [Notion Integrations](https://www.notion.so/my-integrations)
- **Notion Database IDs**: Your Modules and Features database IDs
- **Asana Access Token**: Get from [Asana Apps](https://app.asana.com/0/my-apps)
- **Asana Workspace & User IDs**: Your workspace and user identifiers

## Usage

### View Tasks
1. Click the NotionDev icon in the Activity Bar
2. Your Asana tasks appear in the "Asana Tasks" view
3. Click any task to start working on it

### Work on a Task
- **From Sidebar**: Click on any task
- **From Command Palette**: Run `NotionDev: Work on Ticket` and enter task ID
- **Result**: Loads complete context into `.cursorrules` file

### Current Task Management
- **View Info**: Click the status bar item or run `NotionDev: Show Current Task Info`
- **Add Comment**: Run `NotionDev: Add Comment to Current Ticket`
- **Mark Done**: Run `NotionDev: Mark Current Task as Done`

### Keyboard Shortcuts

You can add custom keyboard shortcuts for any command:
1. Open Keyboard Shortcuts (`Cmd+K Cmd+S`)
2. Search for "NotionDev"
3. Add your preferred shortcuts

## Features in Detail

### Status Bar Integration
The extension shows your current task in the status bar. Click it to see detailed information.

### Auto-refresh
Tasks and current task info refresh automatically every 5 minutes. Disable in settings if needed.

### Context Export
When you select a task, the extension automatically:
- Exports complete specifications to `.cursorrules`
- Opens the file for immediate AI context
- Updates your working status in Asana

## Troubleshooting

### "NotionDev CLI not found"
- Ensure `notion-dev` is installed: `pip install notion-dev`
- Check that Python/pip binaries are in your PATH

### "Invalid configuration"
- Run `NotionDev: Configure` to set up your tokens
- Verify all tokens and IDs are correct
- Check the NotionDev CLI configuration: `~/.notion-dev/config.yml`

### Tasks not showing
- Check your Asana API token is valid
- Ensure you have tasks assigned in Asana
- Try refreshing manually with the refresh button

## Support

- **Issues**: [GitHub Issues](https://github.com/phumblot-gs/notion-dev-cursor-extension/issues)
- **NotionDev CLI**: [PyPI Page](https://pypi.org/project/notion-dev/)

---

Made with ❤️ to accelerate AI-assisted development in Cursor