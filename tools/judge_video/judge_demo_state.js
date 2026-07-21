(() => {
  const iso = (seconds = 0) => new Date(Date.now() + seconds * 1000).toISOString();
  const skills = [
    { skill_id: "web.search", permission: "network.browser.search", risk: "medium" },
    { skill_id: "web.navigate", permission: "network.browser.navigate", risk: "medium" },
    { skill_id: "application.launch", permission: "applications.launch", risk: "medium" },
    { skill_id: "system.time.read", permission: "system.time.read", risk: "low" },
    { skill_id: "system.audio.control", permission: "system.audio.control", risk: "low" },
  ];
  window.RAYLUNO_JUDGE_STATE = {
    copy: (value) => JSON.parse(JSON.stringify(value)),
    iso,
    skills,
    history: [],
    personal: {
      available: true,
      privacy: "local",
      counts: { overdue: 1, today: 2, due_soon: 1, later: 1, unscheduled: 0 },
      focus: { kind: "task", title: "Finalize the Build Week demo", priority: "high" },
      next_reminder: { title: "Upload the public demo video", due_at: iso(5_400) },
      items: [
        { kind: "task", title: "Finalize the Build Week demo", priority: "high", due_date: new Date().toISOString().slice(0, 10) },
        { kind: "task", title: "Verify the Devpost fields", priority: "normal", due_date: new Date().toISOString().slice(0, 10) },
        { kind: "reminder", title: "Upload the public demo video", priority: "normal", due_date: new Date().toISOString().slice(0, 10) },
      ],
    },
    memory: {
      available: true,
      consent_mode: "explicit_only",
      storage: "local_sqlite",
      count: 1,
      clear_pending: null,
      items: [{
        id: 1,
        statement: "My name is Zaid",
        category: "identity",
        source: "user_explicit",
        created_at: iso(-8_640),
        updated_at: iso(-8_640),
      }],
    },
    verified: {
      available: true,
      integrity_ok: true,
      integrity_error: null,
      skills,
      pending: null,
      receipts: [],
      chain_head: "0000000000000000000000000000000000000000000000000000000000000000",
      privacy: "local",
    },
    hashes: [
      "7cc932b81a807c81a70fda71a4459c37de7ad871f33a8f1b58ac857bf4df16a2",
      "1b79f68818edbd9f7f0b6755ae4fcb484a6ec9685b077a2ee7992d2529f14d21",
      "f925c56ce3968ce2ca87d3a35af85bea67a46e2db32920ddb7a59c15efbc1d63",
    ],
    receiptNumber: 0,
  };
})();
