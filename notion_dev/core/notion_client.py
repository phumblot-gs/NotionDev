# notion_dev/core/notion_client.py
import requests
import re
from typing import List, Optional, Dict, Any, Union
from .models import Feature, Module
import logging

logger = logging.getLogger(__name__)

# Constants for batch operations
NOTION_MAX_BLOCKS_PER_REQUEST = 100
NOTION_MAX_RICH_TEXT_LENGTH = 2000  # Notion API limit per rich_text element

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

    def test_connection(self) -> Dict[str, Any]:
        """Test connection to Notion API and validate database access.

        Returns:
            Dict with 'success', 'user', 'modules_db', 'features_db' keys
        """
        result = {
            "success": False,
            "user": None,
            "modules_db": None,
            "features_db": None,
            "errors": []
        }

        # Test 1: Verify token by getting user info
        try:
            url = "https://api.notion.com/v1/users/me"
            response = self._make_request("GET", url)
            result["user"] = response.get("name", response.get("id", "Unknown"))
        except requests.HTTPError as e:
            if e.response.status_code == 401:
                result["errors"].append("Invalid Notion token (401 Unauthorized)")
            else:
                result["errors"].append(f"Notion API error: {e}")
            return result
        except Exception as e:
            result["errors"].append(f"Connection error: {e}")
            return result

        # Test 2: Verify modules database access
        try:
            url = f"https://api.notion.com/v1/databases/{self.modules_db_id}"
            response = self._make_request("GET", url)
            result["modules_db"] = response.get("title", [{}])[0].get("plain_text", "Modules DB")
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                result["errors"].append("Modules database not found or not shared with integration")
            else:
                result["errors"].append(f"Modules database error: {e}")
        except Exception as e:
            result["errors"].append(f"Modules database error: {e}")

        # Test 3: Verify features database access
        try:
            url = f"https://api.notion.com/v1/databases/{self.features_db_id}"
            response = self._make_request("GET", url)
            result["features_db"] = response.get("title", [{}])[0].get("plain_text", "Features DB")
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                result["errors"].append("Features database not found or not shared with integration")
            else:
                result["errors"].append(f"Features database error: {e}")
        except Exception as e:
            result["errors"].append(f"Features database error: {e}")

        result["success"] = len(result["errors"]) == 0
        return result

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

            # New GitHub-related properties (optional)
            repository_url = self._get_property_value(properties, 'repository_url', 'url')
            code_path = self._get_property_value(properties, 'code_path', 'rich_text')
            branch = self._get_property_value(properties, 'branch', 'rich_text')

            content = self._extract_page_content(module_id)

            return Module(
                name=name,
                description=description,
                status=status,
                application=application,
                code_prefix=code_prefix,
                notion_id=module_id,
                content=content,
                repository_url=repository_url,
                code_path=code_path,
                branch=branch
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
        elif prop_type == 'url':
            return prop.get('url')
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

    # ==========================================================================
    # WRITE OPERATIONS - Create and update modules/features in Notion
    # ==========================================================================

    def _markdown_to_blocks(self, markdown: str) -> List[Dict[str, Any]]:
        """Convert markdown text to Notion blocks.

        Supports: headings (h1-h3), paragraphs, bullet lists, numbered lists,
        code blocks, quotes, dividers, bold, italic, code, links.
        """
        blocks = []
        lines = markdown.split('\n')
        i = 0

        while i < len(lines):
            line = lines[i]

            # Skip empty lines
            if not line.strip():
                i += 1
                continue

            # Code block (```)
            if line.strip().startswith('```'):
                language = line.strip()[3:] or 'plain text'
                code_lines = []
                i += 1
                while i < len(lines) and not lines[i].strip().startswith('```'):
                    code_lines.append(lines[i])
                    i += 1
                # _create_code_block returns a list (may split long code)
                blocks.extend(self._create_code_block('\n'.join(code_lines), language))
                i += 1
                continue

            # Heading 1
            if line.startswith('# '):
                blocks.append(self._create_heading_block(line[2:], 1))
                i += 1
                continue

            # Heading 2
            if line.startswith('## '):
                blocks.append(self._create_heading_block(line[3:], 2))
                i += 1
                continue

            # Heading 3
            if line.startswith('### '):
                blocks.append(self._create_heading_block(line[4:], 3))
                i += 1
                continue

            # Divider
            if line.strip() in ['---', '***', '___']:
                blocks.append({'object': 'block', 'type': 'divider', 'divider': {}})
                i += 1
                continue

            # Quote
            if line.startswith('> '):
                blocks.append(self._create_quote_block(line[2:]))
                i += 1
                continue

            # Bullet list
            if line.startswith('- ') or line.startswith('* '):
                blocks.append(self._create_bulleted_list_block(line[2:]))
                i += 1
                continue

            # Numbered list
            if re.match(r'^\d+\.\s', line):
                text = re.sub(r'^\d+\.\s', '', line)
                blocks.append(self._create_numbered_list_block(text))
                i += 1
                continue

            # Table detection (simple markdown tables)
            if '|' in line and i + 1 < len(lines) and '|' in lines[i + 1]:
                # Check if next line is separator (|---|---|)
                if re.match(r'^[\s|:-]+$', lines[i + 1]):
                    table_lines = [line]
                    i += 1
                    # Skip separator
                    i += 1
                    # Collect table rows
                    while i < len(lines) and '|' in lines[i]:
                        table_lines.append(lines[i])
                        i += 1
                    blocks.append(self._create_table_block(table_lines))
                    continue

            # Default: paragraph
            blocks.append(self._create_paragraph_block(line))
            i += 1

        return blocks

    def _split_text_for_notion(
        self,
        content: str,
        annotations: Dict[str, Any] = None,
        link: Dict[str, str] = None
    ) -> List[Dict[str, Any]]:
        """Split text into chunks respecting Notion's 2000 character limit.

        Args:
            content: Text content to split
            annotations: Optional formatting annotations (bold, italic, code, etc.)
            link: Optional link dict {'url': '...'}

        Returns:
            List of rich_text elements, each under 2000 characters
        """
        chunks = []
        max_len = NOTION_MAX_RICH_TEXT_LENGTH

        while content:
            if len(content) <= max_len:
                chunk = content
                content = ""
            else:
                # Try to split at a space to avoid breaking words
                split_pos = content.rfind(' ', 0, max_len)
                if split_pos <= 0:
                    # No space found, split at max_len
                    split_pos = max_len
                chunk = content[:split_pos]
                content = content[split_pos:].lstrip()

            element = {'type': 'text', 'text': {'content': chunk}}
            if annotations:
                element['annotations'] = annotations
            if link:
                element['text']['link'] = link
            chunks.append(element)

        return chunks

    def _parse_rich_text(self, text: str) -> List[Dict[str, Any]]:
        """Parse markdown inline formatting to Notion rich_text array.

        Supports: **bold**, *italic*, `code`, [links](url)
        Handles text longer than 2000 characters by splitting into chunks.
        """
        rich_text = []

        # Pattern to match markdown formatting
        # Order matters: check combined formats first
        pattern = r'(\*\*\*(.+?)\*\*\*|\*\*(.+?)\*\*|\*(.+?)\*|`(.+?)`|\[(.+?)\]\((.+?)\))'

        last_end = 0
        for match in re.finditer(pattern, text):
            # Add plain text before this match
            if match.start() > last_end:
                plain = text[last_end:match.start()]
                if plain:
                    rich_text.extend(self._split_text_for_notion(plain))

            full_match = match.group(0)

            # Bold + Italic (***text***)
            if match.group(2):
                rich_text.extend(self._split_text_for_notion(
                    match.group(2),
                    annotations={'bold': True, 'italic': True}
                ))
            # Bold (**text**)
            elif match.group(3):
                rich_text.extend(self._split_text_for_notion(
                    match.group(3),
                    annotations={'bold': True}
                ))
            # Italic (*text*)
            elif match.group(4):
                rich_text.extend(self._split_text_for_notion(
                    match.group(4),
                    annotations={'italic': True}
                ))
            # Code (`text`)
            elif match.group(5):
                rich_text.extend(self._split_text_for_notion(
                    match.group(5),
                    annotations={'code': True}
                ))
            # Link ([text](url))
            elif match.group(6) and match.group(7):
                rich_text.extend(self._split_text_for_notion(
                    match.group(6),
                    link={'url': match.group(7)}
                ))

            last_end = match.end()

        # Add remaining plain text
        if last_end < len(text):
            remaining = text[last_end:]
            if remaining:
                rich_text.extend(self._split_text_for_notion(remaining))

        # If no formatting found, return simple text (with splitting)
        if not rich_text:
            rich_text.extend(self._split_text_for_notion(text))

        return rich_text

    def _create_paragraph_block(self, text: str) -> Dict[str, Any]:
        """Create a paragraph block."""
        return {
            'object': 'block',
            'type': 'paragraph',
            'paragraph': {'rich_text': self._parse_rich_text(text)}
        }

    def _create_heading_block(self, text: str, level: int) -> Dict[str, Any]:
        """Create a heading block (level 1, 2, or 3)."""
        heading_type = f'heading_{level}'
        return {
            'object': 'block',
            'type': heading_type,
            heading_type: {'rich_text': self._parse_rich_text(text)}
        }

    def _create_bulleted_list_block(self, text: str) -> Dict[str, Any]:
        """Create a bulleted list item block."""
        return {
            'object': 'block',
            'type': 'bulleted_list_item',
            'bulleted_list_item': {'rich_text': self._parse_rich_text(text)}
        }

    def _create_numbered_list_block(self, text: str) -> Dict[str, Any]:
        """Create a numbered list item block."""
        return {
            'object': 'block',
            'type': 'numbered_list_item',
            'numbered_list_item': {'rich_text': self._parse_rich_text(text)}
        }

    def _create_code_block(self, code: str, language: str = 'plain text') -> List[Dict[str, Any]]:
        """Create code block(s), splitting if content exceeds 2000 characters.

        Returns a list of code blocks to handle long code content.
        """
        # Notion has specific language identifiers
        language_map = {
            'python': 'python',
            'py': 'python',
            'javascript': 'javascript',
            'js': 'javascript',
            'typescript': 'typescript',
            'ts': 'typescript',
            'bash': 'bash',
            'sh': 'bash',
            'shell': 'bash',
            'json': 'json',
            'yaml': 'yaml',
            'yml': 'yaml',
            'sql': 'sql',
            'html': 'html',
            'css': 'css',
            'java': 'java',
            'go': 'go',
            'rust': 'rust',
            'c': 'c',
            'cpp': 'c++',
            'c++': 'c++',
        }
        notion_lang = language_map.get(language.lower(), 'plain text')

        # Split code into chunks if too long
        blocks = []
        max_len = NOTION_MAX_RICH_TEXT_LENGTH
        remaining = code

        while remaining:
            if len(remaining) <= max_len:
                chunk = remaining
                remaining = ""
            else:
                # Try to split at a newline to keep code readable
                split_pos = remaining.rfind('\n', 0, max_len)
                if split_pos <= 0:
                    # No newline found, split at max_len
                    split_pos = max_len
                chunk = remaining[:split_pos]
                remaining = remaining[split_pos:].lstrip('\n')

            blocks.append({
                'object': 'block',
                'type': 'code',
                'code': {
                    'rich_text': [{'type': 'text', 'text': {'content': chunk}}],
                    'language': notion_lang
                }
            })

        return blocks if blocks else [{
            'object': 'block',
            'type': 'code',
            'code': {
                'rich_text': [{'type': 'text', 'text': {'content': ''}}],
                'language': notion_lang
            }
        }]

    def _create_quote_block(self, text: str) -> Dict[str, Any]:
        """Create a quote block."""
        return {
            'object': 'block',
            'type': 'quote',
            'quote': {'rich_text': self._parse_rich_text(text)}
        }

    def _create_table_block(self, table_lines: List[str]) -> Dict[str, Any]:
        """Create a table block from markdown table lines."""
        # Parse header and rows
        rows = []
        for line in table_lines:
            cells = [cell.strip() for cell in line.strip('|').split('|')]
            rows.append(cells)

        if not rows:
            return self._create_paragraph_block("(empty table)")

        # Determine table width
        table_width = max(len(row) for row in rows)

        # Build table children (rows)
        table_rows = []
        for row in rows:
            # Pad row to table width
            while len(row) < table_width:
                row.append('')

            table_rows.append({
                'type': 'table_row',
                'table_row': {
                    'cells': [[{'type': 'text', 'text': {'content': cell}}] for cell in row]
                }
            })

        return {
            'object': 'block',
            'type': 'table',
            'table': {
                'table_width': table_width,
                'has_column_header': True,
                'has_row_header': False,
                'children': table_rows
            }
        }

    def _append_blocks_batch(self, page_id: str, blocks: List[Dict[str, Any]]) -> bool:
        """Append blocks to a page in batches of NOTION_MAX_BLOCKS_PER_REQUEST.

        Returns True if all batches succeeded, False otherwise.
        """
        url = f"https://api.notion.com/v1/blocks/{page_id}/children"

        # Split blocks into chunks
        for i in range(0, len(blocks), NOTION_MAX_BLOCKS_PER_REQUEST):
            chunk = blocks[i:i + NOTION_MAX_BLOCKS_PER_REQUEST]
            try:
                self._make_request("PATCH", url, json={"children": chunk})
                logger.info(f"Appended {len(chunk)} blocks to page {page_id}")
            except Exception as e:
                logger.error(f"Error appending blocks to page {page_id}: {e}")
                return False

        return True

    def _delete_all_blocks(self, page_id: str) -> bool:
        """Delete all blocks from a page (to replace content)."""
        url = f"https://api.notion.com/v1/blocks/{page_id}/children"

        try:
            response = self._make_request("GET", url)
            blocks = response.get('results', [])

            for block in blocks:
                block_id = block['id']
                delete_url = f"https://api.notion.com/v1/blocks/{block_id}"
                try:
                    self._make_request("DELETE", delete_url)
                except Exception as e:
                    logger.warning(f"Could not delete block {block_id}: {e}")

            return True
        except Exception as e:
            logger.error(f"Error deleting blocks from page {page_id}: {e}")
            return False

    def create_module(
        self,
        name: str,
        description: str,
        code_prefix: str,
        application: str = "Backend",
        status: str = "Draft",
        content_markdown: str = ""
    ) -> Optional[Module]:
        """Create a new module in Notion.

        Args:
            name: Module name (title)
            description: Short description
            code_prefix: 2-3 character code prefix (e.g., 'CC', 'API')
            application: One of 'Backend', 'Frontend', 'Service'
            status: One of 'Draft', 'Review', 'Validated', 'Obsolete'
            content_markdown: Full documentation in markdown format

        Returns:
            Module object if created successfully, None otherwise
        """
        url = "https://api.notion.com/v1/pages"

        # Validate application and status
        valid_applications = ['Backend', 'Frontend', 'Service']
        valid_statuses = ['Draft', 'Review', 'Validated', 'Obsolete']

        if application not in valid_applications:
            logger.error(f"Invalid application: {application}. Must be one of {valid_applications}")
            return None

        if status not in valid_statuses:
            logger.error(f"Invalid status: {status}. Must be one of {valid_statuses}")
            return None

        # Build page properties
        payload = {
            "parent": {"database_id": self.modules_db_id},
            "properties": {
                "name": {"title": [{"text": {"content": name}}]},
                "description": {"rich_text": [{"text": {"content": description}}]},
                "code_prefix": {"rich_text": [{"text": {"content": code_prefix.upper()}}]},
                "application": {"select": {"name": application}},
                "status": {"select": {"name": status}}
            }
        }

        try:
            # Create the page
            response = self._make_request("POST", url, json=payload)
            page_id = response['id']
            logger.info(f"Created module page: {name} ({page_id})")

            # Add content if provided
            if content_markdown:
                blocks = self._markdown_to_blocks(content_markdown)
                if blocks:
                    self._append_blocks_batch(page_id, blocks)

            # Return the created module
            return Module(
                name=name,
                description=description,
                status=status,
                application=application,
                code_prefix=code_prefix.upper(),
                notion_id=page_id,
                content=content_markdown
            )

        except Exception as e:
            logger.error(f"Error creating module {name}: {e}")
            return None

    def create_feature(
        self,
        name: str,
        module_prefix: str = None,
        code: str = None,
        module_id: str = None,
        status: str = "Draft",
        plan: List[str] = None,
        user_rights: List[str] = None,
        content_markdown: str = ""
    ) -> Optional[Feature]:
        """Create a new feature in Notion.

        Can be called in two ways:
        1. With module_prefix (recommended): code is auto-generated
           create_feature(name="My Feature", module_prefix="CC")
        2. With explicit code and module_id:
           create_feature(name="My Feature", code="CC01", module_id="...")

        Args:
            name: Feature name (title)
            module_prefix: Module's code prefix (e.g., 'CC', 'API') - auto-generates code
            code: Feature code (e.g., 'CC01') - optional if module_prefix provided
            module_id: Notion ID of the parent module - optional if module_prefix provided
            status: One of 'Draft', 'Review', 'Validated', 'Obsolete'
            plan: List of subscription plans
            user_rights: List of user rights
            content_markdown: Full documentation in markdown format

        Returns:
            Feature object if created successfully, None otherwise
        """
        url = "https://api.notion.com/v1/pages"

        # Resolve module_prefix to code and module_id if needed
        if module_prefix:
            module = self.get_module_by_prefix(module_prefix.upper())
            if not module:
                logger.error(f"Module with prefix '{module_prefix}' not found")
                return None
            module_id = module.notion_id
            if not code:
                code = self.generate_next_feature_code(module_prefix)
        elif not code or not module_id:
            logger.error("Either module_prefix or both code and module_id must be provided")
            return None

        valid_statuses = ['Draft', 'Review', 'Validated', 'Obsolete']
        if status not in valid_statuses:
            logger.error(f"Invalid status: {status}. Must be one of {valid_statuses}")
            return None

        # Build page properties
        properties = {
            "name": {"title": [{"text": {"content": name}}]},
            "code": {"rich_text": [{"text": {"content": code.upper()}}]},
            "module": {"relation": [{"id": module_id}]},
            "status": {"select": {"name": status}}
        }

        # Add optional multi-select fields
        if plan:
            properties["plan"] = {"multi_select": [{"name": p} for p in plan]}

        if user_rights:
            properties["user_rights"] = {"multi_select": [{"name": r} for r in user_rights]}

        payload = {
            "parent": {"database_id": self.features_db_id},
            "properties": properties
        }

        try:
            # Create the page
            response = self._make_request("POST", url, json=payload)
            page_id = response['id']
            logger.info(f"Created feature page: {code} - {name} ({page_id})")

            # Add content if provided
            if content_markdown:
                blocks = self._markdown_to_blocks(content_markdown)
                if blocks:
                    self._append_blocks_batch(page_id, blocks)

            # Get module info for return object
            module = self.get_module_by_id(module_id)

            return Feature(
                code=code.upper(),
                name=name,
                status=status,
                module_name=module.name if module else "Unknown",
                plan=plan or [],
                user_rights=user_rights or [],
                notion_id=page_id,
                content=content_markdown,
                module=module
            )

        except Exception as e:
            logger.error(f"Error creating feature {code}: {e}")
            return None

    def update_page_content(
        self,
        page_id: str,
        content_markdown: str,
        replace: bool = True
    ) -> bool:
        """Update the content of a Notion page.

        Args:
            page_id: Notion page ID
            content_markdown: New content in markdown format
            replace: If True, replace all content. If False, append to existing.

        Returns:
            True if successful, False otherwise
        """
        try:
            if replace:
                # Delete existing blocks first
                if not self._delete_all_blocks(page_id):
                    logger.warning(f"Could not delete existing blocks from {page_id}")

            # Convert markdown to blocks and append
            blocks = self._markdown_to_blocks(content_markdown)
            if blocks:
                return self._append_blocks_batch(page_id, blocks)

            return True

        except Exception as e:
            logger.error(f"Error updating page content {page_id}: {e}")
            return False

    def update_module_properties(
        self,
        module_id: str,
        name: str = None,
        description: str = None,
        code_prefix: str = None,
        application: str = None,
        status: str = None
    ) -> bool:
        """Update module properties (not content).

        Args:
            module_id: Notion page ID of the module
            name: New name (optional)
            description: New description (optional)
            code_prefix: New code prefix (optional)
            application: New application type (optional)
            status: New status (optional)

        Returns:
            True if successful, False otherwise
        """
        url = f"https://api.notion.com/v1/pages/{module_id}"

        properties = {}

        if name is not None:
            properties["name"] = {"title": [{"text": {"content": name}}]}

        if description is not None:
            properties["description"] = {"rich_text": [{"text": {"content": description}}]}

        if code_prefix is not None:
            properties["code_prefix"] = {"rich_text": [{"text": {"content": code_prefix.upper()}}]}

        if application is not None:
            valid_applications = ['Backend', 'Frontend', 'Service']
            if application not in valid_applications:
                logger.error(f"Invalid application: {application}")
                return False
            properties["application"] = {"select": {"name": application}}

        if status is not None:
            valid_statuses = ['Draft', 'Review', 'Validated', 'Obsolete']
            if status not in valid_statuses:
                logger.error(f"Invalid status: {status}")
                return False
            properties["status"] = {"select": {"name": status}}

        if not properties:
            logger.warning("No properties to update")
            return True

        try:
            self._make_request("PATCH", url, json={"properties": properties})
            logger.info(f"Updated module properties: {module_id}")
            return True
        except Exception as e:
            logger.error(f"Error updating module {module_id}: {e}")
            return False

    def update_feature_properties(
        self,
        feature_id: str,
        name: str = None,
        code: str = None,
        module_id: str = None,
        status: str = None,
        plan: List[str] = None,
        user_rights: List[str] = None
    ) -> bool:
        """Update feature properties (not content).

        Args:
            feature_id: Notion page ID of the feature
            name: New name (optional)
            code: New code (optional)
            module_id: New parent module ID (optional)
            status: New status (optional)
            plan: New plans list (optional)
            user_rights: New user rights list (optional)

        Returns:
            True if successful, False otherwise
        """
        url = f"https://api.notion.com/v1/pages/{feature_id}"

        properties = {}

        if name is not None:
            properties["name"] = {"title": [{"text": {"content": name}}]}

        if code is not None:
            properties["code"] = {"rich_text": [{"text": {"content": code.upper()}}]}

        if module_id is not None:
            properties["module"] = {"relation": [{"id": module_id}]}

        if status is not None:
            valid_statuses = ['Draft', 'Review', 'Validated', 'Obsolete']
            if status not in valid_statuses:
                logger.error(f"Invalid status: {status}")
                return False
            properties["status"] = {"select": {"name": status}}

        if plan is not None:
            properties["plan"] = {"multi_select": [{"name": p} for p in plan]}

        if user_rights is not None:
            properties["user_rights"] = {"multi_select": [{"name": r} for r in user_rights]}

        if not properties:
            logger.warning("No properties to update")
            return True

        try:
            self._make_request("PATCH", url, json={"properties": properties})
            logger.info(f"Updated feature properties: {feature_id}")
            return True
        except Exception as e:
            logger.error(f"Error updating feature {feature_id}: {e}")
            return False

    def get_module_by_prefix(self, code_prefix: str) -> Optional[Module]:
        """Get a module by its code prefix.

        Args:
            code_prefix: The module's code prefix (e.g., 'CC', 'API')

        Returns:
            Module if found, None otherwise
        """
        url = f"https://api.notion.com/v1/databases/{self.modules_db_id}/query"

        payload = {
            "filter": {
                "property": "code_prefix",
                "rich_text": {
                    "equals": code_prefix.upper()
                }
            }
        }

        try:
            response = self._make_request("POST", url, json=payload)
            results = response.get('results', [])

            if not results:
                logger.warning(f"Module with prefix {code_prefix} not found")
                return None

            page = results[0]
            return self.get_module_by_id(page['id'])

        except Exception as e:
            logger.error(f"Error getting module by prefix {code_prefix}: {e}")
            return None

    def list_modules(self) -> List[Module]:
        """List all modules in the database.

        Returns:
            List of Module objects
        """
        url = f"https://api.notion.com/v1/databases/{self.modules_db_id}/query"

        try:
            response = self._make_request("POST", url, json={})
            modules = []

            for result in response.get('results', []):
                module = self.get_module_by_id(result['id'])
                if module:
                    modules.append(module)

            return modules

        except Exception as e:
            logger.error(f"Error listing modules: {e}")
            return []

    def list_features_for_module(self, module_id: str) -> List[Feature]:
        """List all features for a specific module.

        Args:
            module_id: Notion ID of the module

        Returns:
            List of Feature objects
        """
        url = f"https://api.notion.com/v1/databases/{self.features_db_id}/query"

        payload = {
            "filter": {
                "property": "module",
                "relation": {
                    "contains": module_id
                }
            }
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
            logger.error(f"Error listing features for module {module_id}: {e}")
            return []

    def get_next_feature_code(self, module_id: str) -> str:
        """Get the next available feature code for a module.

        Args:
            module_id: Notion ID of the module

        Returns:
            Next feature code (e.g., 'CC03' if CC01 and CC02 exist)
        """
        module = self.get_module_by_id(module_id)
        if not module:
            return "XX01"

        prefix = module.code_prefix
        features = self.list_features_for_module(module_id)

        if not features:
            return f"{prefix}01"

        # Extract numbers from existing codes
        numbers = []
        for feature in features:
            if feature.code.startswith(prefix):
                try:
                    num = int(feature.code[len(prefix):])
                    numbers.append(num)
                except ValueError:
                    continue

        next_num = max(numbers) + 1 if numbers else 1
        return f"{prefix}{next_num:02d}"

    # Alias methods for CLI compatibility
    def get_feature_by_code(self, code: str) -> Optional[Feature]:
        """Alias for get_feature - used by CLI."""
        return self.get_feature(code)

    def get_all_features(self) -> List[Feature]:
        """Get all features from the database."""
        return self.search_features("")

    def get_features_by_module(self, module_prefix: str) -> List[Feature]:
        """Get features filtered by module prefix."""
        module = self.get_module_by_prefix(module_prefix)
        if not module:
            return []
        return self.list_features_for_module(module.notion_id)

    def generate_next_feature_code(self, module_prefix: str) -> str:
        """Generate the next feature code for a module.

        Feature codes follow the pattern: {MODULE_PREFIX}{NUMBER}
        e.g., CC01, CC02, API01, API02

        Args:
            module_prefix: The module's code prefix (e.g., 'CC', 'API')

        Returns:
            The next available feature code (e.g., 'CC03' if CC01 and CC02 exist)
        """
        prefix = module_prefix.upper()

        # Get all features for this module
        features = self.get_features_by_module(prefix)

        if not features:
            # No existing features, start at 01
            return f"{prefix}01"

        # Extract numeric suffixes from existing codes
        max_num = 0
        for feature in features:
            if feature.code and feature.code.upper().startswith(prefix):
                # Extract the numeric part after the prefix
                num_part = feature.code[len(prefix):]
                try:
                    num = int(num_part)
                    max_num = max(max_num, num)
                except ValueError:
                    # Non-numeric suffix, skip
                    continue

        # Generate next code with zero-padded number
        next_num = max_num + 1
        return f"{prefix}{next_num:02d}"

    def get_modules(self) -> List[Module]:
        """Alias for list_modules - used by remote backend."""
        return self.list_modules()

    def update_feature_content(
        self,
        code: str,
        content_markdown: str,
        replace: bool = True
    ) -> bool:
        """Update a feature's content by its code.

        Args:
            code: Feature code (e.g., 'CC01')
            content_markdown: New content in markdown format
            replace: If True, replace all content. If False, append.

        Returns:
            True if successful, False otherwise
        """
        feature = self.get_feature(code.upper())
        if not feature or not feature.notion_id:
            logger.error(f"Feature {code} not found")
            return False
        return self.update_page_content(feature.notion_id, content_markdown, replace)

    def update_module_content(
        self,
        code_prefix: str,
        content_markdown: str,
        replace: bool = True
    ) -> bool:
        """Update a module's content by its code prefix.

        Args:
            code_prefix: Module code prefix (e.g., 'CC')
            content_markdown: New content in markdown format
            replace: If True, replace all content. If False, append.

        Returns:
            True if successful, False otherwise
        """
        module = self.get_module_by_prefix(code_prefix.upper())
        if not module or not module.notion_id:
            logger.error(f"Module {code_prefix} not found")
            return False
        return self.update_page_content(module.notion_id, content_markdown, replace)

