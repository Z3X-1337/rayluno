(() => {
  const translations = Object.freeze({
    ar: Object.freeze({
      trigger: "الذاكرة",
      title: "خزنة الذاكرة الشخصية",
      eyebrow: "موافقة صريحة فقط",
      close: "إغلاق",
      localTitle: "محلية وشفافة",
      localNote: "لا تُحفظ أي معلومة إلا عندما تطلب ذلك صراحة. لا تُستخدم المحادثة العادية للحفظ.",
      count: "{count} عناصر محفوظة",
      empty: "لا توجد معلومات محفوظة بعد.",
      emptyHint: "قل: تذكّر أنني أفضل الردود المختصرة",
      delete: "حذف",
      confirmDelete: "اضغط مجددًا للتأكيد",
      clearAll: "حذف كل الذاكرة",
      clearTitle: "حذف نهائي لكل الذاكرة",
      clearNote: "سيُحذف كل ما حفظته بموافقتك من قاعدة SQLite المحلية. لا يمكن التراجع.",
      clearConfirm: "تأكيد الحذف النهائي",
      clearCancel: "إلغاء",
      clearExpires: "تنتهي الموافقة خلال {seconds} ثانية",
      clearExpired: "انتهت مهلة الحذف؛ لم يُحذف شيء.",
      deleted: "حُذفت الذاكرة رقم {id}.",
      cleared: "حُذف {count} عناصر من الذاكرة المحلية.",
      failed: "تعذّر تنفيذ العملية.",
      identity: "هوية",
      preference: "تفضيل",
      context: "سياق",
      other: "أخرى",
      source: "محفوظ بطلب صريح",
      commands: "أوامر التحكم",
      rememberCommand: "تذكّر أن…",
      listCommand: "ماذا تتذكر عني؟",
      forgetCommand: "احذف الذاكرة رقم…",
      secretPolicy: "الأسرار مرفوضة",
      secretNote: "كلمات المرور، المفاتيح، الرموز وبيانات الدفع لا تُحفظ.",
      unavailable: "خزنة الذاكرة غير متاحة.",
    }),
    en: Object.freeze({
      trigger: "Memory",
      title: "Personal Memory Vault",
      eyebrow: "Explicit consent only",
      close: "Close",
      localTitle: "Local and transparent",
      localNote: "Nothing is saved unless you explicitly ask. Ordinary conversation is never used for storage.",
      count: "{count} saved items",
      empty: "No personal memories have been saved.",
      emptyHint: "Say: Remember that I prefer concise answers",
      delete: "Delete",
      confirmDelete: "Click again to confirm",
      clearAll: "Delete all memory",
      clearTitle: "Permanently delete all memory",
      clearNote: "Every explicitly saved fact will be removed from the local SQLite database. This cannot be undone.",
      clearConfirm: "Confirm permanent deletion",
      clearCancel: "Cancel",
      clearExpires: "Approval expires in {seconds} seconds",
      clearExpired: "The deletion approval expired; nothing was deleted.",
      deleted: "Memory {id} was deleted.",
      cleared: "Deleted {count} items from local memory.",
      failed: "The operation could not be completed.",
      identity: "Identity",
      preference: "Preference",
      context: "Context",
      other: "Other",
      source: "Saved by explicit request",
      commands: "Control commands",
      rememberCommand: "Remember that…",
      listCommand: "What do you remember about me?",
      forgetCommand: "Delete memory…",
      secretPolicy: "Secrets are rejected",
      secretNote: "Passwords, keys, tokens, and payment details are never stored.",
      unavailable: "The Memory Vault is unavailable.",
    }),
  });

  const state = {
    snapshot: null,
    clear: null,
    clearTimer: null,
    poller: null,
    armedDelete: null,
    armedTimer: null,
  };
  const elements = {};

  function language() {
    return window.assistantLocalization?.getLanguage?.() === "en" ? "en" : "ar";
  }

  function tr(key, replacements = {}) {
    const catalog = translations[language()] || translations.en;
    const template = catalog[key] ?? translations.en[key] ?? key;
    return Object.entries(replacements).reduce(
      (message, [name, value]) => message.replaceAll(`{${name}}`, String(value)),
      template,
    );
  }

  function api() {
    return window.pywebview?.api || null;
  }

  function buildInterface() {
    if (document.querySelector("#memory-v2-trigger")) return;
    const topbar = document.querySelector(".topbar-actions");
    const verified = document.querySelector("#verified-v2-trigger");
    const settings = document.querySelector("#settings-button");

    const trigger = document.createElement("button");
    trigger.id = "memory-v2-trigger";
    trigger.className = "memory-v2-trigger";
    trigger.type = "button";
    trigger.innerHTML = '<span aria-hidden="true">◫</span><b id="memory-v2-trigger-label"></b><i id="memory-v2-count">0</i>';
    if (topbar) {
      if (verified) verified.after(trigger);
      else if (settings) settings.before(trigger);
      else topbar.append(trigger);
    }

    const dialog = document.createElement("dialog");
    dialog.id = "memory-v2-dialog";
    dialog.className = "memory-v2-dialog";
    dialog.setAttribute("aria-labelledby", "memory-v2-title");
    dialog.innerHTML = `
      <div class="memory-v2-shell">
        <header class="memory-v2-header">
          <span class="memory-v2-icon" aria-hidden="true">◫</span>
          <span><small id="memory-v2-eyebrow"></small><b id="memory-v2-title"></b></span>
          <button id="memory-v2-close" class="memory-v2-close" type="button">×</button>
        </header>
        <div class="memory-v2-body">
          <section class="memory-v2-consent">
            <span aria-hidden="true">✓</span>
            <span><b id="memory-v2-local-title"></b><small id="memory-v2-local-note"></small></span>
          </section>
          <div class="memory-v2-summary">
            <b id="memory-v2-summary-count"></b>
            <button id="memory-v2-clear" type="button"></button>
          </div>
          <ol id="memory-v2-list" class="memory-v2-list"></ol>
          <section class="memory-v2-command-card">
            <b id="memory-v2-commands-title"></b>
            <code id="memory-v2-command-remember"></code>
            <code id="memory-v2-command-list"></code>
            <code id="memory-v2-command-forget"></code>
          </section>
          <section class="memory-v2-secret-card">
            <b id="memory-v2-secret-title"></b>
            <small id="memory-v2-secret-note"></small>
          </section>
        </div>
        <section id="memory-v2-clear-gate" class="memory-v2-clear-gate" hidden>
          <b id="memory-v2-clear-title"></b>
          <p id="memory-v2-clear-note"></p>
          <time id="memory-v2-clear-expiry"></time>
          <span>
            <button id="memory-v2-clear-cancel" type="button"></button>
            <button id="memory-v2-clear-confirm" type="button"></button>
          </span>
        </section>
      </div>`;
    document.body.append(dialog);
    cacheElements();
    bindEvents();
    applyText();
  }

  function cacheElements() {
    Object.assign(elements, {
      trigger: document.querySelector("#memory-v2-trigger"),
      triggerLabel: document.querySelector("#memory-v2-trigger-label"),
      count: document.querySelector("#memory-v2-count"),
      dialog: document.querySelector("#memory-v2-dialog"),
      eyebrow: document.querySelector("#memory-v2-eyebrow"),
      title: document.querySelector("#memory-v2-title"),
      close: document.querySelector("#memory-v2-close"),
      localTitle: document.querySelector("#memory-v2-local-title"),
      localNote: document.querySelector("#memory-v2-local-note"),
      summaryCount: document.querySelector("#memory-v2-summary-count"),
      clear: document.querySelector("#memory-v2-clear"),
      list: document.querySelector("#memory-v2-list"),
      commandsTitle: document.querySelector("#memory-v2-commands-title"),
      commandRemember: document.querySelector("#memory-v2-command-remember"),
      commandList: document.querySelector("#memory-v2-command-list"),
      commandForget: document.querySelector("#memory-v2-command-forget"),
      secretTitle: document.querySelector("#memory-v2-secret-title"),
      secretNote: document.querySelector("#memory-v2-secret-note"),
      clearGate: document.querySelector("#memory-v2-clear-gate"),
      clearTitle: document.querySelector("#memory-v2-clear-title"),
      clearNote: document.querySelector("#memory-v2-clear-note"),
      clearExpiry: document.querySelector("#memory-v2-clear-expiry"),
      clearCancel: document.querySelector("#memory-v2-clear-cancel"),
      clearConfirm: document.querySelector("#memory-v2-clear-confirm"),
    });
  }

  function bindEvents() {
    elements.trigger?.addEventListener("click", async () => {
      await refresh();
      if (!elements.dialog.open) elements.dialog.showModal();
    });
    elements.close?.addEventListener("click", () => elements.dialog?.close());
    elements.clear?.addEventListener("click", requestClear);
    elements.clearCancel?.addEventListener("click", cancelClear);
    elements.clearConfirm?.addEventListener("click", confirmClear);
    elements.dialog?.addEventListener("cancel", () => {
      if (state.clear) cancelClear();
    });
  }

  function applyText() {
    if (!elements.trigger) cacheElements();
    if (elements.triggerLabel) elements.triggerLabel.textContent = tr("trigger");
    if (elements.eyebrow) elements.eyebrow.textContent = tr("eyebrow");
    if (elements.title) elements.title.textContent = tr("title");
    if (elements.close) elements.close.setAttribute("aria-label", tr("close"));
    if (elements.localTitle) elements.localTitle.textContent = tr("localTitle");
    if (elements.localNote) elements.localNote.textContent = tr("localNote");
    if (elements.clear) elements.clear.textContent = tr("clearAll");
    if (elements.commandsTitle) elements.commandsTitle.textContent = tr("commands");
    if (elements.commandRemember) elements.commandRemember.textContent = tr("rememberCommand");
    if (elements.commandList) elements.commandList.textContent = tr("listCommand");
    if (elements.commandForget) elements.commandForget.textContent = tr("forgetCommand");
    if (elements.secretTitle) elements.secretTitle.textContent = tr("secretPolicy");
    if (elements.secretNote) elements.secretNote.textContent = tr("secretNote");
    if (elements.clearTitle) elements.clearTitle.textContent = tr("clearTitle");
    if (elements.clearNote) elements.clearNote.textContent = tr("clearNote");
    if (elements.clearCancel) elements.clearCancel.textContent = tr("clearCancel");
    if (elements.clearConfirm) elements.clearConfirm.textContent = tr("clearConfirm");
    render();
  }

  async function refresh() {
    const client = api();
    if (!client || typeof client.get_memory_snapshot !== "function") return;
    try {
      state.snapshot = await client.get_memory_snapshot();
    } catch (_error) {
      state.snapshot = { available: false, count: 0, items: [] };
    }
    render();
  }

  function render() {
    if (!elements.list) return;
    const snapshot = state.snapshot || { available: true, count: 0, items: [] };
    const count = Number(snapshot.count || 0);
    elements.count.textContent = String(count);
    elements.summaryCount.textContent = snapshot.available
      ? tr("count", { count })
      : tr("unavailable");
    elements.trigger.classList.toggle("unavailable", !snapshot.available);
    elements.clear.disabled = !snapshot.available || count === 0;
    elements.list.replaceChildren();
    const items = Array.isArray(snapshot.items) ? snapshot.items : [];
    if (!items.length) {
      const empty = document.createElement("li");
      empty.className = "memory-v2-empty";
      const title = document.createElement("b");
      title.textContent = tr("empty");
      const hint = document.createElement("code");
      hint.textContent = tr("emptyHint");
      empty.append(title, hint);
      elements.list.append(empty);
      return;
    }
    items.forEach((fact) => elements.list.append(buildFact(fact)));
  }

  function buildFact(fact) {
    const item = document.createElement("li");
    item.className = `memory-v2-fact category-${String(fact.category || "other")}`;
    const marker = document.createElement("i");
    marker.textContent = String(fact.id || "—");
    const copy = document.createElement("span");
    const statement = document.createElement("b");
    statement.textContent = String(fact.statement || "");
    const metadata = document.createElement("small");
    metadata.textContent = `${tr(String(fact.category || "other"))} · ${tr("source")}`;
    copy.append(statement, metadata);
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = state.armedDelete === fact.id ? tr("confirmDelete") : tr("delete");
    button.addEventListener("click", () => deleteFact(fact.id));
    item.append(marker, copy, button);
    return item;
  }

  async function deleteFact(id) {
    if (state.armedDelete !== id) {
      state.armedDelete = id;
      window.clearTimeout(state.armedTimer);
      state.armedTimer = window.setTimeout(() => {
        state.armedDelete = null;
        render();
      }, 5_000);
      render();
      return;
    }
    state.armedDelete = null;
    const client = api();
    try {
      const result = await client.forget_memory(id);
      if (!result?.ok) throw new Error("delete_failed");
      state.snapshot = result.memory;
      notify(tr("deleted", { id }));
    } catch (_error) {
      notify(tr("failed"));
    }
    render();
  }

  async function requestClear() {
    const client = api();
    try {
      const result = await client.request_memory_clear();
      if (!result?.ok) throw new Error("clear_request_failed");
      state.clear = result;
      elements.clearGate.hidden = false;
      updateClearCountdown();
      window.clearInterval(state.clearTimer);
      state.clearTimer = window.setInterval(updateClearCountdown, 500);
    } catch (_error) {
      notify(tr("failed"));
    }
  }

  function updateClearCountdown() {
    const expires = Date.parse(state.clear?.expires_at || "");
    const seconds = Number.isFinite(expires) ? Math.max(0, Math.ceil((expires - Date.now()) / 1000)) : 0;
    elements.clearExpiry.textContent = tr("clearExpires", { seconds });
    if (seconds <= 0 && state.clear) {
      state.clear = null;
      elements.clearGate.hidden = true;
      window.clearInterval(state.clearTimer);
      notify(tr("clearExpired"));
    }
  }

  async function confirmClear() {
    const client = api();
    const confirmationId = state.clear?.confirmation_id;
    if (!confirmationId) return;
    try {
      const result = await client.confirm_memory_clear(confirmationId);
      if (!result?.ok) throw new Error(result?.error || "clear_failed");
      state.snapshot = result.memory;
      notify(tr("cleared", { count: result.deleted_count || 0 }));
      closeClearGate();
      render();
    } catch (_error) {
      notify(tr("failed"));
      await refresh();
    }
  }

  async function cancelClear() {
    const client = api();
    const confirmationId = state.clear?.confirmation_id;
    if (client && confirmationId) {
      try {
        await client.cancel_memory_clear(confirmationId);
      } catch (_error) {
        // Cancellation is best effort; the server-side handle still expires.
      }
    }
    closeClearGate();
  }

  function closeClearGate() {
    state.clear = null;
    elements.clearGate.hidden = true;
    window.clearInterval(state.clearTimer);
  }

  function notify(message) {
    if (typeof showToast === "function") showToast(message);
  }

  async function boot() {
    buildInterface();
    await refresh();
    window.clearInterval(state.poller);
    state.poller = window.setInterval(refresh, 4_000);
  }

  window.addEventListener("assistantlanguagechange", applyText);
  if (api()) boot();
  else window.addEventListener("pywebviewready", boot, { once: true });
})();
