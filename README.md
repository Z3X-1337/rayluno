# Rayluno — A local-first personal agent with verifiable execution

Rayluno is an Arabic/English Windows personal agent that organizes a user's day, stores only explicitly approved memory, and performs bounded desktop actions without granting a language model unrestricted operating-system access.

> A useful personal agent should be able to remember and act, but every consequential action should be permission-scoped, reviewable, time-bounded, and independently auditable.

**OpenAI Build Week category:** Apps for Your Life  
**Primary platform:** Windows x64  
**Interface languages:** Arabic and English  
**License:** MIT

## The problem

Personal assistants usually sit at one of two unsafe extremes:

1. they only chat and cannot complete meaningful work; or
2. they can run broad tools that are difficult to constrain, explain, or audit.

Rayluno takes a third path. Natural-language input becomes a closed action plan. An action must match a registered skill manifest, satisfy deterministic allowlist policy, request plan-specific approval when consequential, and produce a locally verifiable receipt.

The model proposes. Deterministic code decides what is allowed.

## What works

- Arabic and English text commands.
- Local wake-word, speech-to-text, and text-to-speech paths for Windows.
- Persistent local tasks, reminders, snooze, completion, and one-time delivery.
- A daily agenda with overdue work, today's commitments, next reminder, and recommended focus.
- An explicit-consent Personal Memory Vault stored in local SQLite.
- Secret refusal for passwords, PINs, tokens, API/private keys, recovery phrases, verification codes, and payment-card data.
- Safe application launching, website navigation, search, time reporting, and volume control.
- Deterministic-first routing with optional local Ollama fallback.
- Registered skill manifests with permission, risk, purpose scope, and confirmation policy.
- Expiring, plan-specific, single-use confirmation handles generated and validated in Python.
- Privacy-aware `rayluno.execution-receipt/v2` records linked by SHA-256.
- Full receipt-chain verification before registered execution and before extending the journal.
- A visible confirmation gate, trust indicator, Memory Vault, and Execution Receipt Inspector.
- A reproducible Judge Mode requiring no model, API key, account, or external service.

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

Judge Mode is explicitly scripted provenance through the real production security boundary. It does **not** claim that scripted output came from a model.

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

Open **Memory**. The fact is visible, labelled `user_explicit`, stored locally, and individually deletable. Memory is not silently injected into model prompts in this release.

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
- argument-key names and a SHA-256 argument fingerprint;
- a visible expiry countdown;
- explicit Approve and Reject controls.

The UI sends the exact server-generated `confirmation_id`, not a generic confirm command. Approval consumes the handle once. Rayluno then executes only allowlisted effects and produces receipts.

Open the top-bar **Verified** indicator to inspect the complete receipt chain and current chain head.

### 5. Demonstrate fail-closed behavior

Enter:

```text
اختبر رفض مهارة غير مسجلة
```

or:

```text
test an unregistered skill
```

The action is rejected before any side effect because it does not resolve to a registered skill.

### Side-effect-free review

```powershell
rayluno --ui --judge-demo --dry-run
```

This exercises planning, confirmation, policy, memory, receipts, and the interface without opening applications or websites.

## Architecture

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
Full receipt-chain integrity verification
        │
        ▼
Bounded operating-system effect
        │
        ▼
