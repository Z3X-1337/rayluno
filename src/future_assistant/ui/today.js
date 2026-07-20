(() => {
  const translations = Object.freeze({
    ar: Object.freeze({
      quickAgendaLabel: "خطة اليوم",
      quickAgendaCommand: "ما خطتي اليوم",
      quickReminderLabel: "تذكير سريع",
      quickReminderCommand: "ذكرني بعد عشر دقائق أراجع العرض",
      todayPanelLabel: "لوحة اليوم",
      todayEyebrow: "القيادة الشخصية",
      todayTitle: "اليوم",
      todayLiveTitle: "بيانات محلية مباشرة",
      todayFocusLabel: "التركيز المقترح",
      todayNoFocus: "لا توجد أولوية عاجلة",
      todayReadyMeta: "يومك تحت السيطرة",
      todayOverdue: "متأخر",
      todayTasks: "مهام اليوم",
      todaySoon: "قريب",
      todayStatsLabel: "ملخص اليوم",
      todayNextReminder: "التذكير القادم",
      todayNoReminder: "لا يوجد تذكير قادم",
      todayAgendaLabel: "الالتزامات",
      todayEmpty: "ابدأ بإضافة مهمة أو تذكير",
      todayLocalTitle: "ذاكرة محلية",
      todayLocalNote: "المهام والتذكيرات لا تغادر جهازك",
      taskKind: "مهمة",
      reminderKind: "تذكير",
      priorityHigh: "أولوية عالية",
      priorityNormal: "أولوية عادية",
      priorityLow: "أولوية منخفضة",
      dueLabel: "الموعد",
      reminderDueToast: "حان موعد: {title}",
    }),
    en: Object.freeze({
      quickAgendaLabel: "Today's plan",
      quickAgendaCommand: "What is my plan today",
      quickReminderLabel: "Quick reminder",
      quickReminderCommand: "Remind me in ten minutes to review the demo",
      todayPanelLabel: "Today panel",
      todayEyebrow: "Personal command",
      todayTitle: "Today",
      todayLiveTitle: "Live local data",
      todayFocusLabel: "Recommended focus",
      todayNoFocus: "Nothing urgent",
      todayReadyMeta: "Your day is under control",
      todayOverdue: "Overdue",
      todayTasks: "Due today",
      todaySoon: "Due soon",
      todayStatsLabel: "Today summary",
      todayNextReminder: "Next reminder",
      todayNoReminder: "No upcoming reminder",
      todayAgendaLabel: "Commitments",
      todayEmpty: "Add a task or reminder to begin",
      todayLocalTitle: "Local memory",
      todayLocalNote: "Tasks and reminders stay on this device",
      taskKind: "Task",
      reminderKind: "Reminder",
      priorityHigh: "High priority",
      priorityNormal: "Normal priority",
      priorityLow: "Low priority",
      dueLabel: "Due",
      reminderDueToast: "Reminder due: {title}",
    }),
  });

  const emptyPersonal = Object.freeze({
    available: false,
    counts: { overdue: 0, today: 0, due_soon: 0, later: 0, unscheduled: 0 },
    focus: null,
    next_reminder: null,
    items: [],
    privacy: "local",
  });

  const todayState = {
    personal: emptyPersonal,
    pollTimer: null,
  };

  const elements = {
    quickAgenda: document.querySelector("#quick-agenda"),
    quickReminder: document.querySelector("#quick-reminder"),
    focusTitle: document.querySelector("#today-focus-title"),
    focusMeta: document.querySelector("#today-focus-meta"),
    overdueCount: document.querySelector("#today-overdue-count"),
    taskCount: document.querySelector("#today-task-count"),
    soonCount: document.querySelector("#today-soon-count"),
    nextReminderTitle: document.querySelector("#next-reminder-title"),
    nextReminderTime: document.querySelector("#next-reminder-time"),
    agendaCount: document.querySelector("#today-agenda-count"),
    agendaList: document.querySelector("#today-agenda-list"),
    transcriptLabel: document.querySelector("#transcript-label"),
    transcriptText: document.querySelector("#transcript-text"),
  };

  function language() {
    const current = window.assistantLocalization?.getLanguage?.();
    return current === "en" ? "en" : "ar";
  }

  function tr(key, replacements = {}) {
    const catalog = translations[language()] || translations.en;
    const template = catalog[key] ?? translations.en[key] ?? key;
    return Object.entries(replacements).reduce(
      (message, [name, value]) => message.replaceAll(`{${name}}`, String(value)),
      template,
    );
  }

  function apiAvailable() {
    return Boolean(window.pywebview?.api);
  }

  function normalizePersonal(value = {}) {
    const counts = value?.counts || {};
    return {
      available: Boolean(value?.available),
      counts: {
        overdue: Number(counts.overdue || 0),
        today: Number(counts.today || 0),
        due_soon: Number(counts.due_soon || 0),
        later: Number(counts.later || 0),
        unscheduled: Number(counts.unscheduled || 0),
      },
      focus: value?.focus || null,
      next_reminder: value?.next_reminder || null,
      items: Array.isArray(value?.items) ? value.items.slice(0, 5) : [],
      privacy: String(value?.privacy || "local"),
    };
  }

  function applyText() {
    document.querySelectorAll(".today-panel [data-i18n]").forEach((element) => {
      element.textContent = tr(element.dataset.i18n);
    });
    document.querySelectorAll(".today-panel [data-i18n-aria-label]").forEach((element) => {
      element.setAttribute("aria-label", tr(element.dataset.i18nAriaLabel));
    });
    document.querySelectorAll(".today-panel [data-i18n-title]").forEach((element) => {
      element.setAttribute("title", tr(element.dataset.i18nTitle));
    });
    if (elements.quickAgenda) {
      elements.quickAgenda.textContent = tr("quickAgendaLabel");
      elements.quickAgenda.dataset.command = tr("quickAgendaCommand");
    }
    if (elements.quickReminder) {
      elements.quickReminder.textContent = tr("quickReminderLabel");
      elements.quickReminder.dataset.command = tr("quickReminderCommand");
    }
  }

  function formatTime(value) {
    if (!value) return "—";
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return "—";
    return new Intl.DateTimeFormat(language() === "ar" ? "ar-JO" : "en-GB", {
      hour: "2-digit",
      minute: "2-digit",
    }).format(parsed);
  }

  function priorityLabel(priority) {
    const keys = { high: "priorityHigh", normal: "priorityNormal", low: "priorityLow" };
    return tr(keys[String(priority)] || keys.normal);
  }

  function renderToday() {
    if (!elements.agendaList) return;
    const personal = normalizePersonal(todayState.personal);
    elements.overdueCount.textContent = String(personal.counts.overdue);
    elements.taskCount.textContent = String(personal.counts.today);
    elements.soonCount.textContent = String(personal.counts.due_soon);

    if (personal.focus?.title) {
      elements.focusTitle.textContent = String(personal.focus.title);
      const kind = personal.focus.kind === "reminder" ? tr("reminderKind") : tr("taskKind");
      elements.focusMeta.textContent = `${kind} · ${priorityLabel(personal.focus.priority)}`;
    } else {
      elements.focusTitle.textContent = tr("todayNoFocus");
      elements.focusMeta.textContent = tr("todayReadyMeta");
    }

    if (personal.next_reminder?.title) {
      elements.nextReminderTitle.textContent = String(personal.next_reminder.title);
      elements.nextReminderTime.textContent = formatTime(personal.next_reminder.due_at);
    } else {
      elements.nextReminderTitle.textContent = tr("todayNoReminder");
      elements.nextReminderTime.textContent = "—";
    }

    elements.agendaList.replaceChildren();
    elements.agendaCount.textContent = String(personal.items.length);
    if (!personal.items.length) {
      const empty = document.createElement("li");
      empty.className = "today-empty";
      empty.textContent = tr("todayEmpty");
      elements.agendaList.append(empty);
      return;
    }

    personal.items.forEach((entry) => {
      const item = document.createElement("li");
      item.className = String(entry.priority || "normal");
      const copy = document.createElement("span");
      copy.className = "today-item-copy";
      const title = document.createElement("b");
      title.textContent = String(entry.title || "");
      const meta = document.createElement("small");
      const due = entry.due_date ? ` · ${tr("dueLabel")} ${entry.due_date}` : "";
      meta.textContent = `${priorityLabel(entry.priority)}${due}`;
      copy.append(title, meta);
      item.append(copy);
      elements.agendaList.append(item);
    });
  }

  async function refreshPersonalSnapshot() {
    if (!apiAvailable() || typeof window.pywebview.api.get_personal_snapshot !== "function") return;
    try {
      todayState.personal = normalizePersonal(await window.pywebview.api.get_personal_snapshot());
      renderToday();
    } catch (_error) {
      // Personal data is optional; the command path remains usable when unavailable.
    }
  }

  async function pollDueReminders() {
    if (!apiAvailable() || typeof window.pywebview.api.poll_due_reminders !== "function") return;
    try {
      const result = await window.pywebview.api.poll_due_reminders();
      const events = Array.isArray(result?.events) ? result.events : [];
      events.forEach((event) => {
        const title = String(event.title || tr("reminderKind"));
        if (typeof showToast === "function") showToast(tr("reminderDueToast", { title }));
        if (elements.transcriptLabel) elements.transcriptLabel.textContent = tr("todayNextReminder");
        if (elements.transcriptText) elements.transcriptText.textContent = title;
      });
      if (events.length) await refreshPersonalSnapshot();
    } catch (_error) {
      // Reminder polling is best effort and never blocks the command path.
    }
  }

  function startPolling() {
    window.clearInterval(todayState.pollTimer);
    todayState.pollTimer = window.setInterval(pollDueReminders, 15_000);
  }

  function loadVerifiedInterface() {
    if (document.querySelector('script[data-rayluno-verified="true"]')) return;
    const script = document.createElement("script");
    script.src = "verified.js";
    script.dataset.raylunoVerified = "true";
    document.body.append(script);
  }

  if (typeof applySnapshot === "function") {
    const baseApplySnapshot = applySnapshot;
    applySnapshot = function applySnapshotWithToday(snapshot = {}) {
      const result = baseApplySnapshot(snapshot);
      if (snapshot.personal) todayState.personal = normalizePersonal(snapshot.personal);
      renderToday();
      return result;
    };
  }

  if (typeof submitCommand === "function") {
    const baseSubmitCommand = submitCommand;
    submitCommand = async function submitCommandWithToday(command) {
      const result = await baseSubmitCommand(command);
      await refreshPersonalSnapshot();
      return result;
    };
  }

  elements.quickAgenda?.addEventListener("click", () =>
    submitCommand(elements.quickAgenda.dataset.command || ""),
  );
  elements.quickReminder?.addEventListener("click", () =>
    submitCommand(elements.quickReminder.dataset.command || ""),
  );

  window.addEventListener("assistantlanguagechange", () => {
    applyText();
    renderToday();
  });

  window.addEventListener("pywebviewready", async () => {
    await refreshPersonalSnapshot();
    await pollDueReminders();
    startPolling();
  });

  applyText();
  renderToday();
  loadVerifiedInterface();
})();
