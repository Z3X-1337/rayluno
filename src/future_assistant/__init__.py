"""Local-first core for the Rayluno bilingual Windows assistant."""

from .config import AssistantConfig
from .domain import Action, ActionKind, Plan, RuntimeResult, RuntimeStatus, VolumeOperation
from .runtime import AssistantRuntime, DryRunEffects, SystemEffects, build_runtime
from .verified_runtime import VerifiedAssistantRuntime, build_verified_runtime
from .verified_skills import (
    ConfirmationPolicy,
    ExecutionReceipt,
    HashChainedReceiptLedger,
    SkillManifest,
    SkillRisk,
    VerifiedSkillEngine,
)

__all__ = [
    "Action",
    "ActionKind",
    "AssistantConfig",
    "AssistantRuntime",
    "ConfirmationPolicy",
    "DryRunEffects",
    "ExecutionReceipt",
    "HashChainedReceiptLedger",
    "Plan",
    "RuntimeResult",
    "RuntimeStatus",
    "SkillManifest",
    "SkillRisk",
    "SystemEffects",
    "VerifiedAssistantRuntime",
    "VerifiedSkillEngine",
    "VolumeOperation",
    "build_runtime",
    "build_verified_runtime",
]

__version__ = "1.0.0"
