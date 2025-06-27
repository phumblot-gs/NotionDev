"""Tests for context builder with .cursorrules support"""
import tempfile
import os
from unittest.mock import MagicMock, patch
from notion_dev.core.context_builder import ContextBuilder
from notion_dev.core.models import Feature, Module, AsanaTask
from notion_dev.core.config import Config, AIConfig


class TestContextBuilder:
    """Test ContextBuilder functionality"""
    
    def test_cursorrules_content_generation(self):
        """Test that .cursorrules content is properly generated"""
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
        
        # Generate .cursorrules content
        content = builder._build_cursorrules_content(context)
        
        # Verify content structure
        assert "# NotionDev Context - TestProject" in content
        assert "## ⚠️ CRITICAL PROJECT CONTEXT" in content
        assert "**Feature**: AU01 - User Authentication" in content
        assert "**Module**: Auth Module" in content
        assert "**Task**: 789 - Implement OAuth" in content
        assert "NOTION FEATURES: AU01" in content
        assert "This feature implements user authentication" in content
    
    def test_cursorrules_export(self):
        """Test exporting to .cursorrules file"""
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
            
            # Export to .cursorrules
            success = builder.export_to_cursorrules(context)
            
            # Verify export
            assert success
            cursorrules_path = os.path.join(tmpdir, ".cursorrules")
            assert os.path.exists(cursorrules_path)
            
            # Read and verify content
            with open(cursorrules_path, 'r') as f:
                content = f.read()
            assert "**Feature**: AU01 - User Authentication" in content
    
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
            
            # Export should clean up .cursor
            builder.export_to_cursorrules(context)
            
            # Verify cleanup
            assert not os.path.exists(cursor_dir)
            assert os.path.exists(os.path.join(tmpdir, ".cursorrules"))