# notion_dev/core/github_client.py
"""GitHub client for repository clone operations."""
import os
import subprocess
import shutil
import logging
from typing import Optional, Dict, Any
from pathlib import Path
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class GitHubClient:
    """Client for GitHub repository operations."""

    def __init__(
        self,
        token: Optional[str] = None,
        clone_dir: str = "/tmp/notiondev",
        shallow_clone: bool = True
    ):
        """Initialize GitHub client.

        Args:
            token: GitHub personal access token (optional, for private repos)
            clone_dir: Base directory for cloned repositories
            shallow_clone: If True, use --depth 1 for faster cloning
        """
        self.token = token
        self.clone_dir = clone_dir
        self.shallow_clone = shallow_clone

        # Ensure clone directory exists
        Path(clone_dir).mkdir(parents=True, exist_ok=True)

    def _get_authenticated_url(self, repo_url: str) -> str:
        """Convert repository URL to authenticated URL if token is available.

        Args:
            repo_url: Original repository URL (https://github.com/owner/repo or git@github.com:owner/repo)

        Returns:
            URL with embedded token for authentication (if token available)
        """
        if not self.token:
            return repo_url

        # Handle SSH URLs
        if repo_url.startswith("git@github.com:"):
            # Convert SSH to HTTPS
            path = repo_url.replace("git@github.com:", "")
            if path.endswith(".git"):
                path = path[:-4]
            return f"https://{self.token}@github.com/{path}.git"

        # Handle HTTPS URLs
        if "github.com" in repo_url:
            parsed = urlparse(repo_url)
            # Insert token as username
            if parsed.scheme == "https":
                path = parsed.path
                if not path.endswith(".git"):
                    path = f"{path}.git"
                return f"https://{self.token}@github.com{path}"

        return repo_url

    def _get_repo_local_path(self, repo_url: str) -> str:
        """Get the local path where a repository will be cloned.

        Args:
            repo_url: Repository URL

        Returns:
            Local filesystem path for the cloned repository
        """
        # Extract repo name from URL
        if repo_url.endswith(".git"):
            repo_url = repo_url[:-4]

        parts = repo_url.rstrip("/").split("/")
        if len(parts) >= 2:
            owner = parts[-2]
            repo = parts[-1]
            return os.path.join(self.clone_dir, f"{owner}_{repo}")

        # Fallback: use URL hash
        import hashlib
        url_hash = hashlib.md5(repo_url.encode()).hexdigest()[:8]
        return os.path.join(self.clone_dir, f"repo_{url_hash}")

    def clone_repository(
        self,
        repo_url: str,
        branch: Optional[str] = None,
        force: bool = False
    ) -> Dict[str, Any]:
        """Clone a repository to local filesystem.

        Args:
            repo_url: GitHub repository URL
            branch: Branch to checkout (optional, defaults to default branch)
            force: If True, remove existing clone and re-clone

        Returns:
            Dict with 'success', 'path', 'error' keys
        """
        local_path = self._get_repo_local_path(repo_url)
        result = {
            "success": False,
            "path": local_path,
            "error": None,
            "repo_url": repo_url,
            "branch": branch
        }

        # Check if already cloned
        if os.path.exists(local_path):
            if force:
                logger.info(f"Removing existing clone at {local_path}")
                try:
                    shutil.rmtree(local_path)
                except Exception as e:
                    result["error"] = f"Failed to remove existing clone: {e}"
                    return result
            else:
                # Repository already exists, try to update it
                return self.update_repository(local_path, branch)

        # Build clone command
        auth_url = self._get_authenticated_url(repo_url)
        cmd = ["git", "clone"]

        if self.shallow_clone:
            cmd.extend(["--depth", "1"])

        if branch:
            cmd.extend(["--branch", branch])

        cmd.extend([auth_url, local_path])

        try:
            logger.info(f"Cloning {repo_url} to {local_path}")
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            if process.returncode != 0:
                error_msg = process.stderr or process.stdout
                # Remove token from error message
                if self.token:
                    error_msg = error_msg.replace(self.token, "***")
                result["error"] = f"Git clone failed: {error_msg}"
                logger.error(result["error"])
                return result

            result["success"] = True
            logger.info(f"Successfully cloned {repo_url}")

        except subprocess.TimeoutExpired:
            result["error"] = "Clone operation timed out (5 minutes)"
            logger.error(result["error"])
        except Exception as e:
            result["error"] = f"Clone error: {e}"
            logger.error(result["error"])

        return result

    def update_repository(
        self,
        local_path: str,
        branch: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update an existing cloned repository.

        Args:
            local_path: Path to the cloned repository
            branch: Branch to checkout (optional)

        Returns:
            Dict with 'success', 'path', 'error' keys
        """
        result = {
            "success": False,
            "path": local_path,
            "error": None,
            "updated": False
        }

        if not os.path.exists(local_path):
            result["error"] = f"Repository not found at {local_path}"
            return result

        try:
            # Checkout branch if specified
            if branch:
                logger.info(f"Checking out branch {branch}")
                process = subprocess.run(
                    ["git", "checkout", branch],
                    cwd=local_path,
                    capture_output=True,
                    text=True
                )
                if process.returncode != 0:
                    # Branch might not exist locally, try fetching
                    process = subprocess.run(
                        ["git", "fetch", "origin", branch],
                        cwd=local_path,
                        capture_output=True,
                        text=True
                    )
                    if process.returncode == 0:
                        subprocess.run(
                            ["git", "checkout", branch],
                            cwd=local_path,
                            capture_output=True,
                            text=True
                        )

            # Pull latest changes
            logger.info(f"Pulling latest changes for {local_path}")
            process = subprocess.run(
                ["git", "pull", "--ff-only"],
                cwd=local_path,
                capture_output=True,
                text=True,
                timeout=120
            )

            if process.returncode != 0:
                # Pull failed, might be shallow clone - try fetch
                logger.warning("Pull failed, repository might be shallow")
                result["updated"] = False
            else:
                result["updated"] = True

            result["success"] = True

        except subprocess.TimeoutExpired:
            result["error"] = "Update operation timed out"
        except Exception as e:
            result["error"] = f"Update error: {e}"

        return result

    def get_repository_info(self, local_path: str) -> Dict[str, Any]:
        """Get information about a cloned repository.

        Args:
            local_path: Path to the cloned repository

        Returns:
            Dict with repository information
        """
        result = {
            "path": local_path,
            "exists": os.path.exists(local_path),
            "branch": None,
            "remote_url": None,
            "last_commit": None
        }

        if not result["exists"]:
            return result

        try:
            # Get current branch
            process = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=local_path,
                capture_output=True,
                text=True
            )
            if process.returncode == 0:
                result["branch"] = process.stdout.strip()

            # Get remote URL
            process = subprocess.run(
                ["git", "config", "--get", "remote.origin.url"],
                cwd=local_path,
                capture_output=True,
                text=True
            )
            if process.returncode == 0:
                url = process.stdout.strip()
                # Remove token from URL
                if self.token and self.token in url:
                    url = url.replace(f"{self.token}@", "")
                result["remote_url"] = url

            # Get last commit
            process = subprocess.run(
                ["git", "log", "-1", "--format=%H %s"],
                cwd=local_path,
                capture_output=True,
                text=True
            )
            if process.returncode == 0:
                result["last_commit"] = process.stdout.strip()

        except Exception as e:
            logger.warning(f"Error getting repository info: {e}")

        return result

    def cleanup_repository(self, local_path: str) -> bool:
        """Remove a cloned repository.

        Args:
            local_path: Path to the cloned repository

        Returns:
            True if successfully removed, False otherwise
        """
        try:
            if os.path.exists(local_path):
                shutil.rmtree(local_path)
                logger.info(f"Removed repository at {local_path}")
                return True
            return True
        except Exception as e:
            logger.error(f"Failed to remove repository at {local_path}: {e}")
            return False

    def cleanup_all(self) -> int:
        """Remove all cloned repositories.

        Returns:
            Number of repositories removed
        """
        count = 0
        if os.path.exists(self.clone_dir):
            for item in os.listdir(self.clone_dir):
                item_path = os.path.join(self.clone_dir, item)
                if os.path.isdir(item_path):
                    if self.cleanup_repository(item_path):
                        count += 1
        return count

    def test_connection(self) -> Dict[str, Any]:
        """Test GitHub connection and token validity.

        Returns:
            Dict with 'success', 'user', 'errors' keys
        """
        import requests

        result = {
            "success": False,
            "user": None,
            "configured": self.token is not None,
            "errors": []
        }

        if not self.token:
            result["success"] = True
            result["user"] = "anonymous (no token configured)"
            return result

        try:
            response = requests.get(
                "https://api.github.com/user",
                headers={"Authorization": f"token {self.token}"},
                timeout=10
            )

            if response.status_code == 200:
                result["success"] = True
                result["user"] = response.json().get("login", "Unknown")
            elif response.status_code == 401:
                result["errors"].append("Invalid GitHub token (401 Unauthorized)")
            else:
                result["errors"].append(f"GitHub API error: HTTP {response.status_code}")

        except Exception as e:
            result["errors"].append(f"Connection error: {e}")

        return result
