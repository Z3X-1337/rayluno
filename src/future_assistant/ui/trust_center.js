(() => {
  const translations = Object.freeze({
    ar: Object.freeze({
      eyebrow: "عقد الثقة التشغيلي",
      title: "ضمانات مثبتة من حالة التشغيل",
      score: "{active}/{total} ضمانات نشطة",
      skills: "{count} مهارات مسجلة",
      judge: "وضع الحكّام نشط",
      unavailable: "تعذّر قراءة عقد الثقة",
      active: "نشط",
      inactive: "متوقف",
      writeAhead: "التصريح قبل الأثر",
      writeAheadNote: "يُختم سجل التصريح قبل استدعاء نظام التشغيل.",
      checkpoint: "نقطة تحقق HMAC",
      checkpointNote: "يُطابق عدد الإيصالات ورأس السلسلة قبل التنفيذ.",
      fingerprints: "بصمات مفتاحية",
      fingerprintsNote: "HMAC-SHA256 محلي بدل بصمات قابلة للتخمين.",
      memory: "ذاكرة بموافقة صريحة",
      memoryNote: "لا حفظ سلبي، وكل عنصر قابل للفحص والحذف.",
      noShell: "لا توجد صلاحية أوامر عامة",
      noShellNote: "النموذج لا يملك أداة تنفيذ نظام عامة أو غير مقيّدة.",
      telemetry: "القياس عن بُعد متوقف",
      telemetryNote: "لا Telemetry افتراضيًا، والبيانات الشخصية محلية.",
      boundary: "حدود صريحة",
      boundaryNote: "هذه نقطة تحقق محلية وليست توقيعًا عتاديًا أو شاهدًا خارجيًا؛ وصول عملية بنفس حساب النظام إلى المفتاح المحلي يخرج عن هذا الضمان.",
    }),
    en: Object.freeze({
      eyebrow: "Runtime trust contract",
      title: "Guarantees proven from live runtime state",
      score: "{active}/{total} guarantees active",
      skills: "{count} registered skills",
      judge: "Judge Mode active",
      unavailable: "Trust contract unavailable",
      active: "Active",
      inactive: "Paused",
      writeAhead: "Authorization before effect",
      writeAheadNote: "An authorization record is sealed before the operating-system call.",
      checkpoint: "HMAC checkpoint",
      checkpointNote: "Receipt count and chain head are verified before execution.",
      fingerprints: "Keyed fingerprints",
      fingerprintsNote: "Installation-scoped HMAC-SHA256 replaces guessable digests.",
      memory: "Explicit-consent memory",
      memoryNote: "No passive storage; every fact is inspectable and deletable.",
      noShell: "No general command authority",
      noShellNote: "The model receives no unrestricted operating-system execution primitive.",
      telemetry: "Telemetry off",
      telemetryNote: "Telemetry is disabled by default and personal state stays local.",
      boundary: "Explicit boundary",
      boundaryNote: "This is a local checkpoint, not a hardware signature or remote witness. A same-user process that can read the local key is outside this guarantee.",
    }),
  });

  const guarantees = Object.freeze([
    ["write_ahead_authorization", "writeAhead", "writeAheadNote", "01"],
    ["authenticated_checkpoint", "checkpoint", "checkpointNote", "02"],
    ["keyed_fingerprints", "fingerprints", "fingerprintsNote", "03"],
    ["explicit_memory", "memory", "memoryNote", "04"],
    ["no_shell", "noShell", "noShellNote", "05"],
    ["telemetry_off", "telemetry", "telemetryNote", "06"],
  ]);

  const state = { snapshot: null, poller: null, observer: null };
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
    if (document.querySelector("#rayluno-trust-center")) return true;
    const body = document.querySelector("#verified-v2-inspector .verified-v2-body");
    const integrity = document.querySelector("#verified-v2-integrity");
    if (!body || !integrity) return false;

    const section = document.createElement("section");
    section.id = "rayluno-trust-center";
    section.className = "rayluno-trust-center";
    section.setAttribute("aria-labelledby", "rayluno-trust-title");
    section.innerHTML = `
      <header class="rayluno-trust-heading">
        <span><small id="rayluno-trust-eyebrow"></small><b id="rayluno-trust-title"></b></span>
        <span class="rayluno-trust-score" id="rayluno-trust-score"></span>
      </header>
      <div class="rayluno-trust-meta">
        <span id="rayluno-trust-skills"></span>
        <span id="rayluno-trust-judge" hidden></span>
      </div>
      <div class="rayluno-trust-grid" id="rayluno-trust-grid"></div>
      <aside class="rayluno-trust-boundary">
        <b id="rayluno-trust-boundary-title"></b>
        <small id="rayluno-trust-boundary-note"></small>
      </aside>`;

    integrity.insertAdjacentElement("afterend", section);
    Object.assign(elements, {
      section,
      eyebrow: section.querySelector("#rayluno-trust-eyebrow"),
      title: section.querySelector("#rayluno-trust-title"),
      score: section.querySelector("#rayluno-trust-score"),
      skills: section.querySelector("#rayluno-trust-skills"),
      judge: section.querySelector("#rayluno-trust-judge"),
      grid: section.querySelector("#rayluno-trust-grid"),
      boundaryTitle: section.querySelector("#rayluno-trust-boundary-title"),
      boundaryNote: section.querySelector("#rayluno-trust-boundary-note"),
    });
    applyText();
    render();
    return true;
  }

  function applyText() {
    if (!elements.section && !createInterface()) return;
    elements.eyebrow.textContent = tr("eyebrow");
    elements.title.textContent = tr("title");
    elements.boundaryTitle.textContent = tr("boundary");
    elements.boundaryNote.textContent = tr("boundaryNote");
    render();
  }

  function buildGuarantee(key, titleKey, noteKey, index, active) {
    const card = document.createElement("article");
    card.className = `rayluno-trust-card ${active ? "active" : "inactive"}`;
    card.dataset.guarantee = key;

    const marker = document.createElement("i");
    marker.textContent = index;
    marker.setAttribute("aria-hidden", "true");

    const copy = document.createElement("span");
    const title = document.createElement("b");
    title.textContent = tr(titleKey);
    const note = document.createElement("small");
    note.textContent = tr(noteKey);
    copy.append(title, note);

    const status = document.createElement("em");
    status.textContent = tr(active ? "active" : "inactive");
    card.append(marker, copy, status);
    return card;
  }

  function render() {
    if (!elements.grid) return;
    const snapshot = state.snapshot || {};
    const values = snapshot.guarantees || {};
    const active = Number(snapshot.active_count || 0);
    const total = Number(snapshot.total_count || guarantees.length);
    const available = snapshot.available !== false;

    elements.section.classList.toggle("unavailable", !available);
    elements.score.textContent = available ? tr("score", { active, total }) : tr("unavailable");
    elements.score.classList.toggle("complete", available && active === total);
    elements.skills.textContent = tr("skills", { count: Number(snapshot.registered_skill_count || 0) });
    elements.judge.hidden = !snapshot.judge_mode;
    elements.judge.textContent = tr("judge");

    elements.grid.replaceChildren();
    guarantees.forEach(([key, titleKey, noteKey, index]) => {
      elements.grid.append(buildGuarantee(key, titleKey, noteKey, index, Boolean(values[key])));
    });
  }

  async function refresh() {
    const client = api();
    if (!client) return;
    try {
      if (typeof client.get_trust_snapshot === "function") {
        state.snapshot = await client.get_trust_snapshot();
      } else if (typeof client.get_verified_snapshot === "function") {
        const verified = await client.get_verified_snapshot();
        state.snapshot = verified?.trust || null;
      }
    } catch (_error) {
      state.snapshot = { available: false, guarantees: {}, active_count: 0, total_count: 6 };
    }
    render();
  }

  function boot() {
    if (!createInterface()) {
      state.observer = new MutationObserver(() => {
        if (createInterface()) {
          state.observer?.disconnect();
          state.observer = null;
          refresh();
        }
      });
      state.observer.observe(document.body, { childList: true, subtree: true });
    }
    refresh();
    window.clearInterval(state.poller);
    state.poller = window.setInterval(refresh, 2_000);
  }

  window.addEventListener("assistantlanguagechange", applyText);
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot, { once: true });
  } else {
    boot();
  }
  if (!api()) window.addEventListener("pywebviewready", refresh, { once: true });
})();
