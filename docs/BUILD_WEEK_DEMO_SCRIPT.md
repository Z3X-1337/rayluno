# OpenAI Build Week Demo Script — Rayluno

Target length: 2:35–2:50. Keep the entire recording below 3:00.

## Recording setup

- Use a clean Windows desktop at 1920×1080.
- Launch with `rayluno --ui --judge-demo`.
- Use a clean v2 receipt journal or archive any pre-v2 development journal first.
- Pre-create one high-priority task and one reminder so Today is populated.
- Keep the repository page closed before the controlled-action scene.
- Record system audio and a clear English voiceover. Brief Arabic commands can remain on screen.
- Do not claim Judge Mode is model inference. State that it is a reproducible scripted-provenance path through the real production security runtime.

## 0:00–0:17 — Hook

**Voiceover**

“Personal AI agents usually face a bad trade-off: they can chat but cannot act, or they can act through broad tools that are difficult to constrain and audit. Rayluno is a local-first Arabic and English personal agent built around verifiable execution.”

**Screen**

Show the complete command center: activity, assistant, Today agenda, compact Verified Execution card, and the top-bar **Verified** indicator.

## 0:17–0:39 — Real personal utility

**Voiceover**

“Rayluno separates tasks, reminders, and the daily agenda. Tasks are obligations, reminders are time-triggered events, and the agenda computes what matters now. The data stays in local SQLite databases.”

**Screen**

Show:

- overdue and today counts;
- recommended focus;
- next reminder;
- one bilingual command such as `ما خطتي اليوم`.

## 0:39–1:24 — Plan-specific confirmation

**Screen command**

```text
جهز عرض الحكام
```

**Voiceover**

“This is Rayluno’s explicitly labelled Judge Mode. It requires no API key or local model, but it passes through the same production execution boundary. The plan proposes opening Notepad and the project repository.”

Pause when the detailed confirmation gate opens.

“Nothing has happened yet. Python generated a short-lived, single-use confirmation handle. The interface shows every selected skill, its permission and risk, an argument fingerprint, and the remaining approval time—without exposing raw argument values.”

Show the countdown and multi-skill list. Click **Approve and execute**.

“Only the exact pending plan is approved. Reusing, changing, or allowing the handle to expire cannot produce a second side effect.”

Show Notepad and the repository opening, then return to Rayluno.

## 1:24–1:55 — Receipt Inspector

Click the top-bar **Verified** indicator.

**Voiceover**

“Rayluno records the complete trust lifecycle: confirmation requested, rejected, replaced, expired, and executed. Every privacy-aware receipt contains safe metadata and links to the previous SHA-256 hash.”

Pause on **CHAIN VERIFIED**.

“Before another registered action, Rayluno reloads and recomputes the full chain. Malformed JSON, editing, deletion, reordering, or a hash mismatch pauses execution before side effects. Raw commands and URL query values are not stored in receipt summaries.”

**Screen**

Show:

- `CHAIN VERIFIED`;
- receipt count;
- current chain head;
- pending and execution events;
- confirmation states and argument-key names.

## 1:55–2:14 — Fail closed

Close the inspector and enter:

```text
اختبر رفض مهارة غير مسجلة
```

**Voiceover**

“This plan uses an unregistered purpose. Rayluno rejects it before any side effect. The model can propose; deterministic code remains the authority.”

Show the blocked result and confirm that no new application or page opens.

## 2:14–2:40 — Codex and GPT-5.6

**Voiceover**

“Codex with GPT-5.6 was the primary engineering collaborator. It audited the imported baseline, split the work into reviewable pull requests, designed the personal-data domains, built the bilingual interface, and implemented the verified-skill boundary. It also diagnosed CI failures through JUnit and Ruff artifacts, then helped harden approval replay, expiry, stale intent, and receipt tampering. We used it to challenge unsafe designs—not to bypass deterministic controls.”

**Screen**

Show quickly:

- the GitHub pull-request history;
- green CI on Windows and Ubuntu, Python 3.11 and 3.13;
- the `414 tests` result;
- README section titled **How Codex and GPT-5.6 were used**.

## 2:40–2:53 — Closing

**Voiceover**

“Rayluno is not a chatbot with a shell. It is a personal agent that can remember, plan, and act through bounded skills—with permission, expiry, integrity verification, and proof.”

**Screen**

Return to the command center and end on the Verified indicator and Today panel.

## Required final checks

- Public YouTube URL.
- Video duration below 3:00.
- Voiceover explicitly says both “Codex” and “GPT-5.6”.
- Show the product actually running.
- Show the detailed confirmation gate and visible countdown.
- Show `CHAIN VERIFIED` in the Receipt Inspector.
- Show one fail-closed unregistered-skill scenario.
- Do not show tokens, license keys, private email, local usernames, file-system home paths, or unrelated browser tabs.
- Use the exact repository URL from the submission.
