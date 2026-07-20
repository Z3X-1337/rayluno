# Rayluno — A local-first personal agent with verifiable execution

Rayluno is an Arabic/English Windows assistant that can organize a user's day and execute
bounded desktop skills without giving a language model unrestricted access to the operating
system.

The central product claim is simple:

> A useful personal agent should be able to act, but every action should be understandable,
> permission-scoped, confirmable when consequential, and independently auditable.

**OpenAI Build Week category:** Apps for Your Life  
**Primary platform:** Windows x64  
**Interface languages:** Arabic and English  
**License:** MIT

---

## The problem

Most personal assistants sit at one of two unsafe extremes:

1. they only chat and cannot complete meaningful work; or
2. they can run broad shell/tool commands that are difficult to explain, constrain, or audit.

Rayluno takes a third path. Natural-language input is converted into a closed action model.
An action must match a registered skill manifest, satisfy an existing allowlist policy, request
explicit confirmation when its provenance or risk requires it, and produce a local execution
receipt after the attempt.

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
- Registered skill manifests with permission, risk, and confirmation policy.
- Atomic confirm/cancel boundaries for consequential model-proposed actions.
- Privacy-aware, SHA-256 hash-linked execution receipts.
- A reproducible judge mode that requires no model, API key, account, or external service.

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

The flag enables two explicitly scripted judge scenarios. It does **not** pretend that scripted
output came from a model; it exists so reviewers can exercise the real execution boundary without
installing Ollama or configuring credentials.

### 3. Demonstrate controlled execution

Enter:

```text
جهز عرض الحكام
```

or:

```text
prepare the judge demo
```

Rayluno will not act immediately. The **Verified Execution** card displays:

- the selected `Skill ID`;
- the required permission;
- the risk level;
- explicit Confirm and Cancel controls.

Confirm the plan. Rayluno executes only the allowlisted actions and displays a compact receipt ID
plus the current hash-chain head.

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

To inspect planning, confirmation, receipts, and the UI without opening applications or websites:

```powershell
rayluno --ui --judge-demo --dry-run
```

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
Atomic confirmation boundary when required
        │
        ▼
Existing SafetyPolicy allowlists
  ├─ allowed URL schemes and domains
  ├─ allowed application IDs
  ├─ bounded query and URL lengths
  └─ no shell, PowerShell, cmd, eval, or exec
        │
        ▼
Bounded system effect
        │
        ▼
Privacy-aware hash-linked ExecutionReceipt
```

## Verified Skills

The initial registry contains:

| Skill ID | Permission | Risk | Confirmation |
|---|---|---:|---|
| `web.search` | `network.browser.search` | Medium | Model/demo proposal |
| `web.navigate` | `network.browser.navigate` | Medium | Model/demo proposal |
| `application.launch` | `applications.launch` | Medium | Model/demo proposal |
| `system.time.read` | `system.time.read` | Low | Never |
| `system.audio.control` | `system.audio.control` | Low | Model/demo proposal |

Unregistered actions fail closed. A new command invalidates an older pending confirmation, so a
later “confirm” cannot execute stale intent.

See [Verified Skills and Execution Receipts](docs/VERIFIED_SKILLS.md).

## Execution receipts

Each registered execution attempt produces a local receipt containing:

- UTC timestamp and compact receipt ID;
- skill, permission, and risk;
- completed, blocked, or failed outcome;
- policy reason;
- a safe action summary;
- previous receipt hash and current receipt hash.

The ledger is tamper-evident, not a digital signature. Editing, removing, or reordering receipt
records breaks the chain. Search terms and full command text are not written to receipt summaries;
for URLs, Rayluno retains safe metadata such as host, path, and query-key names rather than query
values.

Default path:

```text
~/.future_assistant/execution-receipts.jsonl
```

## Personal command center

Rayluno separates three concepts that assistants often mix together:

- **Task:** an obligation that can be completed.
- **Reminder:** a time-triggered event delivered once and optionally snoozed.
- **Agenda:** a computed interpretation of what matters today.

The desktop UI reads real local SQLite data and displays overdue items, today's tasks, upcoming
reminders, a recommended focus item, and local privacy state. The Verified Execution surface sits
beside the agenda so capability and accountability remain visible at the moment of action.

## How Codex and GPT-5.6 were used

Codex powered by GPT-5.6 was the primary engineering collaborator for this Build Week project.
It was used to:

- audit the imported baseline before modifying `main`;
- decompose the product into reviewable stacked pull requests;
- design the task, reminder, agenda, and verified-skill domain boundaries;
- implement bilingual behavior and accessibility checks;
- build the Windows/Ubuntu and Python 3.11/3.13 CI matrix;
- diagnose CI failures from JUnit and Ruff artifacts instead of hiding failing checks;
- adversarially review model-to-system boundaries;
- create tests for confirmation, cancellation, stale-intent invalidation, privacy, and hash chaining;
- document the judge path and security claims.

Key decisions made with Codex/GPT-5.6:

1. **No unrestricted shell.** Broad execution was rejected in favor of bounded skills.
2. **Deterministic first.** Direct commands do not require a language model.
3. **Model output is untrusted.** A proposed action must resolve to a manifest and pass policy.
4. **Confirmation is atomic and one-time.** It cannot authorize a later or changed command.
5. **Receipts minimize sensitive data.** Auditability does not justify storing raw user content.
6. **The judge path is honest.** Scripted reproducibility is explicitly labelled and does not claim
   to be model inference.

GPT-5.6 is not granted direct runtime control over the operating system. The same architectural
boundary that constrains the optional local model would constrain any future cloud planner.

## Development and verification

```powershell
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m compileall -q src
```

CI verifies the project on:

- Windows and Ubuntu;
- Python 3.11 and Python 3.13;
- unit and integration tests;
- Ruff lint and formatting;
- Python compilation.

Useful commands:

```powershell
rayluno --doctor
rayluno --once "يا رايلونو كم الساعة" --dry-run --no-audit
rayluno --ui
```

## Optional local voice and AI

Rayluno supports local wake-word detection, local speech recognition, Windows text-to-speech, and
an optional Ollama fallback. These components are not required for the reproducible judge path.

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
- Hash chaining detects ledger tampering but is not equivalent to a hardware-backed or remotely
  witnessed signature.
- The current installer is not a signed public production release.

## Repository history

The implementation was developed as reviewable stacked pull requests rather than modifying
`main` blindly:

1. Personal Task Core.
2. Reminders and Daily Agenda.
3. Today Command Center.
4. Verified Skills, confirmation gates, receipts, and judge mode.

This structure preserves architectural review points and makes the Build Week engineering process
inspectable.

## License

Rayluno is released under the [MIT License](LICENSE).
