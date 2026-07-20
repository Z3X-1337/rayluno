# Rayluno Personal Memory Vault

Rayluno's personal memory is local, explicit, reviewable, and deletable. It does not silently learn from conversations and it does not save a statement merely because the user mentioned it.

## Consent rule

A fact is persisted only after a direct command such as:

```text
تذكر أن اسمي زيد
احفظ أنني أفضل الوضع الداكن
Remember that I prefer concise answers
Keep in mind that my demo language is Arabic
```

Ordinary conversation, model replies, search queries, task descriptions, and reminder text are not automatically converted into personal memory.

Every stored fact records:

- a local numeric identifier;
- the original wording supplied by the user;
- a category: identity, preference, context, or other;
- source `user_explicit`;
- a SHA-256 fingerprint for deduplication;
- creation and update timestamps.

## Review and deletion

The user can inspect and remove memories through the same Arabic/English command path:

```text
ماذا تتذكر عني
احذف الذاكرة رقم 2

What do you remember about me
Forget memory 2
```

The assistant returns the exact stored statements and their categories. Deletion is immediate and survives application restarts because the source row is removed from the local SQLite vault.

## Sensitive-data boundary

Rayluno refuses to store likely secrets, including:

- passwords, PINs, and verification codes;
- API keys, private keys, and access or refresh tokens;
- card numbers, CVV values, and payment credentials;
- seed or recovery phrases.

This is a safety filter, not a password manager. Users should keep secrets in a dedicated credential vault.

## Storage and privacy

The vault is stored in the user's local Rayluno application-data directory as `memory.sqlite3`. No cloud service is required.

Raw memory text is not written into Rayluno's command audit log. The audit layer continues to represent user commands through privacy-preserving digests.

The SQLite database is currently protected by the operating-system user profile but is not application-encrypted. OS-backed encryption is a separate hardening milestone and must not be claimed before implementation.

## Model-personalization boundary

This milestone creates a trustworthy source of user-approved facts. The memory is **not automatically injected into every model prompt yet**. A later personalization layer will retrieve only a small relevant subset, display what context is being used, and allow the user to disable it.

This separation prevents a memory feature from becoming hidden prompt accumulation.

## Judge demo

1. Ask: `ماذا تتذكر عني` — Rayluno states that no memories exist and explains the consent rule.
2. Say: `تذكر أنني أفضل الردود المختصرة`.
3. Ask again — the exact statement appears as an explicit preference with a memory ID.
4. Repeat the same fact — the vault refreshes the existing fact rather than creating a duplicate.
5. Say: `تذكر أن كلمة المرور هي 123456` — Rayluno refuses and stores nothing.
6. Say: `احذف الذاكرة رقم 1` — the fact disappears immediately.
7. Restart the application and verify that only non-deleted approved memories persist.

The product claim is narrow and defensible: Rayluno remembers what the user explicitly authorizes, and nothing else.
