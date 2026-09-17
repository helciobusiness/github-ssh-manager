"""Custom exceptions for GitHub SSH Manager."""


class SSHManagerError(Exception):
    """Base exception for all GitHub SSH Manager errors."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class SSHNotInstalledError(SSHManagerError):
    """Raised when Windows OpenSSH utilities (ssh, ssh-keygen) are not found."""


class SSHKeyGenerationError(SSHManagerError):
    """Raised when generating an SSH key pair fails."""


class SSHConfigError(SSHManagerError):
    """Raised when reading, parsing, or modifying ~/.ssh/config fails."""


class AccountAlreadyExistsError(SSHManagerError):
    """Raised when attempting to add an account alias or key that already exists."""


class AccountNotFoundError(SSHManagerError):
    """Raised when an account alias or identifier is not found in configuration."""


class InvalidAccountIdentifierError(SSHManagerError):
    """Raised when an account identifier fails character validation or poses traversal risks."""


class AuthenticationError(SSHManagerError):
    """Raised when testing SSH connection to GitHub fails."""


class KeyNotFoundError(SSHManagerError):
    """Raised when expected public or private SSH key file is not found on disk."""


class KeyAlreadyExistsError(SSHManagerError):
    """Raised when an SSH key file already exists at the target path."""


class SecurityViolationError(SSHManagerError):
    """Raised when a security constraint or invalid path traversal is detected."""
