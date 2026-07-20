# Rayluno Verified Skills

Rayluno does not give a language model direct access to a shell. Every external effect is represented by a reviewed skill manifest and executed through an allowlisted executor.

## Trust path

```text
Voice or text request
→ deterministic or local-model plan
→ SkillInvocation
→ manifest lookup
→ exact permission check
→ argument validation
→ risk classification
→ confirmation when required
→ bounded executor
→ privacy-safe execution receipt
```

Each skill declares:

- a stable skill identifier and semantic version;
- a reviewed executor identifier;
- an exact permission set;
- a human-readable name and description;
- a risk level;
- a hard execution timeout.

Executors cannot register themselves dynamically unless their identifiers were pre-approved. Manifest permissions must exactly match executor permissions.

## Confirmation boundary

High-risk skills such as `app.launch` do not execute immediately. The Python runtime creates a short-lived, one-time confirmation grant bound to:

- the skill identifier;
- the complete immutable argument object;
- the local actor;
- the request identifier.

The secret confirmation token never crosses the desktop JavaScript bridge. The UI receives only a random `confirmation_id` plus safe metadata:

```json
{
  "skill_id": "app.launch",
  "skill_version": "1.0.0",
  "risk_level": "high",
  "permissions": ["app.launch"],
  "argument_keys": ["app_id"],
  "argument_digest": "sha256:…",
  "expires_at": "…"
}
```

Approval consumes both the UI handle and the underlying grant once. Replay, expiry, and mismatched invocation attempts fail closed.

## Execution receipts

Every lifecycle event produces `rayluno.execution-receipt/v1`. Receipts record the decision without storing raw command text or argument values.

Recorded fields include:

- skill, version, permission and risk metadata;
- status and result code;
- confirmation state;
- request and receipt identifiers;
- argument names and a SHA-256 digest;
- result field names;
- timestamps;
- previous receipt hash and current receipt hash.

Receipts form an append-only SHA-256 chain. Editing an earlier status, timestamp, skill, or decision breaks verification when the journal is reloaded.

## Judge demo

1. Say: `افتح الحاسبة`.
2. Rayluno displays `app.launch`, `high`, and permission `app.launch` before any system effect.
3. Reject it. The calculator does not open and a rejection receipt appears.
4. Repeat the command and approve it. The calculator opens once.
5. Attempt to approve the same request again. Rayluno rejects the replay.
6. Open the receipt inspector and verify the hash chain.
7. Run a low-risk web search. It executes immediately, while the receipt shows only the `query` key and digest—not the private search text.

This is the product distinction: broad capabilities without transferring unrestricted operating-system authority to the model.
