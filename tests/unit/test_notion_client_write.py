# tests/unit/test_notion_client_write.py
"""Tests for NotionClient write operations (markdown to blocks conversion)."""

import pytest
from notion_dev.core.notion_client import NotionClient


class TestMarkdownToBlocks:
    """Test markdown to Notion blocks conversion."""

    @pytest.fixture
    def client(self):
        """Create a NotionClient instance for testing (no API calls)."""
        # Use dummy values - we're only testing local methods
        return NotionClient(
            token="test_token",
            modules_db_id="test_modules_db",
            features_db_id="test_features_db"
        )

    def test_parse_rich_text_plain(self, client):
        """Test plain text parsing."""
        result = client._parse_rich_text("Hello world")
        assert len(result) == 1
        assert result[0]["type"] == "text"
        assert result[0]["text"]["content"] == "Hello world"

    def test_parse_rich_text_bold(self, client):
        """Test bold text parsing."""
        result = client._parse_rich_text("Hello **bold** world")
        assert len(result) == 3
        assert result[0]["text"]["content"] == "Hello "
        assert result[1]["text"]["content"] == "bold"
        assert result[1]["annotations"]["bold"] is True
        assert result[2]["text"]["content"] == " world"

    def test_parse_rich_text_italic(self, client):
        """Test italic text parsing."""
        result = client._parse_rich_text("Hello *italic* world")
        assert len(result) == 3
        assert result[1]["text"]["content"] == "italic"
        assert result[1]["annotations"]["italic"] is True

    def test_parse_rich_text_code(self, client):
        """Test inline code parsing."""
        result = client._parse_rich_text("Use `code` here")
        assert len(result) == 3
        assert result[1]["text"]["content"] == "code"
        assert result[1]["annotations"]["code"] is True

    def test_parse_rich_text_link(self, client):
        """Test link parsing."""
        result = client._parse_rich_text("Visit [Google](https://google.com) today")
        assert len(result) == 3
        assert result[1]["text"]["content"] == "Google"
        assert result[1]["text"]["link"]["url"] == "https://google.com"

    def test_parse_rich_text_mixed(self, client):
        """Test mixed formatting."""
        result = client._parse_rich_text("**Bold** and *italic* and `code`")
        assert len(result) == 5
        assert result[0]["annotations"]["bold"] is True
        assert result[2]["annotations"]["italic"] is True
        assert result[4]["annotations"]["code"] is True

    def test_create_paragraph_block(self, client):
        """Test paragraph block creation."""
        block = client._create_paragraph_block("Test paragraph")
        assert block["type"] == "paragraph"
        assert block["paragraph"]["rich_text"][0]["text"]["content"] == "Test paragraph"

    def test_create_heading_blocks(self, client):
        """Test heading block creation at all levels."""
        h1 = client._create_heading_block("Title", 1)
        h2 = client._create_heading_block("Subtitle", 2)
        h3 = client._create_heading_block("Section", 3)

        assert h1["type"] == "heading_1"
        assert h2["type"] == "heading_2"
        assert h3["type"] == "heading_3"
        assert h1["heading_1"]["rich_text"][0]["text"]["content"] == "Title"

    def test_create_bulleted_list_block(self, client):
        """Test bulleted list item creation."""
        block = client._create_bulleted_list_block("List item")
        assert block["type"] == "bulleted_list_item"
        assert block["bulleted_list_item"]["rich_text"][0]["text"]["content"] == "List item"

    def test_create_numbered_list_block(self, client):
        """Test numbered list item creation."""
        block = client._create_numbered_list_block("Step one")
        assert block["type"] == "numbered_list_item"
        assert block["numbered_list_item"]["rich_text"][0]["text"]["content"] == "Step one"

    def test_create_code_block(self, client):
        """Test code block creation (returns a list for long content support)."""
        blocks = client._create_code_block("print('hello')", "python")
        assert isinstance(blocks, list)
        assert len(blocks) == 1
        block = blocks[0]
        assert block["type"] == "code"
        assert block["code"]["language"] == "python"
        assert block["code"]["rich_text"][0]["text"]["content"] == "print('hello')"

    def test_create_code_block_language_mapping(self, client):
        """Test code block language mapping."""
        blocks_py = client._create_code_block("code", "py")
        blocks_js = client._create_code_block("code", "js")
        blocks_sh = client._create_code_block("code", "sh")

        assert blocks_py[0]["code"]["language"] == "python"
        assert blocks_js[0]["code"]["language"] == "javascript"
        assert blocks_sh[0]["code"]["language"] == "bash"

    def test_create_code_block_splits_long_content(self, client):
        """Test that long code content is split into multiple blocks."""
        # Create code longer than 2000 characters
        long_code = "x = 1\n" * 500  # ~3000 characters
        blocks = client._create_code_block(long_code, "python")
        assert len(blocks) >= 2
        for block in blocks:
            assert block["type"] == "code"
            assert block["code"]["language"] == "python"
            assert len(block["code"]["rich_text"][0]["text"]["content"]) <= 2000

    def test_create_quote_block(self, client):
        """Test quote block creation."""
        block = client._create_quote_block("Famous quote")
        assert block["type"] == "quote"
        assert block["quote"]["rich_text"][0]["text"]["content"] == "Famous quote"

    def test_create_table_block(self, client):
        """Test table block creation."""
        table_lines = [
            "| Header 1 | Header 2 |",
            "| Cell 1 | Cell 2 |",
            "| Cell 3 | Cell 4 |"
        ]
        block = client._create_table_block(table_lines)

        assert block["type"] == "table"
        assert block["table"]["table_width"] == 2
        assert block["table"]["has_column_header"] is True
        assert len(block["table"]["children"]) == 3  # 3 rows

    def test_markdown_to_blocks_headings(self, client):
        """Test converting markdown headings to blocks."""
        markdown = """# Heading 1
## Heading 2
### Heading 3"""

        blocks = client._markdown_to_blocks(markdown)

        assert len(blocks) == 3
        assert blocks[0]["type"] == "heading_1"
        assert blocks[1]["type"] == "heading_2"
        assert blocks[2]["type"] == "heading_3"

    def test_markdown_to_blocks_lists(self, client):
        """Test converting markdown lists to blocks."""
        markdown = """- Item 1
- Item 2
* Item 3
1. First
2. Second"""

        blocks = client._markdown_to_blocks(markdown)

        assert len(blocks) == 5
        assert blocks[0]["type"] == "bulleted_list_item"
        assert blocks[1]["type"] == "bulleted_list_item"
        assert blocks[2]["type"] == "bulleted_list_item"
        assert blocks[3]["type"] == "numbered_list_item"
        assert blocks[4]["type"] == "numbered_list_item"

    def test_markdown_to_blocks_code_block(self, client):
        """Test converting markdown code blocks."""
        markdown = """```python
def hello():
    print("world")
```"""

        blocks = client._markdown_to_blocks(markdown)

        assert len(blocks) == 1
        assert blocks[0]["type"] == "code"
        assert blocks[0]["code"]["language"] == "python"
        assert "def hello():" in blocks[0]["code"]["rich_text"][0]["text"]["content"]

    def test_markdown_to_blocks_divider(self, client):
        """Test converting markdown dividers."""
        markdown = """Some text
---
More text"""

        blocks = client._markdown_to_blocks(markdown)

        assert len(blocks) == 3
        assert blocks[0]["type"] == "paragraph"
        assert blocks[1]["type"] == "divider"
        assert blocks[2]["type"] == "paragraph"

    def test_markdown_to_blocks_quote(self, client):
        """Test converting markdown quotes."""
        markdown = "> This is a quote"

        blocks = client._markdown_to_blocks(markdown)

        assert len(blocks) == 1
        assert blocks[0]["type"] == "quote"

    def test_markdown_to_blocks_mixed(self, client):
        """Test converting mixed markdown content."""
        markdown = """# Module Title

## Description

This is a **bold** statement with *italic* text.

## Features

- Feature 1
- Feature 2

### Code Example

```python
print("hello")
```

> Important note

---

[Link to docs](https://example.com)"""

        blocks = client._markdown_to_blocks(markdown)

        # Should have multiple block types
        types = [b["type"] for b in blocks]
        assert "heading_1" in types
        assert "heading_2" in types
        assert "heading_3" in types
        assert "paragraph" in types
        assert "bulleted_list_item" in types
        assert "code" in types
        assert "quote" in types
        assert "divider" in types

    def test_markdown_to_blocks_empty_lines(self, client):
        """Test that empty lines are skipped."""
        markdown = """Line 1


Line 2"""

        blocks = client._markdown_to_blocks(markdown)

        assert len(blocks) == 2
        assert blocks[0]["paragraph"]["rich_text"][0]["text"]["content"] == "Line 1"
        assert blocks[1]["paragraph"]["rich_text"][0]["text"]["content"] == "Line 2"

    def test_markdown_to_blocks_table(self, client):
        """Test converting markdown tables."""
        markdown = """| Col 1 | Col 2 |
|-------|-------|
| A | B |
| C | D |"""

        blocks = client._markdown_to_blocks(markdown)

        assert len(blocks) == 1
        assert blocks[0]["type"] == "table"
        assert blocks[0]["table"]["table_width"] == 2


