# Rayluno — Devpost Draft

## Title

Rayluno

## Tagline

A local-first bilingual personal agent that remembers only with consent and acts only with verifiable authorization.

## Category

Apps for Your Life

## One-line summary

Rayluno is an Arabic/English Windows personal agent that manages tasks, reminders, and explicit-consent memory, then performs bounded desktop actions through registered skills, plan-specific approval, write-ahead authorization, deterministic policy, and authenticated execution evidence.

## Inspiration

Personal AI agents usually fail at one of two extremes: they either chat without completing useful work, or receive broad tool access that is difficult to constrain, explain, and audit.

Rayluno explores a third path: the model may propose, but deterministic code decides what is permitted. Authorization is sealed before impact, and evidence is verified before the next action.

## What it does

Rayluno combines four product surfaces:

1. **Personal command center** — local tasks, scheduled reminders, snooze, one-time delivery, daily agenda, overdue counts, and a recommended focus item.
2. **Explicit-consent Memory Vault** — a fact is stored only after an explicit bilingual remember command. Ordinary conversation is not retained. Users can inspect every fact, delete one fact, or purge the vault through a protected confirmation flow.
3. **Verified execution** — operating-system effects must resolve to registered skill manifests with stable IDs, permissions, risk levels, purpose scope, and confirmation policy.
4. **Authenticated execution proof** — Rayluno persists an `execution_authorized` receipt before impact, records the outcome afterward, links receipts with SHA-256, and authenticates the chain head and receipt count using a per-installation HMAC checkpoint.

The desktop exposes the same state used by the runtime: skill IDs, permissions, risk, argument-key names, an installation-scoped HMAC fingerprint, approval expiry, Memory Vault state, authorization/outcome receipts, and chain integrity.

## How it works

```text
Voice or text
→ deterministic parser or optional local-model fallback
→ closed Plan(ActionKind, validated parameters, provenance)
→ registered Skill Manifest
→ expiring single-use confirmation when required
→ deterministic allowlist policy
→ receipt chain and HMAC checkpoint verification
→ persisted write-ahead authorization receipt
→ bounded operating-system effect
→ persisted outcome receipt and updated checkpoint
```

Rayluno exposes no shell, PowerShell, cmd, `eval`, or `exec` capability. A model response cannot directly invoke an operating-system primitive.

## Explicit-consent memory

Memory is local SQLite and opt-in by construction:

- only `تذكر أن…` / `Remember that…` commands write a fact;
- ordinary conversation is never passively persisted;
- every fact is labelled `user_explicit`;
- normalized fingerprints prevent duplicate-memory spam;
- passwords, PINs, PEM private keys, JWTs, provider tokens, recovery phrases, verification codes, and Luhn-valid payment-card numbers are refused;
- memory is not silently injected into model prompts in this release;
- delete-all requires a short-lived, single-use Python confirmation handle.

## Verified execution

The current registry contains bounded skills for browser search, website navigation, application launch, reading system time, and audio control.

Consequential model/demo proposals pause before effects. The desktop sends the exact server-generated `confirmation_id`, not a generic confirm command. The handle expires, is bound to the reviewed plan, and is consumed once. A wrong handle cannot consume the valid plan, and replay cannot cause a second side effect.

After approval, Rayluno must persist authorization proof before it calls the operating-system effect. If that proof cannot be sealed, no effect occurs.

## Execution receipts and authenticated checkpoint

The local JSONL ledger uses `rayluno.execution-receipt/v2` and records:

- confirmation requested, rejected, replaced, or expired;
- write-ahead execution authorization;
- execution completed, blocked, or failed;
- skill, permission, risk, decision state, and policy reason;
- safe action metadata and argument-key names;
- installation-scoped HMAC argument digest, previous hash, and current hash.

Before registered execution and before extending the journal, Rayluno validates every receipt and link, then compares the chain head and receipt count with an HMAC-authenticated local checkpoint. Malformed JSON, editing, reordering, journal deletion, truncation, rollback, missing checkpoint state, or checkpoint tampering pauses verified execution before the next effect.

Raw command text, URL query values, and confirmation capability handles are excluded from persisted audit details. Audit command fingerprints use installation-scoped HMAC-SHA256 rather than plain SHA-256.

## Honest security boundary

