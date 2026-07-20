# Rayluno — A local-first personal agent with verifiable execution

Rayluno is an Arabic/English Windows assistant that organizes a user's day and executes bounded desktop skills without giving a language model unrestricted operating-system access.

> A useful personal agent should be able to act, but every action should be permission-scoped, reviewable, time-bounded, and independently auditable.

**OpenAI Build Week category:** Apps for Your Life  
**Primary platform:** Windows x64  
**Interface languages:** Arabic and English  
**License:** MIT

---

## The problem

Personal assistants usually sit at one of two unsafe extremes:

1. they only chat and cannot complete meaningful work; or
2. they can run broad shell or tool commands that are difficult to constrain, explain, and audit.

Rayluno takes a third path. Natural-language input becomes a closed action plan. An action must match a registered skill manifest, satisfy deterministic allowlist policy, request explicit approval when consequential, and produce a locally verifiable receipt.

The model proposes. Deterministic code decides what is allowed.

## What works

- Arabic and English text commands.
- Local wake-word, speech-to-text, and text-to-speech paths for Windows.
- Personal tasks stored in local SQLite.
- Relative and scheduled reminders, snooze, completion, and one-time delivery.
- A daily agenda with overdue work, today's commitments, next reminder, and recommended focus.
- Safe application launching, website navigation, search, time reporting, and volume control.
- Deterministic-first routing with optional local Ollama fallback.
- A bilingual desktop command center.
- Registered skill manifests with permission, risk, purpose scope, and confirmation policy.
- Expiring, single-use confirmation handles generated and validated in Python.
- Privacy-aware `rayluno.execution-receipt/v2` records linked by SHA-256.
- Full-chain verification before registered execution and before extending the journal.
- A visible confirmation gate, trust indicator, and Execution Receipt Inspector.
- A reproducible Judge Mode requiring no model, API key, account, or external service.

## Two-minute judge path

### 1. Install

Windows with Python 3.11 or newer:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e ".[dev,desktop,commercial]"
```

### 2. Launch the reproducible demo

```powershell
rayluno --ui --judge-demo
```

The flag enables explicitly scripted judge scenarios. It does **not** pretend scripted output came from a model; it exists so reviewers can exercise the real production security boundary without installing Ollama or configuring credentials.

### 3. Demonstrate controlled execution

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
- required permissions;
- risk levels;
- a SHA-256 argument fingerprint;
- a visible expiry countdown;
- explicit Approve and Reject controls.

The UI sends the exact server-generated `confirmation_id`, not a generic `confirm` command. Approval consumes the handle once. Rayluno then executes only allowlisted actions and produces execution receipts.

Open the top-bar **Verified** indicator to inspect the complete receipt chain and current chain head.

### 4. Demonstrate fail-closed behavior

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

This exercises planning, confirmation, policy, receipts, and the interface without opening applications or websites.

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
Verified Skill Registry
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
Existing SafetyPolicy allowlists
  ├─ allowed URL schemes and domains
  ├─ allowed application IDs
  ├─ bounded query and URL lengths
  └─ no shell, PowerShell, cmd, eval, or exec
        │
        ▼
Full receipt-chain integrity verification
        │
        ▼
Bounded system effect
        │
        ▼
Privacy-aware hash-linked ExecutionReceipt v2
```

## Verified Skills

| Skill ID | Permission | Risk | Confirmation |
|---|---|---:|---|
| `web.search` | `network.browser.search` | Medium | Model/demo proposal |
| `web.navigate` | `network.browser.navigate` | Medium | Model/demo proposal |
| `application.launch` | `applications.launch` | Medium | Model/demo proposal |
| `system.time.read` | `system.time.read` | Low | Never |
| `system.audio.control` | `system.audio.control` | Low | Model/demo proposal |

Unregistered actions fail closed. A new command invalidates older pending intent. A mismatched confirmation handle cannot consume a valid plan, an expired handle cannot execute, and a consumed handle cannot cause a second side effect.

See [Verified Skills and Execution Receipts](docs/VERIFIED_SKILLS.md).

## Confirmation security

Python retains the full pending plan in memory and exposes only safe review metadata:

- skill IDs, permissions, and risks;
- creation and expiry timestamps;
- argument-key names;
- a SHA-256 argument digest;
- the random confirmation handle required for that exact plan.

The default lifetime is 45 seconds and is bounded between 1 and 300 seconds. Rejection, replacement, and expiry are recorded without executing the plan. Voice confirmation remains supported for the local voice path; the desktop UI uses the specific server-generated handle.

## Execution receipts

The JSONL ledger uses schema:

```text
rayluno.execution-receipt/v2
```

It records the complete trust lifecycle:

