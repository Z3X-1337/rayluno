"""Exceptions used at automation configuration and executor boundaries."""


class AutomationError(Exception):
    """Base error for the automation package."""


class AutomationConfigurationError(AutomationError):
    """Raised when manifests, permissions, or executors do not line up safely."""


class ExecutorNotAllowedError(AutomationConfigurationError):
    """Raised when code tries to register an executor outside the allowlist."""


class DuplicateExecutorError(AutomationConfigurationError):
    """Raised when an executor identifier is registered more than once."""


class InvalidArgumentsError(AutomationError):
    """A safe, user-correctable validation error from an executor."""


class ConfirmationIssueError(AutomationError):
    """Raised when a confirmation cannot safely be issued for an invocation."""


class ConfirmationNotRequiredError(ConfirmationIssueError):
    """Raised when a caller asks for confirmation for a low-risk skill."""


class AutomationCancelled(AutomationError):
    """Cooperative cancellation raised inside an executor."""
