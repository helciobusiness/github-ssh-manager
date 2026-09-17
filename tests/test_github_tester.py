"""Unit tests for GitHubTester."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import subprocess
import unittest
from unittest.mock import MagicMock, patch

from github_ssh_manager.github_tester import GitHubTester
from github_ssh_manager.models import Account
from github_ssh_manager.ssh_manager import SSHManager


class TestGitHubTester(unittest.TestCase):
    """Test SSH authentication testing and username extraction from GitHub responses."""

    def setUp(self) -> None:
        self.mock_ssh_mgr = MagicMock(spec=SSHManager)
        self.mock_ssh_mgr.ssh_path = Path("C:/Windows/System32/OpenSSH/ssh.exe")
        self.mock_ssh_mgr.ensure_ssh_available.return_value = None
        self.tester = GitHubTester(self.mock_ssh_mgr)
        self.account = Account(
            identifier="helciobusiness",
            alias="github-helciobusiness",
            key_name="github_helciobusiness",
        )

    @patch("subprocess.run")
    def test_auth_success_with_exit_code_1(self, mock_run: MagicMock) -> None:
        # GitHub deliberately exits with code 1 while communicating success
        mock_run.return_value.returncode = 1
        mock_run.return_value.stdout = ""
        mock_run.return_value.stderr = (
            "Hi helciobusiness! You've successfully authenticated, but GitHub does not provide shell access.\n"
        )

        res = self.tester.test_account(self.account)
        self.assertTrue(res.success)
        self.assertEqual(res.github_user, "helciobusiness")
        self.assertEqual(res.alias, "github-helciobusiness")
        self.assertEqual(res.exit_code, 1)

    @patch("subprocess.run")
    def test_auth_success_with_different_user(self, mock_run: MagicMock) -> None:
        mock_run.return_value.returncode = 1
        mock_run.return_value.stdout = ""
        mock_run.return_value.stderr = (
            "Hi opgests! You have successfully authenticated, but GitHub does not provide shell access.\n"
        )

        acct = Account(identifier="opgests", alias="github-opgests", key_name="github_opgests")
        res = self.tester.test_account(acct)
        self.assertTrue(res.success)
        self.assertEqual(res.github_user, "opgests")

    @patch("subprocess.run")
    def test_auth_failure_permission_denied(self, mock_run: MagicMock) -> None:
        mock_run.return_value.returncode = 255
        mock_run.return_value.stdout = ""
        mock_run.return_value.stderr = "git@github-opgests: Permission denied (publickey).\n"

        res = self.tester.test_account(self.account)
        self.assertFalse(res.success)
        self.assertIsNone(res.github_user)
        self.assertIn("Permission denied", res.error_message)

    @patch("subprocess.run")
    def test_auth_timeout(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["ssh"], timeout=10)

        res = self.tester.test_account(self.account, timeout=10)
        self.assertFalse(res.success)
        self.assertIn("timed out", res.error_message)

    @patch("subprocess.run")
    def test_test_all_accounts(self, mock_run: MagicMock) -> None:
        mock_run.return_value.returncode = 1
        mock_run.return_value.stdout = ""
        mock_run.return_value.stderr = "Hi helciobusiness! You've successfully authenticated, but GitHub does not provide shell access.\n"

        accts = [
            Account(identifier="helciobusiness", alias="github-helciobusiness", key_name="github_helciobusiness"),
            Account(identifier="opgests", alias="github-opgests", key_name="github_opgests"),
        ]

        results = self.tester.test_all_accounts(accts)
        self.assertEqual(len(results), 2)
        self.assertTrue(results[0].success)
        self.assertTrue(results[1].success)


if __name__ == "__main__":
    unittest.main()
