# notion_dev/core/config.py - Ajout du support portfolio
import yaml
import os
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass

@dataclass
class NotionConfig:
    token: str
    database_modules_id: str
    database_features_id: str

@dataclass
class AsanaConfig:
    access_token: str
    workspace_gid: str
    user_gid: str
    portfolio_gid: Optional[str] = None  # ← Nouveau champ optionnel

@dataclass
class AIConfig:
    context_max_length: int = 32000
    include_code_examples: bool = True

@dataclass
class GitConfig:
    default_branch: str = "main"
    header_comment_style: str = "auto"

@dataclass
class LoggingConfig:
    level: str = "INFO"
    file: str = "notion-dev.log"

@dataclass
class Config:
    notion: NotionConfig
    asana: AsanaConfig
    ai: AIConfig
    git: GitConfig
    logging: LoggingConfig
    
    # Propriétés auto-détectées (pas dans le fichier config)
    _repository_path: Optional[str] = None
    _project_name: Optional[str] = None
    _cache_directory: Optional[str] = None
    
    @classmethod
    def load(cls, config_path: Optional[str] = None) -> 'Config':
        """Charge la configuration depuis le fichier YAML"""
        if config_path is None:
            config_path = os.path.expanduser("~/.notion-dev/config.yml")
        
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        with open(config_path, 'r') as f:
            data = yaml.safe_load(f)
        
        # Configs obligatoires
        notion_config = NotionConfig(**data['notion'])
        
        # Asana config avec portfolio optionnel
        asana_data = data['asana']
        asana_config = AsanaConfig(
            access_token=asana_data['access_token'],
            workspace_gid=asana_data['workspace_gid'],
            user_gid=asana_data['user_gid'],
            portfolio_gid=asana_data.get('portfolio_gid')  # Optionnel
        )
        
        # Configs optionnelles avec valeurs par défaut
        ai_data = data.get('ai', {})
        ai_config = AIConfig(
            context_max_length=ai_data.get('context_max_length', 32000),
            include_code_examples=ai_data.get('include_code_examples', True)
        )
        
        git_data = data.get('git', {})
        git_config = GitConfig(
            default_branch=git_data.get('default_branch', 'main'),
            header_comment_style=git_data.get('header_comment_style', 'auto')
        )
        
        logging_data = data.get('logging', {})
        logging_config = LoggingConfig(
            level=logging_data.get('level', 'INFO'),
            file=logging_data.get('file', 'notion-dev.log')
        )
        
        return cls(
            notion=notion_config,
            asana=asana_config,
            ai=ai_config,
            git=git_config,
            logging=logging_config
        )
    
    @property
    def repository_path(self) -> str:
        """Chemin du repository courant (auto-détecté)"""
        if self._repository_path is None:
            self._repository_path = os.getcwd()
        return self._repository_path
    
    @property
    def project_name(self) -> str:
        """Nom du projet courant (auto-détecté)"""
        if self._project_name is None:
            self._project_name = os.path.basename(self.repository_path)
        return self._project_name
    
    @property
    def cache_directory(self) -> str:
        """Dossier de cache pour le projet courant"""
        if self._cache_directory is None:
            self._cache_directory = os.path.join(self.repository_path, '.notion-dev')
            # Créer le dossier s'il n'existe pas
            os.makedirs(self._cache_directory, exist_ok=True)
        return self._cache_directory
    
    def validate(self) -> bool:
        """Valide la configuration"""
        required_fields = [
            self.notion.token,
            self.notion.database_modules_id, 
            self.notion.database_features_id,
            self.asana.access_token,
            self.asana.workspace_gid
        ]
        return all(field for field in required_fields)
    
    def get_project_info(self) -> Dict[str, str]:
        """Retourne les infos du projet courant"""
        return {
            'name': self.project_name,
            'path': self.repository_path,
            'cache': self.cache_directory,
            'is_git_repo': os.path.exists(os.path.join(self.repository_path, '.git'))
        }

