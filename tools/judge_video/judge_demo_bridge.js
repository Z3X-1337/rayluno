(() => {
  const s = window.RAYLUNO_JUDGE_STATE;
  function addReceipt(skillId, permission, status, event, confirmation, risk = "medium", keys = []) {
    const hash = s.hashes[Math.min(s.receiptNumber, s.hashes.length - 1)];
    s.verified.receipts.unshift({
      receipt_id: `rcpt_demo_${String(++s.receiptNumber).padStart(3, "0")}`,
      timestamp: new Date().toISOString(),
      skill_id: skillId,
      permission,
      risk,
      status,
      event,
      confirmation_state: confirmation,
      argument_keys: keys,
      previous_hash: s.verified.chain_head,
      receipt_hash: hash,
    });
    s.verified.chain_head = hash;
  }
  function snapshot() {
    return {
      name: "Rayluno",
      version: "1.0 Build Week",
      engine: "Local deterministic engine ready",
      mode: "idle",
      history: s.copy(s.history),
      settings: { name: "Rayluno", language: "en", wake_phrase: "يا رايلونو", english_wake_phrase: "Hey Rayluno", stt_backend: "whispercpp", stt_model: "base", ollama_model: "qwen3.5:4b", tts_voice: "", telemetry_opt_in: false },
      license: { state: "free", edition: "free", pro_active: false, features: [], activation_configured: false, refresh_available: false },
      updates: { configured: false, managed_by_store: false, available: false, staged: false, version: null },
      personal: s.copy(s.personal),
      verified: s.copy(s.verified),
      memory: s.copy(s.memory),
      first_run: false,
    };
  }
  function result(command, value) {
    s.history.unshift({ command, ...value });
    s.history = s.history.slice(0, 20);
    return value;
  }
  async function execute(raw) {
    const command = String(raw || "").trim();
    const normalized = command.toLowerCase();
    await new Promise((resolve) => setTimeout(resolve, 420));
    if (normalized.startsWith("remember that")) {
      const statement = command.replace(/^remember that\s*/i, "").trim();
      s.memory.items.push({ id: 2, statement, category: "preference", source: "user_explicit", created_at: s.iso(), updated_at: s.iso() });
      s.memory.count = s.memory.items.length;
      return result(command, { ok: true, action: "memory.remember", message: "Saved only because you explicitly asked. The fact remains local and inspectable." });
    }
    if (normalized.includes("prepare the judge demo")) {
      s.verified.pending = {
        confirmation_id: "judge-demo-approval-8e4f17",
        expires_at: s.iso(45),
        skill_id: "application.launch",
        permission: "applications.launch",
        risk: "medium",
        argument_digest: "d14f6a50d61e8f9dbb578954779e42cb74956f2bb6311540a2f579af67fd7465",
        skills: [s.skills[0], s.skills[2]],
      };
      addReceipt("application.launch", "applications.launch", "pending", "confirmation_requested", "pending", "medium", ["application_id", "query"]);
      return result(command, { ok: true, action: "confirmation_required", message: "No effect has occurred. Review the exact skills, permission, risk, and fingerprint." });
    }
    if (normalized.includes("test an unregistered skill")) {
      addReceipt("unregistered.demo", "none", "blocked", "execution_blocked", "not_applicable", "critical");
      return result(command, { ok: false, action: "blocked", message: "Blocked before execution: the action is not a registered Rayluno skill." });
    }
    return result(command, { ok: true, action: "none", message: "Processed locally through the deterministic command path." });
  }
  async function approve(id) {
    const pending = s.verified.pending;
    if (!pending || id !== pending.confirmation_id) return { ok: false, message: "Invalid or expired confirmation." };
    s.verified.pending = null;
    addReceipt(pending.skill_id, pending.permission, "completed", "execution_completed", "approved", pending.risk, ["application_id", "query"]);
    return { ok: true, message: "Approved once. Only the reviewed allowlisted actions were executed." };
  }
  async function reject(id) {
    const pending = s.verified.pending;
    if (!pending || id !== pending.confirmation_id) return { ok: false, message: "Invalid or expired confirmation." };
    s.verified.pending = null;
    addReceipt(pending.skill_id, pending.permission, "cancelled", "confirmation_rejected", "rejected", pending.risk);
    return { ok: true, message: "Rejected. No operating-system effect occurred." };
  }
  window.pywebview = { api: {
    get_snapshot: async () => s.copy(snapshot()),
    get_personal_snapshot: async () => s.copy(s.personal),
    get_verified_snapshot: async () => s.copy(s.verified),
    get_verified_receipts: async (limit = 40) => ({ integrity_ok: true, chain_head: s.verified.chain_head, receipt_count: s.verified.receipts.length, receipts: s.copy(s.verified.receipts.slice(0, limit)) }),
    get_memory_snapshot: async () => s.copy(s.memory),
    execute_command: execute,
    approve_skill: approve,
    reject_skill: reject,
    clear_history: async () => { s.history = []; return { ok: true }; },
    poll_due_reminders: async () => ({ events: [] }),
    toggle_voice: async () => ({ ok: true, enabled: false, message: "Judge capture uses text input." }),
  } };
})();
