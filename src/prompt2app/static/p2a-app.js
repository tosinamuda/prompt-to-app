// Prompt2App generated-app bundle (approved web components for the MCP UI resource).
//
// Dual-mode, like mcp-apps-demo's service-app.js:
//   - Inside a real MCP host (ChatGPT): connect via the ext-apps SDK and call server
//     tools (run_app / set_app_input) through the host.
//   - Embedded as a plain iframe by our host SPA: fall back to the REST API.

const EXT_APPS_SDK_URL = "https://esm.sh/@modelcontextprotocol/ext-apps@1.7.1?bundle";
const APP_INFO = { name: "prompt2app-generated-app", version: "0.2.0" };

const extBridge = (() => {
  let app = null;
  let hosted = false;
  let hostCapabilities = null;
  let connecting = null;
  let lastToolResult = null;

  async function connect(timeoutMs = 800) {
    if (window.parent === window) return { hosted: false };
    if (!connecting) connecting = connectOnce(timeoutMs);
    return connecting;
  }

  async function connectOnce(timeoutMs) {
    try {
      const sdk = await import(EXT_APPS_SDK_URL);
      app = new sdk.App(APP_INFO, {}, { autoResize: true });
      app.ontoolresult = (r) => {
        lastToolResult = r || {};
        window.dispatchEvent(new CustomEvent("mcp-app-tool-result", { detail: lastToolResult }));
      };
      app.onerror = () => {};
      const p = app.connect(undefined, { signal: timeoutSignal(timeoutMs) });
      p.catch(() => {});
      await p;
      hosted = true;
      hostCapabilities = app.getHostCapabilities?.() || {};
      if (app.getHostContext && sdk.applyDocumentTheme) {
        const ctx = app.getHostContext() || {};
        if (ctx.theme) sdk.applyDocumentTheme(ctx.theme);
      }
    } catch {
      hosted = false;
      app = null;
    }
    return { hosted, hostCapabilities };
  }

  function timeoutSignal(ms) {
    if (typeof AbortSignal !== "undefined" && AbortSignal.timeout) return AbortSignal.timeout(ms);
    const c = new AbortController();
    setTimeout(() => c.abort(), ms);
    return c.signal;
  }

  async function callServerTool(name, args, timeoutMs = 20000) {
    if (!app || !hostCapabilities?.serverTools) return null;
    const result = await app.callServerTool({ name, arguments: args }, { signal: timeoutSignal(timeoutMs) });
    if (!result) return null;
    if (result.isError) {
      const msg = (result.content || []).map((c) => c.text).filter(Boolean).join(" ") || name;
      throw new Error(msg);
    }
    return result.structuredContent || result.structured_content || result;
  }

  return {
    connect,
    callServerTool,
    isHosted: () => hosted,
    lastToolResult: () => lastToolResult,
  };
})();

class P2AApp extends HTMLElement {
  constructor() {
    super();
    this.apiBase = this.getAttribute("api-base") || "";
    this.appId = null;
    this.surface = null;
    this.values = {};
    this.error = "";
    this.running = false;
    this.chrome = true; // host embeds with ?chrome=0 (its tile already provides the header)
  }

  connectedCallback() {
    // Read chrome BEFORE renderShell so the shell is built bare (no header) when embedded.
    this.chrome = new URLSearchParams(window.location.search).get("chrome") !== "0";
    this.renderShell();
    this.bootstrap();
  }

  async bootstrap() {
    const params = new URLSearchParams(window.location.search);
    await extBridge.connect();
    const hosted = extBridge.lastToolResult();
    const bridgedStructured = hosted?.structuredContent || hosted?.structured_content || {};
    this.appId =
      params.get("app_id") || bridgedStructured.app_id || window.openai?.toolOutput?.structuredContent?.app_id;
    if (!this.appId) {
      this.error = "No app_id provided. Compile a prompt first.";
      this.render();
      return;
    }
    await this.loadSurface();
  }

  async loadSurface() {
    try {
      const res = await fetch(`${this.apiBase}/api/apps/${this.appId}`);
      if (!res.ok) throw new Error(`surface ${res.status}`);
      this.surface = await res.json();
      this.values = { ...(this.surface.values || {}) };
      // seed defaults from field widgets where no staged value exists
      for (const f of this.surface.fields) {
        if (this.values[f.name] === undefined || this.values[f.name] === "") {
          this.values[f.name] = f.default ?? (f.widget === "checkbox" ? false : "");
        }
      }
      this.error = "";
    } catch (e) {
      this.error = `Unable to load app: ${e.message}`;
    }
    this.render();
  }

  renderShell() {
    this.innerHTML = `
      <div class="p2a${this.chrome ? "" : " p2a-bare"}">
        ${this.chrome ? '<header class="p2a-header" data-region="header"></header>' : ""}
        <div class="p2a-body">
          <section class="p2a-form" data-region="form"></section>
          <section class="p2a-output" data-region="output"></section>
        </div>
      </div>`;
  }

  render() {
    if (!this.surface) {
      this.querySelector('[data-region="form"]').innerHTML = this.error
        ? `<p class="p2a-error" role="alert">${esc(this.error)}</p>`
        : `<p class="p2a-muted">Loading…</p>`;
      return;
    }
    if (this.chrome) this.renderHeader();
    this.renderForm();
    this.renderOutput(null);
  }

