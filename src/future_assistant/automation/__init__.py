"""Capability-scoped, confirmable, cancellable automation skills."""

from .cancellation import CancellationToken
from .confirmation import (
    ConfirmationAuthority,
    ConfirmationGrant,
    ConfirmationValidation,
)
from .engine import AutomationEngine
from .errors import (
    AutomationCancelled,
    AutomationConfigurationError,
    AutomationError,
    ConfirmationIssueError,
    ConfirmationNotRequiredError,
    DuplicateExecutorError,
    ExecutorNotAllowedError,
    InvalidArgumentsError,
)
from .examples import (
    APP_LAUNCH_MANIFEST,
    BROWSER_SEARCH_MANIFEST,
    AppEffects,
    AppLaunchExecutor,
    BrowserEffects,
    BrowserSearchExecutor,
)
from .models import (
    AutomationResult,
    ExecutionStatus,
    Permission,
    ResultCode,
    RiskLevel,
    SkillInvocation,
    SkillManifest,
)
from .registry import AutomationExecutor, ExecutorRegistry

__all__ = [
    "APP_LAUNCH_MANIFEST",
    "BROWSER_SEARCH_MANIFEST",
    "AppEffects",
    "AppLaunchExecutor",
    "AutomationCancelled",
    "AutomationConfigurationError",
    "AutomationEngine",
    "AutomationError",
    "AutomationExecutor",
    "AutomationResult",
    "BrowserEffects",
    "BrowserSearchExecutor",
    "CancellationToken",
    "ConfirmationAuthority",
    "ConfirmationGrant",
    "ConfirmationIssueError",
    "ConfirmationNotRequiredError",
    "ConfirmationValidation",
    "DuplicateExecutorError",
    "ExecutionStatus",
    "ExecutorNotAllowedError",
    "ExecutorRegistry",
    "InvalidArgumentsError",
    "Permission",
    "ResultCode",
    "RiskLevel",
    "SkillInvocation",
    "SkillManifest",
]
