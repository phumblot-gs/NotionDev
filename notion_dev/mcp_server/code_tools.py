"""
NOTION FEATURES: ND03
MODULES: NotionDev
DESCRIPTION: Code reading tools for remote MCP server (Product Owner use case)
LAST_SYNC: 2025-12-31
"""

import os
import re
import json
import fnmatch
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class FileMatch:
    """A file matching a search pattern."""
    path: str
    relative_path: str
    line_number: Optional[int] = None
    line_content: Optional[str] = None
    context_before: List[str] = field(default_factory=list)
    context_after: List[str] = field(default_factory=list)


@dataclass
class CodeContext:
    """Aggregated code context for a feature."""
    feature_code: str
    module_prefix: str
    primary_files: List[Dict[str, Any]] = field(default_factory=list)
    secondary_files: List[Dict[str, Any]] = field(default_factory=list)
    tree_summary: str = ""
    total_lines: int = 0
    suggestions: List[str] = field(default_factory=list)


class CodeReader:
    """Read and search code in cloned repositories.

    Provides functionality for Product Owners to analyze code
    through the remote MCP server.
    """

    # File extensions to include by default
    DEFAULT_EXTENSIONS = {
        ".py", ".js", ".ts", ".tsx", ".jsx",
        ".java", ".go", ".rs", ".rb",
        ".html", ".css", ".scss", ".vue", ".svelte",
        ".json", ".yaml", ".yml", ".toml",
        ".md", ".txt",
        ".sql", ".graphql",
        ".sh", ".bash",
        ".dockerfile", ".docker-compose.yml",
    }

    # Directories to always exclude
    EXCLUDED_DIRS = {
        ".git", ".svn", ".hg",
        "node_modules", "__pycache__", ".pytest_cache",
        "venv", ".venv", "env", ".env",
        "dist", "build", "target", "out",
        ".idea", ".vscode",
        "coverage", ".nyc_output",
        ".next", ".nuxt",
    }

    # Maximum file size to read (500KB)
    MAX_FILE_SIZE = 500 * 1024

    # Maximum lines to return per file
    MAX_LINES_PER_FILE = 500

    def __init__(self, repos_base_dir: str = "/data/repos"):
        """Initialize code reader.

        Args:
            repos_base_dir: Base directory where repos are cloned
        """
        self.repos_base_dir = Path(repos_base_dir)

    def get_repo_path(self, module_prefix: str, repository_url: str = None) -> Optional[Path]:
        """Get the local path for a module's repository.

        Args:
            module_prefix: Module code prefix (e.g., 'CC', 'API')
            repository_url: Optional repository URL to find by GitHubClient naming convention

        Returns:
            Path to repository or None if not cloned
        """
        if not self.repos_base_dir.exists():
            return None

        # If repository_url is provided, use GitHubClient naming convention
        if repository_url:
            from ..core.github_client import GitHubClient
            github = GitHubClient(clone_dir=str(self.repos_base_dir))
            local_path = Path(github._get_repo_local_path(repository_url))
            if local_path.exists():
                return local_path

        # Fallback: try exact match with module prefix
        repo_path = self.repos_base_dir / module_prefix
        if repo_path.exists():
            return repo_path

        # Fallback: try case-insensitive match
        for path in self.repos_base_dir.iterdir():
            if path.is_dir() and path.name.upper() == module_prefix.upper():
                return path

        return None

    def read_file(
        self,
        module_prefix: str,
        file_path: str,
        start_line: int = 1,
        end_line: Optional[int] = None,
        repository_url: str = None,
    ) -> Dict[str, Any]:
        """Read the contents of a file in a cloned repository.

        Args:
            module_prefix: Module code prefix
            file_path: Relative path to file within the repository
            start_line: First line to read (1-indexed)
            end_line: Last line to read (None for all)
            repository_url: Optional repository URL to find by GitHubClient naming convention

        Returns:
            Dict with file content and metadata
        """
        repo_path = self.get_repo_path(module_prefix, repository_url)
        if not repo_path:
            return {
                "error": f"Repository not cloned for module '{module_prefix}'",
                "hint": f"Use notiondev_clone_module('{module_prefix}') first"
            }

        full_path = repo_path / file_path
        if not full_path.exists():
            return {
                "error": f"File not found: {file_path}",
                "repository": str(repo_path)
            }

        if not full_path.is_file():
            return {"error": f"Not a file: {file_path}"}

        # Check file size
        file_size = full_path.stat().st_size
        if file_size > self.MAX_FILE_SIZE:
            return {
                "error": f"File too large ({file_size / 1024:.1f}KB > {self.MAX_FILE_SIZE / 1024}KB)",
                "hint": "Use specific line ranges with start_line and end_line"
            }

        try:
            with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            total_lines = len(lines)

            # Apply line range
            start_idx = max(0, start_line - 1)
            end_idx = end_line if end_line else total_lines

            selected_lines = lines[start_idx:end_idx]

            # Truncate if too many lines
            truncated = False
            if len(selected_lines) > self.MAX_LINES_PER_FILE:
                selected_lines = selected_lines[:self.MAX_LINES_PER_FILE]
                truncated = True

            content = "".join(selected_lines)

            return {
                "success": True,
                "file_path": file_path,
                "full_path": str(full_path),
                "content": content,
                "start_line": start_line,
                "end_line": start_idx + len(selected_lines),
                "total_lines": total_lines,
                "truncated": truncated,
                "encoding": "utf-8",
            }

        except Exception as e:
            logger.error(f"Error reading file {full_path}: {e}")
            return {"error": str(e)}

    def search_code(
        self,
        module_prefix: str,
        pattern: str,
        glob_pattern: str = "**/*",
        max_results: int = 50,
        context_lines: int = 2,
        repository_url: str = None,
    ) -> Dict[str, Any]:
        """Search for a pattern in the code of a module.

        Args:
            module_prefix: Module code prefix
            pattern: Regex pattern to search for
            glob_pattern: File glob pattern to filter files
            max_results: Maximum number of matches to return
            context_lines: Number of context lines before/after match
            repository_url: Optional repository URL to find by GitHubClient naming convention

        Returns:
            Dict with search results
        """
        repo_path = self.get_repo_path(module_prefix, repository_url)
        if not repo_path:
            return {
                "error": f"Repository not cloned for module '{module_prefix}'",
                "hint": f"Use notiondev_clone_module('{module_prefix}') first"
            }

        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error as e:
            return {"error": f"Invalid regex pattern: {e}"}

        matches = []
        files_searched = 0
        files_with_matches = set()

        for file_path in self._iter_files(repo_path, glob_pattern):
            files_searched += 1

            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()

                relative_path = str(file_path.relative_to(repo_path))

                for i, line in enumerate(lines):
                    if regex.search(line):
                        # Get context
                        start = max(0, i - context_lines)
                        end = min(len(lines), i + context_lines + 1)

                        matches.append({
                            "file": relative_path,
                            "line_number": i + 1,
                            "line": line.rstrip(),
                            "context_before": [ln.rstrip() for ln in lines[start:i]],
                            "context_after": [ln.rstrip() for ln in lines[i + 1:end]],
                        })

                        files_with_matches.add(relative_path)

                        if len(matches) >= max_results:
                            break

                if len(matches) >= max_results:
                    break

            except Exception as e:
                logger.debug(f"Error searching {file_path}: {e}")
                continue

        return {
            "success": True,
            "pattern": pattern,
            "glob": glob_pattern,
            "matches": matches,
            "total_matches": len(matches),
            "files_searched": files_searched,
            "files_with_matches": len(files_with_matches),
            "truncated": len(matches) >= max_results,
        }

    def list_files(
        self,
        module_prefix: str,
        glob_pattern: str = "**/*",
        include_size: bool = False,
        max_files: int = 500,
        repository_url: str = None,
    ) -> Dict[str, Any]:
        """List files in a module's repository.

        Args:
            module_prefix: Module code prefix
            glob_pattern: Glob pattern to filter files
            include_size: Include file sizes in results
            max_files: Maximum number of files to return
            repository_url: Optional repository URL to find by GitHubClient naming convention

        Returns:
            Dict with file listing
        """
        repo_path = self.get_repo_path(module_prefix, repository_url)
        if not repo_path:
            return {
                "error": f"Repository not cloned for module '{module_prefix}'",
                "hint": f"Use notiondev_clone_module('{module_prefix}') first"
            }

        files = []
        total_size = 0

        for file_path in self._iter_files(repo_path, glob_pattern):
            relative_path = str(file_path.relative_to(repo_path))

            if include_size:
                size = file_path.stat().st_size
                total_size += size
                files.append({
                    "path": relative_path,
                    "size": size,
                    "size_human": self._format_size(size),
                })
            else:
                files.append({"path": relative_path})

            if len(files) >= max_files:
                break

        return {
            "success": True,
            "module": module_prefix,
            "glob": glob_pattern,
            "files": files,
            "total_files": len(files),
            "total_size": total_size if include_size else None,
            "truncated": len(files) >= max_files,
        }

    def prepare_feature_context(
        self,
        module_prefix: str,
        feature_code: str,
        max_total_lines: int = 2000,
        repository_url: str = None,
    ) -> Dict[str, Any]:
        """Prepare aggregated code context for a feature.

        This tool intelligently gathers relevant code for a feature:
        1. Searches for files containing the feature code
        2. Identifies related imports and dependencies
        3. Creates a summary suitable for AI analysis

        Args:
            module_prefix: Module code prefix
            feature_code: Feature code (e.g., 'CC01')
            max_total_lines: Maximum total lines to include
            repository_url: Optional repository URL to find by GitHubClient naming convention

        Returns:
            Dict with aggregated context
        """
        repo_path = self.get_repo_path(module_prefix, repository_url)
        if not repo_path:
            return {
                "error": f"Repository not cloned for module '{module_prefix}'",
                "hint": f"Use notiondev_clone_module('{module_prefix}') first"
            }

        context = CodeContext(
            feature_code=feature_code,
            module_prefix=module_prefix,
        )

        # Step 1: Find primary files (containing the feature code in header)
        primary_pattern = f"NOTION FEATURES:.*{feature_code}"
        primary_search = self.search_code(
            module_prefix,
            primary_pattern,
            max_results=20,
            context_lines=0,
            repository_url=repository_url,
        )

        primary_files = set()
        if primary_search.get("success"):
            for match in primary_search.get("matches", []):
                primary_files.add(match["file"])

        # Step 2: Search for feature code mentions in code/comments
        code_pattern = f"({feature_code}|{feature_code.lower()})"
        code_search = self.search_code(
            module_prefix,
            code_pattern,
            max_results=50,
            context_lines=0,
            repository_url=repository_url,
        )

        secondary_files = set()
        if code_search.get("success"):
            for match in code_search.get("matches", []):
                file_path = match["file"]
                if file_path not in primary_files:
                    secondary_files.add(file_path)

        # Step 3: Build file tree summary
        context.tree_summary = self._build_tree_summary(repo_path)

        # Step 4: Read primary files (with line limit)
        lines_remaining = max_total_lines
        for file_path in primary_files:
            if lines_remaining <= 0:
                break

            result = self.read_file(module_prefix, file_path, repository_url=repository_url)
            if result.get("success"):
                lines = result["content"].count("\n") + 1
                context.primary_files.append({
                    "path": file_path,
                    "lines": lines,
                    "content": result["content"][:lines_remaining * 80],  # Approximate
                })
                lines_remaining -= lines
                context.total_lines += lines

        # Step 5: Add secondary files (metadata only if no space)
        for file_path in secondary_files:
            if lines_remaining > 100:
                result = self.read_file(module_prefix, file_path, repository_url=repository_url)
                if result.get("success"):
                    lines = min(result["content"].count("\n") + 1, 50)  # Cap per file
                    content_preview = "\n".join(result["content"].split("\n")[:50])
                    context.secondary_files.append({
                        "path": file_path,
                        "lines": result["total_lines"],
                        "preview": content_preview,
                    })
                    lines_remaining -= lines
                    context.total_lines += lines
            else:
                context.secondary_files.append({
                    "path": file_path,
                    "hint": "Use notiondev_read_file to see full content",
                })

        # Step 6: Generate suggestions
        if not primary_files:
            context.suggestions.append(
                f"No files found with NOTION FEATURES header containing {feature_code}. "
                "The feature may not be implemented yet or uses different conventions."
            )

        if secondary_files:
            context.suggestions.append(
                f"Found {len(secondary_files)} files referencing {feature_code}. "
                "Review these for related functionality."
            )

        return {
            "success": True,
            "feature_code": feature_code,
            "module": module_prefix,
            "primary_files": context.primary_files,
            "primary_count": len(context.primary_files),
            "secondary_files": context.secondary_files,
            "secondary_count": len(context.secondary_files),
            "tree_summary": context.tree_summary,
            "total_lines": context.total_lines,
            "suggestions": context.suggestions,
        }

    def _iter_files(self, repo_path: Path, glob_pattern: str):
        """Iterate over files matching a glob pattern.

        Args:
            repo_path: Repository root path
            glob_pattern: Glob pattern

        Yields:
            Path objects for matching files
        """
        for path in repo_path.rglob("*"):
            # Skip directories
            if not path.is_file():
                continue

            # Skip excluded directories
            if any(excl in path.parts for excl in self.EXCLUDED_DIRS):
                continue

            # Skip hidden files
            if path.name.startswith(".") and path.name not in {".env.example", ".gitignore"}:
                continue

            # Apply glob filter
            relative = str(path.relative_to(repo_path))
            if not fnmatch.fnmatch(relative, glob_pattern):
                continue

            # Check extension (if not matching everything)
            if glob_pattern == "**/*":
                if path.suffix.lower() not in self.DEFAULT_EXTENSIONS:
                    continue

            yield path

    def _build_tree_summary(self, repo_path: Path, max_depth: int = 3) -> str:
        """Build a directory tree summary.

        Args:
            repo_path: Repository root
            max_depth: Maximum depth to traverse

        Returns:
            String representation of directory tree
        """
        lines = [f"{repo_path.name}/"]

        def walk(path: Path, prefix: str, depth: int):
            if depth > max_depth:
                return

            items = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))

            # Filter out excluded directories
            items = [
                item for item in items
                if item.name not in self.EXCLUDED_DIRS
                and not item.name.startswith(".")
            ]

            for i, item in enumerate(items[:20]):  # Limit items per level
                is_last = i == len(items) - 1 or i == 19
                connector = "└── " if is_last else "├── "

                if item.is_dir():
                    lines.append(f"{prefix}{connector}{item.name}/")
                    new_prefix = prefix + ("    " if is_last else "│   ")
                    walk(item, new_prefix, depth + 1)
                else:
                    lines.append(f"{prefix}{connector}{item.name}")

            if len(items) > 20:
                lines.append(f"{prefix}    ... and {len(items) - 20} more")

        walk(repo_path, "", 1)
        return "\n".join(lines)

    def _format_size(self, size: int) -> str:
        """Format file size in human-readable form."""
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f}{unit}"
            size /= 1024
        return f"{size:.1f}TB"


# Global code reader instance
_code_reader: Optional[CodeReader] = None


def get_code_reader() -> CodeReader:
    """Get the global code reader instance."""
    global _code_reader
    if _code_reader is None:
        from .config import get_config
        config = get_config()
        _code_reader = CodeReader(repos_base_dir=config.repos_cache_dir)
    return _code_reader
