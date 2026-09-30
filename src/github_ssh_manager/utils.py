"""Utility functions for validation, paths, clipboard, and console formatting."""

import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from github_ssh_manager.exceptions import InvalidAccountIdentifierError

# Strict validation: letters, numbers, underscores, and hyphens.
# Must start with letter or number; no path traversal characters.
IDENTIFIER_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_identifier(identifier: str) -> str:
    """Validate that the account identifier is safe for filenames and SSH host aliases.

    Prevents path traversal, invalid characters, and control characters.
    """
    cleaned = identifier.strip()
    if not cleaned:
        raise InvalidAccountIdentifierError("Account identifier cannot be empty.")

    # Guard against obvious path traversal patterns
    traversal_triggers = ["..", "/", "\\", ":", "*", "?", '"', "<", ">", "|", "%"]
    if any(trigger in cleaned for trigger in traversal_triggers):
        raise InvalidAccountIdentifierError(
            f"Invalid identifier '{cleaned}': path traversal or forbidden characters detected."
        )

    if not IDENTIFIER_PATTERN.match(cleaned):
        raise InvalidAccountIdentifierError(
            f"Invalid identifier '{cleaned}'. Must contain only alphanumeric characters, "
            "hyphens, and underscores, start with a letter or digit, and be 1-64 characters long."
        )

    return cleaned


def validate_email(email: str) -> str:
    """Validate email address format."""
    cleaned = email.strip()
    if not cleaned:
        raise ValueError("Email address cannot be empty.")
    if not EMAIL_PATTERN.match(cleaned):
        raise ValueError(f"Invalid email address format: '{cleaned}'.")
    return cleaned


def get_default_ssh_dir() -> Path:
    """Return the user's default .ssh directory dynamically without hardcoding."""
    user_profile = os.environ.get("USERPROFILE")
    if user_profile:
        ssh_dir = Path(user_profile) / ".ssh"
    else:
        ssh_dir = Path.home() / ".ssh"
    return ssh_dir


def copy_to_clipboard(text: str) -> bool:
    """Safely copy text to the Windows clipboard using native clip.exe.

    Returns True if successful, False otherwise without raising.
    """
    try:
        clip_exe = shutil.which("clip.exe") or shutil.which("clip")
        if not clip_exe:
            # Try running clip directly
            clip_exe = "clip.exe"

        # clip.exe reads standard input and places it in the Windows clipboard
        process = subprocess.run(
            [clip_exe],
            input=text.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5,
            check=True,
            shell=False,
        )
        return process.returncode == 0
    except Exception:
        return False


def create_backup_file(file_path: Path) -> Optional[Path]:
    """Create a timestamped backup copy of a file before modifying it."""
    if not file_path.exists():
        return None
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = file_path.with_name(f"{file_path.name}.bak.{timestamp}")
    try:
        shutil.copy2(file_path, backup_path)
        return backup_path
    except OSError:
        return None


def parse_github_repo(repo_or_url: str) -> tuple[str, str]:
    """Parse a GitHub repository URL or slug into (full_repo_path, repo_name).

    Supports:
        - git@github.com:af979031-cloud/kumbify.git
        - git@github.com:af979031-cloud/kumbify
        - https://github.com/af979031-cloud/kumbify.git
        - https://github.com/af979031-cloud/kumbify
        - ssh://git@github.com/af979031-cloud/kumbify.git
        - git@github-anyalias:af979031-cloud/kumbify.git
        - af979031-cloud/kumbify

    Returns:
        (full_path, repo_name), e.g. ("af979031-cloud/kumbify", "kumbify")
    """
    cleaned = repo_or_url.strip()
    if not cleaned:
        raise ValueError("Repository URL or name cannot be empty.")

    # Remove protocol / SSH schemes
    if cleaned.startswith("ssh://"):
        cleaned = cleaned[len("ssh://") :]

    # Remove git@...:
    if "@" in cleaned and ":" in cleaned:
        cleaned = cleaned.split(":", 1)[1]
    # Remove http(s)://github.com/ (or any host)
    elif "://" in cleaned:
        # e.g. https://github.com/owner/repo
        cleaned = cleaned.split("://", 1)[1]
        if "/" in cleaned:
            cleaned = cleaned.split("/", 1)[1]

    # Remove leading slash or git@ prefix if still present
    cleaned = cleaned.lstrip("/")

    # Strip query parameters or fragments if any
    cleaned = cleaned.split("?")[0].split("#")[0]

    # Remove trailing slash
    cleaned = cleaned.rstrip("/")

    # Remove .git suffix
    if cleaned.endswith(".git"):
        cleaned = cleaned[:-4]

    # At this point, cleaned should be "owner/repo" or "repo"
    parts = [p for p in cleaned.split("/") if p]
    if len(parts) >= 2:
        owner = parts[-2]
        repo_name = parts[-1]
        full_path = f"{owner}/{repo_name}"
    elif len(parts) == 1:
        repo_name = parts[0]
        full_path = repo_name
    else:
        raise ValueError(f"Unable to extract repository name from '{repo_or_url}'.")

    return full_path, repo_name