  renderHeader() {
    const el = this.querySelector('[data-region="header"]');
    if (!el) return;
    const s = this.surface;
    el.innerHTML = `
      <div>
        <span class="p2a-kicker">Generated app</span>
        <h1>${esc(s.title)}</h1>
      </div>
      <span class="p2a-task">${esc(s.task_name)}</span>`;
  }

  renderForm() {
    const fields = this.surface.fields.map((f) => this.fieldHtml(f)).join("");
    const constraints = (this.surface.constraints || []).length
      ? `<details class="p2a-constraints"><summary>${this.surface.constraints.length} constraint(s)</summary><ul>${this.surface.constraints
          .map((c) => `<li>${esc(c)}</li>`)
          .join("")}</ul></details>`
      : "";
    this.querySelector('[data-region="form"]').innerHTML = `
      ${this.error ? `<p class="p2a-error" role="alert">${esc(this.error)}</p>` : ""}
      <div class="p2a-fields">${fields}</div>
      ${constraints}
      <div class="p2a-actions">
        <button class="p2a-btn p2a-primary" data-run ${this.running ? "disabled" : ""}>
          ${this.running ? "Running…" : "Run program"}
        </button>
      </div>`;
    this.querySelectorAll("[data-field]").forEach((el) => {
      el.addEventListener("change", (e) => {
        const t = e.currentTarget;
        const name = t.dataset.field;
        this.values[name] = t.type === "checkbox" ? t.checked : t.value;
      });
    });
    this.querySelector("[data-run]")?.addEventListener("click", () => this.run());
  }

  fieldHtml(f) {
    const id = `f_${f.name}`;
    const req = f.required ? `<span class="req">*</span>` : "";
    const v = this.values[f.name];
    const label = `<label for="${id}">${esc(f.label)} ${req}</label>`;
    const hint = f.description ? `<span class="p2a-hint">${esc(f.description)}</span>` : "";
    let control;
    if (f.widget === "checkbox") {
      return `<div class="p2a-field p2a-check">
        <input type="checkbox" id="${id}" data-field="${f.name}" ${v ? "checked" : ""}/>
        <label for="${id}">${esc(f.label)} ${req}</label></div>`;
    } else if (f.widget === "select") {
      const opts = (f.options || [])
        .map((o) => `<option value="${esc(o)}" ${String(v) === String(o) ? "selected" : ""}>${esc(o)}</option>`)
        .join("");
      control = `<select id="${id}" data-field="${f.name}">${opts}</select>`;
    } else if (f.widget === "textarea") {
      control = `<textarea id="${id}" data-field="${f.name}" rows="4">${esc(v ?? "")}</textarea>`;
    } else {
      const type = f.widget === "number" || f.widget === "money" ? "number" : f.widget === "date" ? "date" : "text";
      const step = type === "number" ? 'step="any"' : "";
      const pre = f.widget === "money" ? `<span class="p2a-pre">$</span>` : "";
      control = `<div class="p2a-inputwrap">${pre}<input id="${id}" data-field="${f.name}" type="${type}" ${step} value="${esc(v ?? "")}"/></div>`;
    }
    return `<div class="p2a-field">${label}${control}${hint}</div>`;
  }

  async run() {
    this.running = true;
    this.renderForm();
    this.renderOutput(null, true);
    let result = null;
    try {
      const hostedResult = await this.callHosted("run_app", { app_id: this.appId, inputs: this.values });
      result = hostedResult || (await this.runRest());
      this.error = "";
    } catch (e) {
      this.error = e.message;
    } finally {
      this.running = false;
      this.renderForm();
      this.renderOutput(result);
    }
  }

  async runRest() {
    const res = await fetch(`${this.apiBase}/api/apps/${this.appId}/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ inputs: this.values }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `Run failed: ${res.status}`);
    }
    return res.json();
  }

  async callHosted(name, args) {
    if (!extBridge.isHosted()) return null;
    return extBridge.callServerTool(name, args);
  }

  renderOutput(result, loading = false) {
    const region = this.querySelector('[data-region="output"]');
    const panels = this.surface?.outputs || [];
    const head = `<div class="p2a-out-head">Output</div>`;
    if (loading) {
      const skel = (panels.length ? panels : [{ name: "" }])
        .map(
          (p) =>
            `<div class="p2a-outblock"><h3>${esc(p.name || "")}</h3>` +
            `<div class="p2a-skel"></div><div class="p2a-skel"></div><div class="p2a-skel short"></div></div>`,
        )
        .join("");
      region.innerHTML = head + skel;
      return;
    }
    if (!result) {
      const n = panels.length;
      region.innerHTML =
        head + `<div class="p2a-out-empty">Run the program to generate ${n} output${n === 1 ? "" : "s"}.</div>`;
      return;
    }
    const outputs = result.outputs || {};
    const order = panels.length ? panels.map((p) => p.name) : Object.keys(outputs);
    const blocks = order
      .map((name) => {
        const v = outputs[name];
        const text = v == null ? "—" : typeof v === "object" ? JSON.stringify(v, null, 2) : String(v);
        return `<div class="p2a-outblock"><h3>${esc(name)}</h3><div class="p2a-outval">${esc(text)}</div></div>`;
      })
      .join("");
    region.innerHTML = head + blocks;
  }
}

function esc(v) {
  return String(v ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

customElements.define("p2a-app", P2AApp);
