# Rayluno vNext Architecture

Rayluno vNext evolves the Build Week product into a user-governed personal computer agent without giving a language model unrestricted operating-system authority.

## Product thesis

Rayluno should be able to converse naturally, understand imperfect requests, and complete useful computer tasks while the user can see, constrain, approve, interrupt, and audit every consequential capability.

The product is not an unrestricted shell wrapper. It is a capability operating layer for registered skills.

## Non-negotiable invariants

1. No raw shell, PowerShell, Command Prompt, `eval`, or arbitrary executable invocation from model output.
2. Every side effect maps to a registered Skill Manifest with a schema, permission, risk, and executor.
3. The user owns the policy and can select Safe, Balanced, or Power User profiles.
4. Critical actions require a short-lived, scoped elevation session. “Always allow” cannot silently bypass this rule.
5. Approval is bound to the exact reviewed plan and expires quickly.
6. Authorization is persisted before the external effect; outcome receipts follow the effect.
7. Voice and text share the same semantic planner, policy engine, execution path, and receipts.
8. Always-listening mode is opt-in, visibly active, locally processed, and instantly disableable.
9. Autostart is opt-in and reversible from both the UI and Windows startup settings.
10. Local memory remains explicit-consent only.

## Target architecture

```text
Microphone / Text / UI
        |
        v
Interaction Runtime
- push-to-talk
- optional wake-word listener
- interruption / barge-in
- streaming transcript
- conversational state
        |
        v
Semantic Understanding Layer
- Arabic/English normalization
- typo-tolerant entity aliases
- deterministic parsers
- structured local-model planner
- confidence and clarification
- pending clarification state
        |
        v
Plan Compiler
- typed actions
- JSON-schema validation
- dependency ordering
- dry-run preview
        |
        v
Capability Policy Kernel
- user profile
- per-skill and permission-prefix rules
- ALLOW / CONFIRM / ELEVATE / DENY
- short-lived scoped elevation
- policy explanation
        |
        v
Verified Execution Runtime
- registered skills only
- write-ahead authorization
- cancellable execution
- bounded retries
- hash-linked receipts + HMAC checkpoint
        |
        v
Windows Capability Brokers
- browser
- applications
- media
- notifications
- accessibility/UI Automation
- startup integration
- system settings with UAC when required
```

## Permission profiles

### Safe

- Low-risk deterministic skills may run automatically.
- Model-proposed or medium/high-risk actions require confirmation.
- Critical actions are denied.

### Balanced

- Low-risk actions run automatically.
- Deterministic medium-risk actions may run automatically.
- Model-proposed medium/high-risk actions require confirmation.
- Critical actions require scoped elevation.

### Power User

- Low and medium registered skills may run automatically.
- High-risk actions require confirmation.
- Critical actions require scoped elevation.
- This profile still does not expose arbitrary shell or permanent administrator credentials.

## Administrator operations

Administrator authority is represented by a short-lived `ElevatedSession`, never by storing an administrator password or giving the model a permanent token.

An elevation request must include:

- permission scopes;
- exact planned actions;
- expiry of at most 15 minutes;
- Windows UAC interaction;
- a visible indicator while active;
- immediate revoke control;
- receipts for creation, use, expiry, and revocation.

## Voice architecture

### Competition release

The stable release uses local Vosk push-to-talk because Whisper-native backends crashed inside native Windows libraries on the test machine.

### vNext

The interaction runtime will support two modes:

1. Push-to-talk: one command per microphone click.
2. Wake-word mode: opt-in local listener with a visible microphone indicator.

The natural-conversation design follows a split architecture:

- an interaction model handles turn-taking, short acknowledgements, interruptions, and speech;
- a reasoning/planning model handles structured intent, clarification, and tool calls;
- long-running tools execute asynchronously while the interaction layer remains responsive.

Voice output must be interruptible. Tool activity must be announced before consequential actions. Failures must produce a recoverable explanation rather than silence.

## Understanding imperfect requests

The semantic layer uses a deterministic-first cascade:

1. preserve the original utterance;
2. normalize Arabic characters, diacritics, numbers, and common dialect forms;
3. resolve fuzzy aliases for applications, sites, and entities;
4. run deterministic task/time/media parsers;
5. ask a local model for a strict structured plan;
6. validate the plan against registered schemas;
7. execute only at sufficient confidence;
8. otherwise ask one concise clarification question and remember the pending slot temporarily.

Examples:

- `شغل جيت هوب` resolves to GitHub website or asks whether GitHub Desktop is intended.
- `دكرني كمان عشر دقايق عندي مشروع` becomes a reminder after ten minutes.
- `ذكرني بالمشروع` asks for the missing time instead of inventing one.

## Computer-use strategy

Rayluno will not pretend to “use the computer like a human” through unrestricted mouse and keyboard control. It will use a layered broker model:

1. Native APIs for reliable actions.
2. Browser and application adapters.
3. Windows UI Automation for visible, bounded interaction with known applications.
4. Screenshot/vision assistance only when structured accessibility information is unavailable.
5. User takeover and stop controls at every stage.

Every broker exposes typed operations and validation. The model never emits raw coordinates or commands directly to the operating system.

## Autostart and background mode

Autostart will use a dedicated Windows integration component with:

- explicit opt-in;
- current-state detection;
- enable/disable from settings;
- reversible registration;
- no hidden persistence;
- a tray indicator when background listening is active;
- startup health diagnostics.

## UI redesign

The next interface is organized around four surfaces:

1. Conversation: transcript, voice state, interruptions, and clarification.
2. Today: tasks, reminders, and current focus.
3. Capabilities: permission profile, per-skill rules, elevation status, and autostart.
4. Trust: plan preview, receipts, integrity, privacy, and activity history.

The most important action is always visible: stop listening, cancel execution, reject approval, or revoke elevation.

## Refactor sequence

1. Capability Policy Kernel.
2. Semantic Understanding Layer and clarification state.
3. Windows capability broker interfaces.
4. Opt-in autostart and background host.
5. Wake-word and conversational voice runtime.
6. UI information architecture redesign.
7. Dead-code removal after runtime telemetry and import analysis prove code is unused.

Code is removed only after tests, import analysis, and feature ownership identify a replacement. Broad deletion before the new boundaries exist is prohibited.