def resolve_clone_destination(
    dest_input: Optional[str], default_repo_name: str, base_dir: Optional[Path] = None
) -> Path:
    """Resolve the destination path where the repository will be cloned.

    If dest_input is empty: returns base_dir / default_repo_name.
    If dest_input points to an existing directory: returns dest_dir / default_repo_name.
    Otherwise: returns the specified path directly.
    """
    base = base_dir or Path.cwd()
    if not dest_input or not dest_input.strip():
        return base / default_repo_name

    raw = dest_input.strip()
    expanded = Path(os.path.expandvars(os.path.expanduser(raw)))
    if not expanded.is_absolute():
        expanded = (base / expanded).resolve()

    if expanded.exists() and expanded.is_dir():
        return expanded / default_repo_name

    return expanded


def run_git_clone(
    clone_url: str, destination: Path, dry_run: bool = False
) -> tuple[bool, str]:
    """Execute 'git clone <clone_url> <destination>' safely using subprocess.

    Returns (success, message).
    """
    git_exe = shutil.which("git") or shutil.which("git.exe")
    if not git_exe:
        return False, "Git is not installed or not found in PATH."

    if destination.exists() and any(destination.iterdir()):
        return False, f"Destination folder already exists and is not empty: {destination}"

    if dry_run:
        return True, f"[DRY RUN] Would clone '{clone_url}' into '{destination}'"

    destination.parent.mkdir(parents=True, exist_ok=True)

    cmd = [git_exe, "clone", clone_url, str(destination)]
    try:
        process = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=300,
            check=False,
            shell=False,
        )
        msg = (process.stderr or process.stdout or "").strip()
        return process.returncode == 0, msg
    except subprocess.TimeoutExpired:
        return False, "Git clone timed out after 300 seconds."
    except Exception as exc:
        return False, f"Failed to execute git clone: {exc}"


def configure_repo_identity(
    repo_dir: Path, name: Optional[str] = None, email: Optional[str] = None
) -> tuple[bool, str]:
    """Configure local repository-level Git author name and email."""
    git_exe = shutil.which("git") or shutil.which("git.exe")
    if not git_exe:
        return False, "Git not found."

    messages = []
    success = True
    try:
        if name:
            res_name = subprocess.run(
                [git_exe, "-C", str(repo_dir), "config", "user.name", name],
                capture_output=True,
                text=True,
                check=False,
                shell=False,
            )
            if res_name.returncode != 0:
                success = False
                messages.append(f"Failed to set user.name: {res_name.stderr.strip()}")
            else:
                messages.append(f"user.name set to '{name}'")

        if email:
            res_email = subprocess.run(
                [git_exe, "-C", str(repo_dir), "config", "user.email", email],
                capture_output=True,
                text=True,
                check=False,
                shell=False,
            )
            if res_email.returncode != 0:
                success = False
                messages.append(f"Failed to set user.email: {res_email.stderr.strip()}")
            else:
                messages.append(f"user.email set to '{email}'")

        return success, "; ".join(messages)
    except Exception as exc:
        return False, f"Error configuring Git identity: {exc}"


class Formatter:
    """Format console output messages with standard badges and colors."""

    # ANSI escape codes
    _RESET = "\033[0m"
    _BOLD = "\033[1m"
    _GREEN = "\033[92m"
    _BLUE = "\033[94m"
    _YELLOW = "\033[93m"
    _RED = "\033[91m"
    _CYAN = "\033[96m"

    @classmethod
    def _use_color(cls) -> bool:
        """Determine if color output should be enabled."""
        if not sys.stdout.isatty():
            return False
        # Enable virtual terminal processing on Windows if possible
        if sys.platform == "win32":
            return os.environ.get("TERM") != "dumb"
        return True

    @classmethod
    def ok(cls, msg: str) -> str:
        if cls._use_color():
            return f"{cls._BOLD}{cls._GREEN}[OK]{cls._RESET} {msg}"
        return f"[OK] {msg}"

    @classmethod
    def info(cls, msg: str) -> str:
        if cls._use_color():
            return f"{cls._BOLD}{cls._BLUE}[INFO]{cls._RESET} {msg}"
        return f"[INFO] {msg}"

    @classmethod
    def warning(cls, msg: str) -> str:
        if cls._use_color():
            return f"{cls._BOLD}{cls._YELLOW}[WARNING]{cls._RESET} {msg}"
        return f"[WARNING] {msg}"

    @classmethod
    def error(cls, msg: str) -> str:
        if cls._use_color():
            return f"{cls._BOLD}{cls._RED}[ERROR]{cls._RESET} {msg}"
        return f"[ERROR] {msg}"

    @classmethod
    def action(cls, msg: str) -> str:
        if cls._use_color():
            return f"{cls._BOLD}{cls._CYAN}[ACTION]{cls._RESET} {msg}"
        return f"[ACTION] {msg}"
