"""Reproducible, clearly labelled judge path that requires no model or API key."""

from __future__ import annotations

from .actions import normalize_text
from .domain import Action, ActionKind, Plan, PlanSource
from .planner import Planner

JUDGE_DEMO_COMMAND_AR = "جهز عرض الحكام"
JUDGE_DEMO_COMMAND_EN = "prepare the judge demo"
JUDGE_BLOCK_COMMAND_AR = "اختبر رفض مهارة غير مسجلة"
JUDGE_BLOCK_COMMAND_EN = "test an unregistered skill"


class JudgeDemoPlanner:
    """Provide two transparent scripted scenarios, then delegate normal commands."""

    def __init__(self, fallback: Planner) -> None:
        self.fallback = fallback

    def plan(self, command: str) -> Plan | None:
        normalized = normalize_text(command).strip(" .،!?؟")
        if normalized in {
            normalize_text(JUDGE_DEMO_COMMAND_AR),
            normalize_text(JUDGE_DEMO_COMMAND_EN),
        }:
            return Plan(
                actions=(
                    Action(ActionKind.OPEN_APP, {"app_id": "notepad"}),
                    Action(
                        ActionKind.OPEN_URL,
                        {
                            "url": "https://github.com/Z3X-1337/rayluno",
                            "purpose": "site",
                        },
                    ),
                ),
                source=PlanSource.DEMO,
            )
        if normalized in {
            normalize_text(JUDGE_BLOCK_COMMAND_AR),
            normalize_text(JUDGE_BLOCK_COMMAND_EN),
        }:
            return Plan(
                actions=(
                    Action(
                        ActionKind.OPEN_URL,
                        {
                            "url": "https://github.com/Z3X-1337/rayluno",
                            "purpose": "judge_unregistered",
                        },
                    ),
                ),
                source=PlanSource.DEMO,
            )
        return self.fallback.plan(command)
