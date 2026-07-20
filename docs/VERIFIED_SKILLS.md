# Verified Skills and Execution Receipts

Rayluno treats natural-language input and model output as untrusted proposals. A proposal cannot directly invoke an operating-system primitive. It must resolve to a registered skill and pass the existing safety policy immediately before the side effect.

## Execution boundary

```text
User request
→ deterministic or local-model plan
→ registered SkillManifest
→ permission and risk assessment
→ confirmation boundary when required
→ existing allowlist SafetyPolicy
→ bounded system effect
→ hash-chained ExecutionReceipt
```

## Manifest contract

Every executable skill declares:

- a stable `skill_id`;
- one action kind and optional purpose scope;
- a human-readable permission;
- a risk level;
- a confirmation policy.

Unregistered actions fail closed.

## Confirmation policy

The initial registry distinguishes trusted deterministic parsing from local-model proposals. A deterministic request that maps exactly to a known command can proceed under the existing allowlists. A medium-impact action proposed by the model pauses before any side effect and displays:

- skill ID;
- required permission;
- risk level;
- explicit confirm/cancel instructions.

Confirmation is one-time and applies atomically to the pending plan. Cancellation performs no action. Entering a new command invalidates the old pending confirmation so a later “confirm” cannot execute stale intent.

## Execution receipts

Each attempted registered skill produces a local JSONL receipt containing:

- receipt ID and UTC timestamp;
- skill ID, permission, and risk;
- completed, blocked, or failed status;
- policy reason;
- privacy-aware action summary;
- previous receipt hash and current receipt hash.

The chain is tamper-evident, not a digital signature. Editing, deleting, or reordering receipts breaks the hash linkage. URL query values are not written to the receipt; only safe metadata such as the host, path, and query-key names is retained.

Default path:

```text
~/.future_assistant/execution-receipts.jsonl
```

The ledger remains local and is disabled when the audit path is disabled.

## Initial registry

| Skill | Permission | Risk | Confirmation |
|---|---|---:|---|
| `web.search` | `network.browser.search` | medium | model-proposed |
| `web.navigate` | `network.browser.navigate` | medium | model-proposed |
| `application.launch` | `applications.launch` | medium | model-proposed |
| `system.time.read` | `system.time.read` | low | never |
| `system.audio.control` | `system.audio.control` | low | model-proposed |

## Judge demonstration

1. Give Rayluno an ambiguous natural request that uses the local model to select an application or website.
2. Rayluno pauses and shows the chosen skill, permission, and risk before changing the system.
3. Say `تأكيد` or `confirm`.
4. Rayluno executes through the allowlisted effect and returns a compact receipt ID.
5. Show the local activity surface or JSONL ledger to prove the action and its hash link.

This demonstrates the core product claim: Rayluno is capable because it composes bounded skills, not because it grants an unrestricted shell to a language model.
