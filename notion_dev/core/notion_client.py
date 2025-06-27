# notion_dev/core/notion_client.py
import requests
from typing import List, Optional, Dict, Any
from .models import Feature, Module
import logging

logger = logging.getLogger(__name__)

class NotionClient:
    def __init__(self, token: str, modules_db_id: str, features_db_id: str):
        self.token = token
        self.modules_db_id = modules_db_id
        self.features_db_id = features_db_id
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28"
        }
        
    def _make_request(self, method: str, url: str, **kwargs) -> Dict[Any, Any]:
        """Effectue une requête à l'API Notion"""
        try:
            response = requests.request(method, url, headers=self.headers, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Notion API error: {e}")
            raise
    
    def _extract_page_content(self, page_id: str) -> str:
        """Extract page content preserving Markdown formatting"""
        url = f"https://api.notion.com/v1/blocks/{page_id}/children"
        
        try:
            response = self._make_request("GET", url)
            content_blocks = []
            
            for block in response.get('results', []):
                block_type = block.get('type')
                
                if block_type == 'paragraph':
                    text_content = self._extract_text_from_block(block, preserve_formatting=True)
                    if text_content:
                        content_blocks.append(text_content)
                        
                elif block_type == 'heading_1':
                    text_content = self._extract_text_from_block(block)
                    if text_content:
                        content_blocks.append(f"# {text_content}")
                        
                elif block_type == 'heading_2':
                    text_content = self._extract_text_from_block(block)
                    if text_content:
                        content_blocks.append(f"## {text_content}")
                        
                elif block_type == 'heading_3':
                    text_content = self._extract_text_from_block(block)
                    if text_content:
                        content_blocks.append(f"### {text_content}")
                        
                elif block_type == 'bulleted_list_item':
                    text_content = self._extract_text_from_block(block, preserve_formatting=True)
                    if text_content:
                        content_blocks.append(f"- {text_content}")
                        
                elif block_type == 'numbered_list_item':
                    text_content = self._extract_text_from_block(block, preserve_formatting=True)
                    if text_content:
                        content_blocks.append(f"1. {text_content}")
                        
                elif block_type == 'code':
                    code_content = self._extract_text_from_block(block)
                    language = block.get('code', {}).get('language', '')
                    if code_content:
                        content_blocks.append(f"```{language}\n{code_content}\n```")
                        
                elif block_type == 'quote':
                    text_content = self._extract_text_from_block(block, preserve_formatting=True)
                    if text_content:
                        content_blocks.append(f"> {text_content}")
                        
                elif block_type == 'divider':
                    content_blocks.append("---")
                        
            return "\n\n".join(content_blocks)
        except Exception as e:
            logger.warning(f"Could not extract content for page {page_id}: {e}")
            return ""
    
    def _extract_text_from_block(self, block: Dict, preserve_formatting: bool = False) -> str:
        """Extract text from Notion block with optional markdown formatting"""
        block_type = block.get('type')
        if block_type and block_type in block:
            text_array = block[block_type].get('rich_text', [])
            
            if not preserve_formatting:
                return ''.join([text.get('plain_text', '') for text in text_array])
            
            # Preserve markdown formatting
            formatted_texts = []
            for text in text_array:
                plain = text.get('plain_text', '')
                if not plain:
                    continue
                    
                # Apply formatting based on annotations
                annotations = text.get('annotations', {})
                if annotations.get('bold'):
                    plain = f"**{plain}**"
                if annotations.get('italic'):
                    plain = f"*{plain}*"
                if annotations.get('strikethrough'):
                    plain = f"~~{plain}~~"
                if annotations.get('code'):
                    plain = f"`{plain}`"
                    
                # Handle links
                if text.get('href'):
                    plain = f"[{plain}]({text['href']})"
                    
                formatted_texts.append(plain)
                
            return ''.join(formatted_texts)
        return ""
    
    def get_feature(self, code: str) -> Optional[Feature]:
        """Récupère une feature par son code"""
        url = f"https://api.notion.com/v1/databases/{self.features_db_id}/query"
        
        # Try different filter types in case 'code' is not rich_text
        payload = {
            "filter": {
                "property": "code",
                "rich_text": {
                    "equals": code
                }
            }
        }
        
        try:
            response = self._make_request("POST", url, json=payload)
            results = response.get('results', [])
            
            if not results:
                # Try with title property instead
                logger.warning(f"Feature {code} not found with rich_text filter, trying title filter")
                payload = {
                    "filter": {
                        "property": "code", 
                        "title": {
                            "equals": code
                        }
                    }
                }
                response = self._make_request("POST", url, json=payload)
                results = response.get('results', [])
                
            if not results:
                logger.warning(f"Feature {code} not found in Notion")
                return None
                
            page = results[0]
            properties = page['properties']
            
            # Extraction des propriétés
            feature_name = self._get_property_value(properties, 'name', 'title')
            status = self._get_property_value(properties, 'status', 'select')
            module_relation = self._get_property_value(properties, 'module', 'relation')
            plan = self._get_property_value(properties, 'plan', 'multi_select')
            user_rights = self._get_property_value(properties, 'user_rights', 'multi_select')
            
            # Extraction du contenu de la page
            content = self._extract_page_content(page['id'])
            
            # Récupération du module associé
            module = None
            if module_relation:
                module = self.get_module_by_id(module_relation[0])
            
            return Feature(
                code=code,
                name=feature_name,
                status=status,
                module_name=module.name if module else "Unknown",
                plan=plan,
                user_rights=user_rights,
                notion_id=page['id'],
                content=content,
                module=module
            )
            
        except Exception as e:
            logger.error(f"Error retrieving feature {code}: {e}")
            return None
    
    def get_module_by_id(self, module_id: str) -> Optional[Module]:
        """Récupère un module par son ID Notion"""
        url = f"https://api.notion.com/v1/pages/{module_id}"
        
        try:
            response = self._make_request("GET", url)
            properties = response['properties']
            
            name = self._get_property_value(properties, 'name', 'title')
            description = self._get_property_value(properties, 'description', 'rich_text')
            status = self._get_property_value(properties, 'status', 'select')
            application = self._get_property_value(properties, 'application', 'select')
            code_prefix = self._get_property_value(properties, 'code_prefix', 'rich_text')
            
            content = self._extract_page_content(module_id)
            
            return Module(
                name=name,
                description=description,
                status=status,
                application=application,
                code_prefix=code_prefix,
                notion_id=module_id,
                content=content
            )
            
        except Exception as e:
            logger.error(f"Error retrieving module {module_id}: {e}")
            return None
    
    def _get_property_value(self, properties: Dict, prop_name: str, prop_type: str) -> Any:
        """Extrait la valeur d'une propriété Notion selon son type"""
        if prop_name not in properties:
            return None
            
        prop = properties[prop_name]
        
        if prop_type == 'title':
            return ''.join([t['plain_text'] for t in prop['title']])
        elif prop_type == 'rich_text':
            return ''.join([t['plain_text'] for t in prop['rich_text']])
        elif prop_type == 'select':
            return prop['select']['name'] if prop['select'] else None
        elif prop_type == 'multi_select':
            return [item['name'] for item in prop['multi_select']]
        elif prop_type == 'relation':
            return [item['id'] for item in prop['relation']]
        else:
            return prop.get(prop_type)
    
    def search_features(self, query: str = "") -> List[Feature]:
        """Recherche des features dans Notion"""
        url = f"https://api.notion.com/v1/databases/{self.features_db_id}/query"
        
        payload = {}
        if query:
            payload["filter"] = {
                "or": [
                    {
                        "property": "name",
                        "title": {
                            "contains": query
                        }
                    },
                    {
                        "property": "code", 
                        "rich_text": {
                            "contains": query
                        }
                    }
                ]
            }
        
        try:
            response = self._make_request("POST", url, json=payload)
            features = []
            
            for result in response.get('results', []):
                properties = result['properties']
                code = self._get_property_value(properties, 'code', 'rich_text')
                if code:
                    feature = self.get_feature(code)
                    if feature:
                        features.append(feature)
                        
            return features
            
        except Exception as e:
            logger.error(f"Error searching features: {e}")
            return []

