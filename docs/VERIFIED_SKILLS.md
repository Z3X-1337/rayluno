# Verified Skills and Authenticated Execution Receipts

Rayluno treats natural-language input and model output as untrusted proposals. A proposal cannot directly invoke an operating-system primitive. It must resolve to a registered skill, pass deterministic policy, and—when consequential—survive a short-lived, single-use confirmation boundary.

## Execution boundary

```text
User request
→ deterministic parser or optional local-model proposal
→ closed Plan with explicit provenance
→ registered SkillManifest
→ permission and risk assessment
→ expiring confirmation handle when required
→ deterministic allowlist SafetyPolicy
→ receipt chain and authenticated-checkpoint verification
→ persisted write-ahead authorization receipt
→ bounded system effect
→ persisted outcome receipt and checkpoint advancement
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

A medium-impact action proposed by the local model or Judge Mode pauses before execution. Python creates a random `confirmation_id` and retains the full pending plan in memory. The UI receives only review metadata:

- skill IDs;
- required permissions;
- risk levels;
- creation and expiry timestamps;
- argument-key names;
- an installation-scoped HMAC-SHA256 fingerprint of the arguments.

The raw command, raw argument values, and local HMAC key are not sent to the confirmation surface. The confirmation capability handle is shown to the trusted desktop bridge for that plan but is excluded from persisted audit details.

The default handle lifetime is 45 seconds and is bounded between 1 and 300 seconds. Approval and rejection consume the pending handle once. A mismatched handle cannot consume the valid plan. A new command invalidates the older pending plan, and an expired plan cannot execute.

Voice confirmation remains available for the local voice path. The desktop UI uses the exact server-generated handle rather than sending a generic command such as `confirm`.

## Write-ahead authorization

Approval alone does not cause an operating-system effect. Before calling the effect adapter, Rayluno persists an `execution_authorized` receipt for every action in the closed plan.

- If authorization proof cannot be persisted, no side effect occurs.
- After effects run, Rayluno writes separate outcome receipts.
- If an outcome receipt cannot be sealed after an effect, the runtime reports an error and pauses future verified execution because the checkpoint and journal no longer agree.

This ordering makes the evidence lifecycle explicit: **proposal → decision → durable authorization → effect → outcome**.

## Receipt schema v2

The local JSONL ledger uses:

```text
rayluno.execution-receipt/v2
```

Rayluno records the complete trust lifecycle:

- `confirmation_requested`;
- `confirmation_rejected`;
- `confirmation_replaced`;
- `confirmation_expired`;
- `execution_authorized`;
- `execution`.

Each receipt contains:

- random receipt ID and UTC timestamp;
- event, skill, permission, and risk;
- authorized, completed, blocked, cancelled, pending, expired, or failed status;
- confirmation state and policy reason;
- privacy-aware action summary;
- argument-key names and an installation-scoped HMAC argument digest;
- previous receipt hash and current receipt hash.

URL query values, raw command text, and confirmation handles are excluded from receipt summaries.

## Chain and checkpoint verification

The first receipt links to a fixed genesis hash. Before registered execution and before extending the journal, Rayluno:

1. reloads every JSONL record;
2. validates the receipt schema;
3. recomputes every receipt hash;
4. verifies every `previous_hash` link;
5. loads a local checkpoint containing the expected receipt count and chain head;
6. authenticates the checkpoint with a per-installation HMAC key;
7. compares stored and computed values in constant time.

The runtime fails closed on malformed JSON, receipt editing, reordering, journal deletion, truncation, rollback, a missing checkpoint/key combination, or checkpoint tampering. The desktop changes from **Verified** to **Trust paused**, and the Receipt Inspector displays **INTEGRITY FAILED**.

## Honest boundary

This mechanism is stronger than an unkeyed hash chain, but it is not a hardware-backed signature or a remote transparency log.

- A process running as the same operating-system user that can read the HMAC key can forge local journal and checkpoint state.
- Deleting every trust-state file cannot be distinguished from a clean installation without a hardware or remote witness.
- Restrictive local file permissions are applied where the platform supports them, but the HMAC key is not yet hardware-backed or DPAPI-protected.

Future work can add DPAPI or TPM-backed key protection and remotely witnessed checkpoints.

## Desktop product surface

The compact Today panel remains visible. Verified Execution adds:

- a top-bar trust indicator;
- a bilingual confirmation dialog;
- expiry countdown;
- multi-skill plan review;
- HMAC argument fingerprint;
- explicit Approve and Reject controls;
- a Receipt Inspector with authorization/outcome events, chain status, head hash, and safe metadata.

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

The dialog shows the exact skills, permissions, risks, HMAC fingerprint, and expiry. Approval consumes the exact handle, seals write-ahead authorization, executes only the allowlisted plan, and records outcomes. Opening **Verified** shows the authenticated chain.

Fail-closed scenario:

```text
اختبر رفض مهارة غير مسجلة
```

The plan is rejected before any side effect because it does not resolve to a registered skill.

For a side-effect-free review:

```powershell
rayluno --ui --judge-demo --dry-run
```
