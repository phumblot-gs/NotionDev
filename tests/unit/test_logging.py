"""Tests for logging configuration with rotation"""
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
from notion_dev.cli.main import setup_logging
from notion_dev.core.config import Config, LoggingConfig


class TestLogging:
    """Test logging configuration with rotation"""
    
    def test_setup_logging_creates_rotating_handler(self):
        """Test that setup_logging creates a rotating file handler"""
        # Create a temporary directory for logs
        with tempfile.TemporaryDirectory() as tmpdir:
            # Mock config with custom log location
            config = MagicMock(spec=Config)
            config.logging = LoggingConfig(level="INFO", file="test.log")
            
            # Mock Path.home() to use our temp directory
            with patch('notion_dev.cli.main.Path.home', return_value=Path(tmpdir)):
                setup_logging(config)
                
                # Check log file was created
                log_dir = Path(tmpdir) / ".notion-dev"
                log_file = log_dir / "test.log"
                assert log_dir.exists()
                
                # Get root logger and check handlers
                import logging
                root_logger = logging.getLogger()
                
                # Should have 2 handlers: RotatingFileHandler and StreamHandler
                assert len(root_logger.handlers) == 2
                
                # Check for RotatingFileHandler
                file_handlers = [h for h in root_logger.handlers 
                               if isinstance(h, logging.handlers.RotatingFileHandler)]
                assert len(file_handlers) == 1
                
                # Verify rotation settings
                handler = file_handlers[0]
                assert handler.maxBytes == 10 * 1024 * 1024  # 10MB
                assert handler.backupCount == 5
    
    def test_logging_rotation_settings(self):
        """Test that log rotation settings are correctly applied"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = MagicMock(spec=Config)
            config.logging = LoggingConfig(level="DEBUG", file="app.log")
            
            with patch('notion_dev.cli.main.Path.home', return_value=Path(tmpdir)):
                setup_logging(config)
                
                import logging
                root_logger = logging.getLogger()
                
                # Check log level
                assert root_logger.level == logging.DEBUG
                
                # Check console handler only shows errors
                stream_handlers = [h for h in root_logger.handlers 
                                 if isinstance(h, logging.StreamHandler) 
                                 and not isinstance(h, logging.FileHandler)]
                assert len(stream_handlers) == 1
                assert stream_handlers[0].level == logging.ERROR