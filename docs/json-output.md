# JSON Output Support

The NotionDev CLI now supports JSON output for programmatic access to task and project information.

## Commands with JSON Support

### 1. `notion-dev info --json`

Returns project and current task information in JSON format.

**Output Structure:**
```json
{
  "project": {
    "name": "project-name",
    "path": "/path/to/project",
    "cache": "/path/to/.notion-dev",
    "is_git_repo": true,
    "notion_database_modules_id": "...",
    "notion_database_features_id": "...",
    "asana_workspace_gid": "...",
    "asana_portfolio_gid": "..."
  },
  "current_task": {
    "id": "task-gid",
    "name": "Task Name",
    "feature_code": "AU01",
    "feature_codes": ["AU01", "DA02"],
    "status": "in_progress",
    "started_at": "2024-01-15T10:30:00",
    "url": "https://app.asana.com/0/project-id/task-id",
    "notion_url": "https://www.notion.so/page-id"
  }
}
```

### 2. `notion-dev tickets --json`

Returns all assigned tasks in JSON format.

**Output Structure:**
```json
{
  "tasks": [
    {
      "id": "task-gid",
      "name": "Task Name",
      "feature_code": "AU01",
      "status": "in_progress",
      "completed": false,
      "due_on": "2024-01-20",
      "url": "https://app.asana.com/0/project-id/task-id",
      "notion_url": "https://www.notion.so/page-id",
      "project_name": "Project Name",
      "project_gid": "project-gid"
    }
  ]
}
```

## Usage Examples

### Python Example

```python
import subprocess
import json

# Get current task info
result = subprocess.run(['notion-dev', 'info', '--json'], capture_output=True, text=True)
data = json.loads(result.stdout)
current_task = data.get('current_task')

# Get all tickets
result = subprocess.run(['notion-dev', 'tickets', '--json'], capture_output=True, text=True)
data = json.loads(result.stdout)
tasks = data.get('tasks', [])
```

### Bash Example

```bash
# Get current task ID
TASK_ID=$(notion-dev info --json | jq -r '.current_task.id // empty')

# List in-progress tasks
notion-dev tickets --json | jq '.tasks[] | select(.status == "in_progress") | .name'

# Get tasks with feature codes
notion-dev tickets --json | jq '.tasks[] | select(.feature_code != null) | {name, feature_code}'
```

### VS Code Extension Integration

The JSON output is designed to be consumed by the VS Code extension for seamless integration:

```typescript
interface Task {
  id: string;
  name: string;
  feature_code: string | null;
  status: "in_progress" | "completed";
  completed: boolean;
  due_on: string | null;
  url: string;
  notion_url: string | null;
  project_name: string | null;
  project_gid: string | null;
}

interface ProjectInfo {
  project: {
    name: string;
    path: string;
    cache: string;
    is_git_repo: boolean;
    notion_database_modules_id: string;
    notion_database_features_id: string;
    asana_workspace_gid: string;
    asana_portfolio_gid: string | null;
  };
  current_task: Task | null;
}
```

## Error Handling

If an error occurs, the command will return a non-zero exit code. Always check the exit code before parsing JSON output:

```python
result = subprocess.run(['notion-dev', 'info', '--json'], capture_output=True, text=True)
if result.returncode == 0:
    data = json.loads(result.stdout)
else:
    print(f"Error: {result.stderr}")
```