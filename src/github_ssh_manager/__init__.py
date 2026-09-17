"""GitHub SSH Manager.

A Windows CLI application to configure, manage, and test multiple
GitHub accounts using distinct SSH keys and host aliases.
"""

__version__ = "1.0.0"
__author__ = "Helcio Business"

from github_ssh_manager.exceptions import (
    AccountAlreadyExistsError,
    AccountNotFoundError,
    AuthenticationError,
    InvalidAccountIdentifierError,
    KeyNotFoundError,
    SSHConfigError,
    SSHKeyGenerationError,
    SSHManagerError,
    SSHNotInstalledError,
)
from github_ssh_manager.models import (
    Account,
    AuthTestResult,
    EnvironmentInfo,
    HostBlock,
)

__all__ = [
    "__version__",
    "Account",
    "HostBlock",
    "AuthTestResult",
    "EnvironmentInfo",
    "SSHManagerError",
    "SSHNotInstalledError",
    "SSHKeyGenerationError",
    "SSHConfigError",
    "AccountAlreadyExistsError",
    "AccountNotFoundError",
    "InvalidAccountIdentifierError",
    "AuthenticationError",
    "KeyNotFoundError",
]
