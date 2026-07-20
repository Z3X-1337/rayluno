(() => {
  const translations = Object.freeze({
    ar: Object.freeze({
      trustButton: "موثّق",
      trustButtonFailed: "الثقة متوقفة",
      trustButtonLabel: "فتح سجل التنفيذ الموثق",
      confirmationEyebrow: "بوابة التنفيذ",
      confirmationTitle: "يتطلب هذا الإجراء موافقتك",
      confirmationWarning: "لم ينفّذ رايلونو أي أثر بعد. راجع الصلاحية والمخاطر قبل السماح.",
      skillLabel: "المهارة",
      riskLabel: "المخاطر",
      permissionLabel: "الصلاحية",
      expiryLabel: "تنتهي خلال",
      secondsLabel: "ثانية",
      digestLabel: "بصمة المعاملات",
      rejectAction: "رفض",
      approveAction: "موافقة وتنفيذ",
      resolvingAction: "جارٍ التحقق…",
      confirmationExpired: "انتهت مهلة التأكيد ولم يُنفّذ الإجراء.",
      invalidConfirmation: "تعذّر اعتماد هذا التأكيد بأمان.",
      receiptEyebrow: "دليل التنفيذ",
      receiptTitle: "Execution Receipt Inspector",
      receiptClose: "إغلاق سجل التنفيذ",
      chainVerified: "CHAIN VERIFIED",
      chainFailed: "INTEGRITY FAILED",
      chainVerifiedNote: "كل إيصال مرتبط بما قبله ببصمة SHA-256.",
      chainFailedNote: "أُوقف التنفيذ لأن سجل الإيصالات لم يجتز التحقق.",
      noReceipts: "لا توجد إيصالات تنفيذ بعد.",
      receiptCount: "{count} إيصال",
      receiptSucceeded: "نجح",
      receiptBlocked: "مُنع",
      receiptCancelled: "أُلغي",
      receiptPending: "بانتظار الموافقة",
      receiptOther: "مسجّل",
      verifiedExecution: "تنفيذ موثّق",
      legacyExecution: "مسار قديم — قيد الترحيل",
      latestHash: "آخر بصمة: {hash}",
      receiptLoadFailed: "تعذّر قراءة سجل التنفيذ بأمان.",
      actionApproved: "تم تنفيذ الإجراء بعد الموافقة.",
      actionRejected: "تم رفض الإجراء ولم يحدث أي أثر.",
      highRisk: "HIGH",
      mediumRisk: "MEDIUM",
      lowRisk: "LOW",
      unknownValue: "غير معروف",
    }),
    en: Object.freeze({
      trustButton: "Verified",
      trustButtonFailed: "Trust paused",
      trustButtonLabel: "Open verified execution history",
      confirmationEyebrow: "Execution gate",
      confirmationTitle: "This action needs your approval",
      confirmationWarning: "Rayluno has not performed any effect yet. Review the permission and risk before allowing it.",
      skillLabel: "Skill",
      riskLabel: "Risk",
      permissionLabel: "Permission",
      expiryLabel: "Expires in",
      secondsLabel: "seconds",
      digestLabel: "Argument fingerprint",
      rejectAction: "Reject",
      approveAction: "Approve and execute",
      resolvingAction: "Verifying…",
      confirmationExpired: "The confirmation expired and no action was executed.",
      invalidConfirmation: "This confirmation could not be approved safely.",
      receiptEyebrow: "Execution proof",
      receiptTitle: "Execution Receipt Inspector",
      receiptClose: "Close execution history",
      chainVerified: "CHAIN VERIFIED",
      chainFailed: "INTEGRITY FAILED",
      chainVerifiedNote: "Every receipt is linked to the previous receipt with SHA-256.",
      chainFailedNote: "Execution was paused because the receipt journal failed verification.",
      noReceipts: "No execution receipts yet.",
      receiptCount: "{count} receipts",
      receiptSucceeded: "Succeeded",
      receiptBlocked: "Blocked",
      receiptCancelled: "Cancelled",
      receiptPending: "Awaiting approval",
      receiptOther: "Recorded",
      verifiedExecution: "Verified execution",
      legacyExecution: "Legacy path — migration pending",
      latestHash: "Latest hash: {hash}",
      receiptLoadFailed: "The execution journal could not be read safely.",
      actionApproved: "The action executed after approval.",
      actionRejected: "The action was rejected and no effect occurred.",
      highRisk: "HIGH",
      mediumRisk: "MEDIUM",
      lowRisk: "LOW",
      unknownValue: "Unknown",
    }),
  });

  const verifiedState = {
    pending: null,
    status: {
      available: false,
      integrity_ok: false,
      receipt_count: 0,
      latest_hash: null,
    },
    receipts: [],
    countdownTimer: null,
    busy: false,
  };

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

  function addStylesheet() {
    if (document.querySelector('link[data-rayluno-verified="true"]')) return;
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = "verified.css";
    link.dataset.raylunoVerified = "true";
    document.head.append(link);
  }

  function createInterface() {
    const topbar = document.querySelector(".topbar-actions");
    const settingsButton = document.querySelector("#settings-button");
    if (!topbar || document.querySelector("#verified-status-button")) return;

    const trigger = document.createElement("button");
    trigger.id = "verified-status-button";
    trigger.className = "verified-trigger";
    trigger.type = "button";
    trigger.innerHTML = [
      '<span class="verified-trigger-dot" aria-hidden="true"></span>',
      '<span class="verified-trigger-label"></span>',
    ].join("");
    settingsButton?.before(trigger);

    const confirmation = document.createElement("dialog");
    confirmation.id = "verified-confirmation-dialog";
    confirmation.className = "verified-dialog";
    confirmation.setAttribute("aria-labelledby", "verified-confirmation-title");
    confirmation.innerHTML = `
      <div class="verified-dialog-shell">
        <header class="verified-dialog-header">
          <div class="verified-dialog-title">
            <span class="verified-shield" aria-hidden="true">◇</span>
            <span>
              <small id="verified-confirmation-eyebrow"></small>
              <b id="verified-confirmation-title"></b>
            </span>
          </div>
        </header>
        <div class="verified-dialog-body">
          <div class="verified-warning"><i aria-hidden="true"></i><span id="verified-warning-copy"></span></div>
          <div class="verified-metadata">
            <span class="verified-field"><small class="verified-section-label" id="verified-skill-label"></small><b id="verified-skill-value"></b></span>
            <span class="verified-field"><small class="verified-section-label" id="verified-risk-label"></small><b class="verified-risk" id="verified-risk-value"></b></span>
            <span class="verified-field"><small class="verified-section-label" id="verified-permission-label"></small><code id="verified-permission-value"></code></span>
            <span class="verified-field"><small class="verified-section-label" id="verified-expiry-label"></small><b id="verified-expiry-value"></b></span>
          </div>
          <div class="verified-digest">
            <small class="verified-section-label" id="verified-digest-label"></small>
            <code id="verified-digest-value"></code>
          </div>
        </div>
        <div class="verified-dialog-actions">
          <button class="verified-reject" id="verified-reject" type="button"></button>
          <button class="verified-approve" id="verified-approve" type="button"></button>
        </div>
      </div>
    `;

    const receipts = document.createElement("dialog");
    receipts.id = "verified-receipt-dialog";
    receipts.className = "verified-dialog";
    receipts.setAttribute("aria-labelledby", "verified-receipt-title");
    receipts.innerHTML = `
      <div class="verified-dialog-shell">
        <header class="verified-dialog-header">
          <div class="verified-dialog-title">
            <span class="verified-shield" aria-hidden="true">⌁</span>
            <span>
              <small id="verified-receipt-eyebrow"></small>
              <b id="verified-receipt-title"></b>
            </span>
          </div>
          <button class="verified-close" id="verified-receipt-close" type="button">×</button>
        </header>
        <div class="verified-dialog-body">
          <section class="verified-integrity-card" id="verified-integrity-card">
            <span class="verified-integrity-copy">
              <b id="verified-integrity-title"></b>
              <small id="verified-integrity-note"></small>
            </span>
            <code class="verified-hash" id="verified-latest-hash">—</code>
          </section>
          <div class="verified-section-label" id="verified-receipt-count"></div>
          <ol class="verified-receipt-list" id="verified-receipt-list"></ol>
        </div>
      </div>
    `;

    document.body.append(confirmation, receipts);
    bindInterface();
    applyText();
    renderTrustStatus();
    renderReceipts();
  }

  const elements = {};

  function cacheElements() {
    Object.assign(elements, {
      trigger: document.querySelector("#verified-status-button"),
      triggerLabel: document.querySelector("#verified-status-button .verified-trigger-label"),
      confirmationDialog: document.querySelector("#verified-confirmation-dialog"),
      confirmationEyebrow: document.querySelector("#verified-confirmation-eyebrow"),
      confirmationTitle: document.querySelector("#verified-confirmation-title"),
      warningCopy: document.querySelector("#verified-warning-copy"),
      skillLabel: document.querySelector("#verified-skill-label"),
      skillValue: document.querySelector("#verified-skill-value"),
      riskLabel: document.querySelector("#verified-risk-label"),
      riskValue: document.querySelector("#verified-risk-value"),
      permissionLabel: document.querySelector("#verified-permission-label"),
      permissionValue: document.querySelector("#verified-permission-value"),
      expiryLabel: document.querySelector("#verified-expiry-label"),
      expiryValue: document.querySelector("#verified-expiry-value"),
      digestLabel: document.querySelector("#verified-digest-label"),
      digestValue: document.querySelector("#verified-digest-value"),
      approve: document.querySelector("#verified-approve"),
      reject: document.querySelector("#verified-reject"),
      receiptDialog: document.querySelector("#verified-receipt-dialog"),
      receiptClose: document.querySelector("#verified-receipt-close"),
      receiptEyebrow: document.querySelector("#verified-receipt-eyebrow"),
      receiptTitle: document.querySelector("#verified-receipt-title"),
      integrityCard: document.querySelector("#verified-integrity-card"),
      integrityTitle: document.querySelector("#verified-integrity-title"),
      integrityNote: document.querySelector("#verified-integrity-note"),
      latestHash: document.querySelector("#verified-latest-hash"),
      receiptCount: document.querySelector("#verified-receipt-count"),
      receiptList: document.querySelector("#verified-receipt-list"),
      transcriptLabel: document.querySelector("#transcript-label"),
      transcriptText: document.querySelector("#transcript-text"),
    });
  }

  function bindInterface() {
    cacheElements();
    elements.trigger?.addEventListener("click", openReceiptInspector);
    elements.receiptClose?.addEventListener("click", () => elements.receiptDialog?.close());
    elements.approve?.addEventListener("click", () => resolvePending(true));
    elements.reject?.addEventListener("click", () => resolvePending(false));
    elements.confirmationDialog?.addEventListener("cancel", (event) => {
      event.preventDefault();
      if (!verifiedState.busy) resolvePending(false);
    });
  }

  function applyText() {
    if (!elements.trigger) cacheElements();
    if (elements.triggerLabel) {
      elements.triggerLabel.textContent = tr(
        verifiedState.status.available && verifiedState.status.integrity_ok
          ? "trustButton"
          : "trustButtonFailed",
      );
    }
    elements.trigger?.setAttribute("aria-label", tr("trustButtonLabel"));
    elements.trigger?.setAttribute("title", tr("trustButtonLabel"));
    if (elements.confirmationEyebrow) elements.confirmationEyebrow.textContent = tr("confirmationEyebrow");
    if (elements.confirmationTitle) elements.confirmationTitle.textContent = tr("confirmationTitle");
    if (elements.warningCopy) elements.warningCopy.textContent = tr("confirmationWarning");
    if (elements.skillLabel) elements.skillLabel.textContent = tr("skillLabel");
    if (elements.riskLabel) elements.riskLabel.textContent = tr("riskLabel");
    if (elements.permissionLabel) elements.permissionLabel.textContent = tr("permissionLabel");
    if (elements.expiryLabel) elements.expiryLabel.textContent = tr("expiryLabel");
    if (elements.digestLabel) elements.digestLabel.textContent = tr("digestLabel");
    if (elements.reject) elements.reject.textContent = tr("rejectAction");
    if (elements.approve) elements.approve.textContent = tr("approveAction");
    if (elements.receiptEyebrow) elements.receiptEyebrow.textContent = tr("receiptEyebrow");
    if (elements.receiptTitle) elements.receiptTitle.textContent = tr("receiptTitle");
    elements.receiptClose?.setAttribute("aria-label", tr("receiptClose"));
    elements.receiptClose?.setAttribute("title", tr("receiptClose"));
    renderTrustStatus();
    renderPending();
    renderReceipts();
  }

  function normalizeStatus(value = {}) {
    return {
      available: Boolean(value?.available),
      integrity_ok: Boolean(value?.integrity_ok),
      receipt_count: Number(value?.receipt_count || 0),
      latest_hash: typeof value?.latest_hash === "string" ? value.latest_hash : null,
    };
  }

  function renderTrustStatus() {
    const trusted = verifiedState.status.available && verifiedState.status.integrity_ok;
    elements.trigger?.classList.toggle("failed", !trusted);
    if (elements.triggerLabel) {
      elements.triggerLabel.textContent = tr(trusted ? "trustButton" : "trustButtonFailed");
    }
  }

  function riskText(value) {
    const keys = { high: "highRisk", medium: "mediumRisk", low: "lowRisk" };
    return tr(keys[String(value).toLowerCase()] || "unknownValue");
  }

  function shortHash(value, length = 14) {
    const text = String(value || "");
    if (!text) return "—";
    return text.length > length ? `${text.slice(0, length)}…` : text;
  }

  function renderPending() {
    const pending = verifiedState.pending;
    if (!pending || !elements.confirmationDialog) return;
    elements.skillValue.textContent = String(pending.skill_id || tr("unknownValue"));
    elements.riskValue.textContent = riskText(pending.risk_level);
    elements.permissionValue.textContent = Array.isArray(pending.permissions)
      ? pending.permissions.join(", ")
      : tr("unknownValue");
    elements.digestValue.textContent = String(pending.argument_digest || "—");
    updateCountdown();
  }

  function updateCountdown() {
    const pending = verifiedState.pending;
    if (!pending || !elements.expiryValue) return;
    const expiry = new Date(pending.expires_at).getTime();
    const remaining = Math.max(0, Math.ceil((expiry - Date.now()) / 1000));
    elements.expiryValue.textContent = `${remaining} ${tr("secondsLabel")}`;
    if (remaining > 0) return;
    window.clearInterval(verifiedState.countdownTimer);
    verifiedState.pending = null;
    if (elements.confirmationDialog.open) elements.confirmationDialog.close();
    notify(tr("confirmationExpired"), true);
  }

  function openConfirmation(pending) {
    if (!pending || typeof pending.confirmation_id !== "string") return;
    verifiedState.pending = pending;
    renderPending();
    window.clearInterval(verifiedState.countdownTimer);
    verifiedState.countdownTimer = window.setInterval(updateCountdown, 1000);
    if (!elements.confirmationDialog.open) elements.confirmationDialog.showModal();
  }

  function setBusy(value) {
    verifiedState.busy = Boolean(value);
    if (elements.approve) elements.approve.disabled = verifiedState.busy;
    if (elements.reject) elements.reject.disabled = verifiedState.busy;
    if (elements.approve) {
      elements.approve.textContent = tr(verifiedState.busy ? "resolvingAction" : "approveAction");
    }
  }

  async function resolvePending(approve) {
    const pending = verifiedState.pending;
    if (!pending || verifiedState.busy || !apiAvailable()) return;
    const method = approve ? "approve_skill" : "reject_skill";
    if (typeof window.pywebview.api[method] !== "function") {
      notify(tr("invalidConfirmation"), true);
      return;
    }
    setBusy(true);
    try {
      const result = await window.pywebview.api[method](pending.confirmation_id);
      verifiedState.pending = null;
      window.clearInterval(verifiedState.countdownTimer);
      if (elements.confirmationDialog.open) elements.confirmationDialog.close();
      renderResolution(result, approve);
      await refreshReceipts();
      await refreshStatus();
    } catch (_error) {
      notify(tr("invalidConfirmation"), true);
    } finally {
      setBusy(false);
    }
  }

  function renderResolution(result = {}, approved = false) {
    if (elements.transcriptLabel) {
      elements.transcriptLabel.textContent = approved ? tr("verifiedExecution") : tr("actionRejected");
    }
    if (elements.transcriptText) {
      elements.transcriptText.textContent = String(
        result?.message || tr(approved ? "actionApproved" : "actionRejected"),
      );
    }
    if (typeof setMode === "function") setMode(result?.ok ? "idle" : "error");
    notify(
      String(result?.message || tr(approved ? "actionApproved" : "actionRejected")),
      !result?.ok && approved,
    );
  }

  function notify(message, isError = false) {
    if (typeof showToast === "function") showToast(message, isError);
  }

  function receiptStateKey(receipt) {
    if (receipt?.event === "confirmation_requested") return "receiptPending";
    const status = String(receipt?.status || "");
    if (status === "succeeded") return "receiptSucceeded";
    if (status === "blocked") return "receiptBlocked";
    if (status === "cancelled") return "receiptCancelled";
    return "receiptOther";
  }

  function renderReceipts() {
    if (!elements.receiptList) return;
    const trusted = verifiedState.status.available && verifiedState.status.integrity_ok;
    elements.integrityCard?.classList.toggle("failed", !trusted);
    if (elements.integrityTitle) {
      elements.integrityTitle.textContent = tr(trusted ? "chainVerified" : "chainFailed");
    }
    if (elements.integrityNote) {
      elements.integrityNote.textContent = tr(trusted ? "chainVerifiedNote" : "chainFailedNote");
    }
    if (elements.latestHash) {
      elements.latestHash.textContent = shortHash(verifiedState.status.latest_hash, 18);
      elements.latestHash.title = String(verifiedState.status.latest_hash || "");
    }
    if (elements.receiptCount) {
      elements.receiptCount.textContent = tr("receiptCount", { count: verifiedState.receipts.length });
    }
    elements.receiptList.replaceChildren();
    if (!verifiedState.receipts.length) {
      const empty = document.createElement("li");
      empty.className = "verified-empty";
      empty.textContent = tr("noReceipts");
      elements.receiptList.append(empty);
      return;
    }
    verifiedState.receipts.forEach((receipt) => {
      const item = document.createElement("li");
      item.className = "verified-receipt";

      const icon = document.createElement("span");
      icon.className = "verified-receipt-icon";
      icon.setAttribute("aria-hidden", "true");
      icon.textContent = receipt.status === "succeeded" ? "✓" : "◇";

      const copy = document.createElement("span");
      copy.className = "verified-receipt-copy";
      const title = document.createElement("b");
      title.textContent = `${String(receipt.skill_id || "unknown")} · ${String(receipt.event || "execution")}`;
      const hash = document.createElement("code");
      hash.textContent = shortHash(receipt.receipt_hash, 22);
      hash.title = String(receipt.receipt_hash || "");
      copy.append(title, hash);

      const state = document.createElement("span");
      state.className = "verified-receipt-state";
      state.textContent = tr(receiptStateKey(receipt));
      item.append(icon, copy, state);
      elements.receiptList.append(item);
    });
  }

  async function refreshStatus() {
    if (!apiAvailable() || typeof window.pywebview.api.get_verified_status !== "function") return;
    try {
      verifiedState.status = normalizeStatus(await window.pywebview.api.get_verified_status());
      renderTrustStatus();
      renderReceipts();
    } catch (_error) {
      verifiedState.status = normalizeStatus({});
      renderTrustStatus();
    }
  }

  async function refreshReceipts() {
    if (!apiAvailable() || typeof window.pywebview.api.get_verified_receipts !== "function") return;
    try {
      const result = await window.pywebview.api.get_verified_receipts(20);
      verifiedState.receipts = Array.isArray(result?.receipts) ? result.receipts : [];
      verifiedState.status.integrity_ok = Boolean(result?.integrity_ok);
      verifiedState.status.receipt_count = verifiedState.receipts.length;
      verifiedState.status.latest_hash = verifiedState.receipts[0]?.receipt_hash || null;
      renderTrustStatus();
      renderReceipts();
    } catch (_error) {
      notify(tr("receiptLoadFailed"), true);
    }
  }

  async function openReceiptInspector() {
    await refreshStatus();
    await refreshReceipts();
    if (!elements.receiptDialog.open) elements.receiptDialog.showModal();
  }

  function handleAssistantEvent(event = {}) {
    if (event.verified_status) {
      verifiedState.status = normalizeStatus(event.verified_status);
      renderTrustStatus();
    }
    if (event.verified_confirmation) openConfirmation(event.verified_confirmation);
    if (event.verified_receipt) {
      const receipt = event.verified_receipt;
      const duplicate = verifiedState.receipts.some(
        (current) => current.receipt_id === receipt.receipt_id,
      );
      if (!duplicate) verifiedState.receipts.unshift(receipt);
      verifiedState.receipts = verifiedState.receipts.slice(0, 20);
      verifiedState.status.receipt_count = verifiedState.receipts.length;
      verifiedState.status.latest_hash = receipt.receipt_hash || null;
      renderReceipts();
    }
    if (event.verified_resolution) {
      verifiedState.pending = null;
      window.clearInterval(verifiedState.countdownTimer);
      if (elements.confirmationDialog?.open) elements.confirmationDialog.close();
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
      applySnapshot = function applySnapshotWithVerified(snapshot = {}) {
        const result = baseApplySnapshot(snapshot);
        if (snapshot.verified) {
          verifiedState.status = normalizeStatus(snapshot.verified);
          renderTrustStatus();
        }
        return result;
      };
    }
  }

  addStylesheet();
  createInterface();
  installHooks();

  window.addEventListener("assistantlanguagechange", applyText);
  window.addEventListener("pywebviewready", async () => {
    await refreshStatus();
    await refreshReceipts();
  });

  if (apiAvailable()) {
    refreshStatus();
    refreshReceipts();
  }
})();
