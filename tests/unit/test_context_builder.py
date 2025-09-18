"""Tests for context builder with AGENTS.md support"""
import tempfile
import os
from unittest.mock import MagicMock, patch
from notion_dev.core.context_builder import ContextBuilder
from notion_dev.core.models import Feature, Module, AsanaTask
from notion_dev.core.config import Config, AIConfig


class TestContextBuilder:
    """Test ContextBuilder functionality"""
    
    def test_agents_content_generation(self):
        """Test that AGENTS.md content is properly generated"""
        # Mock config
        config = MagicMock(spec=Config)
        config.ai = AIConfig(context_max_length=100000)
        config.get_project_info.return_value = {
            'name': 'TestProject',
            'path': '/test/path',
            'cache': '/test/path/.notion-dev',
            'is_git_repo': True
        }
        
        # Mock notion client
        notion_client = MagicMock()
        
        # Create context builder
        builder = ContextBuilder(notion_client, config)
        
        # Create test feature
        feature = Feature(
            notion_id="123",
            code="AU01",
            name="User Authentication",
            status="validated",
            module_name="Auth Module",
            plan=["premium", "enterprise"],
            user_rights=["admin", "user"],
            content="## Overview\n\nThis feature implements user authentication."
        )
        
        # Create test task
        task = AsanaTask(
            gid="789",
            name="Implement OAuth",
            notes="OAuth implementation task",
            assignee_gid="user123",
            completed=False,
            feature_code="AU01"
        )
        
        # Build context
        context = {
            'feature': feature,
            'task': task,
            'project_info': config.get_project_info()
        }
        
        # Generate AGENTS.md content
        content = builder._build_agents_content(context)
        
        # Verify content structure
        assert "# AGENTS.md - TestProject" in content
        assert "## Project Overview" in content
        assert "**Active Feature**: AU01 - User Authentication" in content
        assert "**Active Module**: Auth Module" in content
        assert "**Current Task**: 789 - Implement OAuth" in content
        assert "NOTION FEATURES: AU01" in content
        assert "This feature implements user authentication" in content
    
    def test_agents_export(self):
        """Test exporting to AGENTS.md file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Mock config
            config = MagicMock(spec=Config)
            config.ai = AIConfig(context_max_length=100000)
            config.repository_path = tmpdir
            config.get_project_info.return_value = {
                'name': 'TestProject',
                'path': tmpdir,
                'cache': f"{tmpdir}/.notion-dev",
                'is_git_repo': True
            }
            
            # Mock notion client
            notion_client = MagicMock()
            
            # Create context builder
            builder = ContextBuilder(notion_client, config)
            
            # Create test feature
            feature = Feature(
                notion_id="123",
                code="AU01",
                name="User Authentication",
                status="validated",
                module_name="Auth Module",
                plan=[],
                user_rights=[],
                content="Feature documentation"
            )
            
            context = {
                'feature': feature,
                'project_info': config.get_project_info()
            }
            
            # Export to AGENTS.md
            success = builder.export_to_agents_md(context)

            # Verify export
            assert success
            agents_path = os.path.join(tmpdir, "AGENTS.md")
            assert os.path.exists(agents_path)

            # Read and verify content
            with open(agents_path, 'r') as f:
                content = f.read()
            assert "**Active Feature**: AU01 - User Authentication" in content
    
    def test_content_truncation(self):
        """Test that content is properly truncated when exceeding max length"""
        # Mock config with small max length
        config = MagicMock(spec=Config)
        config.ai = AIConfig(context_max_length=500)  # Very small for testing
        
        # Create builder
        builder = ContextBuilder(MagicMock(), config)
        
        # Create long content
        long_content = "A" * 1000
        
        # Test truncation
        truncated = builder._truncate_content(long_content, 500)
        
        # Verify truncation
        assert len(truncated) <= 500
        assert "[Content truncated to fit context limits]" in truncated
    
    def test_legacy_cursor_cleanup(self):
        """Test that old .cursor directory is cleaned up"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create legacy .cursor directory
            cursor_dir = os.path.join(tmpdir, ".cursor")
            os.makedirs(cursor_dir)
            
            # Create a file in it
            test_file = os.path.join(cursor_dir, "test.md")
            with open(test_file, 'w') as f:
                f.write("test")
            
            # Mock config
            config = MagicMock(spec=Config)
            config.ai = AIConfig(context_max_length=100000)
            config.repository_path = tmpdir
            config.get_project_info.return_value = {
                'name': 'TestProject',
                'path': tmpdir,
                'cache': f"{tmpdir}/.notion-dev",
                'is_git_repo': True
            }
            
            # Create builder and export
            builder = ContextBuilder(MagicMock(), config)
            
            feature = Feature(
                notion_id="123",
                code="AU01",
                name="Test Feature",
                status="validated",
                module_name="Test Module",
                plan=[],
                user_rights=[],
                content="Test content"
            )
            
            context = {
                'feature': feature,
                'project_info': config.get_project_info()
            }
            
            # Export should clean up .cursor and .cursorrules
            builder.export_to_agents_md(context)

            # Verify cleanup
            assert not os.path.exists(cursor_dir)
            assert not os.path.exists(os.path.join(tmpdir, ".cursorrules"))
            assert os.path.exists(os.path.join(tmpdir, "AGENTS.md"))