"""ConfigManager handles reading, parsing, updating, and writing ~/.ssh/config."""

import re
from pathlib import Path
from typing import List, Optional, Tuple

from github_ssh_manager.exceptions import (
    AccountAlreadyExistsError,
    AccountNotFoundError,
    SSHConfigError,
)
from github_ssh_manager.models import Account, HostBlock
from github_ssh_manager.utils import create_backup_file, get_default_ssh_dir

HOST_LINE_PATTERN = re.compile(r"^\s*Host\s+(.+)$", re.IGNORECASE)
DIRECTIVE_PATTERN = re.compile(r"^\s*([A-Za-z0-9_-]+)\s+(.+)$")


class ConfigManager:
    """Safely manages SSH configuration files preserving comments and foreign hosts."""

    def __init__(self, config_path: Optional[Path] = None) -> None:
        if config_path:
            self.config_path = config_path
            self.ssh_dir = config_path.parent
        else:
            self.ssh_dir = get_default_ssh_dir()
            self.config_path = self.ssh_dir / "config"

    def read_raw_config(self) -> str:
        """Return the raw text of ~/.ssh/config.

        Returns empty string if file does not exist.
        """
        if not self.config_path.exists():
            return ""
        try:
            return self.config_path.read_text(encoding="utf-8")
        except Exception as exc:
            raise SSHConfigError(f"Failed to read SSH config from {self.config_path}: {exc}")

    def parse_blocks(self) -> List[HostBlock]:
        """Parse ~/.ssh/config into discrete HostBlock structures preserving all lines."""
        raw_text = self.read_raw_config()
        if not raw_text.strip():
            return []

        lines = raw_text.splitlines()
        blocks: List[HostBlock] = []
        current_block: Optional[HostBlock] = None

        for line in lines:
            host_match = HOST_LINE_PATTERN.match(line)
            if host_match:
                # Start of a new Host block
                if current_block is not None:
                    blocks.append(current_block)
                pattern = host_match.group(1).strip()
                current_block = HostBlock(host_pattern=pattern, raw_lines=[line])
            else:
                if current_block is None:
                    # Top-level comments, preamble, or global options before any Host line
                    current_block = HostBlock(host_pattern=None, raw_lines=[line])
                else:
                    current_block.raw_lines.append(line)

                # Parse directive if line is not a comment or empty
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    dir_match = DIRECTIVE_PATTERN.match(line)
                    if dir_match:
                        k, v = dir_match.group(1).strip(), dir_match.group(2).strip()
                        current_block.directives[k.lower()] = v

        if current_block is not None:
            blocks.append(current_block)

        return blocks

    def list_accounts(self) -> List[Account]:
        """Discover and return all GitHub accounts configured in ~/.ssh/config."""
        blocks = self.parse_blocks()
        accounts: List[Account] = []
        for block in blocks:
            acct = block.to_account()
            if acct:
                accounts.append(acct)
        return accounts

    def get_account(self, alias_or_identifier: str) -> Optional[Account]:
        """Find an account by alias (e.g. 'github-opgests') or identifier ('opgests')."""
        target_alias = (
            alias_or_identifier
            if alias_or_identifier.startswith("github-")
            else f"github-{alias_or_identifier}"
        )
        for acct in self.list_accounts():
            if acct.alias.lower() == target_alias.lower() or acct.identifier.lower() == alias_or_identifier.lower():
                return acct
        return None

    def account_exists(self, alias: str) -> bool:
        """Check whether an account alias exists in config."""
        for block in self.parse_blocks():
            if block.host_pattern and block.host_pattern.strip().lower() == alias.strip().lower():
                return True
        return False

    def build_account_block(self, account: Account) -> List[str]:
        """Format an Account into standard OpenSSH config lines."""
        lines = [
            f"Host {account.alias}",
            f"    HostName {account.hostname}",
            f"    User {account.user}",
            f"    IdentityFile {account.identity_file}",
            f"    IdentitiesOnly {'yes' if account.identities_only else 'no'}",
        ]
        for k, v in account.extra_options.items():
            lines.append(f"    {k} {v}")
        return lines

    def render_config(self, blocks: List[HostBlock]) -> str:
        """Serialize blocks back into config text preserving original formatting."""
        rendered_lines: List[str] = []
        for i, block in enumerate(blocks):
            if i > 0 and rendered_lines and rendered_lines[-1].strip() != "":
                # Ensure a blank line separates blocks for neat readability
                rendered_lines.append("")
            rendered_lines.extend(block.raw_lines)

        result = "\n".join(rendered_lines)
        if result and not result.endswith("\n"):
            result += "\n"
        return result

    def add_account(self, account: Account, dry_run: bool = False) -> Tuple[bool, Optional[Path]]:
        """Add a new GitHub account block to ~/.ssh/config.

        Returns (success, backup_path_if_created).
        Raises AccountAlreadyExistsError if alias is already present.
        """
        if self.account_exists(account.alias):
            raise AccountAlreadyExistsError(
                f"Account alias '{account.alias}' already exists in {self.config_path}."
            )

        blocks = self.parse_blocks()
        new_block = HostBlock(
            host_pattern=account.alias,
            directives={
                "hostname": account.hostname,
                "user": account.user,
                "identityfile": account.identity_file,
                "identitiesonly": "yes" if account.identities_only else "no",
                **{k.lower(): v for k, v in account.extra_options.items()},
            },
            raw_lines=self.build_account_block(account),
        )
        blocks.append(new_block)
        new_content = self.render_config(blocks)

        if dry_run:
            return True, None

        self.ssh_dir.mkdir(parents=True, exist_ok=True)
        backup = create_backup_file(self.config_path)

        try:
            self.config_path.write_text(new_content, encoding="utf-8")
            return True, backup
        except Exception as exc:
            raise SSHConfigError(f"Failed to write SSH config: {exc}")

    def remove_account(self, alias: str, dry_run: bool = False) -> Tuple[bool, Optional[Path]]:
        """Remove a specific GitHub account block by alias.

        Returns (success, backup_path_if_created).
        Raises AccountNotFoundError if alias does not exist.
        """
        blocks = self.parse_blocks()
        target_idx = None

        for idx, block in enumerate(blocks):
            if block.host_pattern and block.host_pattern.strip().lower() == alias.strip().lower():
                target_idx = idx
                break

        if target_idx is None:
            raise AccountNotFoundError(f"Account alias '{alias}' not found in {self.config_path}.")

        # Remove only the target block
        blocks.pop(target_idx)
        new_content = self.render_config(blocks)

        if dry_run:
            return True, None

        backup = create_backup_file(self.config_path)
        try:
            self.config_path.write_text(new_content, encoding="utf-8")
            return True, backup
        except Exception as exc:
            raise SSHConfigError(f"Failed to write SSH config during removal: {exc}")
