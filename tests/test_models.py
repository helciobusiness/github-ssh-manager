"""Unit tests for models."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import unittest
from github_ssh_manager.models import Account, HostBlock


class TestModels(unittest.TestCase):
    """Test Account and HostBlock models."""

    def test_account_defaults(self) -> None:
        acct = Account(identifier="work", alias="", key_name="")
        self.assertEqual(acct.alias, "github-work")
        self.assertEqual(acct.key_name, "github_work")
        self.assertEqual(acct.identity_file, "~/.ssh/github_work")
        self.assertEqual(acct.hostname, "github.com")
        self.assertEqual(acct.user, "git")
        self.assertTrue(acct.identities_only)

    def test_account_path_resolution(self) -> None:
        ssh_dir = Path("/mock/ssh")
        acct = Account(identifier="personal", alias="github-personal", key_name="github_personal")

        priv = acct.get_private_key_path(ssh_dir)
        pub = acct.get_public_key_path(ssh_dir)

        self.assertEqual(priv, ssh_dir / "github_personal")
        self.assertEqual(pub, ssh_dir / "github_personal.pub")

    def test_clone_url_generation(self) -> None:
        acct = Account(identifier="opgests", alias="github-opgests", key_name="github_opgests")

        # Standard owner/repo
        self.assertEqual(
            acct.clone_url("helcio/project"),
            "git@github-opgests:helcio/project.git",
        )
        # With .git already
        self.assertEqual(
            acct.clone_url("helcio/project.git"),
            "git@github-opgests:helcio/project.git",
        )
        # Pasted https URL
        self.assertEqual(
            acct.clone_url("https://github.com/helcio/project"),
            "git@github-opgests:helcio/project.git",
        )
        # Pasted standard SSH URL
        self.assertEqual(
            acct.clone_url("git@github.com:helcio/project.git"),
            "git@github-opgests:helcio/project.git",
        )
        # Specific user example
        self.assertEqual(
            acct.clone_url("git@github.com:af979031-cloud/kumbify.git"),
            "git@github-opgests:af979031-cloud/kumbify.git",
        )

    def test_host_block_to_account(self) -> None:
        block = HostBlock(
            host_pattern="github-helciobusiness",
            directives={
                "hostname": "github.com",
                "user": "git",
                "identityfile": "~/.ssh/github_helciobusiness",
                "identitiesonly": "yes",
            },
            raw_lines=[
                "Host github-helciobusiness",
                "    HostName github.com",
                "    User git",
                "    IdentityFile ~/.ssh/github_helciobusiness",
                "    IdentitiesOnly yes",
            ],
        )

        self.assertTrue(block.is_github)
        self.assertEqual(block.identity_file, "~/.ssh/github_helciobusiness")

        acct = block.to_account()
        self.assertIsNotNone(acct)
        self.assertEqual(acct.identifier, "helciobusiness")
        self.assertEqual(acct.alias, "github-helciobusiness")
        self.assertEqual(acct.key_name, "github_helciobusiness")
        self.assertTrue(acct.identities_only)

    def test_non_github_host_block(self) -> None:
        block = HostBlock(
            host_pattern="my-vps",
            directives={
                "hostname": "192.168.1.100",
                "user": "root",
            },
        )
        self.assertFalse(block.is_github)
        self.assertIsNone(block.to_account())


if __name__ == "__main__":
    unittest.main()
