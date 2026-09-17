"""SSH Manager service for locating OpenSSH tools and safely executing commands."""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple

from github_ssh_manager.exceptions import SSHNotInstalledError
from github_ssh_manager.models import EnvironmentInfo
from github_ssh_manager.utils import get_default_ssh_dir


class SSHManager:
    """Manages OpenSSH binaries and subprocess execution on Windows."""

    # Well-known Windows OpenSSH installation directory
    WINDOWS_OPENSSH_DIR = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "OpenSSH"

    def __init__(self, ssh_dir: Optional[Path] = None) -> None:
        self.ssh_dir = ssh_dir or get_default_ssh_dir()
        self.ssh_path = self._find_binary("ssh")
        self.ssh_keygen_path = self._find_binary("ssh-keygen")
        self.ssh_add_path = self._find_binary("ssh-add")

    def _find_binary(self, binary_name: str) -> Optional[Path]:
        """Locate an OpenSSH binary in PATH or Windows System32/OpenSSH."""
        # 1. Check in PATH
        found = shutil.which(binary_name)
        if found:
            return Path(found)

        # 2. Check explicitly with .exe
        found_exe = shutil.which(f"{binary_name}.exe")
        if found_exe:
            return Path(found_exe)

        # 3. Check well-known Windows directory
        win_path = self.WINDOWS_OPENSSH_DIR / f"{binary_name}.exe"
        if win_path.exists():
            return win_path

        return None

    def ensure_ssh_available(self) -> None:
        """Verify that essential OpenSSH tools are available."""
        if not self.ssh_path or not self.ssh_keygen_path:
            missing = []
            if not self.ssh_path:
                missing.append("ssh")
            if not self.ssh_keygen_path:
                missing.append("ssh-keygen")
            raise SSHNotInstalledError(
                f"OpenSSH tools not found: {', '.join(missing)}.\n"
                "Please enable or install the Windows OpenSSH Client feature:\n"
                "Settings -> Apps -> Optional features -> OpenSSH Client, "
                "or run in an elevated PowerShell: Add-WindowsCapability -Online -Name OpenSSH.Client~~~~0.0.1.0"
            )

    def get_ssh_version(self) -> Optional[str]:
        """Query and return the OpenSSH version string."""
        if not self.ssh_path:
            return None
        try:
            # ssh -V writes version info to stderr
            result = subprocess.run(
                [str(self.ssh_path), "-V"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5,
                check=False,
                shell=False,
            )
            out = (result.stderr or result.stdout or "").strip()
            return out if out else None
        except Exception:
            return None

    def check_environment(self) -> EnvironmentInfo:
        """Inspect the current environment and return diagnostic info."""
        version_str = self.get_ssh_version()
        agent_running, _ = self.inspect_ssh_agent()

        return EnvironmentInfo(
            python_version=sys.version.split()[0],
            ssh_available=self.ssh_path is not None,
            ssh_keygen_available=self.ssh_keygen_path is not None,
            ssh_add_available=self.ssh_add_path is not None,
            ssh_path=str(self.ssh_path) if self.ssh_path else None,
            ssh_keygen_path=str(self.ssh_keygen_path) if self.ssh_keygen_path else None,
            ssh_add_path=str(self.ssh_add_path) if self.ssh_add_path else None,
            ssh_version=version_str,
            ssh_dir=str(self.ssh_dir),
            ssh_agent_running=agent_running,
        )

    def inspect_ssh_agent(self) -> Tuple[bool, List[str]]:
        """Inspect the Windows ssh-agent service and return loaded keys."""
        if not self.ssh_add_path:
            return False, ["ssh-add not found."]

        try:
            # ssh-add -l lists loaded keys
            result = subprocess.run(
                [str(self.ssh_add_path), "-l"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5,
                check=False,
                shell=False,
            )
            # Exit code 0: keys listed
            # Exit code 1: agent has no identities
            # Exit code 2: cannot connect to agent (service stopped)
            output = (result.stdout or result.stderr or "").strip()
            if result.returncode == 0:
                lines = [line.strip() for line in output.splitlines() if line.strip()]
                return True, lines
            elif result.returncode == 1:
                return True, ["The agent has no identities."]
            else:
                return False, [f"ssh-agent not reachable: {output}"]
        except Exception as exc:
            return False, [f"Error checking ssh-agent: {exc}"]

    def add_key_to_agent(self, private_key_path: Path) -> Tuple[bool, str]:
        """Attempt to add a private key to ssh-agent."""
        if not self.ssh_add_path:
            return False, "ssh-add not found."

        if not private_key_path.exists():
            return False, f"Key file not found: {private_key_path}"

        try:
            result = subprocess.run(
                [str(self.ssh_add_path), str(private_key_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=10,
                check=False,
                shell=False,
            )
            msg = (result.stdout or result.stderr or "").strip()
            return result.returncode == 0, msg
        except Exception as exc:
            return False, f"Failed to add key to agent: {exc}"
