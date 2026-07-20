# Rayluno — Personal AI that proves what it is allowed to do

Rayluno is a local-first Arabic/English Windows personal agent that organizes a user's day, stores personal memory only after explicit consent, and performs bounded desktop actions without granting an AI model unrestricted operating-system access.

> **The model may propose. Deterministic code decides what is permitted, records authorization before impact, and verifies the evidence before the next action.**

**OpenAI Build Week category:** Apps for Your Life  
**Primary platform:** Windows x64  
**Interface languages:** Arabic and English  
**License:** MIT

## Why Rayluno

Personal assistants often sit at one of two unsafe extremes:

1. they chat but cannot complete meaningful work; or
2. they receive broad tool access that is difficult to constrain, explain, and audit.

Rayluno takes a third path. Natural-language input becomes a closed action plan. Every consequential action must:

1. resolve to a registered skill;
2. pass deterministic allowlist policy;
3. request plan-specific approval;
4. persist authorization proof before impact;
5. execute through a bounded adapter;
6. persist an outcome receipt;
7. preserve a verifiable local trust history.

## What works

- Arabic and English text commands.
- Local wake-word, speech-to-text, and text-to-speech paths for Windows.
- Persistent local tasks, reminders, snooze, completion, and one-time delivery.
- A daily agenda with overdue work, today's commitments, next reminder, and recommended focus.
- An explicit-consent Personal Memory Vault stored in local SQLite.
- Refusal of likely passwords, PINs, private keys, JWTs, provider tokens, recovery phrases, verification codes, and Luhn-valid payment-card numbers.
- Safe application launching, website navigation, search, time reporting, and volume control.
- Deterministic-first routing with optional local Ollama fallback.
- Registered skill manifests with permission, risk, purpose scope, and confirmation policy.
- Expiring, plan-specific, single-use approval handles generated and validated in Python.
- Installation-scoped HMAC-SHA256 fingerprints instead of reversible raw command storage.
- Write-ahead `execution_authorized` receipts persisted before operating-system effects.
- Privacy-aware `rayluno.execution-receipt/v2` records linked by SHA-256.
- A per-installation HMAC-authenticated checkpoint for chain head and receipt count.
- Fail-closed detection for malformed records, editing, reordering, journal deletion, truncation, rollback, missing checkpoint state, or checkpoint tampering.
- A bilingual Runtime Trust Center derived from live Python state.
- A reproducible Judge Mode requiring no account, API key, model, or external service for the core demo.

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

Judge Mode is explicitly labelled scripted provenance through the real production trust boundary. It does **not** claim that scripted output came from a model.

### 3. Prove explicit-consent memory

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

Open **Memory**. The fact is visible, labelled as explicitly supplied, stored locally, and individually deletable. Memory is not silently inserted into model prompts in this release.

### 4. Prove controlled execution

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
- argument-key names and an installation-scoped HMAC fingerprint;
- a visible expiry countdown;
- explicit Approve and Reject controls.

The desktop sends the exact server-generated approval handle, not a generic confirm command. Approval consumes the handle once. Before any operating-system effect, Rayluno persists an `execution_authorized` receipt. It then executes only allowlisted effects and records the outcome separately.

### 5. Open the Runtime Trust Center

Open **Verified**. The Receipt Inspector now contains six live guarantees derived from Python runtime state:

- **Authorization before effect**
- **Authenticated checkpoint**
- **Keyed fingerprints**
- **Explicit-consent memory**
- **No general command authority**
- **Telemetry off**

It also displays the registered-skill count, Judge Mode state, authorization ordering, chain status, and the explicit limits of local-only verification. No local key, raw command, argument value, or approval token is exposed to JavaScript.

### 6. Prove fail-closed behavior

Enter:

```text
اختبر رفض مهارة غير مسجلة
```

or:

```text
test an unregistered skill
```

The proposal is rejected before impact because it does not resolve to a registered skill.

### Side-effect-free review

```powershell
rayluno --ui --judge-demo --dry-run
```

This exercises planning, confirmation, policy, memory, write-ahead authorization, receipts, Trust Center, and the interface without opening applications or websites.

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
Expiring single-use approval when required
        │
        ▼
