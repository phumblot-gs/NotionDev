# notion_dev/core/models.py - Ajout du modèle Project
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from datetime import datetime

@dataclass
class AsanaProject:
    gid: str
    name: str
    created_at: str
    color: Optional[str] = None

@dataclass
class Module:
    name: str
    description: str
    status: str  # draft, review, validated, obsolete
    application: str  # service, backend, frontend
    code_prefix: str
    notion_id: str
    content: str = ""
    
    @property
    def is_active(self) -> bool:
        return self.status in ['review', 'validated']

@dataclass
class Feature:
    code: str
    name: str
    status: str  # draft, review, validated, obsolete
    module_name: str
    plan: List[str]
    user_rights: List[str]
    notion_id: str
    content: str = ""
    module: Optional[Module] = None
    
    @property
    def is_active(self) -> bool:
        return self.status in ['review', 'validated']
    
    def get_full_context(self) -> str:
        """Retourne le contexte complet feature + module"""
        context = f"# Feature {self.code} - {self.name}\n\n"
        context += f"**Status:** {self.status}\n"
        context += f"**Module:** {self.module_name}\n"
        
        # Handle plan field safely
        if self.plan:
            if isinstance(self.plan, list):
                context += f"**Plans:** {', '.join(self.plan)}\n"
            else:
                context += f"**Plans:** {self.plan}\n"
        
        # Handle user_rights field safely
        if self.user_rights:
            if isinstance(self.user_rights, list):
                context += f"**User Rights:** {', '.join(self.user_rights)}\n"
            else:
                context += f"**User Rights:** {self.user_rights}\n"
                
        context += "\n## Feature Documentation\n\n"
        # Clean up content to remove project reference line
        cleaned_content = self.content
        if cleaned_content:
            lines = cleaned_content.split('\n')
            filtered_lines = [line for line in lines if not (line.strip().startswith('*') and 'fait partie du projet' in line)]
            cleaned_content = '\n'.join(filtered_lines)
        context += cleaned_content
        
        if self.module:
            context += f"\n\nBelow the documentation of Module: {self.module.name}\n\n"
            context += self.module.content
            
        return context

@dataclass 
class AsanaTask:
    gid: str
    name: str
    notes: str
    assignee_gid: str
    completed: bool
    project_gid: Optional[str] = None
    project_name: Optional[str] = None
    feature_code: Optional[str] = None
    feature_codes: List[str] = None
    created_by_gid: Optional[str] = None
    
    def __post_init__(self):
        if self.feature_codes is None:
            self.feature_codes = []
    
    def extract_feature_code(self) -> Optional[str]:
        """Extrait le code feature principal (priorité au titre, puis notes)"""
        import re
        
        # Pattern pour codes features (AU01, DA02, API03, etc.)
        pattern = r"\b([A-Z]{2,4}\d{2,3})\b"
        
        # First, search in title
        title_matches = re.findall(pattern, self.name)
        if title_matches:
            self.feature_codes = title_matches
            self.feature_code = title_matches[0]  # Primary code is the first one found
            return self.feature_code
            
        # Then search in notes if no code found in title
        if self.notes:
            # Look for "Feature Code: AU01" format
            feature_code_pattern = r"Feature Code:\s*([A-Z]{2,4}\d{2,3})"
            match = re.search(feature_code_pattern, self.notes, re.IGNORECASE)
            if match:
                self.feature_code = match.group(1).upper()
                self.feature_codes = [self.feature_code]
                return self.feature_code
                
            # Look for direct pattern
            notes_matches = re.findall(pattern, self.notes)
            if notes_matches:
                self.feature_codes = notes_matches
                self.feature_code = notes_matches[0]
                return self.feature_code
            
        return None

