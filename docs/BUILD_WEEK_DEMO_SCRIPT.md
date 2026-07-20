# OpenAI Build Week Demo Script — Rayluno

Target length: 2:35–2:50. Keep the entire recording under 3:00.

## Recording setup

- Use a clean Windows desktop at 1920×1080.
- Launch with `rayluno --ui --judge-demo`.
- Pre-create one high-priority task and one reminder so Today is populated.
- Keep the repository page closed before the demo.
- Record system audio and a clear English voiceover. Brief Arabic commands can remain on screen.
- Do not claim Judge Mode is model inference. State that it is a reproducible scripted provenance path through the real security runtime.

## 0:00–0:18 — Hook

**Voiceover**

“Personal AI agents usually face a bad trade-off: they can chat but cannot act, or they can act through broad tools that are difficult to constrain and audit. Rayluno is a local-first Arabic and English personal agent designed around verifiable execution.”

**Screen**

Show the full command center: activity, assistant, Today agenda, and Verified Execution card.

## 0:18–0:43 — Real personal utility

**Voiceover**

“Rayluno separates tasks, reminders, and the daily agenda. Tasks are obligations, reminders are time-triggered events, and the agenda computes what matters now. The data is stored locally in SQLite.”

**Screen**

Show:

- overdue/today counts;
- recommended focus;
- next reminder;
- one bilingual command, such as `ما خطتي اليوم`.

## 0:43–1:25 — Controlled action

**Screen command**

```text
جهز عرض الحكام
```

**Voiceover**

“This is Rayluno’s explicitly labelled Judge Mode. It requires no API key or local model, but it passes through the same production execution boundary. The plan proposes opening Notepad and the project repository.”

Pause on the Verified Execution card.

“Nothing has happened yet. Rayluno resolved the action to a registered skill, disclosed the permission and risk, and requested one-time confirmation.”

Click **Confirm**.

“Only now does the bounded executor run the allowlisted actions.”

Show Notepad and the repository opening, then return to Rayluno.

## 1:25–1:52 — Execution receipt

**Voiceover**

“Every registered attempt produces a privacy-aware execution receipt. It records the skill, permission, risk, policy reason, safe action summary, and outcome. Receipts are linked with SHA-256, so editing, deleting, or reordering records breaks the chain. Raw commands and URL query values are not stored in the receipt summary.”

**Screen**

Zoom briefly on:

- receipt ID;
- short chain head;
- local privacy indicator.

## 1:52–2:13 — Fail closed

**Screen command**

```text
اختبر رفض مهارة غير مسجلة
```

**Voiceover**

“Now the plan uses an unregistered purpose. Rayluno rejects it before any side effect. The model can propose; deterministic code remains the authority.”

Show the blocked result and that no new app or page opens.

## 2:13–2:39 — Codex and GPT-5.6

**Voiceover**

“Codex with GPT-5.6 was the primary engineering collaborator. It audited the imported baseline, split the work into reviewable pull requests, designed the task and reminder domains, built the bilingual interface, implemented the verified-skill boundary, and diagnosed CI failures through test and Ruff artifacts. We used it to challenge unsafe designs, not to bypass deterministic controls.”

**Screen**

Show quickly:

- GitHub pull-request stack;
- green CI matrix on Windows and Ubuntu, Python 3.11 and 3.13;
- README section titled ‘How Codex and GPT-5.6 were used’.

## 2:39–2:52 — Closing

**Voiceover**

“Rayluno is not a chatbot with a shell. It is a personal agent that can remember, plan, and act through bounded skills—with permission, confirmation, and proof.”

**Screen**

Return to the command center and end on the Verified Execution card.

## Required final checks

- Public YouTube URL.
- Video duration below 3:00.
- Voiceover explicitly says both “Codex” and “GPT-5.6”.
- Show the product actually running.
- Show one confirmation and one fail-closed scenario.
- Do not show tokens, license keys, private email, local usernames, or unrelated browser tabs.
- Use the exact repository URL from the submission.