Deterministic SafetyPolicy allowlists
  ├─ allowed URL schemes and domains
  ├─ allowed application IDs
  ├─ bounded query and URL lengths
  └─ no unrestricted operating-system command primitive
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
- every fact is marked as explicitly supplied by the user;
- normalized fingerprints prevent duplicate-memory spam;
- structured credential patterns and Luhn-valid payment-card numbers are refused;
- users can inspect and delete individual facts;
- delete-all requires a short-lived, single-use Python approval handle;
- invalid or replayed purge handles fail closed;
- memory content stays out of the command audit log;
- memory is not silently inserted into model prompts in this milestone.

Default storage is local SQLite under the Rayluno application-data directory. It can be redirected with `RAYLUNO_MEMORY_PATH`.

## Initial registered skills

| Skill ID | Permission | Risk | Confirmation |
|---|---|---:|---|
| `web.search` | `network.browser.search` | Medium | Model/demo proposal |
| `web.navigate` | `network.browser.navigate` | Medium | Model/demo proposal |
| `application.launch` | `applications.launch` | Medium | Model/demo proposal |
| `system.time.read` | `system.time.read` | Low | Never |
| `system.audio.control` | `system.audio.control` | Low | Model/demo proposal |

Unregistered actions fail closed. A new command invalidates older pending intent. A mismatched handle cannot consume a valid plan, an expired handle cannot execute, and a consumed handle cannot cause a second effect.

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

Raw command text, URL query values, and approval capability handles are excluded from persisted audit details. Command audit fingerprints are installation-scoped HMAC-SHA256 values rather than plain SHA-256 hashes.

## Honest security boundary

The local HMAC checkpoint is stronger than an unkeyed hash chain, but it is not a hardware-backed signature or remote transparency log.

- A process running as the same operating-system user that can read the local HMAC key can forge local state.
- Deleting every local trust-state file cannot be distinguished from a clean installation without a hardware or remote witness.
- Local SQLite data is not application-encrypted in this release.
- Current development installers are not Authenticode-signed production builds.
- A crash after an effect but before its outcome receipt can leave an authorization in an in-doubt state; explicit crash-recovery reconciliation is future work.

Future work includes operating-system protected keys, remotely witnessed checkpoints, encrypted local data, in-doubt execution reconciliation, and signed packaged builds.

## How Codex and GPT-5.6 were used

Codex powered by GPT-5.6 was the primary engineering collaborator. It was used to:

- audit the imported baseline and conduct a full pre-submission security review;
- decompose the product into reviewable pull requests;
- design task, reminder, agenda, memory, skill, confirmation, authorization, receipt, and update boundaries;
- implement bilingual behavior, RTL/LTR support, and accessibility contracts;
- build the Windows/Ubuntu and Python 3.11/3.13 CI matrix;
- diagnose failures from JUnit and Ruff artifacts instead of suppressing checks;
- adversarially review model-to-system and memory-consent boundaries;
- replace plain fingerprints with installation-scoped HMAC fingerprints;
- introduce write-ahead authorization before side effects;
- add authenticated checkpoint and rollback/truncation tests;
- create tests for passive-memory prevention, structured-secret refusal, purge replay, approval replay, expiry, privacy, and journal corruption;
- turn hidden security guarantees into the runtime-backed Trust Center;
- shape the judge path around claims the product can prove.

GPT-5.6 is not granted direct runtime control over the operating system.

## Development and verification

```powershell
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m compileall -q src
```

The audited release passes **451 automated tests** across:

- Windows and Ubuntu;
- Python 3.11 and Python 3.13;
- unit, integration, localization, privacy, memory, approval, authorization-before-effect, expiry, replay, UI-contract, structured-secret, deletion, truncation, rollback, authenticated-checkpoint, Trust Center, and tamper tests;
- JavaScript syntax validation for every UI script;
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

Judge Mode bypasses only bounded evaluation feature gates; it does not install dependencies, expand allowlists, or grant unknown permissions.

## Documentation

- [Final product and security audit](docs/FINAL_PRODUCT_AUDIT.md)
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
7. Security audit hardening: write-ahead authorization, authenticated checkpoint, keyed fingerprints, structured-secret refusal, and bounded Judge Mode access.
8. Runtime Trust Center and permanent JavaScript syntax verification.

## License

Rayluno is released under the [MIT License](LICENSE).
