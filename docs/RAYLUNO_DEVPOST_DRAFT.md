# Rayluno — Devpost Draft

## Title

Rayluno

## Tagline

A local-first bilingual personal agent that can remember, plan, and act — with permission, confirmation, and verifiable proof.

## Category

Apps for Your Life

## One-line summary

Rayluno is an Arabic/English Windows personal agent that manages tasks, reminders, and explicit-consent memory, then performs bounded desktop actions through registered skills, expiring approval handles, deterministic policy, and tamper-evident execution receipts.

## Inspiration

Personal AI agents usually fail at one of two extremes: they either chat without completing useful work, or they receive broad tool access that is difficult to constrain, explain, and audit. A personal assistant should be able to act, but the user should remain the authority at every consequential boundary.

Rayluno explores a third path: the model may propose, but deterministic code decides what is permitted.

## What it does

Rayluno is a local-first Arabic and English Windows assistant with four connected product surfaces:

1. **Personal command center** — local tasks, scheduled reminders, snooze, one-time delivery, daily agenda, overdue counts, and a recommended focus item.
2. **Explicit-consent Memory Vault** — Rayluno stores a fact only after an explicit bilingual remember command. Ordinary conversation is not retained. Users can inspect every fact, delete one fact, or purge the vault through a protected confirmation flow.
3. **Verified execution** — operating-system effects must resolve to registered skill manifests with stable IDs, permissions, risk levels, parameter scope, and confirmation policy.
4. **Execution proof** — every registered decision and attempt produces a privacy-aware receipt linked to the previous record with SHA-256. Rayluno reloads and verifies the complete receipt chain before execution and pauses trust if corruption is detected.

The desktop interface exposes the same state used by the runtime: skill IDs, permissions, risk, argument-key names, a SHA-256 argument fingerprint, an expiry countdown, the exact plan-specific approval boundary, Memory Vault state, and receipt-chain integrity.

## How it works

A request follows this path:

```text
Voice or text
→ deterministic parser or optional local-model fallback
→ closed Plan(ActionKind, validated parameters, provenance)
→ registered Skill Manifest
→ expiring single-use confirmation when required
→ deterministic allowlist policy
→ full receipt-chain verification
→ bounded operating-system effect
→ privacy-aware ExecutionReceipt v2
```

Rayluno does not expose a shell, PowerShell, cmd, `eval`, or `exec` capability. A model response cannot directly invoke an operating-system primitive.

## Explicit-consent memory

Memory is local SQLite and opt-in by construction:

- only `تذكر أن…` / `Remember that…` style commands write a fact;
- ordinary conversation is never passively persisted;
- every fact is labelled `user_explicit`;
- normalized SHA-256 fingerprints prevent duplicate-memory spam;
- passwords, PINs, access tokens, API keys, private keys, recovery phrases, verification codes, and payment-card data are refused;
- internal fingerprints and hidden prompt context are never exposed to the interface;
- memory is not silently injected into model prompts in this release;
- delete-all requires a short-lived, single-use Python confirmation handle.

## Verified execution

The current registry contains bounded skills for:

- browser search;
- website navigation;
- application launch;
- reading system time;
- audio control.

Consequential model/demo proposals pause before effects. The desktop sends the exact server-generated `confirmation_id`, not a generic “confirm” command. The handle expires, is bound to the pending plan, and is consumed once. A wrong handle cannot consume the valid plan, and a replay cannot cause a second side effect.

## Execution receipts

The local JSONL ledger uses `rayluno.execution-receipt/v2` and records:

- confirmation requested, rejected, replaced, or expired;
- execution completed, blocked, or failed;
- skill, permission, risk, decision state, and policy reason;
- safe action metadata and argument-key names;
- argument digest, previous hash, and current hash.

Raw command text and URL query values are excluded from receipt summaries. Before execution and before extending the journal, Rayluno validates the schema, recomputes every hash, and verifies every link. Malformed JSON, editing, deletion, reordering, or a hash mismatch pauses verified execution before side effects.

Hash chaining is tamper-evident, not a hardware-backed or remotely witnessed signature.

## Reproducible judge mode

