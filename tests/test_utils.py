"""Unit tests for utility functions."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import tempfile
import unittest

from unittest.mock import MagicMock, patch

from github_ssh_manager.exceptions import InvalidAccountIdentifierError
from github_ssh_manager.utils import (
    Formatter,
    configure_repo_identity,
    create_backup_file,
    get_default_ssh_dir,
    parse_github_repo,
    resolve_clone_destination,
    run_git_clone,
    validate_email,
    validate_identifier,
)


class TestUtils(unittest.TestCase):
    """Test validation, path, and file helpers."""

    def test_valid_identifiers(self) -> None:
        valid_cases = [
            "opgests",
            "helciobusiness",
            "user_name",
            "account-2",
            "dev-test_01",
            "A1",
        ]
        for case in valid_cases:
            self.assertEqual(validate_identifier(case), case)

    def test_invalid_identifiers_path_traversal(self) -> None:
        traversal_cases = [
            "../something",
            "..\\something",
            "../../etc/passwd",
            "C:\\Users\\admin",
            "/root/ssh",
            "test/path",
            "test\\path",
            "foo:bar",
            "evil*name",
            "hello|world",
        ]
        for case in traversal_cases:
            with self.assertRaises(InvalidAccountIdentifierError):
                validate_identifier(case)

    def test_invalid_identifiers_characters(self) -> None:
        bad_cases = [
            "",
            "   ",
            "-leading-hyphen",
            "_leading_underscore",
            "name with spaces",
            "name@domain",
            "name#hash",
            "a" * 65,  # Too long
        ]
        for case in bad_cases:
            with self.assertRaises(InvalidAccountIdentifierError):
                validate_identifier(case)

    def test_email_validation(self) -> None:
        self.assertEqual(validate_email("opgests@gmail.com"), "opgests@gmail.com")
        self.assertEqual(validate_email("user.name+tag@sub.example.com"), "user.name+tag@sub.example.com")

        invalid_emails = [
            "",
            "not-an-email",
            "@domain.com",
            "user@domain",
            "user @domain.com",
        ]
        for email in invalid_emails:
            with self.assertRaises(ValueError):
                validate_email(email)

    def test_get_default_ssh_dir(self) -> None:
        ssh_dir = get_default_ssh_dir()
        self.assertIsInstance(ssh_dir, Path)
        self.assertEqual(ssh_dir.name, ".ssh")

    def test_formatter_badges(self) -> None:
        self.assertIn("[OK]", Formatter.ok("Success"))
        self.assertIn("[INFO]", Formatter.info("Notice"))
        self.assertIn("[WARNING]", Formatter.warning("Caution"))
        self.assertIn("[ERROR]", Formatter.error("Failure"))
        self.assertIn("[ACTION]", Formatter.action("Do this"))

    def test_backup_creation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            orig = Path(tmp_dir) / "config"
            orig.write_text("Host test\n    HostName test.com\n", encoding="utf-8")

            backup = create_backup_file(orig)
            self.assertIsNotNone(backup)
            self.assertTrue(backup.exists())
            self.assertIn("config.bak.", backup.name)
            self.assertEqual(backup.read_text(encoding="utf-8"), orig.read_text(encoding="utf-8"))

    def test_parse_github_repo(self) -> None:
        test_cases = [
            ("git@github.com:af979031-cloud/kumbify.git", ("af979031-cloud/kumbify", "kumbify")),
            ("git@github.com:af979031-cloud/kumbify", ("af979031-cloud/kumbify", "kumbify")),
            ("https://github.com/af979031-cloud/kumbify.git", ("af979031-cloud/kumbify", "kumbify")),
            ("https://github.com/af979031-cloud/kumbify", ("af979031-cloud/kumbify", "kumbify")),
            ("ssh://git@github.com/af979031-cloud/kumbify.git", ("af979031-cloud/kumbify", "kumbify")),
            ("git@github-helciobusiness:af979031-cloud/kumbify.git", ("af979031-cloud/kumbify", "kumbify")),
            ("af979031-cloud/kumbify", ("af979031-cloud/kumbify", "kumbify")),
        ]
        for url, expected in test_cases:
            self.assertEqual(parse_github_repo(url), expected)

        with self.assertRaises(ValueError):
            parse_github_repo("")

    def test_resolve_clone_destination(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base = Path(tmp_dir)
            # 1. Empty input defaults to base / repo_name
            self.assertEqual(
                resolve_clone_destination("", "kumbify", base_dir=base),
                base / "kumbify",
            )
            # 2. Existing folder appends repo_name
            existing_sub = base / "projects"
            existing_sub.mkdir()
            self.assertEqual(
                resolve_clone_destination(str(existing_sub), "kumbify", base_dir=base),
                existing_sub / "kumbify",
            )
            # 3. Explicit target path is preserved
            explicit_target = base / "custom_folder"
            self.assertEqual(
                resolve_clone_destination(str(explicit_target), "kumbify", base_dir=base),
                explicit_target,
            )

    def test_run_git_clone_dry_run(self) -> None:
        dest = Path("/mock/dest")
        ok, msg = run_git_clone("git@github-test:user/repo.git", dest, dry_run=True)
        self.assertTrue(ok)
        self.assertIn("[DRY RUN]", msg)

    @patch("subprocess.run")
    def test_run_git_clone_success(self, mock_run: MagicMock) -> None:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = ""
        mock_run.return_value.stderr = "Cloning into 'kumbify'..."

        with tempfile.TemporaryDirectory() as tmp_dir:
            dest = Path(tmp_dir) / "kumbify"
            ok, msg = run_git_clone("git@github-helciobusiness:af979031-cloud/kumbify.git", dest)
            self.assertTrue(ok)
            self.assertIn("Cloning into", msg)

    @patch("subprocess.run")
    def test_configure_repo_identity(self, mock_run: MagicMock) -> None:
        mock_run.return_value.returncode = 0
        repo_dir = Path("/mock/repo")
        ok, msg = configure_repo_identity(repo_dir, name="Helcio", email="helcio@example.com")
        self.assertTrue(ok)
        self.assertEqual(mock_run.call_count, 2)


if __name__ == "__main__":
    unittest.main()
