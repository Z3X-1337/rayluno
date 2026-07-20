# Reminders and Daily Agenda

This document defines the second personal-assistant milestone.

## Goal

Turn the task list into an active daily operating surface. Rayluno should answer what matters now, notify once when a reminder becomes due, and let the user snooze or complete it by voice.

## Commands

Arabic examples:

```text
ذكرني الساعة 6 ارسل التقرير
ذكرني بعد عشر دقائق اتصل بالفريق
ما خطتي اليوم
شو عندي متأخر
اجل التذكير رقم 2 عشر دقائق
انجز التذكير رقم 2
```

English examples:

```text
remind me at 6 pm to send the report
remind me in ten minutes to call the team
what is my plan today
what is overdue
snooze reminder 2 for ten minutes
complete reminder 2
```

## Safety and privacy

- Reminder content stays local.
- A reminder is delivered once per due occurrence unless the user snoozes it.
- The scheduler exposes due reminder events; the desktop layer decides how to display or speak them.
- No background shell or unrestricted command execution is introduced.
- Future calendar connectors must remain explicit and permission-gated.