No account, API key, local model, or external service is required.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e ".[dev,desktop,commercial]"
rayluno --ui --judge-demo
```

Controlled execution:

```text
prepare the judge demo
```

Rayluno previews the selected skills and pauses before any side effect. Approving the exact plan executes only allowlisted effects and produces receipts.

Fail-closed scenario:

```text
test an unregistered skill
```

The proposed action is rejected before any effect because it does not resolve to a registered skill.

Side-effect-free review:

```powershell
rayluno --ui --judge-demo --dry-run
```

## How Codex and GPT-5.6 were used

Codex powered by GPT-5.6 was the primary engineering collaborator during Build Week. It was used to:

- audit the imported baseline before modifying `main`;
- decompose the implementation into reviewable pull requests;
- design task, reminder, agenda, memory, verified-skill, and receipt boundaries;
- challenge unsafe alternatives such as unrestricted shell access and generic confirmation commands;
- implement bilingual behavior, RTL/LTR support, and accessibility contracts;
- build the Windows/Ubuntu and Python 3.11/3.13 CI matrix;
- diagnose failures from JUnit and Ruff artifacts rather than suppressing checks;
- design expiring single-use handles, stale-intent invalidation, receipt-chain verification, and tamper fail-closed behavior;
- create adversarial tests for secret refusal, passive-memory prevention, replay, expiry, invalid handles, stale intent, privacy, and journal corruption;
- shape the judge path and documentation around claims the product can prove.

Key decisions made with Codex/GPT-5.6:

1. Reject unrestricted shell access in favor of bounded skills.
2. Route common commands deterministically before optional model fallback.
3. Treat model output as untrusted proposed data.
4. Bind approval to one reviewed plan and a short time window.
5. Preserve auditability without retaining raw sensitive content.
6. Stop execution when receipt integrity fails.
7. Make personal memory explicit, inspectable, local, and deletable.
8. Label Judge Mode honestly as scripted provenance through the real production boundary, not model inference.

GPT-5.6 is not granted direct runtime control over the operating system.

## Challenges

The central engineering challenge was combining useful personal-agent behavior with a boundary that remains understandable under adversarial conditions. A confirmation dialog alone is insufficient if it authorizes changed intent, can be replayed, or relies on an audit log the runtime never verifies.

The memory challenge was equally important: personalization should not become invisible profile building. Rayluno therefore has no passive write path and refuses likely secret material even when explicitly requested.

The product challenge was keeping these controls visible without turning the interface into a security console. Today, Memory, Verified Execution, and Receipt Inspector are separate but composed surfaces.

## Accomplishments

- Arabic/English personal command center.
- Persistent local tasks, reminders, and daily agenda.
- Explicit-consent Memory Vault with secret refusal and protected purge.
- Registered skill manifests and deterministic allowlists.
- Expiring, plan-specific, single-use approval handles.
- Full-chain receipt verification before effects.
- Fail-closed behavior on unregistered skills or ledger corruption.
- Reproducible no-key Judge Mode.
- MIT-licensed public repository.
- 434 automated tests across Windows and Ubuntu, Python 3.11 and 3.13.
- Ruff lint, Ruff formatting, and Python compilation checks in CI.

## What we learned

A personal agent should not be evaluated only by how many tools it can call. The more meaningful question is whether users can understand what will happen, stop it before impact, inspect what happened afterward, and detect when the proof itself is no longer trustworthy.

We also learned that local-first is not enough by itself. Local data can still be collected invisibly. Explicit consent and deletion semantics must be architectural properties, not privacy copy added after implementation.

## What is next

Future work includes rebuilding bounded multi-step workflows on the current Verified Execution v2 contracts, signed or remotely witnessed receipts, encrypted local data, additional registered skills, packaged test builds, and broader Windows accessibility testing.

## Built with

- Python 3.11+
- PyWebView
- SQLite
- HTML, CSS, and JavaScript
- OpenAI Codex
- GPT-5.6
- Ollama (optional local fallback)
- GitHub Actions
- Ruff
- Pytest

## Repository

https://github.com/Z3X-1337/rayluno

## Required fields still pending

- Public YouTube demo URL under three minutes.
- `/feedback` Codex Session ID for the primary Rayluno build thread.
- Final Devpost project/test URL if a packaged build or hosted demonstration is added.
