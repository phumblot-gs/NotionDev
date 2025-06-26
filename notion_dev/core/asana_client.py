# notion_dev/core/asana_client.py - Version avec support portfolio
import requests
from typing import List, Optional, Dict
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
                'opt_fields': 'gid,name,notes,assignee,completed'
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
                    project_name=project_name
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
            'opt_fields': 'gid,name,notes,assignee,completed,projects'
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
                created_by_gid=task_data.get('created_by', {}).get('gid', '') if task_data.get('created_by') else ''
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
                'opt_fields': 'gid,name,notes,assignee,completed,projects,created_by'
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
                created_by_gid=task_data.get('created_by', {}).get('gid', '') if task_data.get('created_by') else ''
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
    
    def test_connection(self) -> bool:
        """Test de connexion simple"""
        try:
            response = self._make_request("GET", "users/me")
            user_data = response.get('data', {})
            logger.info(f"Connected to Asana as: {user_data.get('name', 'Unknown')}")
            return True
        except Exception as e:
            logger.error(f"Asana connection test failed: {e}")
            return False

