# notion_dev/core/asana_client.py - Version avec support portfolio
import requests
from typing import List, Optional, Dict, Any
from .models import AsanaTask, AsanaProject
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class AsanaClient:
    def __init__(self, access_token: str, workspace_gid: str, user_gid: str, portfolio_gid: Optional[str] = None):
        self.access_token = access_token
        self.workspace_gid = workspace_gid
        self.user_gid = user_gid
        self.portfolio_gid = portfolio_gid
        self.base_url = "https://app.asana.com/api/1.0"
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json"
        }
        
    def _make_request(self, method: str, endpoint: str, **kwargs) -> dict:
        """Effectue une requête à l'API Asana"""
        url = f"{self.base_url}/{endpoint}"
        try:
            response = requests.request(method, url, headers=self.headers, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Asana API error: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response: {e.response.text}")
            raise
    
    def get_portfolio_projects(self) -> List[AsanaProject]:
        """Récupère les projets du portfolio spécifié"""
        if not self.portfolio_gid:
            return []
            
        try:
            endpoint = f"portfolios/{self.portfolio_gid}/items"
            params = {
                'opt_fields': 'gid,name,created_at,color'
            }
            
            response = self._make_request("GET", endpoint, params=params)
            projects_data = response.get('data', [])
            
            projects = []
            for project_data in projects_data:
                project = AsanaProject(
                    gid=project_data['gid'],
                    name=project_data['name'],
                    created_at=project_data.get('created_at', ''),
                    color=project_data.get('color')
                )
                projects.append(project)
            
            # Trier par date de création décroissante (plus récents en premier)
            projects.sort(key=lambda p: p.created_at, reverse=True)
            return projects
            
        except Exception as e:
            logger.error(f"Error retrieving portfolio projects: {e}")
            return []
    
    def get_my_tasks(self, completed_since: Optional[str] = None) -> List[AsanaTask]:
        """Récupère les tâches assignées à l'utilisateur"""
        try:
            if self.portfolio_gid:
                return self._get_portfolio_tasks(completed_since)
            else:
                return self._get_all_tasks(completed_since)
                
        except Exception as e:
            logger.error(f"Error retrieving Asana tasks: {e}")
            return []
    
    def _get_portfolio_tasks(self, completed_since: Optional[str] = None) -> List[AsanaTask]:
        """Récupère les tâches filtrées par portfolio"""
        # 1. Récupérer les projets du portfolio
        portfolio_projects = self.get_portfolio_projects()
        if not portfolio_projects:
            logger.warning(f"No projects found in portfolio {self.portfolio_gid}")
            return []
        
        project_gids = [p.gid for p in portfolio_projects]
        project_names = {p.gid: p.name for p in portfolio_projects}
        
        # 2. Récupérer les tâches pour chaque projet
        all_tasks = []
        for project_gid in project_gids:
            tasks = self._get_project_tasks(project_gid, project_names[project_gid], completed_since)
            all_tasks.extend(tasks)
        
        return all_tasks
    
    def _get_project_tasks(self, project_gid: str, project_name: str, completed_since: Optional[str] = None) -> List[AsanaTask]:
        """Récupère les tâches d'un projet spécifique assignées à l'utilisateur"""
        try:
            endpoint = f"projects/{project_gid}/tasks"
            # Cannot filter by assignee when querying project tasks
            params = {
                'completed_since': completed_since or 'now',
                'opt_fields': 'gid,name,notes,assignee,completed,due_on'
            }
            
            response = self._make_request("GET", endpoint, params=params)
            tasks_data = response.get('data', [])
            
            asana_tasks = []
            for task_data in tasks_data:
                # Filter to only keep tasks assigned to the user
                assignee_gid = task_data.get('assignee', {}).get('gid', '') if task_data.get('assignee') else ''
                if assignee_gid != self.user_gid:
                    continue
                    
                asana_task = AsanaTask(
                    gid=task_data['gid'],
                    name=task_data['name'],
                    notes=task_data.get('notes', ''),
                    assignee_gid=assignee_gid,
                    completed=task_data.get('completed', False),
                    project_gid=project_gid,
                    project_name=project_name,
                    due_on=task_data.get('due_on')
                )
                
                # Extraction automatique du code feature
                asana_task.extract_feature_code()
                asana_tasks.append(asana_task)
            
            return asana_tasks
            
        except Exception as e:
            logger.error(f"Error retrieving tasks for project {project_gid}: {e}")
            return []
    
    def _get_all_tasks(self, completed_since: Optional[str] = None) -> List[AsanaTask]:
        """Récupère toutes les tâches assignées (fallback si pas de portfolio)"""
        params = {
            'assignee': self.user_gid,
            'workspace': self.workspace_gid,
            'completed_since': completed_since or 'now',
            'opt_fields': 'gid,name,notes,assignee,completed,projects,due_on,created_by'
        }
        
        response = self._make_request("GET", "tasks", params=params)
        tasks_data = response.get('data', [])
        
        asana_tasks = []
        for task_data in tasks_data:
            # Récupérer le nom du premier projet si disponible
            projects = task_data.get('projects', [])
            project_name = projects[0].get('name') if projects else None
            project_gid = projects[0].get('gid') if projects else None
            
            asana_task = AsanaTask(
                gid=task_data['gid'],
                name=task_data['name'],
                notes=task_data.get('notes', ''),
                assignee_gid=task_data.get('assignee', {}).get('gid', '') if task_data.get('assignee') else '',
                completed=task_data.get('completed', False),
                project_gid=project_gid,
                project_name=project_name,
                created_by_gid=task_data.get('created_by', {}).get('gid', '') if task_data.get('created_by') else '',
                due_on=task_data.get('due_on')
            )
            
            # Extraction automatique du code feature
            asana_task.extract_feature_code()
            asana_tasks.append(asana_task)
            
        return asana_tasks
    
    def get_task(self, task_gid: str) -> Optional[AsanaTask]:
        """Récupère une tâche spécifique"""
        try:
            endpoint = f"tasks/{task_gid}"
            params = {
                'opt_fields': 'gid,name,notes,assignee,completed,projects,created_by,due_on'
            }
            
            response = self._make_request("GET", endpoint, params=params)
            task_data = response.get('data', {})
            
            if not task_data:
                return None
            
            # Récupérer les infos du projet
            projects = task_data.get('projects', [])
            project_name = projects[0].get('name') if projects else None
            project_gid = projects[0].get('gid') if projects else None
            
            asana_task = AsanaTask(
                gid=task_data['gid'],
                name=task_data['name'],
                notes=task_data.get('notes', ''),
                assignee_gid=task_data.get('assignee', {}).get('gid', '') if task_data.get('assignee') else '',
                completed=task_data.get('completed', False),
                project_gid=project_gid,
                project_name=project_name,
                created_by_gid=task_data.get('created_by', {}).get('gid', '') if task_data.get('created_by') else '',
                due_on=task_data.get('due_on')
            )
            
            asana_task.extract_feature_code()
            return asana_task
            
        except Exception as e:
            logger.error(f"Error retrieving task {task_gid}: {e}")
            return None
    
    def update_task_status(self, task_gid: str, completed: bool) -> bool:
        """Met à jour le statut d'une tâche"""
        try:
            endpoint = f"tasks/{task_gid}"
            data = {
                'data': {
                    'completed': completed
                }
            }
            
            self._make_request("PUT", endpoint, json=data)
            return True
            
        except Exception as e:
            logger.error(f"Error updating task {task_gid}: {e}")
            return False
    
    def add_comment_to_task(self, task_gid: str, comment: str) -> bool:
        """Ajoute un commentaire à une tâche Asana"""
        try:
            endpoint = f"tasks/{task_gid}/stories"
            data = {
                'data': {
                    'text': comment
                }
            }
            
            self._make_request("POST", endpoint, json=data)
            return True
            
        except Exception as e:
            logger.error(f"Error adding comment to task {task_gid}: {e}")
            return False
    
    def reassign_task(self, task_gid: str, assignee_gid: str) -> bool:
        """Réassigne une tâche à un utilisateur"""
        try:
            endpoint = f"tasks/{task_gid}"
            data = {
                'data': {
                    'assignee': assignee_gid
                }
            }
            
            self._make_request("PUT", endpoint, json=data)
            return True
            
        except Exception as e:
            logger.error(f"Error reassigning task {task_gid}: {e}")
            return False
    
    def create_task(
        self,
        name: str,
        notes: str = "",
        project_gid: Optional[str] = None,
        assignee_gid: Optional[str] = None,
        due_on: Optional[str] = None
    ) -> Optional[AsanaTask]:
        """Create a new task in Asana.

        Args:
            name: Task name/title
            notes: Task description (supports markdown-like formatting)
            project_gid: Project to add the task to. If None, uses first portfolio project.
            assignee_gid: User to assign to. If None, assigns to self.
            due_on: Due date in YYYY-MM-DD format

        Returns:
            Created AsanaTask or None if failed
        """
        try:
            # Determine project
            if not project_gid and self.portfolio_gid:
                projects = self.get_portfolio_projects()
                if projects:
                    project_gid = projects[0].gid
                    logger.info(f"Using first portfolio project: {projects[0].name}")

            if not project_gid:
                logger.error("No project specified and no portfolio projects available")
                return None

            # Build task data
            task_data = {
                'name': name,
                'notes': notes,
                'assignee': assignee_gid or self.user_gid,
                'projects': [project_gid]
            }

            if due_on:
                task_data['due_on'] = due_on

            endpoint = "tasks"
            response = self._make_request("POST", endpoint, json={'data': task_data})
            created_task = response.get('data', {})

            if not created_task:
                return None

            # Build AsanaTask object
            asana_task = AsanaTask(
                gid=created_task['gid'],
                name=created_task['name'],
                notes=created_task.get('notes', ''),
                assignee_gid=assignee_gid or self.user_gid,
                completed=False,
                project_gid=project_gid,
                project_name=None,  # Would need extra API call to get name
                due_on=due_on
            )

            asana_task.extract_feature_code()
            logger.info(f"Created task: {asana_task.gid} - {asana_task.name}")
            return asana_task

        except Exception as e:
            logger.error(f"Error creating task: {e}")
            return None

    def update_task(
        self,
        task_gid: str,
        name: Optional[str] = None,
        notes: Optional[str] = None,
        append_notes: bool = False,
        assignee_gid: Optional[str] = None,
        due_on: Optional[str] = None,
        completed: Optional[bool] = None
    ) -> Optional[AsanaTask]:
        """Update an existing task in Asana.

        Args:
            task_gid: ID of the task to update
            name: New task name (if provided)
            notes: New notes content (if provided)
            append_notes: If True, append notes to existing. If False, replace.
            assignee_gid: New assignee (if provided)
            due_on: New due date in YYYY-MM-DD format (if provided)
            completed: New completion status (if provided)

        Returns:
            Updated AsanaTask or None if failed
        """
        try:
            # Build update data with only provided fields
            update_data = {}

            if name is not None:
                update_data['name'] = name

            if notes is not None:
                if append_notes:
                    # Fetch current notes first
                    current_task = self.get_task(task_gid)
                    if current_task:
                        current_notes = current_task.notes or ""
                        separator = "\n\n---\n\n" if current_notes else ""
                        update_data['notes'] = current_notes + separator + notes
                    else:
                        update_data['notes'] = notes
                else:
                    update_data['notes'] = notes

            if assignee_gid is not None:
                update_data['assignee'] = assignee_gid

            if due_on is not None:
                update_data['due_on'] = due_on

            if completed is not None:
                update_data['completed'] = completed

            if not update_data:
                logger.warning("No fields to update")
                return self.get_task(task_gid)

            endpoint = f"tasks/{task_gid}"
            response = self._make_request("PUT", endpoint, json={'data': update_data})
            updated_task = response.get('data', {})

            if not updated_task:
                return None

            # Return fresh task data
            return self.get_task(task_gid)

        except Exception as e:
            logger.error(f"Error updating task {task_gid}: {e}")
            return None

    def get_workspace_users(self) -> List[Dict[str, Any]]:
        """Get all users in the workspace.

        Returns:
            List of user dicts with 'gid', 'name', 'email' keys
        """
        try:
            endpoint = f"workspaces/{self.workspace_gid}/users"
            params = {
                'opt_fields': 'gid,name,email'
            }
            response = self._make_request("GET", endpoint, params=params)
            return response.get('data', [])
        except Exception as e:
            logger.error(f"Error fetching workspace users: {e}")
            return []

    def find_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Find a user in the workspace by email address.

        Args:
            email: Email address to search for

        Returns:
            User dict with 'gid', 'name', 'email' or None if not found
        """
        email_lower = email.lower()
        users = self.get_workspace_users()
        for user in users:
            if user.get('email', '').lower() == email_lower:
                return user
        return None

    def test_connection(self) -> Dict[str, Any]:
        """Test connection to Asana API and validate access.

        Returns:
            Dict with 'success', 'user', 'workspace', 'portfolio' keys
        """
        result = {
            "success": False,
            "user": None,
            "user_gid": None,
            "workspace": None,
            "portfolio": None,
            "errors": []
        }

        # Test 1: Verify token and get user info
        try:
            response = self._make_request("GET", "users/me")
            user_data = response.get('data', {})
            result["user"] = user_data.get('name', 'Unknown')
            result["user_gid"] = user_data.get('gid')
            logger.info(f"Connected to Asana as: {result['user']}")
        except requests.HTTPError as e:
            if e.response.status_code == 401:
                result["errors"].append("Invalid Asana token (401 Unauthorized)")
            elif e.response.status_code == 403:
                result["errors"].append("Asana token lacks required permissions (403 Forbidden)")
            else:
                result["errors"].append(f"Asana API error: {e}")
            return result
        except Exception as e:
            result["errors"].append(f"Connection error: {e}")
            return result

        # Test 2: Verify workspace access
        try:
            response = self._make_request("GET", f"workspaces/{self.workspace_gid}")
            workspace_data = response.get('data', {})
            result["workspace"] = workspace_data.get('name', 'Unknown')
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                result["errors"].append(f"Workspace {self.workspace_gid} not found")
            else:
                result["errors"].append(f"Workspace error: {e}")
        except Exception as e:
            result["errors"].append(f"Workspace error: {e}")

        # Test 3: Verify portfolio access (if configured)
        if self.portfolio_gid:
            try:
                response = self._make_request("GET", f"portfolios/{self.portfolio_gid}")
                portfolio_data = response.get('data', {})
                result["portfolio"] = portfolio_data.get('name', 'Unknown')
            except requests.HTTPError as e:
                if e.response.status_code == 404:
                    result["errors"].append(f"Portfolio {self.portfolio_gid} not found")
                else:
                    result["errors"].append(f"Portfolio error: {e}")
            except Exception as e:
                result["errors"].append(f"Portfolio error: {e}")

        result["success"] = len(result["errors"]) == 0
        return result

