"""Unit tests for KeyManager."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import tempfile
import unittest
from unittest.mock import MagicMock, patch

from github_ssh_manager.exceptions import (
    KeyAlreadyExistsError,
    KeyNotFoundError,
    SSHKeyGenerationError,
)
from github_ssh_manager.key_manager import KeyManager
from github_ssh_manager.ssh_manager import SSHManager


class TestKeyManager(unittest.TestCase):
    """Test SSH key management, generation, and fingerprints."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.ssh_dir = Path(self.temp_dir.name)

        # Mock SSHManager
        self.mock_ssh_mgr = MagicMock(spec=SSHManager)
        self.mock_ssh_mgr.ssh_keygen_path = Path("C:/Windows/System32/OpenSSH/ssh-keygen.exe")
        self.mock_ssh_mgr.ensure_ssh_available.return_value = None

        self.key_mgr = KeyManager(self.ssh_dir, self.mock_ssh_mgr)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_key_exists(self) -> None:
        priv, pub = self.key_mgr.key_exists("test_key")
        self.assertFalse(priv)
        self.assertFalse(pub)

        # Create dummy files
        (self.ssh_dir / "test_key").write_text("private dummy", encoding="utf-8")
        (self.ssh_dir / "test_key.pub").write_text("public dummy", encoding="utf-8")

        priv, pub = self.key_mgr.key_exists("test_key")
        self.assertTrue(priv)
        self.assertTrue(pub)

    @patch("subprocess.run")
    def test_generate_ed25519_key_success(self, mock_run: MagicMock) -> None:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "Your identification has been saved."
        mock_run.return_value.stderr = ""

        priv_path = self.key_mgr.generate_ed25519_key(
            key_name="github_opgests",
            email="opgests@gmail.com",
            passphrase=None,
        )

        self.assertEqual(priv_path, self.ssh_dir / "github_opgests")
        mock_run.assert_called_once()
        cmd_called = mock_run.call_args[0][0]
        self.assertIn("-t", cmd_called)
        self.assertIn("ed25519", cmd_called)
        self.assertIn("-C", cmd_called)
        self.assertIn("opgests@gmail.com", cmd_called)
        self.assertIn("-N", cmd_called)
        self.assertIn("", cmd_called)

    @patch("subprocess.run")
    def test_generate_key_with_passphrase(self, mock_run: MagicMock) -> None:
        mock_run.return_value.returncode = 0

        self.key_mgr.generate_ed25519_key(
            key_name="github_secure",
            email="secure@example.com",
            passphrase="my-secret-passphrase",
        )

        cmd_called = mock_run.call_args[0][0]
        self.assertIn("-N", cmd_called)
        self.assertIn("my-secret-passphrase", cmd_called)

    def test_generate_key_already_exists(self) -> None:
        (self.ssh_dir / "github_existing").write_text("dummy", encoding="utf-8")

        with self.assertRaises(KeyAlreadyExistsError):
            self.key_mgr.generate_ed25519_key(
                key_name="github_existing",
                email="test@example.com",
                overwrite=False,
            )

    @patch("subprocess.run")
    def test_generate_key_failure(self, mock_run: MagicMock) -> None:
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "ssh-keygen: unknown option"

        with self.assertRaises(SSHKeyGenerationError):
            self.key_mgr.generate_ed25519_key(
                key_name="github_fail",
                email="test@example.com",
            )

    def test_get_public_key(self) -> None:
        pub_content = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI... opgests@gmail.com"
        (self.ssh_dir / "github_opgests.pub").write_text(pub_content, encoding="utf-8")

        result = self.key_mgr.get_public_key("github_opgests")
        self.assertEqual(result, pub_content)

    def test_get_public_key_not_found(self) -> None:
        with self.assertRaises(KeyNotFoundError):
            self.key_mgr.get_public_key("non_existent")

    @patch("subprocess.run")
    def test_get_fingerprint(self, mock_run: MagicMock) -> None:
        (self.ssh_dir / "github_test.pub").write_text("ssh-ed25519 AAAA test@example.com", encoding="utf-8")
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "256 SHA256:zKq1u7XEuUJ6hVBlTklu1+4TjMoBraVlzZ9yaueJZwY test@example.com (ED25519)"

        fp = self.key_mgr.get_fingerprint("github_test")
        self.assertEqual(fp, "SHA256:zKq1u7XEuUJ6hVBlTklu1+4TjMoBraVlzZ9yaueJZwY")

    def test_delete_keys(self) -> None:
        priv = self.ssh_dir / "github_temp"
        pub = self.ssh_dir / "github_temp.pub"
        priv.write_text("priv", encoding="utf-8")
        pub.write_text("pub", encoding="utf-8")

        priv_del, pub_del = self.key_mgr.delete_keys("github_temp", delete_private=True)
        self.assertTrue(priv_del)
        self.assertTrue(pub_del)
        self.assertFalse(priv.exists())
        self.assertFalse(pub.exists())


if __name__ == "__main__":
    unittest.main()
