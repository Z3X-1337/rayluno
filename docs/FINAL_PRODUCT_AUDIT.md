# Rayluno Final Product and Security Audit

**Audit date:** 2026-07-20  
**Audited release:** post-Trust Center `main`  
**Verification target:** OpenAI Build Week submission

## Executive result

Rayluno is no longer only a polished assistant prototype. Its differentiator is a coherent trust architecture that is enforced by code, tested adversarially, and surfaced to judges through a runtime-backed Trust Center.

The final audited release passes **451 automated tests** across Windows and Ubuntu, Python 3.11 and Python 3.13. CI also validates Python compilation, every UI JavaScript file with Node syntax checking, Ruff lint, and Ruff formatting.

## Audit scope

The review covered:

- deterministic and model-assisted planning;
- model-to-system trust boundaries;
- registered skills and allowlist policy;
- approval lifecycle and replay resistance;
- operating-system effect ordering;
- execution receipts and checkpoint integrity;
- command audit privacy;
- tasks, reminders, and agenda persistence;
- explicit-consent memory and secret refusal;
- PyWebView desktop bridge and UI assets;
- local voice and optional Ollama paths;
- entitlement and Judge Mode behavior;
- activation, licensing, and update staging;
- package data and installation paths;
- CI coverage, cross-platform behavior, and documentation accuracy;
- judge demonstration reproducibility.

## Release-blocking findings resolved

### 1. Effect could precede durable proof

**Former risk:** an operating-system effect could happen before its final receipt was guaranteed to be written.

**Resolution:** Rayluno now persists an `execution_authorized` receipt before invoking the effect adapter. If authorization evidence cannot be sealed, no effect occurs. Outcome receipts are recorded separately.

### 2. Journal deletion or truncation could resemble a new chain

**Former risk:** a missing or emptied receipt file could be interpreted as a fresh empty ledger.

**Resolution:** receipt count and chain head are stored in a per-installation HMAC-authenticated checkpoint. Missing, truncated, rolled-back, malformed, reordered, or tampered state fails closed.

### 3. Approval capability entered audit details

**Former risk:** the short-lived approval handle was included in a persisted detail field.

**Resolution:** capability handles are excluded from persisted audit data. The UI receives the exact handle required for the current plan, but historical logs do not retain it.

### 4. Plain fingerprints were guessable

**Former risk:** plain SHA-256 fingerprints of low-entropy commands or arguments could be guessed offline.

**Resolution:** command and argument fingerprints are now installation-scoped HMAC-SHA256 values. Raw commands and argument values remain excluded from receipts.

### 5. Memory secret refusal depended mainly on labels

**Former risk:** a credential without words such as “password” or “token” could bypass refusal.

**Resolution:** Memory Vault now detects structured private-key material, JWT-like values, common provider credential formats, and Luhn-valid payment-card numbers in addition to bilingual keyword rules.

### 6. Sensitive local state lacked a common protection layer

**Former risk:** audit, receipt, key, checkpoint, task, reminder, and memory files used inconsistent local permission handling.

**Resolution:** a shared local-security layer now provides restrictive file and directory permissions where supported, durable flushes, atomic replacement, and race-safe local key creation.

### 7. Judges could not evaluate bounded voice and local AI without entitlement

**Former risk:** the core demo was accessible, but optional voice/local-AI paths remained behind product entitlement checks.

**Resolution:** explicitly launching `--judge-demo` unlocks only the bounded evaluation feature gates when dependencies are installed. It does not expand skill allowlists, install dependencies, or grant unknown capabilities.

### 8. Deep security value was invisible in the product

**Former risk:** judges would need to infer the strongest engineering work from code and documentation.

**Resolution:** the Runtime Trust Center displays six guarantees derived from live Python state:

- authorization before effect;
- authenticated checkpoint;
- keyed fingerprints;
- explicit-consent memory;
- no general command authority;
- telemetry off.

It also displays registered-skill count, Judge Mode state, authorization ordering, and the explicit limits of local verification.

## Strengths most relevant to judging

### Technical implementation

- Deterministic-first routing minimizes unnecessary model dependence.
- Model output is treated as proposed data, not executable authority.
- The skill registry is deliberately small and inspectable.
- Approval is bound to one reviewed plan, expires, and is single use.
- Authorization and outcome are separate auditable events.
- Receipt history is checked before later registered execution.
- CI covers the target Windows platform as well as Ubuntu.

### Product completeness

- Personal tasks, reminders, agenda, memory, execution approval, receipts, and Trust Center share one desktop experience.
- Arabic/English and RTL/LTR behavior are product-level concerns, not a translated landing page.
- Judge Mode removes account, key, model, and external-service setup from the core evaluation path.
- The fail-closed scenario is visible and reproducible.

