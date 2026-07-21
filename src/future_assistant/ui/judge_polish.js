(() => {
  const translations = Object.freeze({
    ar: Object.freeze({
      badge: "وضع الحكّام · وصول تقييمي محدود",
      proofLabel: "حدود التنفيذ المعلنة",
      proofItems: ["صوت محلي", "خطة مغلقة", "موافقة صريحة", "إيصال موثّق"],
    }),
    en: Object.freeze({
      badge: "JUDGE MODE · BOUNDED EVALUATION ACCESS",
      proofLabel: "Declared execution boundary",
      proofItems: ["Local voice", "Closed plan", "Explicit approval", "Verified receipt"],
    }),
  });

  const language = () => (document.documentElement.lang === "en" ? "en" : "ar");

  function catalog() {
    return translations[language()] || translations.en;
  }

  function createBadge() {
    let badge = document.querySelector("#judge-mode-badge");
    if (badge) return badge;
    badge = document.createElement("div");
    badge.id = "judge-mode-badge";
    badge.className = "judge-mode-badge";
    badge.setAttribute("role", "note");
    badge.setAttribute("aria-live", "polite");
    const marker = document.createElement("i");
    marker.setAttribute("aria-hidden", "true");
    const label = document.createElement("span");
    badge.append(marker, label);
    document.querySelector(".topbar-actions")?.prepend(badge);
    return badge;
  }

  function createProofStrip() {
    let strip = document.querySelector("#judge-proof-strip");
    if (strip) return strip;
    strip = document.createElement("div");
    strip.id = "judge-proof-strip";
    strip.className = "judge-proof-strip";
    strip.setAttribute("role", "list");
    const transcript = document.querySelector(".transcript");
    transcript?.after(strip);
    return strip;
  }

  function render() {
    document.documentElement.dataset.raylunoJudgeMode = "true";
    const text = catalog();
    const badge = createBadge();
    const badgeLabel = badge.querySelector("span");
    if (badgeLabel) badgeLabel.textContent = text.badge;

    const strip = createProofStrip();
    strip.setAttribute("aria-label", text.proofLabel);
    strip.replaceChildren();
    text.proofItems.forEach((item) => {
      const entry = document.createElement("span");
      entry.setAttribute("role", "listitem");
      const marker = document.createElement("i");
      marker.setAttribute("aria-hidden", "true");
      const label = document.createElement("b");
      label.textContent = item;
      entry.append(marker, label);
      strip.append(entry);
    });
  }

  window.addEventListener("assistantlanguagechange", render);
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", render, { once: true });
  } else {
    render();
  }
})();
