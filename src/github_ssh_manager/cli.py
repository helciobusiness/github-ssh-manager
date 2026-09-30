"""Command Line Interface (CLI) and interactive menu for GitHub SSH Manager."""

import argparse
import getpass
import sys
from pathlib import Path
from typing import List, Optional

from github_ssh_manager import __version__
from github_ssh_manager.config_manager import ConfigManager
from github_ssh_manager.exceptions import (
    AccountAlreadyExistsError,
    AccountNotFoundError,
    InvalidAccountIdentifierError,
    KeyAlreadyExistsError,
    KeyNotFoundError,
    SSHManagerError,
    SSHNotInstalledError,
)
from github_ssh_manager.github_tester import GitHubTester
from github_ssh_manager.key_manager import KeyManager
from github_ssh_manager.models import Account, EnvironmentInfo
from github_ssh_manager.ssh_manager import SSHManager
from github_ssh_manager.utils import (
    Formatter,
    configure_repo_identity,
    copy_to_clipboard,
    get_default_ssh_dir,
    parse_github_repo,
    resolve_clone_destination,
    run_git_clone,
    validate_email,
    validate_identifier,
)


class GitHubSSHManagerCLI:
    """Orchestrates CLI commands and interactive console menu."""

    def __init__(
        self,
        ssh_dir: Optional[Path] = None,
        dry_run: bool = False,
        verbose: bool = False,
    ) -> None:
        self.ssh_dir = ssh_dir or get_default_ssh_dir()
        self.dry_run = dry_run
        self.verbose = verbose

        self.ssh_mgr = SSHManager(self.ssh_dir)
        self.config_mgr = ConfigManager(self.ssh_dir / "config")
        self.key_mgr = KeyManager(self.ssh_dir, self.ssh_mgr)
        self.tester = GitHubTester(self.ssh_mgr)

    # -------------------------------------------------------------------------
    # Diagnostic / Environment Header
    # -------------------------------------------------------------------------

    def print_banner(self) -> None:
        print("=" * 60)
        print(f"GitHub SSH Manager v{__version__} (Windows)")
        print("=" * 60)

    def print_environment_check(self, show_accounts: bool = True) -> EnvironmentInfo:
        """Inspect and print system status."""
        env = self.ssh_mgr.check_environment()
        print("\nChecking environment...")
        print(f"{Formatter.ok('Python:')} {env.python_version}")

        if env.ssh_available:
            print(f"{Formatter.ok('OpenSSH:')} {env.ssh_path} ({env.ssh_version or 'detected'})")
        else:
            print(f"{Formatter.error('OpenSSH:')} ssh.exe not found in System32 or PATH.")

        if env.ssh_keygen_available:
            print(f"{Formatter.ok('ssh-keygen:')} {env.ssh_keygen_path}")
        else:
            print(f"{Formatter.error('ssh-keygen:')} ssh-keygen.exe not found.")

        print(f"{Formatter.ok('SSH directory:')} {self.ssh_dir}")

        if show_accounts:
            accounts = self.config_mgr.list_accounts()
            print(f"\nDetected GitHub accounts ({len(accounts)}):")
            if accounts:
                for acct in accounts:
                    priv_exists, pub_exists = self.key_mgr.key_exists(acct.key_name)
                    status = "keys found" if (priv_exists and pub_exists) else "key missing"
                    print(f"  * {Formatter.ok(acct.alias)} (key: {acct.key_name}, {status})")
            else:
                print("  (No accounts configured yet. Select option 1 to add one.)")

        return env

    # -------------------------------------------------------------------------
    # Core Operations
    # -------------------------------------------------------------------------

    def add_account_interactive(self) -> None:
        """Interactive wizard to add a new GitHub SSH account."""
        print("\n" + "-" * 50)
        print("Add New GitHub SSH Account")
        print("-" * 50)

        # 1. Email input
        email = ""
        while not email:
            raw_email = input("GitHub account email: ").strip()
            try:
                email = validate_email(raw_email)
            except ValueError as err:
                print(Formatter.error(str(err)))

        # 2. Identifier input
        identifier = ""
        while not identifier:
            suggested = email.split("@")[0].replace(".", "_")
            raw_id = input(f"Account identifier [default: {suggested}]: ").strip()
            if not raw_id:
                raw_id = suggested
            try:
                identifier = validate_identifier(raw_id)
            except InvalidAccountIdentifierError as err:
                print(Formatter.error(str(err)))
                identifier = ""

        alias = f"github-{identifier}"
        key_name = f"github_{identifier}"

        # 3. Check for existing alias in config
        if self.config_mgr.account_exists(alias):
            print(Formatter.error(f"An account with alias '{alias}' already exists in ~/.ssh/config!"))
            return

        # 4. Check for existing key files
        priv_exists, pub_exists = self.key_mgr.key_exists(key_name)
        use_existing_key = False
        if priv_exists or pub_exists:
            print(Formatter.warning(f"Key files already exist for '{key_name}':"))
            if priv_exists:
                print(f"  - Private key: {self.ssh_dir / key_name}")
            if pub_exists:
                print(f"  - Public key:  {self.ssh_dir / (key_name + '.pub')}")
            print("\nOptions:")
            print("  1. Use existing key")
            print("  2. Cancel")
            print("  3. Choose a different identifier")
            choice = input("Choose option (1-3): ").strip()
            if choice == "1":
                use_existing_key = True
            elif choice == "3":
                return self.add_account_interactive()
            else:
                print(Formatter.info("Account addition cancelled."))
                return

        # 5. Key Generation
        if not use_existing_key:
            print("\nPassphrase Protection:")
            print("  Protecting your private key with a passphrase adds strong security if your PC is compromised.")
            passphrase_choice = input("Do you want to protect this key with a passphrase? (y/N): ").strip().lower()
            passphrase = None
            if passphrase_choice == "y":
                pass1 = getpass.getpass("Enter passphrase: ")
                pass2 = getpass.getpass("Confirm passphrase: ")
                if pass1 != pass2:
                    print(Formatter.error("Passphrases do not match. Aborting."))
                    return
                passphrase = pass1

            print(Formatter.info(f"Generating ED25519 SSH key '{key_name}'..."))
            try:
                self.key_mgr.generate_ed25519_key(
                    key_name=key_name,
                    email=email,
                    passphrase=passphrase,
                    overwrite=False,
                )
                print(Formatter.ok("SSH key generated successfully."))
            except Exception as err:
                print(Formatter.error(f"Key generation failed: {err}"))
                return

        # 6. Read Public Key & Fingerprint
        try:
            pub_key = self.key_mgr.get_public_key(key_name)
            fingerprint = self.key_mgr.get_fingerprint(key_name)
        except Exception as err:
            print(Formatter.error(f"Could not read public key: {err}"))
            return

        print("\n" + "=" * 60)
        print("SSH PUBLIC KEY (Copy this to GitHub)")
        print("=" * 60)
        print(pub_key)
        print("=" * 60)
        if fingerprint:
            print(f"Fingerprint: {fingerprint}")
        print("=" * 60)

        # Clipboard copy
        if copy_to_clipboard(pub_key):
            print(Formatter.ok("Public key copied to Windows clipboard automatically!"))
        else:
            print(Formatter.info("Tip: Copy the public key text above manually."))

        # 7. Add to ~/.ssh/config
        account = Account(
            identifier=identifier,
            alias=alias,
            key_name=key_name,
            email=email,
        )

        print(Formatter.info(f"Adding Host block for '{alias}' to SSH config..."))
        if self.dry_run:
            print(Formatter.info("[DRY RUN] Would append to ~/.ssh/config:"))
            for line in self.config_mgr.build_account_block(account):
                print(f"  {line}")
        else:
            try:
                _, backup = self.config_mgr.add_account(account)
                print(Formatter.ok(f"SSH config updated successfully! (Alias: {alias})"))
                if backup:
                    print(Formatter.info(f"Backup created: {backup}"))
            except Exception as err:
                print(Formatter.error(f"Failed to update SSH config: {err}"))
                return

        # 8. GitHub instructions
        print("\n" + Formatter.action("NEXT STEPS:"))
        print("1. Open GitHub in your browser:")
        print("   https://github.com/settings/ssh/new")
        print("2. Enter a Title (e.g. 'Windows PC - " + identifier + "')")
        print("3. Paste your public key into the 'Key' box and click 'Add SSH key'")
        print("4. Test authentication using menu option 3 (or CLI: test " + identifier + ")")

        # 9. Optional direct repository clone
        clone_now = input("\nDo you want to clone a repository with this account now? (y/N): ").strip().lower()
        if clone_now in ("y", "yes"):
            self.clone_repository(account_or_id=account.alias)

    def list_accounts(self, run_tests: bool = False) -> None:
        """List configured GitHub accounts in a clean table format."""
        accounts = self.config_mgr.list_accounts()
        print("\n" + "=" * 65)
        print("GitHub SSH Accounts")
        print("=" * 65)

        if not accounts:
            print("No GitHub accounts found in ~/.ssh/config.")
            print("Use 'Add GitHub account' to configure your first account.")
            return

        header = f"{'Alias':<24} {'Key Name':<24} {'Keys':<12}"
        if run_tests:
            header += f" {'Auth Status':<20}"
        print(header)
        print("-" * len(header))

        for acct in accounts:
            priv_ok, pub_ok = self.key_mgr.key_exists(acct.key_name)
            if priv_ok and pub_ok:
                key_status = "[OK] Both"
            elif pub_ok:
                key_status = "Public only"
            elif priv_ok:
                key_status = "Priv only"
            else:
                key_status = "Missing"

            row = f"{acct.alias:<24} {acct.key_name:<24} {key_status:<12}"

            if run_tests:
                res = self.tester.test_account(acct)
                if res.success:
                    row += f" [OK] {res.github_user}"
                else:
                    row += f" [FAIL]"
            print(row)

            if self.verbose:
                fp = self.key_mgr.get_fingerprint(acct.key_name)
                if fp:
                    print(f"   Fingerprint: {fp}")

        print("-" * len(header))
        print(f"Total: {len(accounts)}")

    def test_account(self, alias_or_id: Optional[str] = None) -> None:
        """Test authentication for a specific account."""
        accounts = self.config_mgr.list_accounts()
        if not accounts:
            print(Formatter.warning("No GitHub accounts configured."))
            return

        if not alias_or_id:
            print("\nSelect account to test:")
            for i, acct in enumerate(accounts, 1):
                print(f"  {i}. {acct.alias}")
            choice = input(f"Enter choice (1-{len(accounts)}): ").strip()
            try:
                idx = int(choice) - 1
                if idx < 0 or idx >= len(accounts):
                    print(Formatter.error("Invalid choice."))
                    return
                account = accounts[idx]
            except ValueError:
                print(Formatter.error("Please enter a valid number."))
                return
        else:
            account = self.config_mgr.get_account(alias_or_id)
            if not account:
                print(Formatter.error(f"Account '{alias_or_id}' not found in SSH config."))
                return

        print(Formatter.info(f"Testing SSH authentication for '{account.alias}' (ssh -T git@{account.alias})..."))
        res = self.tester.test_account(account)

        if res.success:
            print(Formatter.ok(f"Successfully authenticated as GitHub user: '{res.github_user}'!"))
            print(Formatter.info(f"Raw response: {res.raw_output.splitlines()[-1]}"))
        else:
            print(Formatter.error(f"Authentication failed for '{account.alias}'."))
            if res.error_message:
                print(f"Reason: {res.error_message}")
            if self.verbose and res.raw_output:
                print(f"Diagnostics:\n{res.raw_output}")

    def test_all_accounts(self) -> None:
        """Test all configured accounts sequentially."""
        accounts = self.config_mgr.list_accounts()
        if not accounts:
            print(Formatter.warning("No GitHub accounts configured."))
            return

        print(f"\nTesting {len(accounts)} GitHub SSH accounts...\n")
        success_count = 0

        for acct in accounts:
            res = self.tester.test_account(acct)
            if res.success:
                success_count += 1
                print(f"{Formatter.ok(acct.alias)} -> Authenticated as: {res.github_user}")
            else:
                print(f"{Formatter.error(acct.alias)}")
                if res.error_message:
                    print(f"  Reason: {res.error_message}")

        print(f"\nSummary: {success_count}/{len(accounts)} accounts authenticated successfully.")

    def show_public_key(self, alias_or_id: Optional[str] = None) -> None:
        """Display the public key for an account and optionally copy it."""
        account = self._resolve_account(alias_or_id)
        if not account:
            return

        try:
            pub_key = self.key_mgr.get_public_key(account.key_name)
            fingerprint = self.key_mgr.get_fingerprint(account.key_name)
        except KeyNotFoundError:
            print(Formatter.error(f"Public key file '~/.ssh/{account.key_name}.pub' does not exist."))
            return

        print("\n" + "=" * 60)
        print(f"PUBLIC KEY: {account.alias} (~/.ssh/{account.key_name}.pub)")
        print("=" * 60)
        print(pub_key)
        print("=" * 60)
        if fingerprint:
            print(f"Fingerprint: {fingerprint}")
        print("=" * 60)

        # Offer to copy
        copy_choice = input("Copy to clipboard? (Y/n): ").strip().lower()
        if copy_choice in ("", "y", "yes"):
            if copy_to_clipboard(pub_key):
                print(Formatter.ok("Copied to clipboard!"))
            else:
                print(Formatter.warning("Could not automatically copy to clipboard."))

    def show_ssh_config(self) -> None:
        """Display the current ~/.ssh/config file safely."""
        print("\n" + "=" * 60)
        print(f"SSH Configuration ({self.config_mgr.config_path})")
        print("=" * 60)
        raw = self.config_mgr.read_raw_config()
        if not raw.strip():
            print("(Config file is empty or does not exist)")
        else:
            print(raw)
        print("=" * 60)

    def clone_repository(
        self,
        account_or_id: Optional[str] = None,
        repo_input: Optional[str] = None,
        dest_input: Optional[str] = None,
    ) -> bool:
        """Clone a GitHub repository using an account SSH alias to a chosen destination."""
        account = self._resolve_account(account_or_id)
        if not account:
            return False

        if not repo_input:
            print("\nEnter repository link or path:")
            print("Examples:")
            print("  - git@github.com:af979031-cloud/kumbify.git")
            print("  - https://github.com/af979031-cloud/kumbify")
            print("  - af979031-cloud/kumbify")
            repo_input = input("Repository: ").strip()
            if not repo_input:
                print(Formatter.error("Repository name or URL cannot be empty."))
                return False

        try:
            full_repo, default_repo_name = parse_github_repo(repo_input)
        except ValueError as err:
            print(Formatter.error(str(err)))
            return False

        clone_url = account.clone_url(full_repo)

        if dest_input is None:
            default_dest_display = f".\\{default_repo_name}"
            print(f"\nTarget download location [default: {default_dest_display}]:")
            user_dest = input("> ").strip()
            target_dest = resolve_clone_destination(user_dest, default_repo_name)
        else:
            target_dest = resolve_clone_destination(dest_input, default_repo_name)

        print("\n" + "=" * 60)
        print("CLONE REPOSITORY")
        print("=" * 60)
        print(f"Account:     {account.alias}")
        print(f"Repository:  {full_repo}")
        print(f"SSH URL:     {clone_url}")
        print(f"Destination: {target_dest}")
        print("=" * 60)

        if self.dry_run:
            print(Formatter.info(f"[DRY RUN] Would execute: git clone {clone_url} {target_dest}"))
            return True

        print(Formatter.info(f"Cloning repository into '{target_dest}'..."))
        success, msg = run_git_clone(clone_url, target_dest, dry_run=False)

        if not success:
            print(Formatter.error(f"Clone failed: {msg}"))
            print(
                Formatter.warning(
                    "Troubleshooting tips:\n"
                    "  1. Verify if the repository exists and is accessible.\n"
                    f"  2. Check if your account '{account.alias}' has read permission.\n"
                    f"  3. Test your SSH connection with: python -m github_ssh_manager test {account.alias}"
                )
            )
            return False

        print(Formatter.ok(f"Repository cloned successfully into: {target_dest}"))

        # Offer to configure local repository Git identity
        configure_id = (
            input("\nDo you want to configure Git author identity for this cloned repo? (Y/n): ")
            .strip()
            .lower()
        )
        if configure_id in ("", "y", "yes"):
            author_name = input(f"Git author name [default: {account.identifier}]: ").strip()
            if not author_name:
                author_name = account.identifier

            default_email = account.email or ""
            email_prompt = (
                f"Git author email [default: {default_email}]: "
                if default_email
                else "Git author email: "
            )
            author_email = input(email_prompt).strip()
            if not author_email and default_email:
                author_email = default_email

            if author_name and author_email:
                ok, id_msg = configure_repo_identity(target_dest, author_name, author_email)
                if ok:
                    print(Formatter.ok(f"Local Git identity configured: {author_name} <{author_email}>"))
                else:
                    print(Formatter.warning(f"Could not configure Git identity: {id_msg}"))

        return True

    def generate_clone_url(
        self, alias_or_id: Optional[str] = None, repo: Optional[str] = None
    ) -> None:
        """Generate and display the exact Git clone command."""
        account = self._resolve_account(alias_or_id)
        if not account:
            return

        if not repo:
            repo = input("Enter repository (e.g. 'username/my-repo'): ").strip()
            if not repo:
                print(Formatter.error("Repository name cannot be empty."))
                return

        url = account.clone_url(repo)
        print("\n" + "=" * 60)
        print("GIT CLONE COMMAND")
        print("=" * 60)
        cmd = f"git clone {url}"
        print(cmd)
        print("=" * 60)

        print("\n" + Formatter.info("Git Author Identity Tip:"))
        print(
            "SSH authenticates your connection, while Git author identity is set per repository.\n"
            "Inside your cloned repo, configure your author identity with:\n"
            f"  git config user.name \"Your Name\"\n"
            f"  git config user.email \"{account.email or 'your-email@example.com'}\""
        )

        copy_to_clipboard(cmd)

    def inspect_agent(self) -> None:
        """Inspect the Windows ssh-agent service and list keys."""
        print("\n" + "-" * 50)
        print("SSH Agent Status")
        print("-" * 50)
        running, messages = self.ssh_mgr.inspect_ssh_agent()
        if running:
            print(Formatter.ok("ssh-agent service is responsive."))
            print("Identities loaded:")
            for msg in messages:
                print(f"  * {msg}")
        else:
            print(Formatter.warning("ssh-agent service is not reachable or not running."))
            for msg in messages:
                print(f"  {msg}")
            print(
                "\nNote: GitHub SSH Manager uses direct 'IdentityFile' configuration in ~/.ssh/config,\n"
                "so ssh-agent is optional and not strictly required."
            )

    def remove_account(
        self,
        alias_or_id: Optional[str] = None,
        confirm: bool = False,
        delete_keys: bool = False,
    ) -> None:
        """Safely remove a GitHub account after explicit confirmation."""
        account = self._resolve_account(alias_or_id)
        if not account:
            return

        print("\n" + "=" * 60)
        print(f"REMOVE ACCOUNT: {account.alias}")
        print("=" * 60)
        print(f"Alias:        {account.alias}")
        print(f"IdentityFile: {account.identity_file}")
        print(
            "\n"
            + Formatter.warning(
                "CAUTION: Removing this account will delete the Host block from ~/.ssh/config.\n"
                "Note: This does NOT delete the key from GitHub. You must manually remove it\n"
                "at GitHub -> Settings -> SSH and GPG keys if you wish to revoke access."
            )
        )

        if not confirm:
            print(f"\nTo confirm removal, type the alias '{account.alias}':")
            typed = input("> ").strip()
            if typed != account.alias:
                print(Formatter.info("Removal cancelled. Alias did not match."))
                return

            del_k = input("Do you also want to delete the local private and public key files? (y/N): ").strip().lower()
            delete_keys = (del_k == "y")

        if self.dry_run:
            print(Formatter.info(f"[DRY RUN] Would remove block '{account.alias}' from ~/.ssh/config."))
            if delete_keys:
                print(Formatter.info(f"[DRY RUN] Would delete keys: {account.key_name} and {account.key_name}.pub"))
            return

        try:
            _, backup = self.config_mgr.remove_account(account.alias)
            print(Formatter.ok(f"Removed '{account.alias}' from ~/.ssh/config."))
            if backup:
                print(Formatter.info(f"Backup created: {backup}"))

            if delete_keys:
                priv_del, pub_del = self.key_mgr.delete_keys(account.key_name, delete_private=True)
                print(Formatter.ok(f"Key files deleted: private={priv_del}, public={pub_del}"))
        except Exception as err:
            print(Formatter.error(f"Error removing account: {err}"))

    # -------------------------------------------------------------------------
    # Helper Resolution
    # -------------------------------------------------------------------------

    def _resolve_account(self, alias_or_id: Optional[str] = None) -> Optional[Account]:
        """Resolve an account from alias_or_id or prompt the user."""
        accounts = self.config_mgr.list_accounts()
        if not accounts:
            print(Formatter.warning("No GitHub accounts configured."))
            return None

        if alias_or_id:
            account = self.config_mgr.get_account(alias_or_id)
            if not account:
                print(Formatter.error(f"Account '{alias_or_id}' not found."))
                return None
            return account

        print("\nSelect account:")
        for i, acct in enumerate(accounts, 1):
            print(f"  {i}. {acct.alias}")
        choice = input(f"Enter choice (1-{len(accounts)}): ").strip()
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(accounts):
                return accounts[idx]
        except ValueError:
            pass
        print(Formatter.error("Invalid choice."))
        return None

    # -------------------------------------------------------------------------
    # Interactive Menu Loop
    # -------------------------------------------------------------------------

    def run_interactive_menu(self) -> None:
        """Run the main interactive menu loop."""
        self.print_banner()
        self.print_environment_check(show_accounts=True)

        while True:
            print("\n" + "=" * 35)
            print("Main Menu")
            print("=" * 35)
            print("1. Add GitHub account")
            print("2. List configured accounts")
            print("3. Test account")
            print("4. Test all accounts")
            print("5. Show public key")
            print("6. Show SSH configuration")
            print("7. Clone repository")
            print("8. Generate Git clone URL")
            print("9. Inspect SSH Agent")
            print("10. Remove account")
            print("0. Exit")
            print("=" * 35)

            try:
                choice = input("Choose an option (0-10): ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nGoodbye!")
                break

            if choice == "1":
                self.add_account_interactive()
            elif choice == "2":
                self.list_accounts()
            elif choice == "3":
                self.test_account()
            elif choice == "4":
                self.test_all_accounts()
            elif choice == "5":
                self.show_public_key()
            elif choice == "6":
                self.show_ssh_config()
            elif choice == "7":
                self.clone_repository()
            elif choice == "8":
                self.generate_clone_url()
            elif choice == "9":
                self.inspect_agent()
            elif choice == "10":
                self.remove_account()
            elif choice in ("0", "exit", "q"):
                print("Exiting GitHub SSH Manager. Goodbye!")
                break
            else:
                print(Formatter.warning("Invalid option. Please choose between 0 and 10."))


