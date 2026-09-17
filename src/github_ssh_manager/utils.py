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
