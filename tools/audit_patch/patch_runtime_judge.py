from __future__ import annotations

from common import read, replace_once, write


NEW_EXECUTE = '''    def _execute(
        self,
        command: str,
        language: Language,
        plan: Plan,
        assessments: tuple[SkillAssessment, ...],
        *,
        confirmed: bool,
    ) -> RuntimeResult:
        if not self.receipt_integrity_ok:
            return RuntimeResult(
                RuntimeStatus.BLOCKED,
                self._integrity_failure_message(language),
                plan,
            )
        confirmation_state = "approved" if confirmed else "not_required"
        authorization_receipts: list[ExecutionReceipt] = []
        try:
            for assessment, action in zip(assessments, plan.actions, strict=True):
                authorization_receipts.append(
                    self.receipt_ledger.record(
                        assessment,
                        ExecutionResult(action, False, "execution_authorized"),
                        event="execution_authorized",
                        confirmation_state=confirmation_state,
                        status_override="authorized",
                    )
                )
        except ReceiptIntegrityError:
            self.last_receipts = tuple(authorization_receipts)
            return RuntimeResult(
                RuntimeStatus.BLOCKED,
                self._authorization_failure_message(language),
                plan,
            )

        executions = tuple(
            self.runtime.executor.execute(action, command, language) for action in plan.actions
        )
        outcome_receipts: list[ExecutionReceipt] = []
        try:
            for assessment, execution in zip(assessments, executions, strict=True):
                outcome_receipts.append(
                    self.receipt_ledger.record(
                        assessment,
                        execution,
                        event="execution",
                        confirmation_state=confirmation_state,
                    )
                )
        except ReceiptIntegrityError:
            self.last_receipts = tuple(authorization_receipts + outcome_receipts)
            return RuntimeResult(
                RuntimeStatus.ERROR,
                self._receipt_write_failure_message(language),
                plan,
                executions,
            )
        self.last_receipts = tuple(authorization_receipts + outcome_receipts)
        successes = sum(result.ok for result in executions)
        blocked = sum(result.blocked for result in executions)
        if successes == len(executions):
            status = RuntimeStatus.COMPLETED
        elif blocked == len(executions):
            status = RuntimeStatus.BLOCKED
        elif successes:
            status = RuntimeStatus.PARTIAL
        else:
            status = RuntimeStatus.ERROR
        message = " ".join(result.message for result in executions)
        if confirmed and self.last_receipts:
            message = f"{message} {self._receipt_message(self.last_receipts[-1], language)}"
        return RuntimeResult(status, message, plan, executions)
'''


def patch_runtime() -> None:
    path = "src/future_assistant/verified_runtime.py"
    replace_once(
        path,
        "                f\"risk:{first.manifest.risk.value};\"\n"
        "                f\"confirmation:{pending.confirmation_id}\"\n",
        "                f\"risk:{first.manifest.risk.value}\"\n",
        marker="f\"risk:{first.manifest.risk.value}\"",
    )
    text = read(path)
    start = text.index("    def _execute(\n")
    end = text.index("\n    def _new_pending(\n", start)
    if "execution_authorized" not in text[start:end]:
        write(path, text[:start] + NEW_EXECUTE + text[end:])
    replace_once(
        path,
        "    @staticmethod\n"
        "    def _receipt_write_failure_message(language: Language) -> str:\n",
        "    @staticmethod\n"
        "    def _authorization_failure_message(language: Language) -> str:\n"
        "        if language is Language.EN:\n"
        "            return \"No action was executed because authorization proof could not be sealed.\"\n"
        "        return \"لم يُنفّذ أي إجراء لأن تعذّر ختم إثبات التصريح بالتنفيذ.\"\n\n"
        "    @staticmethod\n"
        "    def _receipt_write_failure_message(language: Language) -> str:\n",
        marker="def _authorization_failure_message",
    )