Privacy-aware hash-linked ExecutionReceipt v2
```

## Personal Memory Vault

Memory is opt-in by construction:

- only explicit bilingual remember commands write a fact;
- ordinary conversation is never passively persisted;
- every fact is marked `user_explicit`;
- normalized SHA-256 fingerprints prevent duplicate-memory spam;
- internal fingerprints and hidden model context are not exposed to the interface;
- users can inspect and delete individual facts;
- delete-all requires a short-lived, single-use Python confirmation handle;
- invalid or replayed purge handles fail closed;
- memory content stays out of the command audit log;
- memory is not silently inserted into model prompts in this milestone.

Default storage is local SQLite under the Rayluno application-data directory. It can be redirected with `RAYLUNO_MEMORY_PATH`.

## Verified Skills

| Skill ID | Permission | Risk | Confirmation |
|---|---|---:|---|
| `web.search` | `network.browser.search` | Medium | Model/demo proposal |
| `web.navigate` | `network.browser.navigate` | Medium | Model/demo proposal |
| `application.launch` | `applications.launch` | Medium | Model/demo proposal |
| `system.time.read` | `system.time.read` | Low | Never |
| `system.audio.control` | `system.audio.control` | Low | Model/demo proposal |

Unregistered actions fail closed. A new command invalidates older pending intent. A mismatched handle cannot consume a valid plan, an expired handle cannot execute, and a consumed handle cannot cause a second side effect.

See [Verified Skills and Execution Receipts](docs/VERIFIED_SKILLS.md).

## Execution receipts

The JSONL ledger uses schema:

```text
rayluno.execution-receipt/v2
```

It records:

- confirmation requested, rejected, replaced, or expired;
- execution completed, blocked, or failed;
- skill, permission, risk, confirmation state, and policy reason;
- safe action metadata and argument-key names;
- argument digest, previous hash, and current hash.

Before registered execution and before appending a receipt, Rayluno reloads the full journal, validates the schema, recomputes every hash, and verifies every link. Malformed JSON, editing, deletion, reordering, or a hash mismatch pauses verified execution before side effects.

Raw command text and URL query values are excluded from receipt summaries.

Default path:

```text
~/.future_assistant/execution-receipts.jsonl
```

Hash chaining is tamper-evident, not a digital signature. Hardware-backed or remotely witnessed signatures are future work.

## How Codex and GPT-5.6 were used

Codex powered by GPT-5.6 was the primary engineering collaborator for this Build Week project. It was used to:

- audit the imported baseline before modifying `main`;
- decompose the product into reviewable pull requests;
- design task, reminder, agenda, memory, verified-skill, confirmation, and receipt boundaries;
- implement bilingual behavior, RTL/LTR support, and accessibility contracts;
- build the Windows/Ubuntu and Python 3.11/3.13 CI matrix;
- diagnose failures from JUnit and Ruff artifacts instead of suppressing checks;
- adversarially review model-to-system and memory-consent boundaries;
- design single-use confirmation handles and stale-intent invalidation;
- build full-chain receipt verification and tamper fail-closed tests;
- create tests for passive-memory prevention, secret refusal, purge replay, confirmation replay, expiry, privacy, and journal corruption;
- shape the judge path around claims the product can prove.

Key decisions made with Codex/GPT-5.6:

1. **No unrestricted shell.** Broad execution was rejected in favor of bounded skills.
2. **Deterministic first.** Common commands do not require a model.
3. **Model output is untrusted.** A proposed action must resolve to a manifest and pass policy.
4. **Approval is plan-specific and time-bounded.** A generic UI confirmation is insufficient.
5. **Receipts minimize sensitive data.** Auditability does not justify retaining raw user content.
6. **Integrity failure stops execution.** A receipt chain is not useful if corruption is ignored.
7. **Memory is explicit and inspectable.** Local-first must not become invisible profile building.
8. **Judge Mode is honest.** Scripted reproducibility is labelled and never presented as model inference.

GPT-5.6 is not granted direct runtime control over the operating system.

## Development and verification

```powershell
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m compileall -q src
```

The current release passes **434 automated tests** across:

- Windows and Ubuntu;
- Python 3.11 and Python 3.13;
- unit, integration, localization, privacy, memory, confirmation, expiry, replay, UI-contract, and tamper tests;
- Ruff lint and formatting;
- Python compilation.

Useful commands:

```powershell
rayluno --doctor
rayluno --once "يا رايلونو كم الساعة" --dry-run --no-audit
rayluno --ui
```

## Optional local voice and AI

Rayluno supports local wake-word detection, local speech recognition, Windows text-to-speech, and an optional Ollama fallback. These components are not required for Judge Mode.

```powershell
python -m pip install -e ".[voice]"
.\scripts\install-arabic-wake-model.ps1 -SetUserEnvironment
ollama pull qwen3.5:4b
rayluno --ui --ollama
```

Model and voice licenses must be reviewed independently before redistribution.

## Privacy and security boundaries

- Microphone samples are not written to disk by the normal voice path.
- Tasks, reminders, memory, settings, audit records, and receipts remain local by default.
- No usage telemetry is enabled by default.
- Web queries leave the device only when the user requests a web action.
- The client contains no private signing keys.
- Update and licensing components fail closed when verification fails.
- Current installers are development artifacts and are not Authenticode-signed production builds.

See:

- [Devpost draft](docs/RAYLUNO_DEVPOST_DRAFT.md)
- [Verified Skills and Execution Receipts](docs/VERIFIED_SKILLS.md)
- [Security and privacy](docs/SECURITY_PRIVACY_AR.md)
- [Architecture](docs/ARCHITECTURE_AR.md)
- [Release readiness](docs/RELEASE_READINESS_AR.md)
- [Third-party notices](THIRD_PARTY_NOTICES.md)

## Current limitations

- The polished desktop release targets Windows x64.
- The initial skill registry is intentionally small.
- Optional Ollama reasoning and full local voice require additional local dependencies.
- Local hash chaining is not equivalent to a hardware-backed or remotely witnessed signature.
- Local SQLite data is not application-encrypted in this release.
- The current installer is not a signed public production release.

## Repository history

The implementation was developed as reviewable pull requests:

1. Personal Task Core.
2. Reminders and Daily Agenda.
3. Today Command Center.
4. Verified Skills, Judge Mode, and execution receipts.
5. Verified Execution v2: expiring handles, full-chain integrity, and Receipt Inspector.
6. Explicit-consent Personal Memory Vault.

## License

Rayluno is released under the [MIT License](LICENSE).
