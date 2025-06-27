# notion_dev/core/context_builder.py
from typing import Dict, Optional, List
from datetime import datetime
from .models import Feature, AsanaTask
from .notion_client import NotionClient
from .config import Config
import os
import shutil
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
        return datetime.now().strftime("%Y-%m-%d")
    
    def _truncate_content(self, content: str, max_length: int) -> str:
        """Truncate content to fit within max_length while preserving structure"""
        if len(content) <= max_length:
            return content
        
        # Reserve space for truncation notice
        truncation_notice = "\n\n---\n*[Content truncated to fit context limits]*"
        available_length = max_length - len(truncation_notice)
        
        # Try to truncate at a meaningful boundary
        truncated = content[:available_length]
        
        # Look for good truncation points (in order of preference)
        boundaries = ['\n## ', '\n### ', '\n\n', '\n', '. ', ' ']
        
        for boundary in boundaries:
            last_pos = truncated.rfind(boundary)
            if last_pos > available_length * 0.7:  # If found in last 30%
                truncated = truncated[:last_pos]
                break
        
        return truncated + truncation_notice
    
    def _build_cursorrules_content(self, context: Dict) -> str:
        """Build content for .cursorrules file with enhanced context"""
        feature = context['feature']
        project_info = context['project_info']
        task = context.get('task', None)
        
        # Build the comprehensive .cursorrules content
        content = f"""# NotionDev Context - {project_info['name']}
# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}

## ⚠️ CRITICAL PROJECT CONTEXT

This is a large-scale project with multiple modules, each containing multiple features.
You are currently working on ONE SPECIFIC FEATURE. This is crucial to understand:

### Project Structure
- **Project**: {project_info['name']} (multi-module application)
- **Total Modules**: Multiple interconnected modules
- **Total Features**: Each module contains numerous features
- **Your Scope**: LIMITED to feature **{feature.code}** in module **{feature.module_name}**

### Regression Prevention Rules

**MANDATORY**: To prevent regressions across the codebase:

1. **Feature Isolation**: You are ONLY authorized to work on feature **{feature.code}**
2. **File Headers Check**: EVERY file has a header indicating which feature it implements
3. **Modification Rules**:
   - ✅ CREATE new files: MUST add the header for feature {feature.code}
   - ✅ MODIFY files: ONLY if header contains feature {feature.code}
   - ❌ NEVER modify files with different feature codes
   - ❌ NEVER remove or alter existing feature headers

### Why This Matters
- Each feature has been carefully isolated to prevent side effects
- Modifying code from other features WILL cause regressions
- The `.cursorrules` file intentionally shows ONLY your current feature
- This limitation is by design to maintain code stability

## Active Development

**Feature**: {feature.code} - {feature.name}  
**Module**: {feature.module_name}  
**Status**: {feature.status}"""

        if task:
            content += f"\n**Task**: {task.gid} - {task.name}"
        
        content += f"""
**Scope**: This feature only - no cross-feature modifications allowed

## Mandatory Headers

### For New Files
Every new file you create MUST start with:
```
/**
 * NOTION FEATURES: {feature.code}
 * MODULES: {feature.module_name}
 * DESCRIPTION: [Brief description of file purpose]
 * LAST_SYNC: {self._get_current_date()}
 */
```

### Before Modifying Existing Files
1. CHECK the file header for NOTION FEATURES
2. ONLY proceed if it contains "{feature.code}"
3. If multiple features listed, ensure {feature.code} is included
4. NEVER modify if {feature.code} is not present

## Development Rules

1. **Scope Enforcement**: Work ONLY on feature {feature.code}
2. **Header Compliance**: ALL files must have proper headers
3. **No Cross-Feature Changes**: Respect feature boundaries
4. **Existing Code**: Read headers before ANY modification
5. **Pattern Following**: Maintain consistency within {feature.module_name}

### Language Requirements

**CRITICAL**: Language usage rules for this project:
- **Documentation reading**: You may encounter documentation in various languages (English, French, etc.)
- **Chat responses**: You may respond in the user's preferred language
- **Code and comments**: ALL code, comments, variable names, and function names MUST be in English
  - ✅ `// Calculate user permissions`
  - ❌ `// Calculer les permissions utilisateur`
  - ✅ `function validateUserInput()`
  - ❌ `function validerEntreeUtilisateur()`

This is a strict requirement regardless of the documentation language or chat language.

Below are the Feature Specifications:

{feature.get_full_context()}

## Project Information
- **Repository**: {project_info['path']}
- **Git Status**: {'Git repository' if project_info['is_git_repo'] else 'Not a git repository'}
- **Cache Location**: {project_info['cache']}

---
*NotionDev - Keeping your code aligned with specifications*
"""
        return content
    
    def export_to_cursorrules(self, context: Dict, custom_path: Optional[str] = None) -> bool:
        """Export context to .cursorrules file only (new standard)"""
        project_path = custom_path or self.config.repository_path
        
        try:
            # Get max context length from config
            max_length = getattr(self.config.ai, 'context_max_length', 100000) if hasattr(self.config, 'ai') else 100000
            
            # Clean up old .cursor directory if it exists
            cursor_dir = os.path.join(project_path, ".cursor")
            if os.path.exists(cursor_dir):
                shutil.rmtree(cursor_dir)
                logger.info("Cleaned up legacy .cursor directory")
            
            # Build .cursorrules content
            cursorrules_content = self._build_cursorrules_content(context)
            
            # Check size and truncate if needed
            original_size = len(cursorrules_content)
            if original_size > max_length:
                logger.warning(f"Context size ({original_size}) exceeds limit ({max_length}), truncating...")
                cursorrules_content = self._truncate_content(cursorrules_content, max_length)
            
            # Write .cursorrules at project root
            cursorrules_path = os.path.join(project_path, ".cursorrules")
            with open(cursorrules_path, 'w', encoding='utf-8') as f:
                f.write(cursorrules_content)
            
            final_size = len(cursorrules_content)
            logger.info(f".cursorrules created: {final_size} chars" +
                       (f" (truncated from {original_size})" if original_size > max_length else ""))
            
            return True
            
        except Exception as e:
            logger.error(f"Error creating .cursorrules: {e}")
            return False
    
    # Keep old method for backward compatibility but deprecate it
    def export_to_cursor(self, context: Dict, custom_path: Optional[str] = None) -> bool:
        """DEPRECATED: Use export_to_cursorrules instead"""
        logger.warning("export_to_cursor is deprecated, using export_to_cursorrules instead")
        return self.export_to_cursorrules(context, custom_path)

