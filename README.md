# GitHub SSH Manager (Windows CLI)

[![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%2F%2011-0078D6.svg)](https://www.microsoft.com/windows)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Zero Dependencies](https://img.shields.io/badge/Dependencies-Standard%20Library%20Only-brightgreen.svg)](requirements.txt)

**GitHub SSH Manager** is a production-grade, secure, and intuitive command-line application built specifically for Windows. It automates configuring, managing, and testing multiple GitHub accounts using dedicated SSH keys and OpenSSH host aliases on a single computer.

---

## The Problem: Multiple GitHub Accounts on One Machine

By default, Git connects to GitHub via SSH using the generic hostname:
```bash
git@github.com:USERNAME/REPOSITORY.git
```
When OpenSSH connects to `github.com`, it attempts to use your default SSH key (`~/.ssh/id_ed25519` or `~/.ssh/id_rsa`). GitHub checks the public key, authenticates the single associated user, and rejects pushes or private repo access meant for any second or third GitHub accounts.

### The Solution: SSH Host Aliases

To seamlessly support multiple accounts (such as your personal profile and your business or client account), each account needs:
1. Its own dedicated SSH key pair (e.g. `~/.ssh/github_helciobusiness` and `~/.ssh/github_opgests`).
2. A distinct **Host alias** configured in `~/.ssh/config`:

```sshconfig
Host github-helciobusiness
    HostName github.com
    User git
    IdentityFile ~/.ssh/github_helciobusiness
    IdentitiesOnly yes

Host github-opgests
    HostName github.com
    User git
    IdentityFile ~/.ssh/github_opgests
    IdentitiesOnly yes
```

When you clone or configure a repository using the alias:
```bash
# Work / Business Account
git clone git@github-helciobusiness:helciobusiness/backend-service.git

# Personal / Client Account
git clone git@github-opgests:opgests/client-project.git
```
OpenSSH automatically selects the exact private key for that account and instructs GitHub who is authenticating—**completely eliminating key collisions and permission errors**.

---

## Key Features

- **Interactive Menu & Direct CLI Subcommands:** Launch an intuitive interactive wizard or automate workflows with scriptable commands.
- **Zero External Dependencies:** Built 100% on the Python standard library. No fragile third-party packages to install.
- **Non-Destructive SSH Config Management:** Parses `~/.ssh/config` line-by-line, strictly preserving existing comments, custom directives, blank lines, and non-GitHub hosts (such as VPS servers).
- **Automated Configuration Backups:** Automatically creates timestamped backups (`config.bak.<timestamp>`) before modifying configuration.
- **Secure Key Generation:** Generates state-of-the-art **ED25519** key pairs (`ssh-keygen -t ed25519`) with optional passphrase protection.
- **Never Stores or Logs Secrets:** Private keys, passphrases, and tokens are never read into memory, stored, or echoed.
- **Native Windows Clipboard Integration:** Automatically copies your new public key to the Windows clipboard via `clip.exe` for instant pasting into GitHub.
- **Live Authentication Testing & Username Extraction:** Tests `ssh -T git@<alias>` and automatically parses GitHub's banner (`Hi <username>! You've successfully authenticated`) without relying on misleading exit codes.
- **Path Traversal & Injection Protection:** Validates account identifiers with strict character white-listing and safe subprocess execution (`shell=False`).
- **Dry-Run Mode (`--dry-run`):** Preview configuration modifications and file operations without touching your filesystem.

---

## Requirements

- **Operating System:** Windows 10 (version 1809+) or Windows 11.
- **Python:** Python 3.10, 3.11, 3.12, 3.13, or 3.14.
- **Windows OpenSSH Client:** Installed by default in modern Windows. If missing, enable it via:
  ```powershell
  # In an elevated PowerShell:
  Add-WindowsCapability -Online -Name OpenSSH.Client~~~~0.0.1.0
  ```

---

## Installation

Clone the repository and install it in editable development mode:

```powershell
git clone https://github.com/helciobusiness/github-ssh-manager.git
cd github-ssh-manager
python -m pip install -e .
```

After installation, you can run the tool via either:
```powershell
python -m github_ssh_manager
# or
github-ssh-manager
```

---

## Quick Start & Usage

### 1. Interactive Menu (Recommended)

Simply run the tool without arguments:

```powershell
python -m github_ssh_manager
```

You will see:
```text
============================================================
GitHub SSH Manager v1.0.0 (Windows)
============================================================

Checking environment...
[OK] Python: 3.14.7
[OK] OpenSSH: C:\Windows\System32\OpenSSH\ssh.exe
[OK] ssh-keygen: C:\Windows\System32\OpenSSH\ssh-keygen.exe
[OK] SSH directory: C:\Users\helci\.ssh

Detected GitHub accounts (1):
  * [OK] github-helciobusiness (key: github_helciobusiness, keys found)

===================================
Main Menu
===================================
1. Add GitHub account
2. List configured accounts
3. Test account
4. Test all accounts
5. Show public key
6. Show SSH configuration
7. Generate Git clone URL
8. Inspect SSH Agent
9. Remove account
0. Exit
===================================
Choose an option (0-9):
```

---

### 2. Step-by-Step: Adding a New Account

1. Select **Option 1** (`Add GitHub account`) or run:
   ```powershell
   python -m github_ssh_manager add
   ```
2. Enter your account email: `opgests@gmail.com`
3. Enter or accept the account identifier: `opgests`
4. Choose whether to protect your private key with a passphrase (recommended for laptops/portable devices).
5. The tool will:
   - Generate `~/.ssh/github_opgests` (ED25519 private key)
   - Generate `~/.ssh/github_opgests.pub` (public key)
   - Compute the SHA256 fingerprint
   - Copy the public key to your Windows clipboard automatically
   - Add the host alias `github-opgests` to `~/.ssh/config`
6. **Add the Public Key to GitHub**:
   - Open [https://github.com/settings/ssh/new](https://github.com/settings/ssh/new) in your browser.
   - Enter a title (e.g., `Windows PC - opgests`).
   - Paste the public key from your clipboard and click **Add SSH key**.
7. **Test Authentication**:
   - Run **Option 3** (`Test account`) or:
     ```powershell
     python -m github_ssh_manager test opgests
     ```
   - You will see:
     ```text
     [INFO] Testing SSH authentication for 'github-opgests' (ssh -T git@github-opgests)...
     [OK] Successfully authenticated as GitHub user: 'opgests'!
     ```

---

### 3. CLI Subcommands

For power users and automated scripts:

| Subcommand | Description | Example |
|---|---|---|
| `list` | List all configured accounts and key status | `python -m github_ssh_manager list` |
| `list --test` | List accounts and run live network auth tests | `python -m github_ssh_manager list --test` |
| `add` | Add an account interactively or via flags | `python -m github_ssh_manager add --email opgests@gmail.com --identifier opgests` |
| `test <account>` | Test authentication for a specific alias | `python -m github_ssh_manager test github-opgests` |
| `test-all` | Test all configured accounts sequentially | `python -m github_ssh_manager test-all` |
| `public-key <account>` | Display public key and fingerprint | `python -m github_ssh_manager public-key github-opgests --copy` |
| `config` | Display current `~/.ssh/config` content | `python -m github_ssh_manager config` |
| `clone-url <account> <repo>` | Generate exact Git clone command | `python -m github_ssh_manager clone-url github-opgests opgests/app` |
| `agent` | Inspect Windows `ssh-agent` service | `python -m github_ssh_manager agent` |
| `remove <account>` | Safely remove account and optionally delete keys | `python -m github_ssh_manager remove github-opgests` |

#### Global Options
- `--dry-run`: Simulate file/config changes without writing to disk.
- `--verbose`: Display detailed diagnostic information and full raw outputs.
- `--ssh-dir <path>`: Specify a custom SSH directory (ideal for testing).

---

## Git Author Identity vs SSH Authentication

> [!IMPORTANT]
> **SSH Authentication** and **Git Author Identity** are completely independent:
> - **SSH (via host alias)** identifies who is authorized to push/pull to the repository on GitHub.
> - **Git author config (`user.name` and `user.email`)** determines what name and email appear on commits in the commit history.

When cloning a repository with a specific account alias, configure your repository-level author identity:

```powershell
# 1. Clone using the account alias
git clone git@github-opgests:opgests/my-project.git
cd my-project

# 2. Configure repository-level commit author
git config user.name "Your Name"
git config user.email "opgests@gmail.com"
```
*(Do not use `--global` when setting `user.name` and `user.email`, so each repository maintains its own distinct identity!)*

---

## Security Model & Design Principles

1. **Private Key Protection:** The application never reads, displays, or transmits private SSH keys.
2. **Zero Credential Storage:** No GitHub passwords, personal access tokens, or passphrases are ever requested, cached, or stored on disk.
3. **Safe Subprocess Execution:** All external tool invocations use direct argument lists (`subprocess.run(args, shell=False)`), preventing shell command injection.
4. **Input Sanitization & Path Traversal Prevention:** Account identifiers are strictly restricted to alphanumeric characters, hyphens, and underscores. Any path traversal characters (`..`, `/`, `\`, `:`) are immediately rejected.
5. **Non-Destructive Operations:** Modifying `~/.ssh/config` always creates an automatic timestamped backup (`config.bak.<timestamp>`) beforehand. Deleting accounts requires explicit typed confirmation.

---

## Project Structure

```
github-ssh-manager/
│
├── src/
│   └── github_ssh_manager/
│       ├── __init__.py           # Package version & top-level exports
│       ├── __main__.py           # python -m github_ssh_manager entrypoint
│       ├── cli.py               # Menu & argparse subcommand handlers
│       ├── models.py            # Account, HostBlock, AuthTestResult dataclasses
│       ├── exceptions.py        # Typed exception hierarchy
│       ├── utils.py             # Validation, clipboard, and console formatting
│       ├── ssh_manager.py       # Windows OpenSSH discovery & execution
│       ├── key_manager.py       # ED25519 key generation & fingerprinting
│       ├── config_manager.py    # Robust non-destructive ~/.ssh/config parser
│       └── github_tester.py     # SSH authentication testing & username extraction
│
├── tests/
│   ├── __init__.py
│   ├── test_models.py           # Model and clone URL tests
│   ├── test_utils.py            # Validation & path traversal guards
│   ├── test_config_manager.py   # Config parsing, preservation & updates
│   ├── test_key_manager.py      # Key generation & fingerprint tests
│   ├── test_github_tester.py    # GitHub response parser & username extraction
│   └── test_cli.py              # CLI argument parser & dry-run tests
│
├── .gitignore                   # Python build & SSH private key safety guards
├── pyproject.toml               # Package metadata and entry points
├── requirements.txt             # Dependency declaration (Standard Library only)
├── LICENSE                      # MIT License
└── README.md                    # Project documentation
```

---

## Running the Automated Test Suite

All unit tests run completely isolated using temporary directories and mocked subprocesses, ensuring your real `~/.ssh` directory is never modified:

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```

All 35 automated tests cover:
- Path traversal prevention and identifier validation
- Non-destructive `~/.ssh/config` parsing and comment preservation
- Safe block insertion, duplicate alias rejection, and clean block removal
- Key conflict detection and ED25519 command construction
- Extraction of authenticated GitHub usernames from OpenSSH responses
- Dry-run mode validation and argument parsing

---

## Troubleshooting & FAQ

### 1. `Permission denied (publickey)` when testing an account
- Verify you copied the **entire** contents of `~/.ssh/github_<identifier>.pub` to GitHub.
- On GitHub, go to **Settings → SSH and GPG keys** and confirm that the key fingerprint matches the fingerprint displayed by:
  ```powershell
  python -m github_ssh_manager public-key <account>
  ```

### 2. Why does `ssh -T git@github.com` exit with code 1?
GitHub's SSH server closes the connection immediately after authentication because it does not provide an interactive shell. OpenSSH flags this closed connection as exit code `1`. GitHub SSH Manager inspects the actual response text (`Hi <username>!`) rather than assuming non-zero exit codes represent failure.

### 3. OpenSSH tools not found
Ensure Windows OpenSSH is enabled on Windows 10/11:
- Open Windows **Settings → System → Optional Features**.
- Search for **OpenSSH Client**. If not installed, click **Add a feature** and install it.

---

## Future Roadmap

- [ ] GitHub CLI (`gh`) integration for automatic public key upload.
- [ ] Lightweight Windows Systray / GUI status app.
- [ ] Automatic Git repository remote detection and alias migration helper.
- [ ] Integration with Windows Credential Manager for optional passphrase caching.

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
