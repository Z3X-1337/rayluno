# Rayluno Personal Tasks

Rayluno can now create, list, complete, and remove personal tasks through the same
Arabic/English text path used by the desktop and voice runtimes.

## Examples

Arabic:

```text
اضف مهمة تجهيز العرض
ذكرني ان ارسل التقرير غدا
ضيف مهمة مراجعة الفيديو اليوم باولوية عالية
اعرض مهامي
انجز المهمة رقم 1
اعرض كل المهام
احذف المهمة رقم 1
```

English:

```text
add a task to prepare the demo
remind me to call the team tomorrow high priority
show my tasks
mark task 1 as done
show all tasks
delete task 1
```

## Storage and privacy

- Tasks are stored in a per-user SQLite database under Rayluno's local application-data
  directory.
- No cloud service is required.
- Task titles are not written verbatim to Rayluno's command audit log; command text is
  represented there only by a SHA-256 digest.
- The SQLite database is local but is **not application-encrypted yet**. Anyone with access
  to the operating-system user profile may be able to read it. Encryption and OS-backed
  key protection are tracked as a later hardening milestone.

## Architecture boundary

Task management is handled by `TaskCommandPlanner` and `TaskService`. It returns a
reply-only plan and never enters the operating-system action executor. Opening apps,
websites, and changing system volume continue to use the existing allowlisted
`SafetyPolicy` path.
