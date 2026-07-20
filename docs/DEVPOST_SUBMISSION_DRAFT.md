# Rayluno — Devpost Submission Draft

This file is a preparation artifact. It is not proof that Rayluno has been submitted.

## Project name

Rayluno

## Tagline

A local-first personal agent that can remember, plan, and act through bounded skills—with permission, confirmation, and proof.

## Category

Apps for Your Life

## Built with

- Python
- SQLite
- pywebview
- JavaScript
- HTML
- CSS
- Ollama
- whisper.cpp
- Vosk
- GitHub Actions
- Codex
- GPT-5.6

## Description

### Inspiration

Personal AI assistants usually face a bad trade-off. Some can only chat and cannot complete useful work. Others receive broad access to shell commands or tools that are difficult to constrain, explain, and audit. A personal agent should be able to act without requiring the user to surrender control of the computer.

### What it does

Rayluno is an Arabic and English, local-first Windows personal agent. It manages personal tasks, reminders, and a computed daily agenda, then executes a deliberately bounded set of desktop skills.

The Today Command Center shows overdue work, today's tasks, the next reminder, and a recommended focus item using data stored in local SQLite databases.

When Rayluno needs to perform an external action, the action must resolve to a registered Skill Manifest. The manifest declares a stable Skill ID, permission, risk level, parameter scope, and confirmation policy. Consequential model-proposed actions pause before any side effect and display the selected skill, required permission, and risk. The user can confirm or cancel the exact pending plan.

After a registered attempt, Rayluno creates a privacy-aware Execution Receipt. Receipts record the skill, permission, risk, outcome, policy reason, and a safe action summary. SHA-256 links each receipt to the previous receipt, making edits, deletion, or reordering detectable. Raw command text and URL query values are excluded from receipt summaries.

Unregistered actions fail closed. Rayluno does not give a model access to shell, PowerShell, cmd, eval, or exec.

### How we built it

Rayluno is a Python application with a bilingual pywebview desktop interface and JavaScript/CSS product surface. Personal tasks and reminders use SQLite. The runtime uses a deterministic-first planner for direct commands and supports an optional local Ollama fallback. Local voice paths use Vosk for wake-word detection, whisper.cpp for speech recognition, and installed Windows voices for speech output.

The execution architecture is:

```text
Request
→ deterministic parser or optional local-model proposal
→ closed action plan with provenance
→ registered skill manifest
→ permission/risk assessment
→ atomic confirmation when required
→ allowlist safety policy
→ bounded side effect
→ hash-linked execution receipt
```

A clearly labelled Judge Mode allows reviewers to exercise the real registry, confirmation boundary, policy, executor, and receipt ledger without installing a model or configuring an API key. It does not claim scripted provenance is model inference.

### How Codex and GPT-5.6 were used

Codex with GPT-5.6 was the primary engineering collaborator. It audited the imported baseline, decomposed the work into reviewable stacked pull requests, designed the task/reminder/agenda boundaries, implemented bilingual behavior and accessibility checks, built the verified-skill and receipt architecture, and created the Windows/Ubuntu CI matrix.

Codex also diagnosed failures from JUnit and Ruff artifacts rather than weakening quality gates. GPT-5.6 was used to adversarially review the model-to-system boundary and reject the initial idea of unrestricted command execution. The key decisions were to keep direct commands deterministic, treat model output as untrusted proposals, make confirmation atomic and one-time, minimize sensitive audit data, and provide an honest reproducible judge path.

GPT-5.6 is not granted direct runtime control over the operating system. Deterministic code remains authoritative at the side-effect boundary.

### Challenges

The hardest design problem was balancing usefulness with control. A purely conversational assistant would not demonstrate meaningful agency, while an unrestricted shell would be unsafe and difficult to defend. The Skill Manifest boundary provides extensibility without abandoning explicit permissions and policy.

The second challenge was making accountability visible at the moment of action. The Verified Execution card exposes the selected skill, permission, risk, confirmation state, receipt ID, and hash-chain head directly in the command center instead of hiding security in backend logs.

The third challenge was creating a judge path that is reproducible without misrepresenting scripted behavior as AI inference. Judge Mode is explicitly labelled with demo provenance and exercises the production execution boundary.

### Accomplishments

- Bilingual Arabic and English product experience.
- Local task lifecycle and persistent SQLite storage.
- Relative and scheduled reminders, snooze, completion, and one-time delivery.
- Computed daily agenda and recommended focus.
- Registered skills with permission, risk, purpose scope, and confirmation policy.
- Atomic confirm/cancel boundary.
- Stale pending intent invalidation.
- Fail-closed unregistered actions.
- Privacy-aware SHA-256 hash-linked execution receipts.
- Visible Verified Execution product surface.
- Reproducible no-key Judge Mode.
- 407 automated tests passing across Windows and Ubuntu on Python 3.11 and 3.13.
- Ruff lint, formatting, and Python compilation in CI.

### What we learned

An agent does not become trustworthy by adding a confirmation dialog after giving the model broad power. Trust has to be designed into the action vocabulary, permission model, policy boundary, provenance, and audit representation.

We also learned that reproducibility and honesty are product features. A scripted judge scenario is useful when it is clearly identified and passes through the real runtime; it becomes misleading only when it is presented as live model reasoning.

### What is next

- Expand the skill registry with scoped file, calendar, email, and multi-step workflow skills.
- Add user-managed per-skill permission grants and revocation.
- Add signed or externally witnessed receipts for stronger tamper evidence.
- Add workflow previews and rollback-aware operations.
- Package a signed Windows release and conduct broader device testing.
- Evaluate the experience with Arabic and bilingual users.

## Repository URL

https://github.com/Z3X-1337/rayluno

## Judge testing instructions

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e ".[dev,desktop,commercial]"
rayluno --ui --judge-demo
```

Controlled execution command:

```text
جهز عرض الحكام
```

Click Confirm when the Verified Execution card appears.

Fail-closed command:

```text
اختبر رفض مهارة غير مسجلة
```

For a side-effect-free inspection:

```powershell
rayluno --ui --judge-demo --dry-run
```

No account, API key, database server, or local language model is required for Judge Mode.

## Required values still to insert before submission

- Public YouTube demo URL, under 3 minutes: `[REQUIRED]`
- `/feedback` Codex Session ID: `[REQUIRED]`
- Submitter Type: `Individual` unless team status changes.
- Country of Residence: `Jordan`.
- Confirm the final Devpost project identity before modifying any existing project.