The local checkpoint is not a hardware-backed signature or a remote transparency log. A process running as the same operating-system user that can read the local HMAC key can forge local state. Deleting every local trust-state file cannot be distinguished from a clean installation without a hardware or remote witness. Local SQLite data is not application-encrypted in this release.

## Reproducible Judge Mode

No account, API key, local model, or external service is required for the core judge path.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e ".[dev,desktop,commercial]"
rayluno --ui --judge-demo
```

Judge Mode is visibly labelled scripted provenance through the production trust boundary. It also unlocks only the bounded voice/local-AI evaluation feature gates when optional dependencies are installed; it does not expand allowlists or expose arbitrary execution.

Controlled execution:

```text
prepare the judge demo
```

Rayluno previews the selected skills and pauses before any effect. Approving the exact plan seals authorization, executes only allowlisted effects, and records outcomes.

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
- design task, reminder, agenda, memory, skill, confirmation, authorization, and receipt boundaries;
- challenge unsafe alternatives such as unrestricted shell access and generic confirmation commands;
- implement bilingual behavior, RTL/LTR support, and accessibility contracts;
- build the Windows/Ubuntu and Python 3.11/3.13 CI matrix;
- diagnose failures from JUnit and Ruff artifacts rather than suppressing checks;
- replace plain fingerprints with installation-scoped HMAC fingerprints;
- design write-ahead authorization and an authenticated receipt checkpoint;
- create adversarial tests for passive-memory prevention, structured-secret refusal, replay, expiry, invalid handles, deletion, truncation, rollback, privacy, and journal corruption;
- shape the judge path around claims the product can prove.

Key decisions made with Codex/GPT-5.6:

1. Reject unrestricted shell access in favor of bounded skills.
2. Route common commands deterministically before optional model fallback.
3. Treat model output as untrusted proposed data.
4. Bind approval to one reviewed plan and a short time window.
5. Seal authorization before effect.
6. Preserve auditability without retaining raw sensitive content.
7. Stop execution when trust evidence fails validation.
8. Make personal memory explicit, inspectable, local, and deletable.
9. Label Judge Mode honestly as scripted provenance, not model inference.

GPT-5.6 is not granted direct runtime control over the operating system.

## Challenges

The central engineering challenge was making useful action compatible with a trust boundary that remains understandable under adversarial conditions. A confirmation dialog alone is insufficient if it authorizes changed intent, can be replayed, or permits an effect before evidence is durable.

The second challenge was proving local integrity without overstating it. Rayluno now detects common editing, deletion, truncation, and rollback cases with an authenticated local checkpoint, while documenting that a fully compromised same-user context still requires hardware or remote witnessing.

The memory challenge was preventing personalization from becoming invisible profile building. Rayluno therefore has no passive write path and refuses structured secret material even when explicitly requested.

## Accomplishments

- Arabic/English personal command center.
- Persistent local tasks, reminders, and daily agenda.
- Explicit-consent Memory Vault with structured-secret refusal and protected purge.
- Registered skill manifests and deterministic allowlists.
- Expiring, plan-specific, single-use approval handles.
- Write-ahead authorization persisted before effects.
- Full-chain verification plus HMAC-authenticated checkpoint.
- Fail-closed behavior on unknown skills, deletion, truncation, rollback, or ledger corruption.
- Reproducible no-key Judge Mode.
- MIT-licensed public repository.
- **448 automated tests** across Windows and Ubuntu, Python 3.11 and 3.13.
- Ruff lint, Ruff formatting, and Python compilation checks in CI.

## What we learned

A personal agent should not be evaluated only by how many tools it can call. The more meaningful questions are whether users can understand what will happen, stop it before impact, prove that authorization preceded the effect, inspect what happened afterward, and detect when the proof is no longer trustworthy.

Local-first is also not enough by itself. Local data can still be collected invisibly, and local evidence can still be modified. Consent, deletion, authorization ordering, and integrity verification must be architectural properties.

## What is next

Future work includes rebuilding bounded multi-step workflows on the current contracts, DPAPI or hardware-backed key protection, remotely witnessed checkpoints, encrypted local data, additional registered skills, packaged test builds, and broader Windows accessibility testing.

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

## Submission fields

- Codex `/feedback` Session ID: `019f4f59-682c-78c2-beeb-75f49ca0c808`
- Public YouTube demo URL: pending final edited video.
- Final Devpost submission: pending explicit approval before submission.
