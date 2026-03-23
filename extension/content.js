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

  function getWindowsUsername() {
    return new Promise((resolve) => {
      chrome.runtime.sendMessage({ action: "get_windows_username" }, (r) => {
        resolve(r || { username: null, groups: [], error: null });
      });
    });
  }

  function getStoredAdUser() {
    return new Promise((resolve) => {
      chrome.runtime.sendMessage({ action: "get_ad_user" }, (r) => {
        resolve(r || { username: null, groups: [], playbooks: [], playbook_titles: {} });
      });
    });
  }

  function saveAdUser(username, groups, team, playbooks, playbook_titles) {
    return new Promise((resolve) => {
      chrome.runtime.sendMessage(
        { action: "save_ad_user", username, groups, team, playbooks, playbook_titles },
        () => resolve()
      );
    });
  }

  let isOpen         = false;
  let loading        = false;
  let messages       = [];
  let buttons        = [];
  let meta           = null;
  let adUsername     = null;
  let adGroups       = [];
  let accessState    = "checking";
  let acEnabled      = true;
  let userPlaybooks  = [];
  let playbookTitles = {};
  let activePlaybook = null;
  let loginError     = "";
  let loginInput     = "";

  const ICON_ROBOT     = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v3"/><circle cx="12" cy="6" r="1.2" fill="none"/><path d="M9 5.6h6"/><path d="M8.4 6.4H7.3A3.3 3.3 0 0 0 4 9.7V15a5 5 0 0 0 5 5h6a5 5 0 0 0 5-5V9.7a3.3 3.3 0 0 0-3.3-3.3H15.6"/><path d="M9.2 13h.01"/><path d="M14.8 13h.01"/><path d="M9.3 16.1c.9.9 1.9 1.4 2.7 1.4s1.8-.5 2.7-1.4"/></svg>`;
  const ICON_X         = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>`;
  const ICON_CLIPBOARD = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="2" width="6" height="4" rx="1"/><path d="M9 4H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2h-3"/><path d="M9 13h6"/><path d="M9 17h6"/><path d="M9 9h6"/></svg>`;
  const ICON_REFRESH   = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 0 1-9 9 9 9 0 0 1-8.66-6.5"/><path d="M3 12a9 9 0 0 1 9-9 9 9 0 0 1 8.66 6.5"/><path d="M21 3v6h-6"/><path d="M3 21v-6h6"/></svg>`;
  const ICON_ALERT     = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 9v4"/><path d="M12 17h.01"/><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z"/></svg>`;
  const ICON_LOCK      = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>`;

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

  async function attemptAdLogin(username, groups) {
    const { status, data } = await apiFetch("/ad-login", {
      method: "POST",
      body: JSON.stringify({ username: (username || "").trim().toLowerCase(), groups: groups || [] }),
    });
    return { status, data };
  }

  async function init() {
    try { const { data } = await apiFetch("/meta"); meta = data; } catch {}
    try {
      const { data } = await apiFetch("/flags");
      if (data && data.maintenance_mode) maintenance = true;
      if (data && data.features && data.features.access_control === false) acEnabled = false;
    } catch {}

    if (!acEnabled) { accessState = "allowed"; autoStart(); return; }

    accessState = "checking";

    const native      = await getWindowsUsername();
    const winUsername = native.username;
    const winGroups   = native.groups || [];

    if (winUsername) {
      try {
        const { status, data } = await attemptAdLogin(winUsername, winGroups);
        if (status === 200) {
          adUsername     = data.username;
          adGroups       = winGroups;
          userPlaybooks  = data.playbooks || [];
          playbookTitles = data.playbook_titles || {};
          await saveAdUser(adUsername, adGroups, data.team, userPlaybooks, playbookTitles);
          accessState = "allowed";
          autoStart();
          return;
        } else if (status === 403) {
          adUsername  = winUsername;
          adGroups    = winGroups;
          accessState = "not_registered";
        } else {
          const stored = await getStoredAdUser();
          if (stored.username) {
            adUsername     = stored.username;
            adGroups       = stored.groups || [];
            userPlaybooks  = stored.playbooks || [];
            playbookTitles = stored.playbook_titles || {};
            accessState    = "allowed";
            autoStart();
            return;
          }
          accessState = "needs_login";
        }
      } catch {
        const stored = await getStoredAdUser();
        if (stored.username) {
          adUsername     = stored.username;
          adGroups       = stored.groups || [];
          userPlaybooks  = stored.playbooks || [];
          playbookTitles = stored.playbook_titles || {};
          accessState    = "allowed";
          autoStart();
          return;
        }
        accessState = "needs_login";
      }
    } else {
      const stored = await getStoredAdUser();
      if (stored.username) {
        adUsername     = stored.username;
        adGroups       = stored.groups || [];
        userPlaybooks  = stored.playbooks || [];
        playbookTitles = stored.playbook_titles || {};
        accessState    = "allowed";
        autoStart();
        return;
      }
      accessState = "needs_login";
    }

    render();
  }

  function autoStart() {
    messages = [];
    buttons  = [];
    if (acEnabled && userPlaybooks.length > 1 && !activePlaybook) {
      render();
      return;
    }
    if (acEnabled && userPlaybooks.length === 1) activePlaybook = userPlaybooks[0];
    render();
    fetchNode("home");
  }

  async function handleManualLogin(username) {
    if (!username || !username.trim()) return;
    loginError  = "";
    accessState = "checking";
    render();
    try {
      const native = await getWindowsUsername();
      const groups = (native.username && native.username === username.trim().toLowerCase())
        ? (native.groups || []) : [];
      const { status, data } = await attemptAdLogin(username, groups);
      if (status === 200) {
        adUsername     = data.username;
        adGroups       = groups;
        userPlaybooks  = data.playbooks || [];
        playbookTitles = data.playbook_titles || {};
        await saveAdUser(adUsername, adGroups, data.team, userPlaybooks, playbookTitles);
        accessState = "allowed";
        loginError  = "";
        autoStart();
        return;
      } else if (status === 403) {
        adUsername  = username.trim().toLowerCase();
        accessState = "not_registered";
      } else {
        accessState = "needs_login";
        loginError  = "Verification failed. Please try again.";
      }
    } catch {
      accessState = "needs_login";
      loginError  = "Could not reach the server. Make sure the backend is running on port 8001.";
    }
    render();
  }

  async function fetchNode(nodeId, userLabel) {
    loading = true;
    if (userLabel) messages.push({ role: "user", text: userLabel });
    buttons = [];
    render();
    try {
      const body = { node_id: nodeId };
      if (acEnabled && adUsername) {
        body.username = adUsername;
        body.groups   = adGroups || [];
      }
      if (activePlaybook) body.playbook = activePlaybook;
      const { status, data } = await apiFetch("/chat", { method: "POST", body: JSON.stringify(body) });
      if (status === 503) {
        messages.push({ role: "bot", title: "\uD83D\uDD27 Under Maintenance", text: data?.detail?.message || "The playbook is currently under maintenance." });
        buttons = [];
      } else if (status === 403) {
        accessState = "not_registered";
      } else if (status === 404) {
        messages.push({ role: "bot", title: "Feature Unavailable", text: data?.detail || "This feature is currently disabled." });
        buttons = [{ label: "\uD83C\uDFE0 Back to Home", next: "home" }];
      } else {
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

  function toggleChat() {
    isOpen = !isOpen;
    if (isOpen && accessState === "allowed" && messages.length === 0) {
      if (acEnabled && userPlaybooks.length > 1 && !activePlaybook) {
        render();
        return;
      }
      if (acEnabled && userPlaybooks.length === 1 && !activePlaybook) activePlaybook = userPlaybooks[0];
      if (activePlaybook || !acEnabled) {
        render();
        fetchNode("home");
        return;
      }
    }
    render();
  }

  function autoStart() {
    messages = [];
    buttons  = [];
    activePlaybook = null;
    if (acEnabled && userPlaybooks.length > 1) {
      render();
      return;
    }
    if (acEnabled && userPlaybooks.length === 1) activePlaybook = userPlaybooks[0];
    if (isOpen) fetchNode("home");
    render();
  }

  function pickPlaybook(filename) {
    activePlaybook = filename;
    messages = [];
    buttons  = [];
    render();
    fetchNode("home");
  }

  function selectOption(label, next) { fetchNode(next, label); }

  function render() {
    const company = meta?.company || "National Data & Surveying Services";
    const version = meta?.version || "";
    let html = "";

    if (isOpen) html += `<div class="nds-backdrop"></div>`;

    if (isOpen) {
      html += `<div class="nds-chat-window">`;

      html += `<div class="nds-chat-window__header">
        <div class="nds-chat-window__header-top">
          <div class="nds-chat-window__header-left">
            <span class="nds-chat-window__logo">NDS</span>
            <div class="nds-chat-window__header-text">
              <span class="nds-chat-window__title">Playbook</span>
              <span class="nds-chat-window__subtitle">${esc(company)}</span>
            </div>
          </div>
          ${version ? `<span class="nds-chat-window__version">v${esc(version)}</span>` : ""}
        </div>
        ${adUsername && accessState === "allowed" ? `<div class="nds-chat-window__header-bar">
          <span class="nds-header-email" title="${esc(adUsername)}">${esc(adUsername)}</span>
          <div class="nds-header-actions">
            ${activePlaybook && acEnabled && userPlaybooks.length > 1
              ? `<button class="nds-header-btn nds-header-btn--ghost" data-action="switch-playbook">\u21c4 Switch</button>`
              : ""}
            ${activePlaybook
              ? `<button class="nds-header-btn nds-header-btn--ghost" data-action="restart">${ICON_REFRESH} Start Over</button>`
              : ""}
          </div>
        </div>` : ""}
      </div>`;

      html += `<div class="nds-chat-window__body">`;

      if (accessState === "checking") {
        html += `<div class="nds-chat-window__welcome">
          <div class="nds-chat-window__welcome-icon">${ICON_CLIPBOARD}</div>
          <p class="nds-chat-window__desc">Verifying your access\u2026</p>
        </div>`;

      } else if (accessState === "needs_login") {
        const prefill = loginInput || (adUsername ? esc(adUsername) : "");
        html += `<div class="nds-chat-window__welcome">
          <div class="nds-chat-window__welcome-icon">${ICON_LOCK}</div>
          <h3>Verification Required</h3>
          <p class="nds-chat-window__desc">Enter your Windows login username to verify access.</p>
          <div class="nds-login-form">
            <input class="nds-login-input" data-input="username" type="text"
              placeholder="e.g. nds-25217" value="${prefill}"
              autocomplete="username" spellcheck="false" />
            ${loginError ? `<p class="nds-login-error">${esc(loginError)}</p>` : ""}
            <button class="nds-chat-window__start-btn" data-action="submit-login">Verify &amp; Continue</button>
          </div>
        </div>`;

      } else if (accessState === "not_registered") {
        html += `<div class="nds-chat-window__welcome">
          <div class="nds-chat-window__welcome-icon">${ICON_LOCK}</div>
          <h3>Access Not Granted</h3>
          <p class="nds-chat-window__desc"><strong>${esc(adUsername || "Your account")}</strong> is not in any authorised group.</p>
          <p class="nds-chat-window__desc" style="font-size:0.8em;opacity:0.6;">Contact your team lead to get access.</p>
        </div>`;

      } else if (acEnabled && userPlaybooks.length > 1 && !activePlaybook) {
        html += `<div class="nds-chat-window__welcome">
          <div class="nds-chat-window__welcome-icon">${ICON_CLIPBOARD}</div>
          <h3>Select a Playbook</h3>
          <p class="nds-chat-window__desc">You have access to multiple playbooks. Choose one to open.</p>
          <div class="nds-option-buttons" style="margin-top:12px;">`;
        for (const fname of userPlaybooks) {
          const label = playbookTitles[fname] || fname.replace(".json", "").replace(/_/g, " ").replace(/-/g, " ");
          html += `<button class="nds-option-btn" data-action="pick-playbook" data-file="${esc(fname)}">${esc(label)}</button>`;
        }
        html += `</div></div>`;

      } else {
        html += `<div class="nds-message-list">`;
        for (const msg of messages) {
          if (msg.role === "bot") {
            html += `<div class="nds-message nds-message--bot"><div class="nds-message__bubble nds-message__bubble--bot">`;
            if (msg.title) html += `<div class="nds-msg-title">${esc(msg.title)}</div>`;
            if (msg.text)  html += `<div class="nds-msg-answer">${formatText(msg.text)}</div>`;
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
            const btn    = buttons[i];
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
        : `<span class="nds-chat-fab__icon nds-chat-fab__icon--robot">${ICON_ROBOT}</span>`}
    </button>`;

    container.innerHTML = html;

    if (accessState === "needs_login") {
      const inputEl = shadow.querySelector("[data-input='username']");
      if (inputEl) {
        inputEl.focus();
        inputEl.addEventListener("keydown", (e) => {
          if (e.key === "Enter") { loginInput = inputEl.value; handleManualLogin(inputEl.value); }
        });
        inputEl.addEventListener("input", (e) => { loginInput = e.target.value; });
      }
    }

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
    if      (action === "toggle")          toggleChat();
    else if (action === "restart")         { messages = []; buttons = []; render(); fetchNode("home"); }
    else if (action === "switch-playbook") { activePlaybook = null; messages = []; buttons = []; render(); }
    else if (action === "pick-playbook")   { const f = btn.dataset.file; if (f) pickPlaybook(f); }
    else if (action === "option") {
      const idx = parseInt(btn.dataset.index, 10);
      const b   = buttons[idx];
      if (b) selectOption(b.label, b.next);
    }
    else if (action === "submit-login") {
      const inputEl = shadow.querySelector("[data-input='username']");
      const val     = inputEl ? inputEl.value : loginInput;
      loginInput    = val;
      handleManualLogin(val);
    }
  });

  chrome.runtime.onMessage.addListener((msg) => {
    if (msg.action === "toggle_chatbot") toggleChat();
  });

  init();
})();
