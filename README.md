# Rayluno — A local-first personal agent with verifiable execution

Rayluno is an Arabic/English Windows personal agent that organizes a user's day, stores only explicitly approved memory, and performs bounded desktop actions without granting a language model unrestricted operating-system access.

> The model may propose. Deterministic code decides what is permitted, records authorization before impact, and verifies the evidence before the next action.

**OpenAI Build Week category:** Apps for Your Life  
**Primary platform:** Windows x64  
**Interface languages:** Arabic and English  
**License:** MIT

## Why Rayluno

Personal assistants often sit at one of two unsafe extremes:

1. they chat but cannot complete meaningful work; or
2. they receive broad tool or shell access that is difficult to constrain, explain, and audit.

Rayluno takes a third path. Natural-language input becomes a closed action plan. An action must resolve to a registered skill manifest, pass deterministic policy, request plan-specific approval when consequential, persist authorization proof before impact, and produce a locally verifiable outcome receipt.

## What works

- Arabic and English text commands.
- Local wake-word, speech-to-text, and text-to-speech paths for Windows.
- Persistent local tasks, reminders, snooze, completion, and one-time delivery.
- A daily agenda with overdue work, today's commitments, next reminder, and recommended focus.
- An explicit-consent Personal Memory Vault stored in local SQLite.
- Secret refusal for passwords, PINs, private keys, JWTs, provider tokens, recovery phrases, verification codes, and Luhn-valid payment-card numbers.
- Safe application launching, website navigation, search, time reporting, and volume control.
- Deterministic-first routing with optional local Ollama fallback.
- Registered skill manifests with permission, risk, purpose scope, and confirmation policy.
- Expiring, plan-specific, single-use confirmation handles generated and validated in Python.
- Installation-scoped HMAC-SHA256 fingerprints instead of reversible raw command storage.
- Write-ahead `execution_authorized` receipts persisted before operating-system effects.
- Privacy-aware `rayluno.execution-receipt/v2` records linked by SHA-256.
- A per-installation HMAC-authenticated checkpoint for chain head and receipt count.
- Fail-closed detection for malformed entries, editing, reordering, journal deletion, truncation, rollback, missing checkpoint state, or checkpoint tampering.
- A visible confirmation gate, trust indicator, Memory Vault, and Execution Receipt Inspector.
- A reproducible Judge Mode requiring no model, API key, account, or external service for the core demo.

## Three-minute judge path

### 1. Install

Windows with Python 3.11 or newer:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e ".[dev,desktop,commercial]"
```

### 2. Launch

```powershell
rayluno --ui --judge-demo
```

Judge Mode is explicitly labelled scripted provenance through the real production trust boundary. It does **not** claim that scripted output came from a model. Judge Mode also unlocks the bounded local voice and local-AI feature gates for evaluation when their optional dependencies are installed; it does not unlock arbitrary or unknown capabilities.

### 3. Demonstrate explicit memory

Enter ordinary conversation:

```text
أنا أفضل الردود المختصرة
```

Then ask:

```text
ماذا تتذكر عني
```

Nothing is stored. Now explicitly approve a memory:

```text
تذكر أنني أفضل الردود المختصرة
```

Open **Memory**. The fact is visible, labelled `user_explicit`, stored locally, and individually deletable. Memory is not silently inserted into model prompts in this release.

### 4. Demonstrate controlled execution

Enter:

```text
جهز عرض الحكام
```

or:

```text
prepare the judge demo
```

Rayluno performs no side effect immediately. The confirmation gate displays:

- every selected `Skill ID`;
- required permissions and risk levels;
- argument-key names and an installation-scoped HMAC-SHA256 fingerprint;
- a visible expiry countdown;
- explicit Approve and Reject controls.

The desktop sends the exact server-generated `confirmation_id`, not a generic confirm command. Approval consumes the handle once. Before any operating-system effect, Rayluno persists an `execution_authorized` receipt. It then executes only allowlisted effects and records the outcome separately.

Open **Verified** to inspect the complete receipt chain, authorization/outcome lifecycle, current chain head, and integrity state.

### 5. Demonstrate fail-closed behavior

Enter:

```text
اختبر رفض مهارة غير مسجلة
```

or:

```text
test an unregistered skill
```

The proposed action is rejected before any effect because it does not resolve to a registered skill.

### Side-effect-free review

```powershell
rayluno --ui --judge-demo --dry-run
```

This exercises planning, confirmation, policy, memory, write-ahead authorization, receipts, and the interface without opening applications or websites.

## Trust architecture

```text
Voice or text request
        │
        ▼
