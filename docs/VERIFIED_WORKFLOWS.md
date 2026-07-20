# Rayluno Verified Workflows

Rayluno workflows are finite sequences of reviewed skills. They are not shell scripts, generated command strings, recursive agents, or hidden loops.

## Execution contract

A workflow contains between one and five steps. Every step declares:

- a unique step identifier;
- a human-readable label;
- one immutable `SkillInvocation`;
- one request identifier;
- the same local actor identity as every other step.

A workflow cannot invoke a skill whose identifier begins with `workflow.`. This prevents workflow recursion and unbounded agent chains.

Execution is strictly serial:

```text
preview
→ step 1
→ step 2
→ confirmation gate when required
→ resume the same step after approval
→ continue only after success
→ stop and skip the remainder on block, rejection, timeout, or failure
```

## Public preview

Before execution, Rayluno can expose a privacy-safe preview containing:

- workflow and step names;
- skill identifiers and versions;
- permission and risk metadata;
- argument field names;
- SHA-256 argument fingerprints;
- workflow fingerprint.

Raw argument values are excluded from public snapshots.

## Confirmation behavior

When a high-risk step requires confirmation:

1. earlier successful steps remain completed;
2. the current step becomes `confirmation_required`;
3. later steps remain `pending` and do not execute;
4. the secret confirmation token remains inside Python;
5. approval resumes exactly the paused step;
6. rejection cancels the workflow and marks later steps `skipped`;
7. replaying the confirmation handle is rejected;
8. an expired confirmation blocks the workflow and skips the remainder.

## Failure behavior

The workflow stops after the first non-success outcome. It never attempts to “work around” a denied permission or failed skill.

Terminal states are:

- `succeeded`;
- `blocked`;
- `cancelled`;
- `timed_out`;
- `failed`.

Each executed lifecycle event retains its normal tamper-evident execution receipt. The workflow does not replace or weaken the receipt chain.

## Judge demonstration

A bounded workspace-preparation workflow can demonstrate:

1. a low-risk checklist search executes and receives a receipt;
2. an application-launch step pauses before opening anything;
3. the UI shows the pending skill, permission, risk, and argument fingerprint;
4. rejection leaves the application closed and skips the final step;
5. a second run is approved;
6. the application opens once and the workflow continues to its final research step;
7. the receipt inspector verifies the complete SHA-256 chain.

The defensible product claim is:

> Rayluno can execute multi-step goals, but every effect remains a reviewed skill and every high-risk transition remains under human control.