def patch_judge_mode() -> None:
    path = "src/future_assistant/cli.py"
    replace_once(
        path,
        "    def has_feature(feature: str) -> bool:\n"
        "        return bool(entitlements and entitlements.has_feature(feature))\n",
        "    judge_features = frozenset({\"ai.local\", \"automation.pro\", \"voice.local\"})\n\n"
        "    def has_feature(feature: str) -> bool:\n"
        "        if args.judge_demo and feature in judge_features:\n"
        "            return True\n"
        "        return bool(entitlements and entitlements.has_feature(feature))\n",
        marker="judge_features = frozenset",
    )
    replace_once(
        path,
        "                debug=args.debug_ui,\n"
        "            )\n",
        "                debug=args.debug_ui,\n"
        "                judge_mode=args.judge_demo,\n"
        "            )\n",
        marker="judge_mode=args.judge_demo",
    )

    path = "src/future_assistant/ui/window.py"
    replace_once(
        path,
        "        ai_report_page_opener: Callable[[str], bool] | None = None,\n"
        "    ) -> None:\n",
        "        ai_report_page_opener: Callable[[str], bool] | None = None,\n"
        "        judge_mode: bool = False,\n"
        "    ) -> None:\n",
        marker="judge_mode: bool = False",
    )
    replace_once(
        path,
        "        self._ai_report_page_opener = ai_report_page_opener or webbrowser.open_new_tab\n"
        "        self._window: Any | None = None\n",
        "        self._ai_report_page_opener = ai_report_page_opener or webbrowser.open_new_tab\n"
        "        self._judge_mode = bool(judge_mode)\n"
        "        self._window: Any | None = None\n",
        marker="self._judge_mode = bool(judge_mode)",
    )
    replace_once(
        path,
        "        status[\"activation_configured\"] = self._online_activation_available\n"
        "        status[\"refresh_available\"] = self._refresh_state_available\n",
        "        status[\"activation_configured\"] = self._online_activation_available\n"
        "        status[\"refresh_available\"] = self._refresh_state_available\n"
        "        status[\"judge_mode\"] = self._judge_mode\n",
        marker="status[\"judge_mode\"]",
    )
    replace_once(
        path,
        "        if self._entitlements is None:\n"
        "            return False\n"
        "        try:\n"
        "            return self._entitlements.has_feature(feature)\n",
        "        if self._judge_mode and feature in {\"ai.local\", \"automation.pro\", \"voice.local\"}:\n"
        "            return True\n"
        "        if self._entitlements is None:\n"
        "            return False\n"
        "        try:\n"
        "            return self._entitlements.has_feature(feature)\n",
        marker="if self._judge_mode and feature in",
    )
    text = read(path)
    start = text.index("def start_desktop(\n")
    end = text.index('    \"\"\"Start the lightweight native WebView', start)
    signature = text[start:end]
    if "judge_mode: bool = False" not in signature:
        signature = signature.replace(
            "    debug: bool = False,\n) -> None:\n",
            "    debug: bool = False,\n    judge_mode: bool = False,\n) -> None:\n",
        )
        text = text[:start] + signature + text[end:]
        write(path, text)
    replace_once(
        path,
        "        activation_state_store=activation_state_store,\n"
        "    )\n",
        "        activation_state_store=activation_state_store,\n"
        "        judge_mode=judge_mode,\n"
        "    )\n",
        marker="judge_mode=judge_mode",
    )


def patch_ui_status() -> None:
    path = "src/future_assistant/ui/verified_v2.js"
    replace_once(
        path,
        '      succeeded: "مكتمل",\n',
        '      succeeded: "مكتمل",\n      authorized: "مصرّح",\n',
        marker='authorized: "مصرّح"',
    )
    replace_once(
        path,
        '      succeeded: "Completed",\n',
        '      succeeded: "Completed",\n      authorized: "Authorized",\n',
        marker='authorized: "Authorized"',
    )
    replace_once(
        path,
        '      completed: "succeeded",\n',
        '      completed: "succeeded",\n      authorized: "authorized",\n',
        marker='authorized: "authorized"',
    )


def main() -> None:
    patch_runtime()
    patch_judge_mode()
    patch_ui_status()


if __name__ == "__main__":
    main()
