# notion_dev/core/context_builder.py
from typing import Dict, Optional, List
from .models import Feature, AsanaTask
from .notion_client import NotionClient
from .config import Config
import os
import logging

logger = logging.getLogger(__name__)

class ContextBuilder:
    def __init__(self, notion_client: NotionClient, config: Config):
        self.notion_client = notion_client
        self.config = config
    
    def build_feature_context(self, feature_code: str) -> Optional[Dict]:
        """Construit le contexte complet pour une feature"""
        feature = self.notion_client.get_feature(feature_code)
        if not feature:
            logger.error(f"Feature {feature_code} not found")
            return None
        
        context = {
            'feature': feature,
            'project_info': self.config.get_project_info(),
            'full_context': feature.get_full_context(),
            'cursor_rules': self._generate_cursor_rules(feature),
            'ai_instructions': self._generate_ai_instructions(feature)
        }
        
        return context
    
    def build_task_context(self, task: AsanaTask) -> Optional[Dict]:
        """Construit le contexte pour une tâche Asana"""
        if not task.feature_code:
            logger.warning(f"Task {task.gid} has no feature code")
            return None
            
        feature_context = self.build_feature_context(task.feature_code)
        if not feature_context:
            return None
        
        context = feature_context.copy()
        context.update({
            'task': task,
            'task_description': f"# Task: {task.name}\n\n{task.notes}"
        })
        
        return context
    
    def _generate_cursor_rules(self, feature: Feature) -> str:
        """Génère les règles pour Cursor"""
        project_info = self.config.get_project_info()
        
        rules = f"""# Règles de Développement - {project_info['name']}

## Projet Courant
**{project_info['name']}**
- Path: {project_info['path']}
- Git Repository: {'✅' if project_info['is_git_repo'] else '❌'}

## Feature Actuelle
**{feature.code} - {feature.name}**
- Status: {feature.status}
- Module: {feature.module_name}
- Plans: {', '.join(feature.plan) if isinstance(feature.plan, list) else (feature.plan or 'N/A')}
- User Rights: {', '.join(feature.user_rights) if isinstance(feature.user_rights, list) else (feature.user_rights or 'N/A')}

## Standards de Code Obligatoires
Tous les fichiers créés ou modifiés doivent avoir un header :

```typescript
/**
 * NOTION FEATURES: {feature.code}
 * MODULES: {feature.module_name}
 * DESCRIPTION: [Description du rôle du fichier]
 * LAST_SYNC: {self._get_current_date()}
 */
```

## Architecture du Module
{feature.module.description if feature.module else 'Module information not available'}

## Documentation de la Feature
{feature.content[:1500]}{'...' if len(feature.content) > 1500 else ''}
"""
        return rules
    
    def _generate_ai_instructions(self, feature: Feature) -> str:
        """Génère les instructions pour l'IA"""
        project_info = self.config.get_project_info()
        
        instructions = f"""# Instructions IA - Développement Feature {feature.code}

## Contexte du Projet
Projet: **{project_info['name']}**
Repository: {project_info['path']}

## Contexte du Développement
Tu assistes un développeur pour implémenter la feature **{feature.code} - {feature.name}**.

## Objectifs
- Suivre exactement les spécifications de la feature
- Respecter l'architecture du module {feature.module_name}
- Ajouter les headers Notion obligatoires
- Créer du code testable et maintenable
- S'adapter au type de projet (détecté automatiquement)

## Spécifications Complètes
{feature.get_full_context()}

## Instructions de Code
1. **Headers obligatoires** dans tous les fichiers
2. **Tests unitaires** pour chaque fonction
3. **Gestion d'erreurs** appropriée
4. **Documentation** inline pour les fonctions complexes
5. **Respect des patterns** du module existant

## Détection automatique du projet
- Cache local: {project_info['cache']}
- Structure détectée automatiquement depuis le dossier courant

## Validation
Avant de proposer du code, vérifier :
- [ ] Header Notion présent
- [ ] Code aligné avec les specs
- [ ] Gestion des cas d'erreur
- [ ] Tests unitaires inclus
"""
        return instructions
    
    def _get_current_date(self) -> str:
        """Retourne la date actuelle au format YYYY-MM-DD"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d")
    
    def export_to_cursor(self, context: Dict, custom_path: Optional[str] = None) -> bool:
        """Exporte le contexte vers les fichiers Cursor"""
        # Utiliser le chemin custom ou le repository path courant
        project_path = custom_path or self.config.repository_path
        
        try:
            cursor_dir = os.path.join(project_path, ".cursor")
            os.makedirs(cursor_dir, exist_ok=True)
            
            # Fichier rules.md
            rules_path = os.path.join(cursor_dir, "rules.md")
            with open(rules_path, 'w', encoding='utf-8') as f:
                f.write(context['cursor_rules'])
            
            # Fichier context.md
            context_path = os.path.join(cursor_dir, "context.md")
            with open(context_path, 'w', encoding='utf-8') as f:
                f.write(context['ai_instructions'])
            
            # Fichier project-info.md avec infos du projet
            project_info_path = os.path.join(cursor_dir, "project-info.md")
            project_info = context['project_info']
            with open(project_info_path, 'w', encoding='utf-8') as f:
                f.write(f"""# Projet: {project_info['name']}

## Informations
- **Path:** {project_info['path']}
- **Cache:** {project_info['cache']}
- **Git Repository:** {'Oui' if project_info['is_git_repo'] else 'Non'}

## Feature Actuelle
- **Code:** {context['feature'].code}
- **Nom:** {context['feature'].name}
- **Module:** {context['feature'].module_name}

*Généré automatiquement par NotionDev*
""")
            
            logger.info(f"Context exported to {cursor_dir}")
            return True
            
        except Exception as e:
            logger.error(f"Error exporting context: {e}")
            return False

