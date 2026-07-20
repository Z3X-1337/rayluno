(() => {
  const translations = Object.freeze({
    ar: Object.freeze({
      trustReady: "موثّق",
      trustPaused: "الثقة متوقفة",
      trustLabel: "فتح سجل التنفيذ الموثق",
      gateEyebrow: "بوابة التنفيذ",
      gateTitle: "يتطلب هذا الإجراء موافقتك",
      gateWarning: "لم ينفّذ رايلونو أي أثر بعد. راجع المهارة والصلاحية والمخاطر.",
      skill: "المهارة",
      permission: "الصلاحية",
      risk: "المخاطر",
      expires: "تنتهي خلال",
      seconds: "ثانية",
      fingerprint: "بصمة المعاملات",
      actions: "الإجراءات",
      approve: "موافقة وتنفيذ",
      reject: "رفض",
      resolving: "جارٍ التحقق…",
      expired: "انتهت مهلة التأكيد ولم يُنفّذ أي إجراء.",
      inspectorEyebrow: "دليل التنفيذ",
      inspectorTitle: "Execution Receipt Inspector",
      close: "إغلاق",
      chainVerified: "CHAIN VERIFIED",
      chainFailed: "INTEGRITY FAILED",
      chainVerifiedNote: "أُعيد حساب كل إيصال وربطه بما قبله ببصمة SHA-256.",
      chainFailedNote: "أُوقف التنفيذ لأن سجل الإيصالات لم يجتز التحقق.",
      noReceipts: "لا توجد إيصالات تنفيذ بعد.",
      receiptCount: "{count} إيصال",
      latestHash: "آخر بصمة",
      status: "الحالة",
      event: "الحدث",
      confirmation: "التأكيد",
      argumentKeys: "مفاتيح المعاملات",
      openInspector: "فتح تفاصيل سلسلة الإيصالات",
      requestPending: "بانتظار قرار المستخدم",
      succeeded: "مكتمل",
      authorized: "مصرّح",
      authorized: "مصرّح",
      blocked: "ممنوع",
      cancelled: "ملغي",
      pending: "معلّق",
      expiredStatus: "منتهي",
      failed: "فشل",
      unknown: "غير معروف",
      resultApproved: "نُفّذ الإجراء بعد موافقة صريحة.",
      resultRejected: "رُفض الإجراء ولم يحدث أي أثر.",
      loadFailed: "تعذّر قراءة حالة التنفيذ الموثق.",
    }),
    en: Object.freeze({
      trustReady: "Verified",
      trustPaused: "Trust paused",
      trustLabel: "Open verified execution history",
      gateEyebrow: "Execution gate",
      gateTitle: "This action needs your approval",
      gateWarning: "Rayluno has performed no effect. Review the skill, permission, and risk.",
      skill: "Skill",
      permission: "Permission",
      risk: "Risk",
      expires: "Expires in",
      seconds: "seconds",
      fingerprint: "Argument fingerprint",
      actions: "Actions",
      approve: "Approve and execute",
      reject: "Reject",
      resolving: "Verifying…",
      expired: "The confirmation expired and no action was executed.",
      inspectorEyebrow: "Execution proof",
      inspectorTitle: "Execution Receipt Inspector",
      close: "Close",
      chainVerified: "CHAIN VERIFIED",
      chainFailed: "INTEGRITY FAILED",
      chainVerifiedNote: "Every receipt was recomputed and linked to the previous SHA-256 hash.",
      chainFailedNote: "Execution is paused because the receipt journal failed verification.",
      noReceipts: "No execution receipts yet.",
      receiptCount: "{count} receipts",
      latestHash: "Latest hash",
      status: "Status",
      event: "Event",
      confirmation: "Confirmation",
      argumentKeys: "Argument keys",
      openInspector: "Open receipt-chain details",
      requestPending: "Waiting for the user's decision",
      succeeded: "Completed",
      authorized: "Authorized",
      authorized: "Authorized",
      blocked: "Blocked",
      cancelled: "Cancelled",
      pending: "Pending",
      expiredStatus: "Expired",
      failed: "Failed",
      unknown: "Unknown",
      resultApproved: "The action executed after explicit approval.",
      resultRejected: "The action was rejected and no effect occurred.",
      loadFailed: "Verified execution state could not be loaded.",
    }),
  });

  const state = {
    snapshot: null,
    pendingId: null,
    busy: false,
    timer: null,
    poller: null,
    boundCard: false,
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

  function createInterface() {
    if (document.querySelector("#verified-v2-trigger")) return;
    const topbar = document.querySelector(".topbar-actions");
    const settings = document.querySelector("#settings-button");

    const trigger = document.createElement("button");
    trigger.id = "verified-v2-trigger";
    trigger.className = "verified-v2-trigger";
    trigger.type = "button";
    trigger.innerHTML = [
      '<i class="verified-v2-dot" aria-hidden="true"></i>',
      '<span id="verified-v2-trigger-label"></span>',
    ].join("");
    if (topbar) settings?.before(trigger) || topbar.append(trigger);

    const gate = document.createElement("dialog");
    gate.id = "verified-v2-gate";
    gate.className = "verified-v2-dialog verified-v2-gate";
    gate.setAttribute("aria-labelledby", "verified-v2-gate-title");
    gate.innerHTML = `
      <div class="verified-v2-shell">
        <header class="verified-v2-header">
          <span class="verified-v2-shield" aria-hidden="true">◇</span>
          <span><small id="verified-v2-gate-eyebrow"></small><b id="verified-v2-gate-title"></b></span>
        </header>
        <div class="verified-v2-body">
          <p class="verified-v2-warning" id="verified-v2-warning"></p>
          <div class="verified-v2-grid">
            <span><small id="verified-v2-skill-label"></small><b id="verified-v2-skill"></b></span>
            <span><small id="verified-v2-risk-label"></small><b id="verified-v2-risk"></b></span>
            <span><small id="verified-v2-permission-label"></small><code id="verified-v2-permission"></code></span>
            <span><small id="verified-v2-expiry-label"></small><b id="verified-v2-expiry"></b></span>
          </div>
          <div class="verified-v2-fingerprint">
            <small id="verified-v2-fingerprint-label"></small>
            <code id="verified-v2-fingerprint"></code>
          </div>
          <div class="verified-v2-skill-list">
            <small id="verified-v2-actions-label"></small>
            <ol id="verified-v2-actions"></ol>
          </div>
        </div>
        <footer class="verified-v2-actions">
          <button id="verified-v2-reject" class="verified-v2-reject" type="button"></button>
          <button id="verified-v2-approve" class="verified-v2-approve" type="button"></button>
        </footer>
      </div>`;

    const inspector = document.createElement("dialog");
    inspector.id = "verified-v2-inspector";
    inspector.className = "verified-v2-dialog verified-v2-inspector";
    inspector.setAttribute("aria-labelledby", "verified-v2-inspector-title");
    inspector.innerHTML = `
      <div class="verified-v2-shell">
        <header class="verified-v2-header">
          <span class="verified-v2-shield" aria-hidden="true">⌁</span>
          <span><small id="verified-v2-inspector-eyebrow"></small><b id="verified-v2-inspector-title"></b></span>
          <button id="verified-v2-close" class="verified-v2-close" type="button">×</button>
        </header>
        <div class="verified-v2-body">
          <section class="verified-v2-integrity" id="verified-v2-integrity">
            <span><b id="verified-v2-integrity-title"></b><small id="verified-v2-integrity-note"></small></span>
            <code id="verified-v2-chain-head">—</code>
          </section>
          <div class="verified-v2-receipt-heading">
            <small id="verified-v2-receipt-count"></small>
            <span id="verified-v2-latest-label"></span>
          </div>
          <ol class="verified-v2-receipts" id="verified-v2-receipts"></ol>
        </div>
      </div>`;

    document.body.append(gate, inspector);
    cacheElements();
    bindInterface();
    applyText();
  }

  function cacheElements() {
    Object.assign(elements, {
      trigger: document.querySelector("#verified-v2-trigger"),
      triggerLabel: document.querySelector("#verified-v2-trigger-label"),
      gate: document.querySelector("#verified-v2-gate"),
      gateEyebrow: document.querySelector("#verified-v2-gate-eyebrow"),
      gateTitle: document.querySelector("#verified-v2-gate-title"),
      warning: document.querySelector("#verified-v2-warning"),
      skillLabel: document.querySelector("#verified-v2-skill-label"),
      skill: document.querySelector("#verified-v2-skill"),
      riskLabel: document.querySelector("#verified-v2-risk-label"),
      risk: document.querySelector("#verified-v2-risk"),
      permissionLabel: document.querySelector("#verified-v2-permission-label"),
      permission: document.querySelector("#verified-v2-permission"),
      expiryLabel: document.querySelector("#verified-v2-expiry-label"),
      expiry: document.querySelector("#verified-v2-expiry"),
      fingerprintLabel: document.querySelector("#verified-v2-fingerprint-label"),
      fingerprint: document.querySelector("#verified-v2-fingerprint"),
      actionsLabel: document.querySelector("#verified-v2-actions-label"),
      actions: document.querySelector("#verified-v2-actions"),
      reject: document.querySelector("#verified-v2-reject"),
      approve: document.querySelector("#verified-v2-approve"),
      inspector: document.querySelector("#verified-v2-inspector"),
      inspectorEyebrow: document.querySelector("#verified-v2-inspector-eyebrow"),
      inspectorTitle: document.querySelector("#verified-v2-inspector-title"),
      close: document.querySelector("#verified-v2-close"),
      integrity: document.querySelector("#verified-v2-integrity"),
      integrityTitle: document.querySelector("#verified-v2-integrity-title"),
      integrityNote: document.querySelector("#verified-v2-integrity-note"),
      chainHead: document.querySelector("#verified-v2-chain-head"),
      receiptCount: document.querySelector("#verified-v2-receipt-count"),
      latestLabel: document.querySelector("#verified-v2-latest-label"),
      receipts: document.querySelector("#verified-v2-receipts"),
      transcriptLabel: document.querySelector("#transcript-label"),
      transcriptText: document.querySelector("#transcript-text"),
    });
  }

  function bindInterface() {
    elements.trigger?.addEventListener("click", openInspector);
    elements.close?.addEventListener("click", () => elements.inspector?.close());
    elements.approve?.addEventListener("click", () => resolvePending(true));
    elements.reject?.addEventListener("click", () => resolvePending(false));
    elements.gate?.addEventListener("cancel", (event) => {
      event.preventDefault();
      if (!state.busy) resolvePending(false);
    });
    bindCardButtons();
    new MutationObserver(bindCardButtons).observe(document.body, { childList: true, subtree: true });
  }

  function bindCardButtons() {
    if (state.boundCard) return;
    const confirm = document.querySelector("#verified-confirm");
    const cancel = document.querySelector("#verified-cancel");
    const receipt = document.querySelector(".verified-receipt");
    if (!confirm || !cancel) return;
    confirm.addEventListener(
      "click",
      (event) => {
        event.preventDefault();
        event.stopImmediatePropagation();
        resolvePending(true);
      },
      true,
    );
    cancel.addEventListener(
      "click",
      (event) => {
        event.preventDefault();
        event.stopImmediatePropagation();
        resolvePending(false);
      },
      true,
    );
    if (receipt) {
      receipt.tabIndex = 0;
      receipt.setAttribute("role", "button");
      receipt.setAttribute("aria-label", tr("openInspector"));
      receipt.addEventListener("click", openInspector);
      receipt.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") openInspector();
      });
    }
    state.boundCard = true;
  }

  function applyText() {
    if (!elements.trigger) cacheElements();
    const ready = Boolean(state.snapshot?.integrity_ok);
    if (elements.triggerLabel) elements.triggerLabel.textContent = tr(ready ? "trustReady" : "trustPaused");
    elements.trigger?.setAttribute("aria-label", tr("trustLabel"));
    elements.trigger?.setAttribute("title", tr("trustLabel"));
    if (elements.gateEyebrow) elements.gateEyebrow.textContent = tr("gateEyebrow");
    if (elements.gateTitle) elements.gateTitle.textContent = tr("gateTitle");
    if (elements.warning) elements.warning.textContent = tr("gateWarning");
    if (elements.skillLabel) elements.skillLabel.textContent = tr("skill");
    if (elements.riskLabel) elements.riskLabel.textContent = tr("risk");
    if (elements.permissionLabel) elements.permissionLabel.textContent = tr("permission");
    if (elements.expiryLabel) elements.expiryLabel.textContent = tr("expires");
    if (elements.fingerprintLabel) elements.fingerprintLabel.textContent = tr("fingerprint");
    if (elements.actionsLabel) elements.actionsLabel.textContent = tr("actions");
    if (elements.approve && !state.busy) elements.approve.textContent = tr("approve");
    if (elements.reject && !state.busy) elements.reject.textContent = tr("reject");
    if (elements.inspectorEyebrow) elements.inspectorEyebrow.textContent = tr("inspectorEyebrow");
    if (elements.inspectorTitle) elements.inspectorTitle.textContent = tr("inspectorTitle");
    if (elements.close) elements.close.setAttribute("aria-label", tr("close"));
    if (elements.latestLabel) elements.latestLabel.textContent = tr("latestHash");
  }

  function renderTrust() {
    const ok = Boolean(state.snapshot?.integrity_ok);
    elements.trigger?.classList.toggle("failed", !ok);
    document.documentElement.classList.toggle("verified-integrity-failed", !ok);
    applyText();
  }

  function renderPending() {
    const pending = state.snapshot?.pending;
    if (!pending) {
      state.pendingId = null;
      if (elements.gate?.open && !state.busy) elements.gate.close();
      window.clearInterval(state.timer);
      return;
    }
    const isNew = pending.confirmation_id !== state.pendingId;
    state.pendingId = pending.confirmation_id;
    elements.skill.textContent = String(pending.skill_id || tr("unknown"));
    elements.permission.textContent = String(pending.permission || tr("unknown"));
    elements.risk.textContent = String(pending.risk || tr("unknown")).toUpperCase();
    elements.risk.dataset.risk = String(pending.risk || "unknown");
    elements.fingerprint.textContent = String(pending.argument_digest || "—");
    elements.fingerprint.title = String(pending.argument_digest || "");
    elements.actions.replaceChildren();
    const skills = Array.isArray(pending.skills) ? pending.skills : [];
    skills.forEach((skill) => {
      const item = document.createElement("li");
      const name = document.createElement("b");
      name.textContent = String(skill.skill_id || tr("unknown"));
      const detail = document.createElement("code");
      detail.textContent = `${skill.permission || "—"} · ${String(skill.risk || "—").toUpperCase()}`;
      item.append(name, detail);
      elements.actions.append(item);
    });
    updateCountdown();
    window.clearInterval(state.timer);
    state.timer = window.setInterval(updateCountdown, 500);
    if (isNew && !elements.gate.open) elements.gate.showModal();
  }

  function updateCountdown() {
    const expiresAt = Date.parse(state.snapshot?.pending?.expires_at || "");
    const remaining = Number.isFinite(expiresAt) ? Math.max(0, Math.ceil((expiresAt - Date.now()) / 1000)) : 0;
    if (elements.expiry) elements.expiry.textContent = `${remaining} ${tr("seconds")}`;
    elements.gate?.style.setProperty("--verified-time", String(Math.max(0, Math.min(1, remaining / 45))));
    if (remaining <= 0 && state.snapshot?.pending && !state.busy) {
      if (elements.transcriptText) elements.transcriptText.textContent = tr("expired");
      refreshVerified();
    }
  }

  async function resolvePending(approve) {
    const client = api();
    const confirmationId = state.snapshot?.pending?.confirmation_id;
    if (!client || !confirmationId || state.busy) return;
    state.busy = true;
    elements.approve.disabled = true;
    elements.reject.disabled = true;
    elements.approve.textContent = tr("resolving");
    try {
      const result = approve
        ? await client.approve_skill(confirmationId)
        : await client.reject_skill(confirmationId);
      const message = String(result?.message || (approve ? tr("resultApproved") : tr("resultRejected")));
      if (elements.transcriptLabel) elements.transcriptLabel.textContent = approve ? tr("trustReady") : tr("status");
      if (elements.transcriptText) elements.transcriptText.textContent = message;
      if (typeof showToast === "function") showToast(message);
      elements.gate?.close();
      await refreshApplicationSnapshot();
      await refreshVerified();
    } catch (_error) {
      if (elements.transcriptText) elements.transcriptText.textContent = tr("loadFailed");
    } finally {
      state.busy = false;
      elements.approve.disabled = false;
      elements.reject.disabled = false;
      applyText();
    }
  }

  async function refreshApplicationSnapshot() {
    const client = api();
    if (!client || typeof client.get_snapshot !== "function") return;
    try {
      const snapshot = await client.get_snapshot();
      if (typeof applySnapshot === "function") applySnapshot(snapshot);
    } catch (_error) {
      // The verified surface remains independently refreshable.
    }
  }

  async function refreshVerified() {
    const client = api();
    if (!client || typeof client.get_verified_snapshot !== "function") return;
    try {
      state.snapshot = await client.get_verified_snapshot();
      renderTrust();
      renderPending();
    } catch (_error) {
      state.snapshot = { available: false, integrity_ok: false, pending: null };
      renderTrust();
    }
  }

  async function openInspector() {
    const client = api();
    if (!client || typeof client.get_verified_receipts !== "function") return;
    try {
      const result = await client.get_verified_receipts(40);
      renderInspector(result || {});
      if (!elements.inspector.open) elements.inspector.showModal();
    } catch (_error) {
      renderInspector({ integrity_ok: false, receipts: [] });
      if (!elements.inspector.open) elements.inspector.showModal();
    }
  }

  function renderInspector(result) {
    const integrityOk = Boolean(result.integrity_ok);
    elements.integrity.classList.toggle("failed", !integrityOk);
    elements.integrityTitle.textContent = tr(integrityOk ? "chainVerified" : "chainFailed");
    elements.integrityNote.textContent = tr(integrityOk ? "chainVerifiedNote" : "chainFailedNote");
    const head = String(result.chain_head || "—");
    elements.chainHead.textContent = head === "—" ? head : `${head.slice(0, 16)}…${head.slice(-8)}`;
    elements.chainHead.title = head;
    const receipts = Array.isArray(result.receipts) ? result.receipts : [];
    elements.receiptCount.textContent = tr("receiptCount", { count: result.receipt_count ?? receipts.length });
    elements.receipts.replaceChildren();
    if (!receipts.length) {
      const empty = document.createElement("li");
      empty.className = "verified-v2-empty";
      empty.textContent = tr("noReceipts");
      elements.receipts.append(empty);
      return;
    }
    receipts.forEach((receipt) => elements.receipts.append(buildReceipt(receipt)));
  }

  function buildReceipt(receipt) {
    const item = document.createElement("li");
    item.className = `verified-v2-receipt status-${String(receipt.status || "unknown")}`;
    const header = document.createElement("span");
    const skill = document.createElement("b");
    skill.textContent = String(receipt.skill_id || tr("unknown"));
    const status = document.createElement("i");
    status.textContent = statusLabel(receipt.status);
    header.append(skill, status);

    const metadata = document.createElement("dl");
    appendField(metadata, tr("event"), receipt.event);
    appendField(metadata, tr("confirmation"), receipt.confirmation_state);
    appendField(metadata, tr("permission"), receipt.permission);
    appendField(metadata, tr("argumentKeys"), (receipt.argument_keys || []).join(", ") || "—");

    const footer = document.createElement("span");
    const id = document.createElement("code");
    id.textContent = String(receipt.receipt_id || "—");
    const time = document.createElement("time");
    time.textContent = formatTime(receipt.timestamp);
    footer.append(id, time);

    item.append(header, metadata, footer);
    item.title = String(receipt.receipt_hash || "");
    return item;
  }

  function appendField(list, label, value) {
    const wrapper = document.createElement("div");
    const term = document.createElement("dt");
    term.textContent = label;
    const description = document.createElement("dd");
    description.textContent = String(value || "—");
    wrapper.append(term, description);
    list.append(wrapper);
  }

  function statusLabel(status) {
    const key = {
      completed: "succeeded",
      authorized: "authorized",
      authorized: "authorized",
      blocked: "blocked",
      cancelled: "cancelled",
      pending: "pending",
      expired: "expiredStatus",
      failed: "failed",
    }[String(status)] || "unknown";
    return tr(key);
  }

  function formatTime(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "—";
    return new Intl.DateTimeFormat(language() === "ar" ? "ar-JO" : "en-GB", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    }).format(date);
  }

  async function boot() {
    createInterface();
    await refreshVerified();
    window.clearInterval(state.poller);
    state.poller = window.setInterval(refreshVerified, 2_000);
  }

  window.addEventListener("assistantlanguagechange", () => {
    applyText();
    renderTrust();
    renderPending();
  });

  if (api()) boot();
  else window.addEventListener("pywebviewready", boot, { once: true });
})();
