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
    
    def _build_agents_content(self, context: Dict) -> str:
        """Build content for AGENTS.md file following the standard"""
        feature = context['feature']
        project_info = context['project_info']
        task = context.get('task', None)

        # Build AGENTS.md content following the standard
        content = f"""# AGENTS.md - {project_info['name']}

*Generated by NotionDev on {datetime.now().strftime('%Y-%m-%d %H:%M')}*

## Project Overview

NotionDev is a Python CLI tool that integrates Notion, Asana, and Git for developers. It streamlines development workflows by automatically loading feature specifications from Notion into AI coding assistants while synchronizing with Asana tickets.

**Current Context:**
- **Project**: {project_info['name']}
- **Active Module**: {feature.module_name}
- **Active Feature**: {feature.code} - {feature.name}
- **Status**: {feature.status}"""

        if task:
            content += f"""
- **Current Task**: {task.gid} - {task.name}"""

        content += f"""

## Build and Test Commands

### Development Commands
```bash
# Run CLI in development mode
python -m notion_dev.cli.main

# List Asana tickets
python -m notion_dev.cli.main tickets

# Start working on a ticket
python -m notion_dev.cli.main work TASK-123456789

# Generate AI context
python -m notion_dev.cli.main context

# Interactive mode
python -m notion_dev.cli.main interactive
```

### Testing
```bash
# Run unit tests
pytest tests/unit -v

# Install for testing
chmod +x install_notion_dev.sh
./install_notion_dev.sh
~/notion-dev-install/test_config.sh
```

## Architecture and Current Module

### Module: {feature.module_name}
{feature.module.description if feature.module else 'Module information not available'}

### Module Documentation
{feature.module.content if feature.module else 'No module content available'}

## Current Feature Context

⚠️ **IMPORTANT**: You are working on a specific feature within a larger codebase. Follow isolation rules to prevent regressions.

### Feature Scope
- **Feature Code**: {feature.code}
- **Feature Name**: {feature.name}
- **Module**: {feature.module_name}
- **Status**: {feature.status}

### Regression Prevention Rules

**MANDATORY**: To prevent regressions across the codebase:

1. **Feature Isolation**: Work ONLY on feature **{feature.code}**
2. **File Headers Check**: Every file has a header indicating which feature it implements
3. **Modification Rules**:
   - ✅ CREATE new files: MUST add the header for feature {feature.code}
   - ✅ MODIFY files: ONLY if header contains feature {feature.code}
   - ❌ NEVER modify files with different feature codes
   - ❌ NEVER remove or alter existing feature headers

### Feature Specifications
{feature.get_full_context()}

## Code Standards

### Mandatory File Headers

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

### Language Requirements
- **Documentation reading**: You may encounter documentation in various languages
- **Chat responses**: You may respond in the user's preferred language
- **Code and comments**: ALL code, comments, variable names, and function names MUST be in English

## Development Workflow

### Notion Integration
- Features are documented in Notion with detailed specifications
- Each feature has a unique code (e.g., {feature.code})
- Module documentation provides architectural context

### Asana Integration
- Tasks link to feature codes for traceability
- Use `notion-dev work TASK-ID` to start working on a task

### Git Integration
- Headers in code files ensure traceability
- Follow feature isolation to prevent regressions

## Security Considerations

- API tokens are stored in `~/.notion-dev/config.yml`
- Never commit sensitive configuration to repository
- Use environment variables for CI/CD deployments

## Project Information
- **Repository**: {project_info['path']}
- **Git Status**: {'Git repository' if project_info['is_git_repo'] else 'Not a git repository'}
- **Cache Location**: {project_info['cache']}

---
*Generated by NotionDev - Keeping your code aligned with specifications*
"""
        return content
    
    def export_to_agents_md(self, context: Dict, custom_path: Optional[str] = None) -> bool:
        """Export context to AGENTS.md file following the standard"""
        project_path = custom_path or self.config.repository_path

        try:
            # Get max context length from config
            max_length = getattr(self.config.ai, 'context_max_length', 100000) if hasattr(self.config, 'ai') else 100000

            # Clean up old .cursor directory and .cursorrules file if they exist
            cursor_dir = os.path.join(project_path, ".cursor")
            if os.path.exists(cursor_dir):
                shutil.rmtree(cursor_dir)
                logger.info("Cleaned up legacy .cursor directory")

            cursorrules_file = os.path.join(project_path, ".cursorrules")
            if os.path.exists(cursorrules_file):
                os.remove(cursorrules_file)
                logger.info("Cleaned up legacy .cursorrules file")

            # Build AGENTS.md content
            agents_content = self._build_agents_content(context)

            # Check size and truncate if needed
            original_size = len(agents_content)
            if original_size > max_length:
                logger.warning(f"Context size ({original_size}) exceeds limit ({max_length}), truncating...")
                agents_content = self._truncate_content(agents_content, max_length)

            # Write AGENTS.md at project root
            agents_path = os.path.join(project_path, "AGENTS.md")
            with open(agents_path, 'w', encoding='utf-8') as f:
                f.write(agents_content)

            final_size = len(agents_content)
            logger.info(f"AGENTS.md created: {final_size} chars" +
                       (f" (truncated from {original_size})" if original_size > max_length else ""))

            return True

        except Exception as e:
            logger.error(f"Error creating AGENTS.md: {e}")
            return False
    
    # Keep old methods for backward compatibility but deprecate them
    def export_to_cursorrules(self, context: Dict, custom_path: Optional[str] = None) -> bool:
        """DEPRECATED: Use export_to_agents_md instead"""
        logger.warning("export_to_cursorrules is deprecated, using export_to_agents_md instead")
        return self.export_to_agents_md(context, custom_path)

    def export_to_cursor(self, context: Dict, custom_path: Optional[str] = None) -> bool:
        """DEPRECATED: Use export_to_agents_md instead"""
        logger.warning("export_to_cursor is deprecated, using export_to_agents_md instead")
        return self.export_to_agents_md(context, custom_path)

