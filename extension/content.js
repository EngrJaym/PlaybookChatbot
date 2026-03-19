(function () {
  if (document.getElementById("nds-playbook-root")) return;

  const API_URL = "http://127.0.0.1:8001/api";

  function apiFetch(path, options = {}) {
    return new Promise((resolve, reject) => {
      chrome.runtime.sendMessage(
        {
          action: "api_fetch",
          url: `${API_URL}${path}`,
          options: {
            method: options.method || "GET",
            headers: { "Content-Type": "application/json", ...(options.headers || {}) },
            body: options.body || undefined,
          },
        },
        (response) => {
          if (chrome.runtime.lastError) { reject(new Error(chrome.runtime.lastError.message)); return; }
          if (!response) { reject(new Error("No response from background")); return; }
          if (!response.ok) { reject(new Error(response.error || "Network error")); return; }
          resolve({ status: response.status, data: response.data });
        }
      );
    });
  }

  function getStoredToken() {
    return new Promise((resolve) => {
      chrome.runtime.sendMessage({ action: "get_stored_token" }, (r) => {
        resolve(r && r.id_token ? r.id_token : null);
      });
    });
  }

  function googleSignIn() {
    return new Promise((resolve) => {
      chrome.runtime.sendMessage({ action: "google_sign_in" }, (r) => {
        resolve(r && r.id_token ? r.id_token : null);
      });
    });
  }

  function signOut() {
    return new Promise((resolve) => {
      chrome.runtime.sendMessage({ action: "sign_out" }, () => resolve());
    });
  }

  let isOpen      = false;
  let started     = false;
  let loading     = false;
  let messages    = [];
  let buttons     = [];
  let meta        = null;
  let maintenance = false;
  let idToken     = null;
  let userEmail   = null;
  let accessState = "checking";
  let acEnabled   = true;

  const ICON_ROBOT     = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v3"/><circle cx="12" cy="6" r="1.2" fill="none"/><path d="M9 5.6h6"/><path d="M8.4 6.4H7.3A3.3 3.3 0 0 0 4 9.7V15a5 5 0 0 0 5 5h6a5 5 0 0 0 5-5V9.7a3.3 3.3 0 0 0-3.3-3.3H15.6"/><path d="M9.2 13h.01"/><path d="M14.8 13h.01"/><path d="M9.3 16.1c.9.9 1.9 1.4 2.7 1.4s1.8-.5 2.7-1.4"/></svg>`;
  const ICON_X         = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>`;
  const ICON_CLIPBOARD = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="2" width="6" height="4" rx="1"/><path d="M9 4H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2h-3"/><path d="M9 13h6"/><path d="M9 17h6"/><path d="M9 9h6"/></svg>`;
  const ICON_REFRESH   = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 0 1-9 9 9 9 0 0 1-8.66-6.5"/><path d="M3 12a9 9 0 0 1 9-9 9 9 0 0 1 8.66 6.5"/><path d="M21 3v6h-6"/><path d="M3 21v-6h6"/></svg>`;
  const ICON_ALERT     = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 9v4"/><path d="M12 17h.01"/><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z"/></svg>`;
  const ICON_LOCK      = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>`;
  const ICON_GOOGLE    = `<svg viewBox="0 0 24 24" width="18" height="18"><path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4"/><path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/><path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18A10.96 10.96 0 0 0 1 12c0 1.77.42 3.45 1.18 4.93l3.66-2.84z" fill="#FBBC05"/><path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/></svg>`;

  const root = document.createElement("div");
  root.id = "nds-playbook-root";
  document.body.appendChild(root);
  const shadow = root.attachShadow({ mode: "open" });
  const styleLink = document.createElement("link");
  styleLink.rel = "stylesheet";
  styleLink.href = chrome.runtime.getURL("chatbot.css");
  shadow.appendChild(styleLink);
  const container = document.createElement("div");
  container.className = "nds-chatbot";
  shadow.appendChild(container);

  async function init() {
    try { const { data } = await apiFetch("/meta"); meta = data; } catch {}
    try {
      const { data } = await apiFetch("/flags");
      if (data && data.maintenance_mode) maintenance = true;
      if (data && data.features && data.features.access_control === false) acEnabled = false;
    } catch {}

    if (!acEnabled) { accessState = "allowed"; render(); return; }

    const stored = await getStoredToken();
    if (stored) {
      const ok = await verifyWithBackend(stored);
      if (ok) { render(); return; }
    }
    accessState = "needs_signin";
    render();
  }

  async function verifyWithBackend(token) {
    try {
      const { status, data } = await apiFetch("/login", {
        method: "POST",
        body: JSON.stringify({ id_token: token }),
      });
      if (status === 200) {
        idToken = token;
        userEmail = data.email;
        accessState = "allowed";
        return true;
      }
      if (status === 403) {
        userEmail = data?.detail?.match(/'([^']+)'/)?.[1] || "";
        accessState = "not_registered";
        return false;
      }
      accessState = "needs_signin";
      await signOut();
      return false;
    } catch {
      accessState = "needs_signin";
      return false;
    }
  }

  async function handleSignIn() {
    accessState = "checking";
    render();
    const token = await googleSignIn();
    if (!token) { accessState = "needs_signin"; render(); return; }
    await verifyWithBackend(token);
    render();
  }

  async function handleSignOut() {
    await signOut();
    idToken = null;
    userEmail = null;
    accessState = "needs_signin";
    started = false;
    messages = [];
    buttons = [];
    render();
  }

  async function fetchNode(nodeId, userLabel) {
    loading = true;
    if (userLabel) messages.push({ role: "user", text: userLabel });
    buttons = [];
    render();
    try {
      const body = { node_id: nodeId };
      if (acEnabled && idToken) body.id_token = idToken;
      const { status, data } = await apiFetch("/chat", {
        method: "POST",
        body: JSON.stringify(body),
      });
      if (status === 503) {
        maintenance = true;
        messages.push({ role: "bot", title: "\u{1F527} Under Maintenance", text: data?.detail?.message || "The playbook is currently under maintenance." });
        buttons = [];
      } else if (status === 401) {
        await signOut();
        idToken = null;
        accessState = "needs_signin";
        started = false;
      } else if (status === 403) {
        accessState = "not_registered";
        started = false;
      } else if (status === 404) {
        messages.push({ role: "bot", title: "Feature Unavailable", text: data?.detail || "This feature is currently disabled." });
        buttons = [{ label: "\u{1F3E0} Back to Home", next: "home" }];
      } else {
        maintenance = false;
        messages.push({ role: "bot", title: data.message, text: data.answer || null, citation: data.citation || null });
        buttons = data.buttons || [];
      }
    } catch {
      messages.push({ role: "bot", title: "Connection Error", text: "\u26A0\uFE0F Could not reach the server." });
      buttons = [{ label: "Try Again", next: "home" }];
    } finally {
      loading = false;
      render();
      scrollToBottom();
    }
  }

  function formatText(text) {
    if (!text) return "";
    const lines = text.split("\n");
    let html = "", listItems = [], listType = null;
    const flushList = () => {
      if (listItems.length > 0) {
        const tag = listType === "ol" ? "ol" : "ul";
        html += `<${tag} class="nds-msg-list">${listItems.join("")}</${tag}>`;
        listItems = []; listType = null;
      }
    };
    const inlineFmt = (str) => str.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) { flushList(); continue; }
      if (/^[•\-*]\s/.test(trimmed)) {
        if (listType !== "ul") flushList();
        listType = "ul";
        listItems.push(`<li>${inlineFmt(trimmed.replace(/^[•\-*]\s*/, ""))}</li>`);
        continue;
      }
      const numMatch = trimmed.match(/^(\d+)\.\s(.+)/);
      if (numMatch) {
        if (listType !== "ol") flushList();
        listType = "ol";
        listItems.push(`<li>${inlineFmt(numMatch[2])}</li>`);
        continue;
      }
      flushList();
      if (/^WARNING:\s*/i.test(trimmed)) {
        const content = trimmed.replace(/^WARNING:\s*/i, "");
        html += `<p class="nds-msg-para nds-msg-warning"><span class="nds-msg-warning__icon">${ICON_ALERT}</span><span class="nds-msg-warning__text">${inlineFmt(content)}</span></p>`;
      } else {
        html += `<p class="nds-msg-para">${inlineFmt(trimmed)}</p>`;
      }
    }
    flushList();
    return html;
  }

  function scrollToBottom() {
    requestAnimationFrame(() => {
      const list = shadow.querySelector(".nds-message-list");
      if (list) list.scrollTop = list.scrollHeight;
    });
  }

  function toggleChat() { isOpen = !isOpen; render(); }
  function startChat() { messages = []; buttons = []; started = true; render(); fetchNode("home"); }
  function selectOption(label, next) { fetchNode(next, label); }

  function render() {
    const title   = meta?.title   || "NDS Playbook Chatbot";
    const company = meta?.company || "National Data & Surveying Services";
    const version = meta?.version || "";
    let html = "";

    if (isOpen) html += `<div class="nds-backdrop"></div>`;

    if (isOpen) {
      html += `<div class="nds-chat-window">`;

      html += `<div class="nds-chat-window__header">
        <div class="nds-chat-window__header-left">
          <span class="nds-chat-window__logo">NDS</span>
          <div class="nds-chat-window__header-text">
            <span class="nds-chat-window__title">Playbook</span>
            <span class="nds-chat-window__subtitle">${esc(company)}</span>
            ${version ? `<span class="nds-chat-window__version">v${esc(version)}</span>` : ""}
          </div>
        </div>
        <div style="display:flex;align-items:center;gap:6px;">
          ${userEmail ? `<span style="font-size:0.7em;opacity:0.7;color:#fff;max-width:120px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${esc(userEmail)}">${esc(userEmail)}</span>
          <button class="nds-chat-window__restart" data-action="signout" title="Sign out" style="padding:4px 8px;">
            <span style="font-size:0.75em;">Sign out</span>
          </button>` : ""}
          ${started ? `<button class="nds-chat-window__restart" data-action="restart">
            <span class="nds-chat-window__restart-icon">${ICON_REFRESH}</span>
            <span>Start Over</span>
          </button>` : ""}
        </div>
      </div>`;

      html += `<div class="nds-chat-window__body">`;

      if (accessState === "checking") {
        html += `<div class="nds-chat-window__welcome">
          <div class="nds-chat-window__welcome-icon">${ICON_CLIPBOARD}</div>
          <p class="nds-chat-window__desc">Verifying access…</p>
        </div>`;

      } else if (accessState === "needs_signin") {
        html += `<div class="nds-chat-window__welcome">
          <div class="nds-chat-window__welcome-icon">${ICON_LOCK}</div>
          <h3>Sign in Required</h3>
          <p class="nds-chat-window__desc">Sign in with your NDS Google account to access the playbook.</p>
          <button class="nds-chat-window__start-btn" data-action="signin" style="display:flex;align-items:center;justify-content:center;gap:8px;">
            ${ICON_GOOGLE} <span>Sign in with Google</span>
          </button>
        </div>`;

      } else if (accessState === "not_registered") {
        html += `<div class="nds-chat-window__welcome">
          <div class="nds-chat-window__welcome-icon">${ICON_LOCK}</div>
          <h3>Access Not Granted</h3>
          <p class="nds-chat-window__desc"><strong>${esc(userEmail || "")}</strong> is not registered in any team.</p>
          <p class="nds-chat-window__desc" style="font-size:0.8em;opacity:0.6;">Contact your team lead to get access.</p>
          <button class="nds-option-btn nds-option-btn--back" data-action="signout" style="margin-top:12px;">Try a different account</button>
        </div>`;

      } else if (!started) {
        html += `<div class="nds-chat-window__welcome">
          <div class="nds-chat-window__welcome-icon">${ICON_CLIPBOARD}</div>
          <h3>${esc(title)}</h3>
          <p class="nds-chat-window__company">${esc(company)}</p>
          <p class="nds-chat-window__desc">Your interactive guide to account setup, mapping, estimation, pricing, PSU, study types, QC checklists, and more.</p>
          <button class="nds-chat-window__start-btn" data-action="start">Open Playbook</button>
        </div>`;

      } else {
        html += `<div class="nds-message-list">`;
        for (const msg of messages) {
          if (msg.role === "bot") {
            html += `<div class="nds-message nds-message--bot"><div class="nds-message__bubble nds-message__bubble--bot">`;
            if (msg.title) html += `<div class="nds-msg-title">${esc(msg.title)}</div>`;
            if (msg.text) html += `<div class="nds-msg-answer">${formatText(msg.text)}</div>`;
            html += `</div></div>`;
          } else {
            html += `<div class="nds-message nds-message--user"><div class="nds-message__bubble nds-message__bubble--user">${esc(msg.text)}</div></div>`;
          }
        }
        if (loading) html += `<div class="nds-typing"><span class="nds-dot"></span><span class="nds-dot"></span><span class="nds-dot"></span></div>`;
        html += `</div>`;

        if (buttons.length > 0) {
          const isCompact = buttons.length > 6;
          html += `<div class="nds-option-buttons ${isCompact ? "nds-option-buttons--compact" : ""}">`;
          for (let i = 0; i < buttons.length; i++) {
            const btn = buttons[i];
            const isBack = btn.label.toLowerCase().includes("back") || btn.label.toLowerCase().includes("home");
            html += `<button class="nds-option-btn ${isBack ? "nds-option-btn--back" : ""}" ${loading ? "disabled" : ""} data-action="option" data-index="${i}">${esc(btn.label)}</button>`;
          }
          html += `</div>`;
        }
      }

      html += `</div></div>`;
    }

    html += `<button class="nds-chat-fab ${isOpen ? "nds-chat-fab--open" : ""}" data-action="toggle" aria-label="${isOpen ? "Close chat" : "Open chat"}">
      ${isOpen
        ? `<span class="nds-chat-fab__icon nds-chat-fab__icon--close">${ICON_X}</span>`
        : `<span class="nds-chat-fab__icon nds-chat-fab__icon--robot">${ICON_ROBOT}</span>`
      }
    </button>`;

    container.innerHTML = html;
    scrollToBottom();
  }

  function esc(str) {
    const d = document.createElement("div");
    d.textContent = str || "";
    return d.innerHTML;
  }

  container.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-action]");
    if (!btn) {
      if (e.target.closest(".nds-backdrop")) toggleChat();
      return;
    }
    const action = btn.dataset.action;
    if (action === "toggle")       toggleChat();
    else if (action === "signin")  handleSignIn();
    else if (action === "signout") handleSignOut();
    else if (action === "start")   startChat();
    else if (action === "restart") startChat();
    else if (action === "option") {
      const idx = parseInt(btn.dataset.index, 10);
      const b = buttons[idx];
      if (b) selectOption(b.label, b.next);
    }
  });

  chrome.runtime.onMessage.addListener((msg) => {
    if (msg.action === "toggle_chatbot") toggleChat();
  });

  init();
})();

