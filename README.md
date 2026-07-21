# Rayluno — Personal AI that proves what it is allowed to do

Rayluno is a local-first Arabic/English Windows personal assistant that organizes a user's day, stores personal memory only after explicit consent, and performs bounded desktop actions without granting an AI model unrestricted operating-system access.

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
2. pass deterministic allow-list policy;
3. request plan-specific approval when required;
4. persist authorization proof before impact;
5. execute through a bounded adapter;
6. persist an outcome receipt;
7. preserve a verifiable local trust history.

## Implemented product surface

- Arabic and English text commands.
- Local Vosk push-to-talk speech recognition for the stable Windows judge path.
- Background Vosk model preloading and faster end-of-speech detection in the judge launcher to reduce first-command latency.
- Existing local wake-word, recorder, Whisper, Vosk, OneCore TTS, and SAPI components.
- Conservative Arabic normalization for common typing and transcription mistakes.
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

## Reproducible three-minute judge path

The commands below are the supported Windows evaluation path. They use the same Vosk push-to-talk route that was exercised on the target Windows machine.

### 1. Install

Use Python 3.11 x64 or newer:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e ".[dev,desktop,commercial,voice]"
```

Install or discover the Arabic Vosk model:

```powershell
.\scripts\install-arabic-wake-model.ps1 -SetUserEnvironment
```

### 2. Run the preflight exactly

```powershell
.\scripts\start-judge-demo.ps1 -CheckOnly
```

The preflight validates the Python environment, local voice dependencies, and model configuration without opening the interface.

### 3. Launch the deterministic core demo

```powershell
.\scripts\start-judge-demo.ps1
```

This expands to the stable command:

```powershell
$env:RAYLUNO_NAME = "Rayluno"
$env:RAYLUNO_LANGUAGE = "ar"
$env:RAYLUNO_STT_BACKEND = "vosk"
$env:RAYLUNO_WHISPER_LANGUAGE = "ar"
$env:RAYLUNO_TTS_ENABLED = "false"
$env:RAYLUNO_RMS_THRESHOLD = "250"
$env:RAYLUNO_PRELOAD_VOSK = "true"
python -m future_assistant.safe_voice_cli --ui --judge-demo
```

The launcher fixes the visible product name to **Rayluno**, begins loading the local Vosk model while the interface opens, and uses a shorter bounded silence endpoint. It does not add a network dependency or broaden any permission.

Optional local Ollama fallback, after confirming Ollama is running:

```powershell
.\scripts\start-judge-demo.ps1 -UseOllama
```

Optional Windows OneCore voice replies, after confirming a complete Arabic voice is installed:

```powershell
.\scripts\start-judge-demo.ps1 -EnableTts
```

The default judge launcher keeps TTS off because installed Windows voice availability varies between machines. Enabling it uses the existing OneCore implementation; it does not introduce a new cloud voice service.

### 4. Prove explicit-consent memory

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

### 5. Prove controlled execution and explicit approval

Enter:

```text
جهز عرض الحكام
```

Rayluno performs no side effect immediately. The confirmation gate displays:

- every selected `Skill ID`;
- required permissions and risk levels;
- argument-key names and an installation-scoped HMAC fingerprint;
- a visible expiry countdown;
- explicit Approve and Reject controls.

The desktop sends the exact server-generated approval handle, not a generic confirm command. Approval consumes the handle once. Before any operating-system effect, Rayluno persists an `execution_authorized` receipt. It then executes only allow-listed effects and records the outcome separately.

### 6. Prove fail-closed behavior

Enter:

```text
اختبر رفض مهارة غير مسجلة
```

The proposal is rejected before impact because it does not resolve to a registered skill.

### 7. Inspect the evidence

Open **Verified**. The Runtime Trust Center reports six live guarantees derived from Python state:

- **Authorization before effect**
- **Authenticated checkpoint**
- **Keyed fingerprints**
- **Explicit-consent memory**
- **No general command authority**
- **Telemetry off**

The Receipt Inspector displays chain status, receipt count, registered skills, Judge Mode state, and the honest limits of local-only verification. No local key, raw command, argument value, or approval token is exposed to JavaScript.

A side-effect-free review is also available:

```powershell
python -m future_assistant.safe_voice_cli --ui --judge-demo --dry-run
```

## Judge Mode is an explicit evaluation entitlement override

`--judge-demo` is not a hidden licensing bypass and is not presented as a customer activation path. It is an intentionally visible evaluation mode for reviewers.

In Judge Mode, the feature checker returns `true` only for these existing bounded capabilities:

- `ai.local`
- `automation.pro`
- `voice.local`

Judge Mode also enables two clearly scripted scenarios and removes the wake-word requirement from the desktop review flow for repeatability. It does **not**:

- install a paid license;
- modify persistent entitlement state;
- add domains or applications;
- register unknown skills;
- expand permissions;
- provide shell, `eval`, or unrestricted command authority;
- claim that scripted demo provenance came from a model.

Judge Mode is displayed in the Runtime Trust Center and should remain disabled in normal customer operation.

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
Deterministic SafetyPolicy allow-lists
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

The JSONL ledger uses `rayluno.execution-receipt/v2`. It records confirmation, write-ahead authorization, outcome, skill, permission, risk, policy reason, safe action metadata, argument-key names, installation-scoped HMAC argument digest, previous hash, and current hash.

Before registered execution and before extending the journal, Rayluno reloads the complete ledger, validates the schema, recomputes every receipt hash, verifies every link, and compares the chain head and receipt count with a per-installation HMAC-authenticated checkpoint. A failure pauses verified execution before the next effect.

Raw command text, URL query values, and approval capability handles are excluded from persisted audit details.

## Honest security and deployment boundary

The local HMAC checkpoint is stronger than an unkeyed hash chain, but it is not a hardware-backed signature or remote transparency log.

- A process running as the same operating-system user that can read the local HMAC key can forge local state.
- Deleting every local trust-state file cannot be distinguished from a clean installation without a hardware or remote witness.
- Local SQLite data is not application-encrypted in this release.
- Current development installers are not Authenticode-signed production builds.
- A crash after an effect but before its outcome receipt can leave an authorization in an in-doubt state; explicit crash-recovery reconciliation is future work.

### Temporary activation hosting

The current activation endpoint is pinned to an HTTPS subdomain provided by a third-party hosting platform. The client still validates a plain HTTPS endpoint, rejects credentials in URLs, rejects query strings and fragments, uses the standard HTTPS port, refuses redirects, bounds response sizes, and verifies the returned signed entitlement.

This host is a temporary prototype/evaluation deployment, not the claimed final production architecture. A production release should migrate activation to a first-party Rayluno domain with independent deployment ownership, monitoring, availability controls, incident response, and key-management procedures.

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

The final judge branch passes **467 automated tests** across:

- Windows and Ubuntu;
- Python 3.11 and Python 3.13;
- unit, integration, localization, privacy, memory, approval, authorization-before-effect, expiry, replay, UI-contract, structured-secret, deletion, truncation, rollback, authenticated-checkpoint, Trust Center, voice-preload, and tamper tests;
- JavaScript syntax validation for every UI script;
- Ruff lint and formatting;
- Python compilation.

The previous audited baseline contained 462 passing tests. The final total is taken from the successful Windows 3.11 JUnit artifact after the complete CI matrix passed.

## Documentation

- [Final judge video script](docs/FINAL_JUDGE_SCRIPT.md)
- [Final product and security audit](docs/FINAL_PRODUCT_AUDIT.md)
- [Pre-submission security audit](docs/SECURITY_AUDIT_2026-07-20.md)
- [Devpost draft](docs/RAYLUNO_DEVPOST_DRAFT.md)
- [Verified Skills and Execution Receipts](docs/VERIFIED_SKILLS.md)
- [Security and privacy](docs/SECURITY_PRIVACY_AR.md)
- [Architecture](docs/ARCHITECTURE_AR.md)
- [Release readiness](docs/RELEASE_READINESS_AR.md)
- [Third-party notices](THIRD_PARTY_NOTICES.md)

## License

Rayluno is released under the [MIT License](LICENSE).
