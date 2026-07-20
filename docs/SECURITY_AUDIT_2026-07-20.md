# Rayluno security audit — 2026-07-20

## Scope

The pre-submission review covered planning, registered skills, operating-system effects, execution receipts, audit logs, tasks, reminders, explicit memory, the desktop bridge, local voice, licensing, activation, signed updates, CI, packaging, and Judge Mode.

## Remediation gates

1. Every external effect must have a persisted `execution_authorized` receipt first.
2. Receipt state must match a per-installation HMAC-authenticated checkpoint.
3. Journal deletion, truncation, rollback, anchor tampering, and missing trust state must fail closed.
4. Confirmation capability handles must never be persisted in audit details.
5. Command and argument fingerprints must use installation-scoped HMAC-SHA256.
6. Structured credentials, private keys, JWTs, and Luhn-valid payment cards must be rejected by Memory Vault.
7. Sensitive local state must receive restrictive permissions where supported.
8. Explicit Judge Mode may exercise bounded voice and local-AI paths without a paid license.

## Verification

The remediation branch is accepted only after the complete Windows/Ubuntu and Python 3.11/3.13 CI matrix passes, including the original suite and the new adversarial regression tests.

## Honest boundary

The authenticated local checkpoint is not a hardware-backed signature or a remote transparency log. Deleting every local trust-state file cannot be distinguished from a clean installation without a hardware or remote witness. Rayluno states this limitation rather than claiming impossible local-only guarantees.
