# Verified Skills and Execution Receipts

Rayluno treats natural-language input and model output as untrusted proposals. A proposal cannot directly invoke an operating-system primitive. It must resolve to a registered skill, pass deterministic policy, and—when consequential—survive a short-lived, single-use confirmation boundary.

## Execution boundary

```text
User request
→ deterministic parser or optional local-model proposal
→ closed Plan with explicit provenance
→ registered SkillManifest
→ permission and risk assessment
→ expiring confirmation handle when required
→ existing allowlist SafetyPolicy
→ bounded system effect
→ verified, hash-linked ExecutionReceipt
```

## Manifest contract

Every executable skill declares:

- a stable `skill_id`;
- one action kind and optional purpose scope;
- a human-readable permission;
- a risk level;
- a confirmation policy.

Unregistered actions fail closed before side effects.

## Confirmation lifecycle

A medium-impact action proposed by the local model or Judge Mode pauses before execution. Python creates a random `confirmation_id` and retains the full pending plan in memory. The UI receives only safe review metadata:

- skill IDs;
- required permissions;
- risk levels;
- creation and expiry timestamps;
- argument-key names;
- a SHA-256 digest of the arguments.

Raw command text and raw argument values are not sent to the confirmation surface.

The default handle lifetime is 45 seconds and is bounded between 1 and 300 seconds. Approval and rejection consume the pending handle once. A mismatched handle cannot consume the valid pending plan. A new command invalidates the older pending plan, and an expired plan cannot execute.

Voice confirmation remains available for the local voice path. The desktop UI uses the exact server-generated handle rather than sending a generic text command such as `confirm`.

## Receipt schema v2

The local JSONL ledger uses schema:

```text
rayluno.execution-receipt/v2
```

Rayluno records the full trust lifecycle, not only successful execution:

- `confirmation_requested`;
- `confirmation_rejected`;
- `confirmation_replaced`;
- `confirmation_expired`;
- `execution`.

Each receipt contains:

- random receipt ID and UTC timestamp;
- event, skill, permission, and risk;
- completed, blocked, cancelled, pending, expired, or failed status;
- confirmation state and policy reason;
- privacy-aware action summary;
- argument-key names and an argument digest;
- previous receipt hash and current receipt hash.

URL query values and raw command text are excluded from receipt summaries.

## Full-chain integrity verification

The first receipt links to a fixed genesis hash. Before any registered execution and before extending the journal, Rayluno:

1. reloads every JSONL record;
2. validates the receipt schema;
3. recomputes every receipt hash;
4. verifies every `previous_hash` link;
5. compares stored and computed hashes in constant time.

Malformed JSON, editing, deletion, reordering, or an invalid hash marks the journal untrusted. Verified execution then pauses before side effects. The desktop surface changes from **Verified** to **Trust paused**, and the Receipt Inspector displays **INTEGRITY FAILED**.

Hash chaining is tamper-evident, not a digital signature. An attacker who can rewrite the entire journal and all hashes is outside this local-only threat model. Future work can add hardware-backed or remotely witnessed signatures.

Default path:

```text
~/.future_assistant/execution-receipts.jsonl
```

## Desktop product surface

The compact Today panel remains always visible. Verified Execution v2 adds:

- a top-bar trust indicator;
- a bilingual confirmation dialog;
- expiry countdown;
- multi-skill plan review;
- argument fingerprint;
- explicit Approve and Reject controls;
- a Receipt Inspector with chain status, head hash, event timeline, and safe metadata.

The interface reads the same Python runtime state used for execution. It is not a decorative mock.

## Initial registry

| Skill | Permission | Risk | Confirmation |
|---|---|---:|---|
| `web.search` | `network.browser.search` | medium | model/demo proposal |
| `web.navigate` | `network.browser.navigate` | medium | model/demo proposal |
| `application.launch` | `applications.launch` | medium | model/demo proposal |
| `system.time.read` | `system.time.read` | low | never |
| `system.audio.control` | `system.audio.control` | low | model/demo proposal |

## Judge demonstration

Launch:

```powershell
rayluno --ui --judge-demo
```

Controlled execution:

```text
جهز عرض الحكام
```

The dialog shows the exact skills, permissions, risks, fingerprint, and expiry. Approving the handle executes the allowlisted plan and adds execution receipts. Opening the trust indicator shows the verified chain.

Fail-closed scenario:

```text
اختبر رفض مهارة غير مسجلة
```

The plan is rejected before any side effect because it does not resolve to a registered skill.

For a side-effect-free review:

```powershell
rayluno --ui --judge-demo --dry-run
```