- confirmation requested;
- confirmation rejected;
- pending intent replaced;
- confirmation expired;
- execution completed, blocked, or failed.

Each receipt contains a random ID, UTC timestamp, event, skill, permission, risk, confirmation state, policy reason, safe action summary, argument-key names, argument digest, previous hash, and current hash.

Before registered execution and before appending a receipt, Rayluno reloads the full journal, validates the schema, recomputes every hash, and verifies every link. Malformed JSON, editing, deletion, reordering, or a hash mismatch pauses verified execution before side effects. The interface changes to **Trust paused** and the Receipt Inspector displays **INTEGRITY FAILED**.

Raw command text and URL query values are excluded from receipt summaries.

Default path:

```text
~/.future_assistant/execution-receipts.jsonl
```

Hash chaining is tamper-evident, not a digital signature. Hardware-backed or remotely witnessed signatures are future work.

### Pre-v2 development journals

Receipt schema v2 deliberately rejects older development-format journals. During development, archive the old `execution-receipts.jsonl` before launching v2. A clean judge installation starts with an empty, valid v2 chain.

## Personal command center

Rayluno separates three concepts assistants often mix together:

- **Task:** an obligation that can be completed.
- **Reminder:** a time-triggered event delivered once and optionally snoozed.
- **Agenda:** a computed interpretation of what matters today.

The desktop UI reads real local SQLite data and displays overdue items, today's tasks, upcoming reminders, a recommended focus item, and local privacy state. The compact Verified Execution card remains beside the agenda, while the detailed gate and Receipt Inspector appear only when needed.

## How Codex and GPT-5.6 were used

Codex powered by GPT-5.6 was the primary engineering collaborator for this Build Week project. It was used to:

- audit the imported baseline before modifying `main`;
- decompose the product into reviewable stacked pull requests;
- design the task, reminder, agenda, and verified-skill domain boundaries;
- implement bilingual behavior and accessibility checks;
- build the Windows/Ubuntu and Python 3.11/3.13 CI matrix;
- diagnose CI failures from JUnit and Ruff artifacts instead of hiding failing checks;
- adversarially review model-to-system boundaries;
- design single-use confirmation handles and stale-intent invalidation;
- build full-chain receipt verification and tamper fail-closed tests;
- document the judge path and security claims.

Key decisions made with Codex/GPT-5.6:

1. **No unrestricted shell.** Broad execution was rejected in favor of bounded skills.
2. **Deterministic first.** Direct commands do not require a language model.
3. **Model output is untrusted.** A proposed action must resolve to a manifest and pass policy.
4. **Approval is plan-specific and time-bounded.** A generic UI confirmation is insufficient.
5. **Receipts minimize sensitive data.** Auditability does not justify storing raw user content.
6. **Integrity failure stops execution.** A receipt chain is not useful if the runtime ignores corruption.
7. **The judge path is honest.** Scripted reproducibility is explicitly labelled and never presented as model inference.

GPT-5.6 is not granted direct runtime control over the operating system. The same boundary constraining the optional local model would constrain any future cloud planner.

## Development and verification

```powershell
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m compileall -q src
```

The current verified-execution v2 branch passes **414 automated tests** across:

- Windows and Ubuntu;
- Python 3.11 and Python 3.13;
- unit, integration, localization, privacy, confirmation, expiry, replay, UI-contract, and tamper tests;
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
- Tasks, reminders, settings, audit records, and receipts remain local by default.
- No usage telemetry is enabled by default.
- Web queries leave the device only when the user requests a web action.
- The client contains no private signing keys.
- Update and licensing components fail closed when verification fails.
- Current installers are development artifacts and are not Authenticode-signed production builds.

See:

- [Security and privacy](docs/SECURITY_PRIVACY_AR.md)
- [Architecture](docs/ARCHITECTURE_AR.md)
- [Release readiness](docs/RELEASE_READINESS_AR.md)
- [Third-party notices](THIRD_PARTY_NOTICES.md)

## Current limitations

- The polished desktop release targets Windows x64.
- The initial skill registry is intentionally small.
- Optional Ollama reasoning and full local voice require additional local dependencies.
- Local hash chaining is not equivalent to a hardware-backed or remotely witnessed signature.
- The current installer is not a signed public production release.

## Repository history

The implementation was developed as reviewable pull requests rather than modifying `main` blindly:

1. Personal Task Core.
2. Reminders and Daily Agenda.
3. Today Command Center.
4. Verified Skills, Judge Mode, and execution receipts.
5. Verified Execution v2: expiring handles, full-chain integrity, and Receipt Inspector.

## License

Rayluno is released under the [MIT License](LICENSE).
