"""Unit tests for utility functions."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import tempfile
import unittest

from github_ssh_manager.exceptions import InvalidAccountIdentifierError
from github_ssh_manager.utils import (
    Formatter,
    create_backup_file,
    get_default_ssh_dir,
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


if __name__ == "__main__":
    unittest.main()