Deterministic parser ── optional local-model fallback
        │
        ▼
Closed Plan(ActionKind, validated parameters, provenance)
        │
        ▼
Registered Skill Manifest
  ├─ stable Skill ID
  ├─ permission
  ├─ risk level
  ├─ parameter purpose scope
  └─ confirmation policy
        │
        ▼
Expiring single-use confirmation handle when required
        │
        ▼
Deterministic SafetyPolicy allowlists
  ├─ allowed URL schemes and domains
  ├─ allowed application IDs
  ├─ bounded query and URL lengths
  └─ no shell, PowerShell, cmd, eval, or exec
        │
        ▼
Verify receipt chain + HMAC-authenticated checkpoint
        │
        ▼
Persist write-ahead execution authorization
        │
        ▼
Bounded operating-system effect
        │
        ▼
Persist outcome receipt and advance authenticated checkpoint
```

## Personal Memory Vault

Memory is opt-in by construction:

- only explicit bilingual remember commands write a fact;
- ordinary conversation is never passively persisted;
- every fact is marked `user_explicit`;
- normalized SHA-256 fingerprints prevent duplicate-memory spam;
- structured credential patterns and Luhn-valid payment-card numbers are refused;
- internal fingerprints and hidden model context are not exposed to the interface;
- users can inspect and delete individual facts;
- delete-all requires a short-lived, single-use Python confirmation handle;
- invalid or replayed purge handles fail closed;
- memory content stays out of the command audit log;
- memory is not silently inserted into model prompts in this milestone.

Default storage is local SQLite under the Rayluno application-data directory. It can be redirected with `RAYLUNO_MEMORY_PATH`.

## Verified skills

| Skill ID | Permission | Risk | Confirmation |
|---|---|---:|---|
| `web.search` | `network.browser.search` | Medium | Model/demo proposal |
| `web.navigate` | `network.browser.navigate` | Medium | Model/demo proposal |
| `application.launch` | `applications.launch` | Medium | Model/demo proposal |
| `system.time.read` | `system.time.read` | Low | Never |
| `system.audio.control` | `system.audio.control` | Low | Model/demo proposal |

Unregistered actions fail closed. A new command invalidates older pending intent. A mismatched handle cannot consume a valid plan, an expired handle cannot execute, and a consumed handle cannot cause a second side effect.

## Execution receipts and authenticated checkpoint

The JSONL ledger uses:

```text
rayluno.execution-receipt/v2
```

It records:

- confirmation requested, rejected, replaced, or expired;
- write-ahead execution authorization;
- execution completed, blocked, or failed;
- skill, permission, risk, confirmation state, and policy reason;
- safe action metadata and argument-key names;
- installation-scoped HMAC argument digest, previous hash, and current hash.

Before registered execution and before extending the journal, Rayluno reloads the complete ledger, validates the schema, recomputes every receipt hash, verifies every link, and compares the chain head and receipt count with a per-installation HMAC-authenticated checkpoint. A failure pauses verified execution before the next effect.

Raw command text, URL query values, and confirmation capability handles are excluded from persisted audit details. Command audit fingerprints are installation-scoped HMAC-SHA256 values rather than plain SHA-256 hashes.

Default paths are derived from the Rayluno application-data directory. Sensitive files receive restrictive local permissions where the platform supports them.

## Honest security boundary

The local HMAC checkpoint is stronger than an unkeyed hash chain, but it is not a hardware-backed signature or a remote transparency log.

- A process running as the same operating-system user that can read the local HMAC key can forge local state.
- Deleting every local trust-state file cannot be distinguished from a clean installation without a hardware or remote witness.
- Local SQLite data is not application-encrypted in this release.
- Current development installers are not Authenticode-signed production builds.

Future work includes DPAPI or hardware-backed key protection, remotely witnessed checkpoints, and encrypted local data. Rayluno states these limits directly rather than claiming impossible local-only guarantees.

## How Codex and GPT-5.6 were used

Codex powered by GPT-5.6 was the primary engineering collaborator for this Build Week project. It was used to:

- audit the imported baseline before modifying `main`;
- decompose the product into reviewable pull requests;
- design task, reminder, agenda, memory, skill, confirmation, authorization, receipt, and update boundaries;
- implement bilingual behavior, RTL/LTR support, and accessibility contracts;
- build the Windows/Ubuntu and Python 3.11/3.13 CI matrix;
- diagnose failures from JUnit and Ruff artifacts instead of suppressing checks;
- adversarially review model-to-system and memory-consent boundaries;
- design single-use confirmation handles and stale-intent invalidation;
- replace plain fingerprints with installation-scoped HMAC fingerprints;
- introduce write-ahead authorization before side effects;
- add authenticated checkpoint and rollback/truncation tests;
- create tests for passive-memory prevention, structured-secret refusal, purge replay, confirmation replay, expiry, privacy, and journal corruption;
- shape the judge path around claims the product can prove.

Key decisions made with Codex/GPT-5.6:

1. **No unrestricted shell.** Broad execution was rejected in favor of bounded skills.
2. **Deterministic first.** Common commands do not require a model.
3. **Model output is untrusted.** A proposed action must resolve to a manifest and pass policy.
4. **Approval is plan-specific and time-bounded.** A generic UI confirmation is insufficient.
5. **Authorization precedes impact.** The system seals intent before performing an effect.
6. **Receipts minimize sensitive data.** Auditability does not justify retaining raw user content.
7. **Integrity failure stops execution.** Evidence is not useful if corruption is ignored.
8. **Memory is explicit and inspectable.** Local-first must not become invisible profile building.
9. **Judge Mode is honest.** Scripted reproducibility is labelled and never presented as model inference.

GPT-5.6 is not granted direct runtime control over the operating system.

## Development and verification

```powershell
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m compileall -q src
```

The audited release passes **448 automated tests** across:

- Windows and Ubuntu;
- Python 3.11 and Python 3.13;
- unit, integration, localization, privacy, memory, confirmation, authorization-before-effect, expiry, replay, UI-contract, structured-secret, deletion, truncation, rollback, HMAC checkpoint, and tamper tests;
- Ruff lint and formatting;
- Python compilation.

Useful commands:

```powershell
rayluno --doctor
rayluno --once "يا رايلونو كم الساعة" --dry-run --no-audit
rayluno --ui --judge-demo
```

## Optional local voice and AI

Rayluno supports local wake-word detection, local speech recognition, Windows text-to-speech, and optional Ollama fallback. Install the required local components before testing these paths:

```powershell
python -m pip install -e ".[voice]"
.\scripts\install-arabic-wake-model.ps1 -SetUserEnvironment
ollama pull qwen3.5:4b
rayluno --ui --judge-demo --ollama
```

Judge Mode bypasses only the bounded evaluation feature gates; it does not install dependencies, expose a shell, expand allowlists, or grant unknown permissions.

## Documentation

- [Pre-submission security audit](docs/SECURITY_AUDIT_2026-07-20.md)
- [Devpost draft](docs/RAYLUNO_DEVPOST_DRAFT.md)
- [Verified Skills and Execution Receipts](docs/VERIFIED_SKILLS.md)
- [Security and privacy](docs/SECURITY_PRIVACY_AR.md)
- [Architecture](docs/ARCHITECTURE_AR.md)
- [Release readiness](docs/RELEASE_READINESS_AR.md)
- [Third-party notices](THIRD_PARTY_NOTICES.md)

## Repository history

The implementation was developed as reviewable pull requests:

1. Personal Task Core.
2. Reminders and Daily Agenda.
3. Today Command Center.
4. Verified Skills, Judge Mode, and execution receipts.
5. Verified Execution v2: expiring handles, full-chain integrity, and Receipt Inspector.
6. Explicit-consent Personal Memory Vault.
7. Security audit hardening: write-ahead authorization, HMAC checkpoint, keyed fingerprints, structured-secret refusal, and bounded Judge Mode evaluation access.

## License

Rayluno is released under the [MIT License](LICENSE).
