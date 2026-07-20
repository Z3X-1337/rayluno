# ADR-0001: Personal time engine stays separate from operating-system effects

## Status

Accepted.

## Decision

Tasks, reminders, and daily-agenda calculations are handled by local domain services that return reply-only plans and due-event objects. They do not execute operating-system effects.

## Rationale

- Time and task data are personal state, not device commands.
- Keeping them outside the action executor reduces the blast radius of parser or model errors.
- The desktop and voice layers can subscribe to due events without granting shell access.
- Future calendar integrations can be permission-gated adapters rather than hidden side effects.

## Consequences

- A separate scheduler loop is required in the desktop composition root.
- Reminder delivery is idempotent and tracked independently from task completion.
- UI and voice notification channels remain replaceable and testable.