### Real-world impact

- The product addresses a genuine adoption barrier: users want agents that can act without receiving broad invisible authority.
- Explicit-consent memory addresses personalization without passive profile building.
- Receipt and Trust Center surfaces make security understandable to non-specialist users.

### Differentiation

Most assistant demos emphasize the number of tools an agent can call. Rayluno emphasizes whether each action was registered, reviewed, authorized before impact, and independently inspectable afterward. The Runtime Trust Center turns that architecture into a visible product feature.

## Remaining risks and recommended disposition

### High — crash recovery for in-doubt authorization

A process crash after an effect but before the outcome receipt may leave an authorization without a conclusive outcome. The chain remains internally valid, but the next launch cannot prove whether the effect happened.

**Recommendation:** do not redesign this immediately before submission. State it honestly. Post-submission, add operation correlation IDs and startup reconciliation that marks unmatched authorizations as `in_doubt` and pauses consequential execution until acknowledged.

### High — local key protection

The HMAC key is protected by local filesystem controls, not DPAPI, TPM, Secure Enclave, or a remote witness. A process running as the same operating-system user with key access can forge local state.

**Recommendation:** keep the current honest limitation. Post-submission, protect keys with Windows DPAPI or hardware-backed storage and optionally witness checkpoints remotely.

### High — unsigned distributable

Development installation is not an Authenticode-signed public release.

**Recommendation:** judges should use the documented source installation path. Do not claim production-distribution readiness. Add signed packaging after the hackathon.

### Medium — data-at-rest encryption

Tasks, reminders, and memory are local SQLite but not application-encrypted.

**Recommendation:** avoid claiming encryption. Post-submission, add a key-management design before encrypting individual databases.

### Medium — voice is not exercised by the standard CI matrix

Voice dependencies require audio hardware, Windows runtime components, and local models. Unit and contract coverage exists, but microphone-to-transcript-to-speech behavior still needs a manual Windows smoke test.

**Recommendation:** record the voice path only after running it on a real Windows machine. Do not simulate microphone success in the final video.

### Medium — background reminders require the application to be running

The current reminder delivery loop is part of the running application, not a Windows background service.

**Recommendation:** present this as a desktop-agent milestone. A background service or scheduled-task integration belongs after submission.

### Medium — dependency and release supply chain

The project has constrained dependency ranges and signed update verification logic, but no committed lock file, SBOM artifact, or mandatory vulnerability-audit job.

**Recommendation:** avoid destabilizing the submission build. Add reproducible lock generation, CycloneDX SBOM, dependency review, and pinned GitHub Action commit SHAs after submission.

### Low — broader accessibility validation

The interface includes bilingual and accessibility contracts, but a full screen-reader and keyboard-only audit has not been performed on a packaged Windows build.

**Recommendation:** manually verify focus order, dialogs, scaling, and screen-reader labels before public release.

## Features deliberately deferred

### Bounded multi-step workflows

The concept was valid, but the existing branch was built against an older trust architecture. Merging it before submission would create parallel execution contracts and widen the demo beyond three minutes.

**Decision:** defer and rebuild on the current authorization, checkpoint, and Trust Center contracts.

### More registered skills

Adding many skills would increase feature count but also expand policy, test, and demonstration surface.

**Decision:** keep the initial registry small. In judging, explain that bounded authority is intentional, then show how a new skill must declare permission, risk, purpose, confirmation policy, and tests.

## Final submission recommendation

The competition build should now be frozen except for:

1. verified documentation corrections;
2. the final video and thumbnail;
3. a real Windows smoke test;
4. critical defects discovered during that smoke test.

Do not add workflow orchestration, cloud synchronization, passive memory, broad file access, or new operating-system actions before submission.

## Required final manual checks

- Launch `rayluno --ui --judge-demo` on a clean Windows environment.
- Verify English and Arabic language switching.
- Save and inspect one explicit memory.
- Confirm ordinary conversation is not saved.
- Run the controlled judge scenario and inspect the approval dialog.
- Approve once and verify replay cannot produce a second effect.
- Open the Receipt Inspector and confirm Trust Center reports six active guarantees.
- Run the unregistered-skill scenario and confirm no effect.
- Test the microphone and speech path only after installing the optional voice dependencies.
- Record the final video from the actual Windows application.

## Audit conclusion

No review can guarantee a competition result. The project now has a defensible and differentiated thesis, a coherent product path, an unusually strong test matrix for a hackathon submission, and security claims that are implemented, visible, and intentionally limited. The highest-value remaining work is presentation and real-device verification, not additional feature count.
