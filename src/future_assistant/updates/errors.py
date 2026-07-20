"""Exceptions raised by the secure update subsystem."""


class UpdateError(Exception):
    """Base class for update failures safe to show as a generic error."""


class UpdateDependencyError(UpdateError):
    """A dependency required for secure verification is unavailable."""


class ManifestValidationError(UpdateError):
    """A release manifest or its signed envelope is malformed."""


class SignatureVerificationError(UpdateError):
    """The manifest signature cannot be trusted."""


class UnknownSigningKeyError(SignatureVerificationError):
    """The envelope names a key that is not in the trusted keyring."""


class UpdatePolicyError(UpdateError):
    """A validly signed manifest violates local update policy."""


class ChannelMismatchError(UpdatePolicyError):
    """The manifest belongs to a different release channel."""


class DowngradeBlockedError(UpdatePolicyError):
    """A manifest attempts to install an older version."""


class IncompatibleOSError(UpdatePolicyError):
    """The update requires a newer Windows version."""


class NoUpdateAvailableError(UpdatePolicyError):
    """The checked release is not newer than the installed version."""


class TransportSecurityError(UpdateError):
    """A download URL or redirect violates transport security policy."""


class UpdateTransportError(UpdateError):
    """A network transport failed."""


class DownloadError(UpdateError):
    """An update could not be downloaded safely."""


class DownloadSizeError(DownloadError):
    """A response exceeded its limit or did not match the declared size."""


class DownloadIntegrityError(DownloadError):
    """Downloaded bytes do not match the signed SHA-256 digest."""
