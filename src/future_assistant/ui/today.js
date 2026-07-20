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
      verifiedEyebrow: "درع التنفيذ",
      verifiedTitle: "تنفيذ موثّق",
      verifiedSafe: "كل إجراء مقيّد بمهارة وصلاحية",
      verifiedPending: "بانتظار تأكيدك",
      verifiedPermission: "الصلاحية",
      verifiedRisk: "المخاطر",
      verifiedConfirm: "تأكيد",
      verifiedCancel: "إلغاء",
      verifiedConfirmCommand: "تأكيد",
      verifiedCancelCommand: "إلغاء",
      verifiedLastReceipt: "آخر إيصال",
      verifiedNoReceipt: "لم يُنفّذ إجراء بعد",
      verifiedChainReady: "سلسلة تدقيق مترابطة",
      verifiedUnavailable: "محرك التحقق غير متاح",
      riskLow: "منخفضة",
      riskMedium: "متوسطة",
      riskHigh: "عالية",
      riskCritical: "حرجة",
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
      verifiedEyebrow: "Execution shield",
      verifiedTitle: "Verified execution",
      verifiedSafe: "Every action is bound to a skill and permission",
      verifiedPending: "Waiting for your confirmation",
      verifiedPermission: "Permission",
      verifiedRisk: "Risk",
      verifiedConfirm: "Confirm",
      verifiedCancel: "Cancel",
      verifiedConfirmCommand: "confirm",
      verifiedCancelCommand: "cancel",
      verifiedLastReceipt: "Latest receipt",
      verifiedNoReceipt: "No action has executed yet",
      verifiedChainReady: "Hash-linked audit chain",
      verifiedUnavailable: "Verification engine unavailable",
      riskLow: "Low",
      riskMedium: "Medium",
      riskHigh: "High",
      riskCritical: "Critical",
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

  const emptyVerified = Object.freeze({
    available: false,
    skills: [],
    pending: null,
    receipts: [],
    chain_head: null,
    privacy: "local",
  });

  const todayState = {
    personal: emptyPersonal,
    verified: emptyVerified,
    pollTimer: null,
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

  function createElement(tag, className, id) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (id) element.id = id;
    return element;
  }

  function ensureVerifiedSurface() {
    const panel = document.querySelector(".today-panel");
    if (!panel || document.querySelector("#verified-execution")) return;

    const section = createElement("section", "verified-execution", "verified-execution");
    section.setAttribute("aria-live", "polite");

    const heading = createElement("div", "verified-heading");
    const headingCopy = createElement("span");
    const eyebrow = createElement("small", "", "verified-eyebrow");
    const title = createElement("b", "", "verified-title");
    headingCopy.append(eyebrow, title);
    const status = createElement("span", "verified-status", "verified-status");
    status.setAttribute("aria-hidden", "true");
    status.textContent = "✓";
    heading.append(headingCopy, status);

    const skill = createElement("strong", "verified-skill", "verified-skill");
    const detail = createElement("small", "verified-detail", "verified-detail");

    const actions = createElement("div", "verified-actions", "verified-actions");
    const confirm = createElement("button", "verified-confirm", "verified-confirm");
    confirm.type = "button";
    const cancel = createElement("button", "verified-cancel", "verified-cancel");
    cancel.type = "button";
    actions.append(confirm, cancel);

    const receipt = createElement("div", "verified-receipt");
    const receiptLabel = createElement("small", "", "verified-receipt-label");
    const receiptId = createElement("code", "", "verified-receipt-id");
    const chain = createElement("span", "", "verified-chain");
    receipt.append(receiptLabel, receiptId, chain);

    section.append(heading, skill, detail, actions, receipt);
    const privacy = panel.querySelector(".today-privacy");
    panel.insertBefore(section, privacy || null);
  }

  ensureVerifiedSurface();

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
    verifiedEyebrow: document.querySelector("#verified-eyebrow"),
    verifiedTitle: document.querySelector("#verified-title"),
    verifiedStatus: document.querySelector("#verified-status"),
    verifiedSkill: document.querySelector("#verified-skill"),
    verifiedDetail: document.querySelector("#verified-detail"),
    verifiedActions: document.querySelector("#verified-actions"),
    verifiedConfirm: document.querySelector("#verified-confirm"),
    verifiedCancel: document.querySelector("#verified-cancel"),
    verifiedReceiptLabel: document.querySelector("#verified-receipt-label"),
    verifiedReceiptId: document.querySelector("#verified-receipt-id"),
    verifiedChain: document.querySelector("#verified-chain"),
  };

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

  function normalizeVerified(value = {}) {
    return {
      available: Boolean(value?.available),
      skills: Array.isArray(value?.skills) ? value.skills.slice(0, 20) : [],
      pending: value?.pending || null,
      receipts: Array.isArray(value?.receipts) ? value.receipts.slice(0, 5) : [],
      chain_head: value?.chain_head ? String(value.chain_head) : null,
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
    if (elements.verifiedEyebrow) elements.verifiedEyebrow.textContent = tr("verifiedEyebrow");
    if (elements.verifiedTitle) elements.verifiedTitle.textContent = tr("verifiedTitle");
    if (elements.verifiedConfirm) elements.verifiedConfirm.textContent = tr("verifiedConfirm");
    if (elements.verifiedCancel) elements.verifiedCancel.textContent = tr("verifiedCancel");
    if (elements.verifiedReceiptLabel) {
      elements.verifiedReceiptLabel.textContent = tr("verifiedLastReceipt");
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

  function riskLabel(risk) {
    const keys = {
      low: "riskLow",
      medium: "riskMedium",
      high: "riskHigh",
      critical: "riskCritical",
    };
    return tr(keys[String(risk)] || keys.medium);
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

  function renderVerified() {
    if (!elements.verifiedSkill) return;
    const verified = normalizeVerified(todayState.verified);
    const surface = document.querySelector("#verified-execution");
    surface?.classList.toggle("pending", Boolean(verified.pending));
    surface?.classList.toggle("unavailable", !verified.available);

    if (!verified.available) {
      elements.verifiedStatus.textContent = "!";
      elements.verifiedSkill.textContent = tr("verifiedUnavailable");
      elements.verifiedDetail.textContent = "—";
      elements.verifiedActions.hidden = true;
    } else if (verified.pending?.skill_id) {
      elements.verifiedStatus.textContent = "…";
      elements.verifiedSkill.textContent = `${tr("verifiedPending")} · ${verified.pending.skill_id}`;
      elements.verifiedDetail.textContent = `${tr("verifiedPermission")}: ${verified.pending.permission} · ${tr("verifiedRisk")}: ${riskLabel(verified.pending.risk)}`;
      elements.verifiedActions.hidden = false;
    } else {
      elements.verifiedStatus.textContent = "✓";
      elements.verifiedSkill.textContent = tr("verifiedSafe");
      elements.verifiedDetail.textContent = `${verified.skills.length} skills · ${tr("verifiedChainReady")}`;
      elements.verifiedActions.hidden = true;
    }

    const latest = verified.receipts[0];
    elements.verifiedReceiptId.textContent = latest?.receipt_id || tr("verifiedNoReceipt");
    elements.verifiedReceiptId.title = latest?.receipt_hash || "";
    elements.verifiedChain.textContent = verified.chain_head
      ? `#${verified.chain_head.slice(0, 10)}`
      : "—";
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

  async function refreshVerifiedSnapshot() {
    if (!apiAvailable() || typeof window.pywebview.api.get_verified_snapshot !== "function") return;
    try {
      todayState.verified = normalizeVerified(await window.pywebview.api.get_verified_snapshot());
      renderVerified();
    } catch (_error) {
      todayState.verified = emptyVerified;
      renderVerified();
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

  if (typeof applySnapshot === "function") {
    const baseApplySnapshot = applySnapshot;
    applySnapshot = function applySnapshotWithToday(snapshot = {}) {
      const result = baseApplySnapshot(snapshot);
      if (snapshot.personal) todayState.personal = normalizePersonal(snapshot.personal);
      if (snapshot.verified) todayState.verified = normalizeVerified(snapshot.verified);
      renderToday();
      renderVerified();
      return result;
    };
  }

  if (typeof submitCommand === "function") {
    const baseSubmitCommand = submitCommand;
    submitCommand = async function submitCommandWithToday(command) {
      const result = await baseSubmitCommand(command);
      await Promise.all([refreshPersonalSnapshot(), refreshVerifiedSnapshot()]);
      return result;
    };
  }

  elements.quickAgenda?.addEventListener("click", () =>
    submitCommand(elements.quickAgenda.dataset.command || ""),
  );
  elements.quickReminder?.addEventListener("click", () =>
    submitCommand(elements.quickReminder.dataset.command || ""),
  );
  elements.verifiedConfirm?.addEventListener("click", () =>
    submitCommand(tr("verifiedConfirmCommand")),
  );
  elements.verifiedCancel?.addEventListener("click", () =>
    submitCommand(tr("verifiedCancelCommand")),
  );

  window.addEventListener("assistantlanguagechange", () => {
    applyText();
    renderToday();
    renderVerified();
  });

  window.addEventListener("pywebviewready", async () => {
    await Promise.all([refreshPersonalSnapshot(), refreshVerifiedSnapshot()]);
    await pollDueReminders();
    startPolling();
  });

  applyText();
  renderToday();
  renderVerified();
})();
