"""Unit tests for CLI subcommands and parser."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import tempfile
import unittest

from github_ssh_manager.cli import GitHubSSHManagerCLI, build_parser, main
from github_ssh_manager.models import Account


class TestCLI(unittest.TestCase):
    """Test argument parsing and CLI command dispatch in isolated temporary directory."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.ssh_dir = Path(self.temp_dir.name)
        self.config_file = self.ssh_dir / "config"
        self.config_file.write_text(
            "Host github-testuser\n"
            "    HostName github.com\n"
            "    User git\n"
            "    IdentityFile ~/.ssh/github_testuser\n"
            "    IdentitiesOnly yes\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_parser_subcommands(self) -> None:
        parser = build_parser()

        args = parser.parse_args(["list"])
        self.assertEqual(args.subcommand, "list")

        args = parser.parse_args(["add", "--email", "test@example.com", "--identifier", "test"])
        self.assertEqual(args.subcommand, "add")
        self.assertEqual(args.email, "test@example.com")
        self.assertEqual(args.identifier, "test")

        args = parser.parse_args(["test", "github-testuser"])
        self.assertEqual(args.subcommand, "test")
        self.assertEqual(args.account, "github-testuser")

        args = parser.parse_args(["clone-url", "github-testuser", "user/repo"])
        self.assertEqual(args.subcommand, "clone-url")
        self.assertEqual(args.account, "github-testuser")
        self.assertEqual(args.repo, "user/repo")

        args = parser.parse_args([
            "clone",
            "git@github.com:af979031-cloud/kumbify.git",
            "--account",
            "github-testuser",
            "--dest",
            "./target",
        ])
        self.assertEqual(args.subcommand, "clone")
        self.assertEqual(args.repo, "git@github.com:af979031-cloud/kumbify.git")
        self.assertEqual(args.account, "github-testuser")
        self.assertEqual(args.dest, "./target")

        args = parser.parse_args(["--dry-run", "remove", "github-testuser", "--yes"])
        self.assertTrue(args.dry_run)
        self.assertEqual(args.subcommand, "remove")
        self.assertTrue(args.yes)

    def test_cli_list_command(self) -> None:
        cli = GitHubSSHManagerCLI(ssh_dir=self.ssh_dir)
        accounts = cli.config_mgr.list_accounts()
        self.assertEqual(len(accounts), 1)
        self.assertEqual(accounts[0].alias, "github-testuser")

    def test_cli_dry_run_clone(self) -> None:
        cli = GitHubSSHManagerCLI(ssh_dir=self.ssh_dir, dry_run=True)
        ok = cli.clone_repository(
            account_or_id="github-testuser",
            repo_input="git@github.com:af979031-cloud/kumbify.git",
            dest_input=str(self.ssh_dir / "kumbify"),
        )
        self.assertTrue(ok)

    def test_cli_dry_run_remove(self) -> None:
        cli = GitHubSSHManagerCLI(ssh_dir=self.ssh_dir, dry_run=True)
        cli.remove_account("github-testuser", confirm=True)
        # Verify file is still untouched due to dry_run
        accounts = cli.config_mgr.list_accounts()
        self.assertEqual(len(accounts), 1)


if __name__ == "__main__":
    unittest.main()
