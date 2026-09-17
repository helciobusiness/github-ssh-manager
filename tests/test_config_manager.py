"""Unit tests for ConfigManager."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import tempfile
import unittest

from github_ssh_manager.config_manager import ConfigManager
from github_ssh_manager.exceptions import (
    AccountAlreadyExistsError,
    AccountNotFoundError,
)
from github_ssh_manager.models import Account


class TestConfigManager(unittest.TestCase):
    """Test ~/.ssh/config reading, parsing, updating, and preservation."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temp_dir.name) / "config"
        self.mgr = ConfigManager(self.config_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_parse_empty_or_missing_config(self) -> None:
        self.assertEqual(self.mgr.list_accounts(), [])
        self.assertEqual(self.mgr.parse_blocks(), [])

    def test_parse_existing_account(self) -> None:
        content = (
            "Host github-helciobusiness\n"
            "    HostName github.com\n"
            "    User git\n"
            "    IdentityFile ~/.ssh/github_helciobusiness\n"
            "    IdentitiesOnly yes\n"
        )
        self.config_path.write_text(content, encoding="utf-8")

        accounts = self.mgr.list_accounts()
        self.assertEqual(len(accounts), 1)
        acct = accounts[0]
        self.assertEqual(acct.alias, "github-helciobusiness")
        self.assertEqual(acct.identifier, "helciobusiness")
        self.assertEqual(acct.key_name, "github_helciobusiness")
        self.assertEqual(acct.identity_file, "~/.ssh/github_helciobusiness")
        self.assertTrue(acct.identities_only)

    def test_preserve_foreign_hosts_and_comments(self) -> None:
        content = (
            "# Global SSH comments at the top\n"
            "ServerAliveInterval 60\n"
            "\n"
            "Host my-vps\n"
            "    HostName 198.51.100.1\n"
            "    User admin\n"
            "    Port 2222\n"
            "\n"
            "Host github-helciobusiness\n"
            "    HostName github.com\n"
            "    User git\n"
            "    IdentityFile ~/.ssh/github_helciobusiness\n"
            "    IdentitiesOnly yes\n"
        )
        self.config_path.write_text(content, encoding="utf-8")

        # Add second account: opgests
        new_acct = Account(
            identifier="opgests",
            alias="github-opgests",
            key_name="github_opgests",
            email="opgests@gmail.com",
        )
        success, backup = self.mgr.add_account(new_acct)
        self.assertTrue(success)
        self.assertIsNotNone(backup)

        # Re-read file
        new_text = self.config_path.read_text(encoding="utf-8")

        # Verify preamble and foreign host are strictly preserved
        self.assertIn("# Global SSH comments at the top", new_text)
        self.assertIn("ServerAliveInterval 60", new_text)
        self.assertIn("Host my-vps", new_text)
        self.assertIn("Port 2222", new_text)

        # Verify both GitHub accounts exist
        accounts = self.mgr.list_accounts()
        self.assertEqual(len(accounts), 2)
        aliases = [a.alias for a in accounts]
        self.assertIn("github-helciobusiness", aliases)
        self.assertIn("github-opgests", aliases)

    def test_duplicate_account_rejection(self) -> None:
        content = (
            "Host github-opgests\n"
            "    HostName github.com\n"
            "    User git\n"
            "    IdentityFile ~/.ssh/github_opgests\n"
        )
        self.config_path.write_text(content, encoding="utf-8")

        dup_acct = Account(
            identifier="opgests",
            alias="github-opgests",
            key_name="github_opgests",
        )
        with self.assertRaises(AccountAlreadyExistsError):
            self.mgr.add_account(dup_acct)

    def test_dry_run_add_does_not_modify_file(self) -> None:
        initial = (
            "Host github-helciobusiness\n"
            "    HostName github.com\n"
            "    User git\n"
            "    IdentityFile ~/.ssh/github_helciobusiness\n"
        )
        self.config_path.write_text(initial, encoding="utf-8")

        new_acct = Account(
            identifier="opgests",
            alias="github-opgests",
            key_name="github_opgests",
        )
        success, backup = self.mgr.add_account(new_acct, dry_run=True)
        self.assertTrue(success)
        self.assertIsNone(backup)
        # File must remain unchanged
        self.assertEqual(self.config_path.read_text(encoding="utf-8"), initial)

    def test_remove_account(self) -> None:
        content = (
            "Host github-helciobusiness\n"
            "    HostName github.com\n"
            "    User git\n"
            "    IdentityFile ~/.ssh/github_helciobusiness\n"
            "\n"
            "Host github-opgests\n"
            "    HostName github.com\n"
            "    User git\n"
            "    IdentityFile ~/.ssh/github_opgests\n"
        )
        self.config_path.write_text(content, encoding="utf-8")

        # Remove opgests
        success, backup = self.mgr.remove_account("github-opgests")
        self.assertTrue(success)
        self.assertIsNotNone(backup)

        remaining = self.mgr.list_accounts()
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0].alias, "github-helciobusiness")

        # Attempting to remove it again should raise AccountNotFoundError
        with self.assertRaises(AccountNotFoundError):
            self.mgr.remove_account("github-opgests")


if __name__ == "__main__":
    unittest.main()
