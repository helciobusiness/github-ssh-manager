"""Data models for GitHub SSH Manager."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class Account:
    """Represents a configured GitHub account with an SSH key and host alias."""

    identifier: str
    alias: str
    key_name: str
    email: Optional[str] = None
    hostname: str = "github.com"
    user: str = "git"
    identity_file: str = ""
    identities_only: bool = True
    extra_options: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.alias:
            self.alias = f"github-{self.identifier}"
        if not self.key_name:
            self.key_name = f"github_{self.identifier}"
        if not self.identity_file:
            self.identity_file = f"~/.ssh/{self.key_name}"

    def get_private_key_path(self, ssh_dir: Path) -> Path:
        """Resolve the absolute path to the private key."""
        if self.identity_file.startswith("~/.ssh/"):
            rel_name = self.identity_file[len("~/.ssh/") :]
            return ssh_dir / rel_name
        p = Path(self.identity_file).expanduser()
        if not p.is_absolute():
            return ssh_dir / p
        return p

    def get_public_key_path(self, ssh_dir: Path) -> Path:
        """Resolve the absolute path to the public key."""
        priv = self.get_private_key_path(ssh_dir)
        return priv.with_name(f"{priv.name}.pub")

    def clone_url(self, repo: str) -> str:
        """Generate git clone URL using this account's SSH alias."""
        from github_ssh_manager.utils import parse_github_repo

        full_repo, _ = parse_github_repo(repo)
        return f"git@{self.alias}:{full_repo}.git"


@dataclass
class HostBlock:
    """Represents a discrete block in ~/.ssh/config."""

    host_pattern: Optional[str] = None  # None for top-level comments or global lines
    directives: Dict[str, str] = field(default_factory=dict)
    raw_lines: List[str] = field(default_factory=list)

    @property
    def is_github(self) -> bool:
        """Check if this host block targets github.com."""
        for key, val in self.directives.items():
            if key.lower() == "hostname" and val.lower() == "github.com":
                return True
        return False

    @property
    def identity_file(self) -> Optional[str]:
        """Return IdentityFile directive if present."""
        for key, val in self.directives.items():
            if key.lower() == "identityfile":
                return val
        return None

    def to_account(self) -> Optional[Account]:
        """Convert a GitHub HostBlock to an Account instance."""
        if not self.is_github or not self.host_pattern:
            return None

        alias = self.host_pattern.strip()
        # Extract identifier from alias if format is github-<id>
        if alias.startswith("github-") and len(alias) > 7:
            identifier = alias[7:]
        else:
            identifier = alias

        id_file = self.identity_file or f"~/.ssh/github_{identifier}"
        # Extract key_name from identity_file
        key_name = Path(id_file).name

        identities_only = True
        for k, v in self.directives.items():
            if k.lower() == "identitiesonly":
                identities_only = (v.lower() == "yes")

        user = self.directives.get("user", "git")
        hostname = self.directives.get("hostname", "github.com")

        extra = {
            k: v
            for k, v in self.directives.items()
            if k.lower() not in ("hostname", "user", "identityfile", "identitiesonly")
        }

        return Account(
            identifier=identifier,
            alias=alias,
            key_name=key_name,
            hostname=hostname,
            user=user,
            identity_file=id_file,
            identities_only=identities_only,
            extra_options=extra,
        )


@dataclass
class AuthTestResult:
    """Result of an SSH authentication test against GitHub."""

    alias: str
    success: bool
    github_user: Optional[str] = None
    raw_output: str = ""
    exit_code: int = 0
    error_message: Optional[str] = None


@dataclass
class EnvironmentInfo:
    """System environment diagnostics."""

    python_version: str
    ssh_available: bool
    ssh_keygen_available: bool
    ssh_add_available: bool
    ssh_path: Optional[str] = None
    ssh_keygen_path: Optional[str] = None
    ssh_add_path: Optional[str] = None
    ssh_version: Optional[str] = None
    ssh_dir: str = ""
    ssh_agent_running: bool = False
    details: List[str] = field(default_factory=list)