# -------------------------------------------------------------------------
# Argument Parser & CLI Entry Point
# -------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build the command line argument parser."""
    parser = argparse.ArgumentParser(
        prog="github-ssh-manager",
        description="Manage and configure multiple GitHub accounts using SSH on Windows.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate operations without modifying files or config.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Display detailed diagnostic output.",
    )
    parser.add_argument(
        "--ssh-dir",
        type=Path,
        default=None,
        help="Custom SSH directory path (defaults to ~/.ssh).",
    )

    subparsers = parser.add_subparsers(dest="subcommand", help="Available subcommands")

    # add
    p_add = subparsers.add_parser("add", help="Add a new GitHub SSH account")
    p_add.add_argument("--email", help="GitHub account email")
    p_add.add_argument("--identifier", help="Safe identifier (e.g. opgests)")

    # list
    p_list = subparsers.add_parser("list", help="List configured GitHub accounts")
    p_list.add_argument("--test", action="store_true", help="Perform live network test for each account")

    # test
    p_test = subparsers.add_parser("test", help="Test authentication for an account")
    p_test.add_argument("account", nargs="?", help="Account alias or identifier")

    # test-all
    subparsers.add_parser("test-all", help="Test authentication for all accounts")

    # public-key
    p_pub = subparsers.add_parser("public-key", help="Display public key for an account")
    p_pub.add_argument("account", nargs="?", help="Account alias or identifier")
    p_pub.add_argument("--copy", action="store_true", help="Copy public key to clipboard")

    # config
    subparsers.add_parser("config", help="Display ~/.ssh/config")

    # clone-url
    p_clone_url = subparsers.add_parser("clone-url", help="Generate Git clone URL using account alias")
    p_clone_url.add_argument("account", nargs="?", help="Account alias or identifier")
    p_clone_url.add_argument("repo", nargs="?", help="Repository (e.g. username/repo)")

    # clone
    p_clone = subparsers.add_parser("clone", help="Clone a GitHub repository using an account SSH alias")
    p_clone.add_argument("repo", help="Repository URL or owner/repo (e.g. git@github.com:af979031-cloud/kumbify.git)")
    p_clone.add_argument("--account", help="Account alias or identifier to use for cloning")
    p_clone.add_argument("--dest", help="Destination directory path on your machine")

    # agent
    subparsers.add_parser("agent", help="Inspect Windows ssh-agent")

    # remove
    p_rm = subparsers.add_parser("remove", help="Remove an account")
    p_rm.add_argument("account", nargs="?", help="Account alias or identifier")
    p_rm.add_argument("--yes", action="store_true", help="Skip confirmation prompt")
    p_rm.add_argument("--delete-keys", action="store_true", help="Also delete local key files")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """Main application entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    cli = GitHubSSHManagerCLI(
        ssh_dir=args.ssh_dir,
        dry_run=args.dry_run,
        verbose=args.verbose,
    )

    try:
        if args.subcommand is None:
            # Default to interactive menu
            cli.run_interactive_menu()
            return 0

        if args.subcommand == "add":
            if args.email and args.identifier:
                # Direct non-interactive addition
                ident = validate_identifier(args.identifier)
                email = validate_email(args.email)
                alias = f"github-{ident}"
                key_name = f"github_{ident}"
                account = Account(identifier=ident, alias=alias, key_name=key_name, email=email)

                if not cli.dry_run:
                    cli.key_mgr.generate_ed25519_key(key_name, email)
                    cli.config_mgr.add_account(account)
                print(Formatter.ok(f"Account {alias} created."))
                pub = cli.key_mgr.get_public_key(key_name) if not cli.dry_run else "(generated public key)"
                print(f"Public key:\n{pub}")
            else:
                cli.add_account_interactive()

        elif args.subcommand == "list":
            cli.list_accounts(run_tests=args.test)

        elif args.subcommand == "test":
            cli.test_account(args.account)

        elif args.subcommand == "test-all":
            cli.test_all_accounts()

        elif args.subcommand == "public-key":
            cli.show_public_key(args.account)

        elif args.subcommand == "config":
            cli.show_ssh_config()

        elif args.subcommand == "clone-url":
            cli.generate_clone_url(args.account, args.repo)

        elif args.subcommand == "clone":
            cli.clone_repository(
                account_or_id=args.account,
                repo_input=args.repo,
                dest_input=args.dest,
            )

        elif args.subcommand == "agent":
            cli.inspect_agent()

        elif args.subcommand == "remove":
            cli.remove_account(args.account, confirm=args.yes, delete_keys=args.delete_keys)

        return 0

    except (SSHNotInstalledError, SSHManagerError, ValueError) as exc:
        print(Formatter.error(str(exc)), file=sys.stderr)
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1
    except KeyboardInterrupt:
        print("\nAborted by user.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
