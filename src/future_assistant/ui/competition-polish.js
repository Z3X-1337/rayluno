(() => {
  "use strict";

  if (window.raylunoCompetitionPolish) return;

  const catalogs = Object.freeze({
    ar: Object.freeze({
      localRuntime: "محرك محلي",
      verifiedActions: "أفعال موثقة",
      telemetryOff: "التتبع متوقف",
      proofEyebrow: "دليل التنفيذ المباشر",
      proofReady: "جاهز لأمر صوتي أو نصي",
      proofListening: "الصوت يبقى داخل جهازك",
      proofUnderstanding: "تحويل الطلب إلى نية منظمة",
      proofPolicy: "فحص المهارة والصلاحية والمخاطر",
      proofExecuting: "تنفيذ المهارة المسجلة فقط",
      proofComplete: "اكتمل التنفيذ وخُتم الدليل",
      proofBlocked: "تم منع الطلب قبل الأثر",
      live: "مباشر",
      capture: "التقاط",
      captureNote: "صوت أو نص",
      understand: "فهم",
      understandNote: "نية منظمة",
      policy: "تحقق",
      policyNote: "صلاحية ومخاطر",
      execute: "تنفيذ",
      executeNote: "مهارة مسجلة",
      prove: "إثبات",
      proveNote: "إيصال مترابط",
      waitingCommand: "بانتظار الطلب…",
      localVoice: "الصوت محلي",
      planBound: "الموافقة مرتبطة بالخطة",
      evidenceFirst: "تصريح قبل الأثر",
      sourceVoice: "VOSK محلي",
      sourceText: "إدخال نصي",
      sourceResult: "دليل التنفيذ",
    }),
    en: Object.freeze({
      localRuntime: "LOCAL RUNTIME",
      verifiedActions: "VERIFIED ACTIONS",
      telemetryOff: "TELEMETRY OFF",
      proofEyebrow: "LIVE EXECUTION PROOF",
      proofReady: "Ready for a voice or text command",
      proofListening: "Voice stays on this device",
      proofUnderstanding: "Turning the request into a structured intent",
      proofPolicy: "Checking skill, permission, and risk",
      proofExecuting: "Executing registered capability only",
      proofComplete: "Execution complete and proof sealed",
      proofBlocked: "Request blocked before effect",
      live: "LIVE",
      capture: "Capture",
      captureNote: "Voice or text",
      understand: "Understand",
      understandNote: "Structured intent",
      policy: "Verify",
      policyNote: "Permission and risk",
      execute: "Act",
      executeNote: "Registered skill",
      prove: "Prove",
      proveNote: "Linked receipt",
      waitingCommand: "Waiting for a request…",
      localVoice: "Local voice",
      planBound: "Plan-bound approval",
      evidenceFirst: "Authorization before effect",
      sourceVoice: "LOCAL VOSK",
      sourceText: "TEXT INPUT",
      sourceResult: "EXECUTION PROOF",
    }),
  });

  const order = Object.freeze(["capture", "understand", "policy", "execute", "prove"]);
  const state = {
    stage: "idle",
    command: "",
    source: "voice",
    nonce: 0,
    settleTimer: null,
  };

  function language() {
    return document.documentElement.lang === "en" ? "en" : "ar";
  }

  function tr(key) {
    return catalogs[language()][key] || catalogs.en[key] || key;
  }

  function element(tag, className, text = "") {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
  }

  function ensureTrustStrip() {
    const actions = document.querySelector(".topbar-actions");
    if (!actions || document.querySelector("#competition-trust-strip")) return;

    const strip = element("div", "competition-trust-strip");
    strip.id = "competition-trust-strip";
    ["localRuntime", "verifiedActions", "telemetryOff"].forEach((key) => {
      const badge = element("span", "", tr(key));
      badge.dataset.competitionText = key;
      strip.append(badge);
    });
    actions.prepend(strip);
  }

  function ensureProofJourney() {
    const stage = document.querySelector(".assistant-stage");
    const transcript = document.querySelector(".transcript");
    const commandBar = document.querySelector(".command-bar");
    if (!stage || !transcript || !commandBar || document.querySelector("#proof-journey")) return;
    stage.classList.add("competition-stage");

    const section = element("section", "proof-journey");
    section.id = "proof-journey";
    section.setAttribute("aria-live", "polite");
    section.setAttribute("aria-label", tr("proofEyebrow"));

    const header = element("header", "proof-journey-header");
    const headerCopy = element("span");
    const eyebrow = element("small", "", tr("proofEyebrow"));
    eyebrow.dataset.competitionText = "proofEyebrow";
    const headline = element("strong", "", tr("proofReady"));
    headline.id = "proof-headline";
    headerCopy.append(eyebrow, headline);
    const live = element("span", "proof-live-badge", tr("live"));
    live.dataset.competitionText = "live";
    header.append(headerCopy, live);

    const steps = element("ol", "proof-steps");
    steps.id = "proof-steps";
    const definitions = [
      ["capture", "capture", "captureNote"],
      ["understand", "understand", "understandNote"],
      ["policy", "policy", "policyNote"],
      ["execute", "execute", "executeNote"],
      ["prove", "prove", "proveNote"],
    ];
    definitions.forEach(([id, labelKey, noteKey], index) => {
      const item = element("li", "proof-step");
      item.dataset.proofStage = id;
      const number = element("span", "proof-step-index", String(index + 1).padStart(2, "0"));
      const label = element("b", "", tr(labelKey));
      label.dataset.competitionText = labelKey;
      const note = element("small", "", tr(noteKey));
      note.dataset.competitionText = noteKey;
      item.append(number, label, note);
      steps.append(item);
    });

    const commandRow = element("div", "proof-command-row");
    const command = element("code", "", tr("waitingCommand"));
    command.id = "proof-command";
    const source = element("span", "", tr("sourceVoice"));
    source.id = "proof-source";
    commandRow.append(command, source);

    section.append(header, steps, commandRow);
    commandBar.parentNode.insertBefore(section, commandBar);

    const values = element("div", "proof-value-line");
    ["localVoice", "planBound", "evidenceFirst"].forEach((key) => {
      const item = element("span", "", tr(key));
      item.dataset.competitionText = key;
      values.append(item);
    });
    commandBar.parentNode.insertBefore(values, commandBar);
  }

  function headlineFor(stage) {
    const keys = {
      idle: "proofReady",
      capture: "proofListening",
      understand: "proofUnderstanding",
      policy: "proofPolicy",
      execute: "proofExecuting",
      prove: "proofComplete",
      blocked: "proofBlocked",
    };
    return tr(keys[stage] || keys.idle);
  }

  function render() {
    const headline = document.querySelector("#proof-headline");
    const command = document.querySelector("#proof-command");
    const source = document.querySelector("#proof-source");
    if (!headline || !command || !source) return;

    headline.textContent = headlineFor(state.stage);
    command.textContent = state.command || tr("waitingCommand");
    source.textContent = tr(
      state.stage === "prove" ? "sourceResult" : state.source === "text" ? "sourceText" : "sourceVoice",
    );
    document.body.dataset.proofState = state.stage;

    const activeIndex = order.indexOf(state.stage);
    document.querySelectorAll("[data-proof-stage]").forEach((item) => {
      const index = order.indexOf(item.dataset.proofStage);
      item.classList.toggle("is-complete", state.stage === "prove" || (activeIndex > index && activeIndex >= 0));
      item.classList.toggle("is-active", index === activeIndex);
      item.classList.toggle("is-blocked", state.stage === "blocked" && item.dataset.proofStage === "policy");
    });
  }

  function cancelTimers() {
    state.nonce += 1;
    window.clearTimeout(state.settleTimer);
  }

  function setStage(stage, { command = state.command, source = state.source } = {}) {
    state.stage = stage;
    state.command = String(command || "").trim();
    state.source = source;
    render();
  }

  function beginCommand(command, source) {
    cancelTimers();
    const nonce = state.nonce;
    setStage("understand", { command, source });
    window.setTimeout(() => {
      if (nonce === state.nonce && state.stage === "understand") setStage("policy");
    }, 260);
    window.setTimeout(() => {
      if (nonce === state.nonce && state.stage === "policy") setStage("execute");
    }, 620);
  }

  function settle(ok) {
    cancelTimers();
    setStage(ok ? "prove" : "blocked", {
      source: ok ? "result" : state.source,
    });
    state.settleTimer = window.setTimeout(() => {
      if (state.stage === "prove" || state.stage === "blocked") {
        setStage("idle", { command: "", source: "voice" });
      }
    }, 7000);
  }

  function handleAssistantEvent(event = {}) {
    if (event.mode === "listening" && !event.result) {
      const transcript = String(event.transcript || "");
      const listeningPrompt = transcript.includes("أستمع") || transcript.toLowerCase().includes("listening");
      if (listeningPrompt || !state.command) {
        cancelTimers();
        setStage("capture", { command: "", source: "voice" });
      }
    }
    if (event.mode === "thinking" && event.transcript) {
      beginCommand(String(event.transcript), "voice");
    }
    if (event.result) {
      settle(Boolean(event.result.ok));
    } else if (event.mode === "error") {
      settle(false);
    }
  }

  function attachCommandHooks() {
    const form = document.querySelector("#command-form");
    const input = document.querySelector("#command-input");
    if (form && input) {
      form.addEventListener("submit", () => {
        const command = String(input.value || "").trim();
        if (command) beginCommand(command, "text");
      }, true);
    }

    document.querySelectorAll(".quick-actions button").forEach((button) => {
      button.addEventListener("click", () => {
        const command = button.dataset.command || button.textContent || "";
        if (String(command).trim()) beginCommand(String(command), "text");
      }, true);
    });

    const activity = document.querySelector("#activity-list");
    if (activity) {
      const observer = new MutationObserver(() => {
        if (!["understand", "policy", "execute"].includes(state.stage)) return;
        const first = activity.querySelector("li:not(.empty-activity)");
        if (first) settle(!first.classList.contains("failed"));
      });
      observer.observe(activity, { childList: true });
    }
  }

  function refreshLanguage() {
    document.querySelectorAll("[data-competition-text]").forEach((node) => {
      node.textContent = tr(node.dataset.competitionText);
    });
    const section = document.querySelector("#proof-journey");
    if (section) section.setAttribute("aria-label", tr("proofEyebrow"));
    render();
  }

  ensureTrustStrip();
  ensureProofJourney();
  attachCommandHooks();

  const originalAssistantEvent = window.assistantEvent;
  window.assistantEvent = (event = {}) => {
    if (typeof originalAssistantEvent === "function") originalAssistantEvent(event);
    handleAssistantEvent(event);
  };

  window.addEventListener("assistantlanguagechange", refreshLanguage);
  render();

  window.raylunoCompetitionPolish = Object.freeze({
    setStage,
    beginCommand,
    settle,
    refreshLanguage,
  });
})();