class TestModuleFeatureTemplates:
    """Test that module and feature templates convert correctly."""

    @pytest.fixture
    def client(self):
        return NotionClient(
            token="test_token",
            modules_db_id="test_modules_db",
            features_db_id="test_features_db"
        )

    def test_module_template_conversion(self, client):
        """Test converting a module documentation template."""
        module_doc = """# User Authentication Module

## Objective

Handle all user authentication and authorization for the platform.

## Stack Technique

- **Languages**: Python 3.11
- **Frameworks**: FastAPI 0.100
- **Database**: PostgreSQL 15

## Environments

| Environment | URL | Notes |
|-------------|-----|-------|
| Dev | http://localhost:8000 | Local |
| Prod | https://api.example.com | Production |

## CI/CD

### Local Development Commands

```bash
# Start server
uvicorn main:app --reload

# Run tests
pytest tests/
```

## Security & Compliance

- **Authentication**: JWT tokens
- **Authorization**: RBAC

## Useful Links

- [FastAPI Docs](https://fastapi.tiangolo.com)
"""

        blocks = client._markdown_to_blocks(module_doc)

        # Verify structure
        assert len(blocks) > 10  # Should have multiple blocks

        # Check specific elements exist
        types = [b["type"] for b in blocks]
        assert types.count("heading_1") >= 1
        assert types.count("heading_2") >= 5
        assert types.count("heading_3") >= 1
        assert "bulleted_list_item" in types
        assert "table" in types
        assert "code" in types

    def test_feature_template_conversion(self, client):
        """Test converting a feature documentation template."""
        feature_doc = """# User Registration

## Description

Allow new users to create an account on the platform.

## Use Cases

### UC1: Standard Registration
**Actor**: New user
**Flow**:
1. User fills registration form
2. System validates email
3. System creates account

## Business Rules

| ID | Rule | Description |
|----|------|-------------|
| BR1 | Email unique | Each email can only be used once |
| BR2 | Password strength | Minimum 8 characters |

## Endpoints

| Method | Route | Description |
|--------|-------|-------------|
| POST | /api/v1/register | Create new account |

## Required Tests

- [ ] Email validation works
- [ ] Password hashing is correct
"""

        blocks = client._markdown_to_blocks(feature_doc)

        # Verify structure
        assert len(blocks) > 8

        # Check elements
        types = [b["type"] for b in blocks]
        assert "heading_1" in types
        assert "heading_2" in types
        assert "heading_3" in types
        assert "numbered_list_item" in types
        assert "table" in types
