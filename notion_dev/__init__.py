# notion_dev/__init__.py
"""
NotionDev - Intégration Notion ↔ Asana ↔ Git pour développeurs
"""

__version__ = "1.0.2"

from .core.config import Config
from .core.models import Feature, Module, AsanaTask
from .core.notion_client import NotionClient
from .core.asana_client import AsanaClient
from .core.context_builder import ContextBuilder

__all__ = [
    'Config',
    'Feature',
    'Module',
    'AsanaTask',
    'NotionClient',
    'AsanaClient',
    'ContextBuilder'
]
