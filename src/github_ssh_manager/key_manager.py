"""KeyManager handles SSH key generation, fingerprinting, and public key inspection."""

import re
import subprocess
from pathlib import Path
from typing import Optional, Tuple

from github_ssh_manager.exceptions import (
    KeyAlreadyExistsError,
    KeyNotFoundError,
    SSHKeyGenerationError,
)
from github_ssh_manager.ssh_manager import SSHManager
from github_ssh_manager.utils import get_default_ssh_dir

FINGERPRINT_PATTERN = re.compile(r"(SHA256:[A-Za-z0-9+/=]+)")


class KeyManager:
    """Manages SSH key generation, public key reading, and fingerprints."""

    def __init__(
        self, ssh_dir: Optional[Path] = None, ssh_manager: Optional[SSHManager] = None
    ) -> None:
        self.ssh_dir = ssh_dir or get_default_ssh_dir()
        self.ssh_manager = ssh_manager or SSHManager(self.ssh_dir)

    def key_exists(self, key_name: str) -> Tuple[bool, bool]:
        """Check if private and public key files exist for a given key name.

        Returns (has_private, has_public).
        """
        priv = self.ssh_dir / key_name
        pub = self.ssh_dir / f"{key_name}.pub"
        return priv.exists(), pub.exists()

    def generate_ed25519_key(
        self,
        key_name: str,
        email: str,
        passphrase: Optional[str] = None,
        overwrite: bool = False,
    ) -> Path:
        """Generate a new ED25519 key pair using ssh-keygen.

        Args:
            key_name: Basename of the key (e.g. 'github_opgests')
            email: Comment string (typically account email)
            passphrase: Optional passphrase. If None or empty, key has no passphrase.
            overwrite: If False, raises KeyAlreadyExistsError if key file exists.

        Returns:
            Path to the generated private key.
        """
        self.ssh_manager.ensure_ssh_available()

        # Ensure .ssh directory exists
        self.ssh_dir.mkdir(parents=True, exist_ok=True)

        priv_path = self.ssh_dir / key_name
        pub_path = self.ssh_dir / f"{key_name}.pub"

        if not overwrite and (priv_path.exists() or pub_path.exists()):
            raise KeyAlreadyExistsError(
                f"SSH key files already exist for '{key_name}':\n"
                f"  Private: {priv_path} (exists={priv_path.exists()})\n"
                f"  Public:  {pub_path} (exists={pub_path.exists()})"
            )

        cmd = [
            str(self.ssh_manager.ssh_keygen_path),
            "-t",
            "ed25519",
            "-C",
            email,
            "-f",
            str(priv_path),
        ]

        if passphrase:
            cmd.extend(["-N", passphrase])
        else:
            cmd.extend(["-N", ""])

        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=15,
                check=False,
                shell=False,
            )

            if result.returncode != 0:
                err_msg = (result.stderr or result.stdout or "").strip()
                raise SSHKeyGenerationError(
                    f"ssh-keygen failed (code {result.returncode}): {err_msg}"
                )

            return priv_path
        except subprocess.TimeoutExpired:
            raise SSHKeyGenerationError("ssh-keygen timed out.")
        except Exception as exc:
            if isinstance(exc, (KeyAlreadyExistsError, SSHKeyGenerationError)):
                raise
            raise SSHKeyGenerationError(f"Unexpected error generating key: {exc}")

    def get_public_key(self, key_name: str) -> str:
        """Read and return the public key contents.

        Never reads or returns the private key.
        """
        pub_path = self.ssh_dir / f"{key_name}.pub"
        if not pub_path.exists():
            raise KeyNotFoundError(f"Public key file not found: {pub_path}")

        return pub_path.read_text(encoding="utf-8").strip()

    def get_fingerprint(self, key_name: str) -> Optional[str]:
        """Compute the SHA256 fingerprint of the public key using ssh-keygen.

        Returns formatted fingerprint string (e.g. 'SHA256:zKq1u7...').
        """
        pub_path = self.ssh_dir / f"{key_name}.pub"
        if not pub_path.exists():
            return None

        if not self.ssh_manager.ssh_keygen_path:
            return None

        try:
            cmd = [
                str(self.ssh_manager.ssh_keygen_path),
                "-lf",
                str(pub_path),
                "-E",
                "sha256",
            ]
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5,
                check=False,
                shell=False,
            )
            out = (result.stdout or "").strip()
            match = FINGERPRINT_PATTERN.search(out)
            if match:
                return match.group(1)
            # Fallback to full output if regex did not match pattern
            return out if out else None
        except Exception:
            return None

    def delete_keys(self, key_name: str, delete_private: bool = True) -> Tuple[bool, bool]:
        """Delete key files.

        Returns (private_deleted, public_deleted).
        """
        priv_path = self.ssh_dir / key_name
        pub_path = self.ssh_dir / f"{key_name}.pub"

        priv_deleted = False
        pub_deleted = False

        if delete_private and priv_path.exists():
            priv_path.unlink()
            priv_deleted = True

        if pub_path.exists():
            pub_path.unlink()
            pub_deleted = True

        return priv_deleted, pub_deleted
