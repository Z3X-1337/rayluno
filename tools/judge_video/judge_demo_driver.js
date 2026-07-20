(() => {
  const sleep = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));

  async function typeCommand(text, delay = 32) {
    const input = document.querySelector("#command-input");
    const form = document.querySelector("#command-form");
    input.focus();
    input.value = "";
    for (const character of text) {
      input.value += character;
      input.dispatchEvent(new Event("input", { bubbles: true }));
      await sleep(delay);
    }
    await sleep(250);
    form.requestSubmit();
  }

  async function waitFor(selector, { timeout = 12_000, visible = false } = {}) {
    const started = Date.now();
    while (Date.now() - started < timeout) {
      const element = document.querySelector(selector);
      if (element && (!visible || element.open || element.offsetParent !== null)) return element;
      await sleep(100);
    }
    throw new Error(`Timed out waiting for ${selector}`);
  }

  async function run() {
    localStorage.setItem("future-assistant.ui-language", "en");
    window.dispatchEvent(new Event("pywebviewready"));
    await waitFor("#memory-v2-trigger");
    await waitFor("#verified-v2-trigger");
    document.querySelector('[data-language="en"]')?.click();
    await sleep(2_200);

    await typeCommand("Remember that I prefer concise, technical answers");
    await sleep(2_800);

    document.querySelector("#memory-v2-trigger")?.click();
    await waitFor("#memory-v2-dialog", { visible: true });
    await sleep(4_600);
    document.querySelector("#memory-v2-close")?.click();
    await sleep(1_200);

    await typeCommand("Prepare the judge demo");
    await waitFor("#verified-v2-gate", { visible: true, timeout: 15_000 });
    await sleep(5_000);
    document.querySelector("#verified-v2-approve")?.click();
    await sleep(3_200);

    document.querySelector("#verified-v2-trigger")?.click();
    await waitFor("#verified-v2-inspector", { visible: true });
    await sleep(5_000);
    document.querySelector("#verified-v2-close")?.click();
    await sleep(1_300);

    await typeCommand("Test an unregistered skill");
    await sleep(3_500);
    document.querySelector("#verified-v2-trigger")?.click();
    await waitFor("#verified-v2-inspector", { visible: true });
    await sleep(5_000);
    document.querySelector("#verified-v2-close")?.click();
    await sleep(2_000);

    window.__RAYLUNO_DEMO_DONE__ = true;
  }

  const fail = (error) => {
    window.__RAYLUNO_DEMO_ERROR__ = String(error?.stack || error);
  };
  if (document.readyState === "complete") run().catch(fail);
  else window.addEventListener("load", () => run().catch(fail), { once: true });
})();
