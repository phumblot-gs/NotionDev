# NotionDev

> **Notion ↔ Asana ↔ Git Integration for Developers**  
> Accelerate your development with AI context automatically loaded from your Notion specifications

NotionDev is designed for large projects that require focusing AI agents on precisely presented context to avoid code regressions.
We implement a workflow with automatic context switching, based on your specifications.
For this, we assume your application is organized into modules, and your modules into features. We also assume your modules and features are documented in two Notion databases.

NotionDev allows developers to automatically load the complete context of their features from Notion directly into their IDE rules (Cursor), while synchronizing with their assigned Asana tickets.
They can then comment on Asana tickets, tag their code with implemented features, and reassign a ticket to the person who created it when work is completed.

NotionDev works in a multi-project environment: you can have multiple git projects locally, you can work on distinct features in each project.

[![PyPI version](https://badge.fury.io/py/notion-dev.svg)](https://pypi.org/project/notion-dev/)
[![Python](https://img.shields.io/badge/python-3.9+-green.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Tests](https://github.com/phumblot-gs/NotionDev/actions/workflows/tests.yml/badge.svg)](https://github.com/phumblot-gs/NotionDev/actions/workflows/tests.yml)

## ✨ Features

- 🎯 **Integrated workflow**: Asana ticket + Notion documentation → AI Context → Code
- 🤖 **Automatic AI Context**: Direct export to Cursor with complete specs
- 🔄 **Multi-project**: Automatic detection of current project
- 📋 **Traceability**: Automatic headers in code to link functional ↔ technical
- 🚀 **Zero config per project**: One global configuration for all your projects

## 🎯 Use Case

**Before NotionDev:**
```bash
# Manual and scattered workflow
1. Open Asana ticket
2. Search for documentation in Notion  
3. Copy-paste specs into Cursor
4. Code without complete context
5. Code doesn't directly reference implemented specifications
```

**With NotionDev:**
```bash
# Automated and integrated workflow
notion-dev work TASK-123456789
# → Automatically loads entire context into Cursor
# → Ready to code with AI 
# Generated code mentions implemented features
```

## 📋 Prerequisites

- **Python 3.9+**
- **macOS**
- **API Access**: Notion + Asana
- **Notion Structure**: "Modules" and "Features" databases with feature codes

### Required Notion Structure

For NotionDev to work, your Notion workspace must contain 2 databases with the attributes below (case-sensitive):

**"Modules" Database:**
- `name` (Title): Module name
- `description` (Text): Short description  
- `status` (Select): draft, review, validated, obsolete
- `application` (Select): service, backend, frontend
- `code_prefix` (Text): Feature code prefix (AU, DA, API...)

**"Features" Database:**
- `code` (Text): Unique code (AU01, DA02...)
- `name` (Title): Feature name
- `status` (Select): draft, review, validated, obsolete
- `module` (Relation): Link to parent module
- `plan` (Multi-select): Subscription plans  
- `user_rights` (Multi-select): Access rights

## 🚀 Installation

### Install from PyPI (Recommended)

```bash
pip install notion-dev
```

### Install from Source

```bash
# Clone the repository
git clone https://github.com/phumblot-gs/NotionDev.git
cd NotionDev

# Install in development mode
pip install -e .
```

### First Time Setup

After installation:
```bash
# Create configuration directory
mkdir -p ~/.notion-dev

# Copy the example configuration
# You'll need to edit this with your tokens
cat > ~/.notion-dev/config.yml << 'EOF'
notion:
  token: "secret_YOUR_NOTION_TOKEN"
  database_modules_id: "YOUR_MODULES_DB_ID"
  database_features_id: "YOUR_FEATURES_DB_ID"

asana:
  access_token: "YOUR_ASANA_TOKEN"
  workspace_gid: "YOUR_WORKSPACE_ID"
  user_gid: "YOUR_USER_ID"
EOF
```

### Configuration

#### 1. Get API Tokens

**🔑 Notion Token:**
1. Go to https://www.notion.so/my-integrations
2. Create a new "NotionDev" integration
3. Copy the token (starts with `secret_`)
4. Get the database IDs for modules and features
   URL: `notion.so/workspace/[DATABASE_ID]?v=...`

**🔑 Asana Token:**
1. Go to https://app.asana.com/0/my-apps
2. Create a "Personal Access Token"
3. Copy the generated token
4. Get your workspace ID
5. Get your user account ID

#### 2. Configure config.yml

```bash
# Copy the template
cp ~/.notion-dev/config.example.yml ~/.notion-dev/config.yml

# Edit with your tokens
nano ~/.notion-dev/config.yml
```

```yaml
notion:
  token: "secret_YOUR_NOTION_TOKEN"
  database_modules_id: "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"  
  database_features_id: "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"

asana:
  access_token: "x/YOUR_ASANA_TOKEN"
  workspace_gid: "1234567890123456"
  user_gid: "1234567890123456"
```

#### 3. Test Installation

```bash
# Complete configuration test
~/notion-dev-install/test_config.sh

# First test
notion-dev tickets
```

## 📖 Usage

### Main Commands

```bash
# View current project info
notion-dev info

# List your assigned Asana tickets  
notion-dev tickets

# Work on a specific ticket
notion-dev work TASK-123456789

# Get context for a feature
# other than the one in the Asana ticket
notion-dev context --feature AU01

# Record a comment on the ticket in Asana
notion-dev comment "This is a comment"

# Mark work as completed
# This action assigns the ticket to the person who created it
notion-dev done

# Interactive mode
notion-dev interactive
```

### Typical Developer Workflow

To understand the spirit of NotionDev, here's an example workflow.
In this example, we assume documentation has been validated in Notion (Definition of Ready), and Asana tickets have been added to the current sprint, assigned to developers.
We put ourselves in the developer's shoes.

#### 🌅 Morning - Choose Your Ticket

```bash
cd ~/projects/my-saas-frontend
notion-dev tickets
```

```
                    My Asana Tickets                    
┏━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┓
┃ ID      ┃ Name                             ┃ Feature     ┃ Status      ┃
┡━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━┩
│ 23456789│ Implement Google SSO             │ AU02        │ 🔄 In progress │
│ 34567890│ Dashboard analytics              │ DA01        │ 🔄 In progress │
└─────────┴────────────────────────────────┴─────────────┴─────────────┘
```

#### 🎯 Start Working

```bash
notion-dev work 23456789
```

```
📋 Asana Ticket
AU02 - Implement Google SSO

ID: 1234567890123456
Feature Code: AU02
Status: 🔄 In progress
Project: my-saas-frontend

🎯 Feature
AU02 - SSO Google Login

Module: User Authentication
Status: validated
Plans: premium
User Rights: standard, admin

Export context to Cursor? [Y/n]: y
✅ Context exported to /Users/dev/projects/my-saas-frontend/.cursor/
💡 You can now open Cursor and start coding!
```

#### 💻 Develop with Cursor

```bash
# Open Cursor with loaded context
cursor .
```

The AI context automatically contains:
- ✅ Complete specifications for feature AU02
- ✅ User Authentication module documentation  
- ✅ Code standards with mandatory headers
- ✅ AI instructions adapted to the project

#### 🔄 Switch Projects

```bash
# Switch to another project - automatic detection
cd ~/projects/my-saas-api
notion-dev info
```

```
📊 Project: my-saas-api
Name: my-saas-api
Path: /Users/dev/projects/my-saas-api
Cache: /Users/dev/projects/my-saas-api/.notion-dev
Git Repository: ✅ Yes
```

### Traceability Headers

In the context loaded in the /.cursor folder, NotionDev adds instructions for the AI agent to automatically insert a header in each project file with the feature code.
The goal is to verify functional code coverage and avoid regressions since the AI agent has instructions not to modify code corresponding to a feature other than the one being worked on.

```typescript
/**
 * NOTION FEATURES: AU02
 * MODULES: User Authentication
 * DESCRIPTION: Google OAuth authentication service
 * LAST_SYNC: 2025-01-15
 */
export class GoogleAuthService {
  // Implementation...
}
```

## 🏗️ Architecture

### Automatic Multi-project

NotionDev automatically detects the project from the current directory:

```bash
~/projects/
├── saas-frontend/          # notion-dev → Context "saas-frontend"
│   └── .notion-dev/        # Isolated cache
├── saas-api/              # notion-dev → Context "saas-api"  
│   └── .notion-dev/        # Isolated cache
└── saas-admin/            # notion-dev → Context "saas-admin"
    └── .notion-dev/        # Isolated cache
```

## ⚙️ Advanced Configuration

### Context Size Management

The `context_max_length` parameter controls the maximum size of the `.cursorrules` file to ensure compatibility with your AI model's context window:

```yaml
ai:
  # For Claude Opus/Sonnet (recommended)
  context_max_length: 100000  # ~100KB
  
  # For GPT-3.5 (more limited)
  context_max_length: 32000   # ~32KB
```

**How it works:**
- Default: 100,000 characters
- If content exceeds the limit, it's intelligently truncated
- Priority is given to critical sections (headers, rules, project context)
- Documentation is truncated first if needed
- A message `[Content truncated to fit context limits]` is added when truncation occurs

**Checking truncation:**
After running `notion-dev work`, check the logs:
```
.cursorrules created: 45000 chars                    # Normal
.cursorrules created: 100000 chars (truncated from 125000)  # Truncated
```

### Language Configuration

NotionDev enforces English for all code and comments, regardless of documentation language:

- **Documentation**: Can be in any language (French, English, etc.)
- **Generated code**: Always in English
- **Comments**: Always in English
- **Variable/function names**: Always in English

This is automatically enforced through the `.cursorrules` file.

### Custom Shell Aliases

```bash
# In ~/.zshrc or ~/.bash_profile
alias nd="notion-dev"
alias ndt="notion-dev tickets"
alias ndw="notion-dev work"
alias ndi="notion-dev info"
```

## 🔧 Troubleshooting

### Common Errors

**❌ "Invalid configuration"**
```bash
# Check tokens
notion-dev info
# Retest config
~/notion-dev-install/test_config.sh
```

### Debug Logs

NotionDev uses rotating logs to prevent disk space issues:

```bash
# View detailed logs
tail -f ~/.notion-dev/notion-dev.log

# Debug with verbose level
export NOTION_DEV_LOG_LEVEL=DEBUG
notion-dev tickets
```

**Log rotation:**
- Maximum file size: 10MB
- Keeps 5 backup files (notion-dev.log.1 through .5)
- Automatic rotation when size limit is reached
- Logs location: `~/.notion-dev/notion-dev.log`

## 🤝 Contributing

### Local Development

```bash
# Clone and install in development mode
git clone https://github.com/your-org/notion-dev.git
cd notion-dev
python -m venv venv
source venv/bin/activate
pip install -e .
```

### Project Structure

```
notion-dev/
├── notion_dev/
│   ├── core/              # Business logic
│   │   ├── config.py      # Multi-project configuration
│   │   ├── asana_client.py # Asana API client
│   │   ├── notion_client.py # Notion API client
│   │   └── context_builder.py # AI context generator
│   ├── cli/
│   │   └── main.py        # CLI interface
│   └── models/            # Data models
├── install_notion_dev.sh  # Installation script
└── README.md
```

## 📝 Changelog

### v1.0.0 (2025-01-26)
- ✅ Initial release
- ✅ Automatic multi-project support
- ✅ Notion + Asana + Cursor integration
- ✅ Automatic traceability headers
- ✅ Asana API 5.2.0 compatible client

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

## 💬 Support

- **Issues**: [GitHub Issues](https://github.com/your-org/notion-dev/issues)
- **Documentation**: [Wiki](https://github.com/your-org/notion-dev/wiki)
- **Discussions**: [GitHub Discussions](https://github.com/your-org/notion-dev/discussions)

---

**Developed with ❤️ to accelerate AI-assisted development**