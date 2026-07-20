(() => {
  const translations = Object.freeze({
    ar: Object.freeze({
      triggerLabel: "الذاكرة",
      triggerAria: "فتح ذاكرة رايلونو المعتمدة",
      eyebrow: "ذاكرة شخصية",
      title: "Memory Vault",
      close: "إغلاق ذاكرة رايلونو",
      consentTitle: "EXPLICIT ONLY",
      consentNote: "لا يحفظ رايلونو أي معلومة إلا عندما تطلب ذلك صراحة، ويمكنك حذف كل حقيقة فورًا.",
      listLabel: "ما يعرفه رايلونو بموافقتك",
      countLabel: "{count} حقائق",
      empty: "لا توجد حقائق محفوظة. قل: تذكر أنني أفضل الردود المختصرة.",
      unavailable: "ذاكرة رايلونو غير متاحة حاليًا، ولم تُحمّل أي بيانات شخصية.",
      deleteLabel: "حذف الذاكرة رقم {id}",
      deleteSuccess: "حُذفت الذاكرة رقم {id}.",
      deleteFailed: "تعذّر حذف هذه الذاكرة بأمان.",
      identity: "هوية",
      preference: "تفضيل",
      context: "سياق",
      other: "أخرى",
      sourceExplicit: "موافقة صريحة",
    }),
    en: Object.freeze({
      triggerLabel: "Memory",
      triggerAria: "Open Rayluno's approved memory",
      eyebrow: "Personal memory",
      title: "Memory Vault",
      close: "Close Rayluno memory",
      consentTitle: "EXPLICIT ONLY",
      consentNote: "Rayluno saves a fact only when you explicitly ask and lets you delete every fact immediately.",
      listLabel: "What Rayluno knows with your consent",
      countLabel: "{count} facts",
      empty: "No approved facts yet. Say: Remember that I prefer concise answers.",
      unavailable: "Rayluno memory is unavailable, and no personal data was loaded.",
      deleteLabel: "Delete memory {id}",
      deleteSuccess: "Memory {id} was deleted.",
      deleteFailed: "This memory could not be deleted safely.",
      identity: "Identity",
      preference: "Preference",
      context: "Context",
      other: "Other",
      sourceExplicit: "Explicit consent",
    }),
  });

  const memoryState = {
    available: false,
    count: 0,
    items: [],
    busyIds: new Set(),
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

  function apiAvailable() {
    return Boolean(window.pywebview?.api);
  }

  function normalizeSnapshot(value = {}) {
    return {
      available: Boolean(value?.available),
      count: Number(value?.count || 0),
      items: Array.isArray(value?.items) ? value.items.slice(0, 100) : [],
    };
  }

  function addStylesheet() {
    if (document.querySelector('link[data-rayluno-memory="true"]')) return;
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = "memory.css";
    link.dataset.raylunoMemory = "true";
    document.head.append(link);
  }

  function createInterface() {
    const topbar = document.querySelector(".topbar-actions");
    const verifiedTrigger = document.querySelector("#verified-status-button");
    const settingsButton = document.querySelector("#settings-button");
    if (!topbar || document.querySelector("#memory-vault-button")) return;

    const trigger = document.createElement("button");
    trigger.id = "memory-vault-button";
    trigger.className = "memory-trigger";
    trigger.type = "button";
    trigger.innerHTML = [
      '<span class="memory-trigger-icon" aria-hidden="true">M</span>',
      '<span class="memory-trigger-label"></span>',
      '<span class="memory-trigger-count">0</span>',
    ].join("");
    if (verifiedTrigger) verifiedTrigger.after(trigger);
    else settingsButton?.before(trigger);

    const dialog = document.createElement("dialog");
    dialog.id = "memory-vault-dialog";
    dialog.className = "memory-dialog";
    dialog.setAttribute("aria-labelledby", "memory-vault-title");
    dialog.innerHTML = `
      <div class="memory-dialog-shell">
        <header class="memory-dialog-header">
          <div class="memory-dialog-title">
            <span class="memory-vault-mark" aria-hidden="true">M</span>
            <span>
              <small id="memory-vault-eyebrow"></small>
              <b id="memory-vault-title"></b>
            </span>
          </div>
          <button class="memory-close" id="memory-vault-close" type="button">×</button>
        </header>
        <div class="memory-dialog-body">
          <section class="memory-consent-card">
            <span class="memory-consent-icon" aria-hidden="true">✓</span>
            <span class="memory-consent-copy">
              <b id="memory-consent-title"></b>
              <small id="memory-consent-note"></small>
            </span>
          </section>
          <div class="memory-list-header">
            <span class="memory-section-label" id="memory-list-label"></span>
            <span class="memory-list-count" id="memory-list-count"></span>
          </div>
          <ol class="memory-list" id="memory-vault-list"></ol>
        </div>
      </div>
    `;
    document.body.append(dialog);
    cacheElements();
    bindInterface();
    applyText();
    render();
  }

  function cacheElements() {
    Object.assign(elements, {
      trigger: document.querySelector("#memory-vault-button"),
      triggerLabel: document.querySelector("#memory-vault-button .memory-trigger-label"),
      triggerCount: document.querySelector("#memory-vault-button .memory-trigger-count"),
      dialog: document.querySelector("#memory-vault-dialog"),
      close: document.querySelector("#memory-vault-close"),
      eyebrow: document.querySelector("#memory-vault-eyebrow"),
      title: document.querySelector("#memory-vault-title"),
      consentTitle: document.querySelector("#memory-consent-title"),
      consentNote: document.querySelector("#memory-consent-note"),
      listLabel: document.querySelector("#memory-list-label"),
      listCount: document.querySelector("#memory-list-count"),
      list: document.querySelector("#memory-vault-list"),
    });
  }

  function bindInterface() {
    elements.trigger?.addEventListener("click", openVault);
    elements.close?.addEventListener("click", () => elements.dialog?.close());
  }

  function applyText() {
    if (!elements.trigger) cacheElements();
    if (elements.triggerLabel) elements.triggerLabel.textContent = tr("triggerLabel");
    elements.trigger?.setAttribute("aria-label", tr("triggerAria"));
    elements.trigger?.setAttribute("title", tr("triggerAria"));
    if (elements.eyebrow) elements.eyebrow.textContent = tr("eyebrow");
    if (elements.title) elements.title.textContent = tr("title");
    elements.close?.setAttribute("aria-label", tr("close"));
    elements.close?.setAttribute("title", tr("close"));
    if (elements.consentTitle) elements.consentTitle.textContent = tr("consentTitle");
    if (elements.consentNote) elements.consentNote.textContent = tr("consentNote");
    if (elements.listLabel) elements.listLabel.textContent = tr("listLabel");
    render();
  }

  function categoryLabel(category) {
    const value = String(category || "other");
    return tr(["identity", "preference", "context", "other"].includes(value) ? value : "other");
  }

  function render() {
    if (!elements.list) return;
    elements.trigger?.classList.toggle("unavailable", !memoryState.available);
    if (elements.triggerCount) elements.triggerCount.textContent = String(memoryState.count);
    if (elements.listCount) {
      elements.listCount.textContent = tr("countLabel", { count: memoryState.items.length });
    }
    elements.list.replaceChildren();

    if (!memoryState.available) {
      const unavailable = document.createElement("li");
      unavailable.className = "memory-empty memory-unavailable-note";
      unavailable.textContent = tr("unavailable");
      elements.list.append(unavailable);
      return;
    }
    if (!memoryState.items.length) {
      const empty = document.createElement("li");
      empty.className = "memory-empty";
      empty.textContent = tr("empty");
      elements.list.append(empty);
      return;
    }

    memoryState.items.forEach((fact) => {
      const item = document.createElement("li");
      item.className = "memory-item";

      const id = document.createElement("span");
      id.className = "memory-item-id";
      id.textContent = `#${Number(fact.id)}`;

      const copy = document.createElement("span");
      copy.className = "memory-item-copy";
      const statement = document.createElement("b");
      statement.textContent = String(fact.statement || "");
      const meta = document.createElement("span");
      meta.className = "memory-item-meta";
      const category = document.createElement("span");
      category.className = "memory-category";
      category.textContent = categoryLabel(fact.category);
      const source = document.createElement("span");
      source.className = "memory-source";
      source.textContent = tr("sourceExplicit");
      meta.append(category, source);
      copy.append(statement, meta);

      const remove = document.createElement("button");
      remove.className = "memory-delete";
      remove.type = "button";
      remove.textContent = "×";
      remove.disabled = memoryState.busyIds.has(Number(fact.id));
      remove.setAttribute("aria-label", tr("deleteLabel", { id: fact.id }));
      remove.setAttribute("title", tr("deleteLabel", { id: fact.id }));
      remove.addEventListener("click", () => deleteMemory(Number(fact.id)));

      item.append(id, copy, remove);
      elements.list.append(item);
    });
  }

  async function refresh() {
    if (!apiAvailable() || typeof window.pywebview.api.get_memory_snapshot !== "function") {
      memoryState.available = false;
      render();
      return;
    }
    try {
      Object.assign(
        memoryState,
        normalizeSnapshot(await window.pywebview.api.get_memory_snapshot(100)),
      );
    } catch (_error) {
      memoryState.available = false;
      memoryState.count = 0;
      memoryState.items = [];
    }
    render();
  }

  async function deleteMemory(memoryId) {
    if (
      !Number.isInteger(memoryId) ||
      memoryId < 1 ||
      memoryState.busyIds.has(memoryId) ||
      !apiAvailable() ||
      typeof window.pywebview.api.forget_memory !== "function"
    ) {
      return;
    }
    memoryState.busyIds.add(memoryId);
    render();
    try {
      const result = await window.pywebview.api.forget_memory(memoryId);
      if (!result?.ok) {
        notify(String(result?.message || tr("deleteFailed")), true);
        return;
      }
      notify(String(result?.message || tr("deleteSuccess", { id: memoryId })));
      await refresh();
    } catch (_error) {
      notify(tr("deleteFailed"), true);
    } finally {
      memoryState.busyIds.delete(memoryId);
      render();
    }
  }

  async function openVault() {
    await refresh();
    if (!elements.dialog?.open) elements.dialog?.showModal();
  }

  function notify(message, isError = false) {
    if (typeof showToast === "function") showToast(message, isError);
  }

  function handleAssistantEvent(event = {}) {
    if (event.memory_snapshot) {
      Object.assign(memoryState, normalizeSnapshot(event.memory_snapshot));
      render();
    }
  }

  function installHooks() {
    const previousAssistantEvent = window.assistantEvent;
    window.assistantEvent = (event = {}) => {
      if (typeof previousAssistantEvent === "function") previousAssistantEvent(event);
      handleAssistantEvent(event);
    };

    if (typeof applySnapshot === "function") {
      const baseApplySnapshot = applySnapshot;
      applySnapshot = function applySnapshotWithMemory(snapshot = {}) {
        const result = baseApplySnapshot(snapshot);
        if (snapshot.memory) {
          Object.assign(memoryState, normalizeSnapshot(snapshot.memory));
          render();
        }
        return result;
      };
    }

    if (typeof submitCommand === "function") {
      const baseSubmitCommand = submitCommand;
      submitCommand = async function submitCommandWithMemory(command) {
        const result = await baseSubmitCommand(command);
        await refresh();
        return result;
      };
    }
  }

  addStylesheet();
  createInterface();
  installHooks();

  window.addEventListener("assistantlanguagechange", applyText);
  window.addEventListener("pywebviewready", refresh);
  if (apiAvailable()) refresh();
})();
