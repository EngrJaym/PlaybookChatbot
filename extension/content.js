(function () {
  if (document.getElementById("nds-playbook-root")) return;

  const DEFAULT_API_URL = "http://127.0.0.1:8001/api";
  let API_URL = DEFAULT_API_URL;

  // ── State ────────────────────────────────────────────────────
  let isOpen = false;
  let started = false;
  let loading = false;
  let messages = [];
  let buttons = [];
  let meta = null;
  let maintenance = false;
  let availablePlaybooks = [];
  let activePlaybook = null;

  function normalizeApiUrl(raw) {
    const cleaned = (raw || "").trim().replace(/\/+$/, "");
    return cleaned || DEFAULT_API_URL;
  }

  function loadApiUrlFromStorage() {
    return new Promise((resolve) => {
      try {
        chrome.storage.sync.get(["ndsApiUrl"], (result) => {
          API_URL = normalizeApiUrl(result?.ndsApiUrl);
          resolve();
        });
      } catch {
        API_URL = DEFAULT_API_URL;
        resolve();
      }
    });
  }

  function loadUiStateFromStorage() {
    return new Promise((resolve) => {
      try {
        chrome.storage.local.get(["ndsChatOpen"], (result) => {
          isOpen = Boolean(result?.ndsChatOpen);
          resolve();
        });
      } catch {
        isOpen = false;
        resolve();
      }
    });
  }

  function saveUiState() {
    try {
      chrome.storage.local.set({ ndsChatOpen: isOpen });
    } catch {}
  }

  // ── SVG Icons ────────────────────────────────────────────────
  const ICON_ROBOT = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v3"/><circle cx="12" cy="6" r="1.2" fill="none"/><path d="M9 5.6h6"/><path d="M8.4 6.4H7.3A3.3 3.3 0 0 0 4 9.7V15a5 5 0 0 0 5 5h6a5 5 0 0 0 5-5V9.7a3.3 3.3 0 0 0-3.3-3.3H15.6"/><path d="M9.2 13h.01"/><path d="M14.8 13h.01"/><path d="M9.3 16.1c.9.9 1.9 1.4 2.7 1.4s1.8-.5 2.7-1.4"/></svg>`;
  const ICON_X = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>`;
  const ICON_CLIPBOARD = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="2" width="6" height="4" rx="1"/><path d="M9 4H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2h-3"/><path d="M9 13h6"/><path d="M9 17h6"/><path d="M9 9h6"/></svg>`;
  const ICON_REFRESH = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 0 1-9 9 9 9 0 0 1-8.66-6.5"/><path d="M3 12a9 9 0 0 1 9-9 9 9 0 0 1 8.66 6.5"/><path d="M21 3v6h-6"/><path d="M3 21v-6h6"/></svg>`;
  const ICON_ALERT = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 9v4"/><path d="M12 17h.01"/><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z"/></svg>`;

  // ── DOM Setup ────────────────────────────────────────────────
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

  // ── Fetch helpers ────────────────────────────────────────────
  // Route every request through the background service-worker so we
  // are not blocked by the host page's Content-Security-Policy.
  function apiFetch(path, options = {}) {
    const url = API_URL + path;
    const defaultHeaders = { "Content-Type": "application/json" };
    const fetchOptions = {
      ...options,
      headers: { ...defaultHeaders, ...(options.headers || {}) },
    };
    return new Promise((resolve, reject) => {
      chrome.runtime.sendMessage(
        { action: "api_fetch", url, options: fetchOptions },
        (response) => {
          if (chrome.runtime.lastError) {
            return reject(new Error(chrome.runtime.lastError.message));
          }
          if (!response || response.ok === false) {
            // response.ok === false means the background fetch() itself
            // threw (network error), not an HTTP error status.
            if (response && response.error) {
              return reject(new Error(response.error));
            }
            return reject(new Error("Background fetch failed"));
          }
          // Normalise so callers can use { status, ok, data }
          resolve({
            status: response.status,
            ok:     response.status >= 200 && response.status < 300,
            data:   response.data,
          });
        }
      );
    });
  }

  async function fetchMeta() {
    try {
      const { ok, data } = await apiFetch("/meta");
      if (ok && data) meta = data;
    } catch {}
    try {
      const { ok, data } = await apiFetch("/flags");
      if (ok && data?.maintenance_mode) maintenance = true;
    } catch {}
    try {
      const { ok, data } = await apiFetch("/playbooks");
      if (ok && data) {
        availablePlaybooks = (data?.playbooks || []).filter(p => p.file && p.file !== "(google_docs)");
      }
    } catch {}
  }

  async function fetchNode(nodeId, userLabel) {
    loading = true;
    if (userLabel) {
      messages.push({ role: "user", text: userLabel });
    }
    buttons = [];
    render();

    try {
      const body = { node_id: nodeId };
      if (activePlaybook) body.playbook = activePlaybook;
      const { status, data, ok } = await apiFetch("/chat", {
        method: "POST",
        body: JSON.stringify(body),
      });

      if (status === 503) {
        maintenance = true;
        messages.push({
          role: "bot",
          title: "\u{1F527} Under Maintenance",
          text: data?.detail?.message || "The playbook is currently under maintenance.",
        });
        buttons = [];
      } else if (status === 404) {
        messages.push({
          role: "bot",
          title: "Feature Unavailable",
          text: data?.detail || "This feature is currently disabled.",
        });
        buttons = [{ label: "\u{1F3E0} Back to Home", next: "home" }];
      } else if (status === 401 || status === 403) {
        const isUnauthorized = status === 401;
        messages.push({
          role: "bot",
          title: isUnauthorized ? "Secure Access Required" : "Team Access Required",
          text: isUnauthorized
            ? "Please access the chatbot through your company network or approved gateway, then try again."
            : "Your account is not currently assigned to an allowed team for this chatbot; please contact your administrator.",
        });
        buttons = [{ label: "Try Again", next: "home" }];
      } else if (!ok) {
        const detail =
          typeof data?.detail === "string"
            ? data.detail
            : data?.detail?.message || `Request failed (${status}).`;
        messages.push({
          role: "bot",
          title: "Request Failed",
          text: detail,
        });
        buttons = [{ label: "Try Again", next: "home" }];
      } else {
        maintenance = false;
        messages.push({
          role: "bot",
          title: data.message,
          text: data.answer || null,
          citation: data.citation || null,
        });
        buttons = data.buttons || [];
      }
    } catch {
      const isLocalDefault =
        API_URL.includes("127.0.0.1") || API_URL.includes("localhost");
      const hint = isLocalDefault
        ? " This PC is trying localhost. If the API runs on another machine (for example your office server), open extension options and set the API URL to that server (include /api)."
        : " Check that the server is running and this PC can reach that address on the network.";
      messages.push({
        role: "bot",
        title: "Connection Error",
        text: `Could not reach the server at ${API_URL}.${hint}`,
      });
      buttons = [
        { label: "Try Again", next: "home" },
        { label: "API settings", next: "__open_options__" },
      ];
    } finally {
      loading = false;
      render();
      scrollToBottom();
    }
  }

  // ── Text formatting ──────────────────────────────────────────
  function formatText(text) {
    if (!text) return "";
    const lines = text.split("\n");
    let html = "";
    let listItems = [];
    let listType = null;

    function flushList() {
      if (listItems.length > 0) {
        const tag = listType === "ol" ? "ol" : "ul";
        html += `<${tag} class="nds-msg-list">${listItems.join("")}</${tag}>`;
        listItems = [];
        listType = null;
      }
    }

    function inlineFmt(str) {
      return str.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    }

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
      const isWarning = /^WARNING:\s*/i.test(trimmed);
      if (isWarning) {
        const content = trimmed.replace(/^WARNING:\s*/i, "");
        html += `<p class="nds-msg-para nds-msg-warning"><span class="nds-msg-warning__icon">${ICON_ALERT}</span><span class="nds-msg-warning__text">${inlineFmt(content)}</span></p>`;
      } else {
        html += `<p class="nds-msg-para">${inlineFmt(trimmed)}</p>`;
      }
    }
    flushList();
    return html;
  }

  // ── Scroll ───────────────────────────────────────────────────
  function scrollToBottom() {
    requestAnimationFrame(() => {
      const list = shadow.querySelector(".nds-message-list");
      if (list) list.scrollTop = list.scrollHeight;
    });
  }

  // ── Actions ──────────────────────────────────────────────────
  function toggleChat() {
    isOpen = !isOpen;
    saveUiState();
    render();
  }

  function startChat() {
    messages = [];
    buttons = [];
    if (availablePlaybooks.length > 1 && !activePlaybook) {
      started = true;
      render();
      return;
    }
    if (availablePlaybooks.length === 1 && !activePlaybook) {
      activePlaybook = availablePlaybooks[0].file;
    }
    started = true;
    render();
    fetchNode("home");
  }

  function pickPlaybook(filename) {
    activePlaybook = filename;
    messages = [];
    buttons = [];
    render();
    fetchNode("home");
  }

  function selectOption(label, next) {
    if (next === "__open_options__") {
      try {
        chrome.runtime.openOptionsPage();
      } catch {}
      return;
    }
    fetchNode(next, label);
  }

  // ── Render ───────────────────────────────────────────────────
  function render() {
    const hasMultiple = availablePlaybooks.length > 1;
    const welcomeTitle = hasMultiple ? "NDS Playbook Chatbot" : (meta?.title || "NDS Playbook Chatbot");
    const company = meta?.company || "National Data & Surveying Services";
    const version = meta?.version || "";

    let html = "";

    if (isOpen) {
      html += `<div class="nds-backdrop"></div>`;
    }

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
        ${started && activePlaybook ? `<div class="nds-chat-window__header-bar">
          <span class="nds-header-email">${esc(activePlaybook.replace('.json','').replace(/_/g,' ').replace(/-/g,' ').toUpperCase())}</span>
          <div class="nds-header-actions">
            ${hasMultiple ? `<button class="nds-header-btn nds-header-btn--ghost" data-action="switch-playbook">\u21c4 Switch</button>` : ""}
            <button class="nds-header-btn nds-header-btn--ghost" data-action="restart"><span style="display:inline-flex;align-items:center;">${ICON_REFRESH}</span> Start Over</button>
          </div>
        </div>` : ""}
      </div>`;

      html += `<div class="nds-chat-window__body">`;

      if (!started) {
        html += `<div class="nds-chat-window__welcome">
          <div class="nds-chat-window__welcome-icon">${ICON_CLIPBOARD}</div>
          <h3>${esc(welcomeTitle)}</h3>
          <p class="nds-chat-window__company">${esc(company)}</p>
          <p class="nds-chat-window__desc">Your interactive guide to company processes, playbooks, and procedures.</p>
          <button class="nds-chat-window__start-btn" data-action="start">Open Playbook</button>
        </div>`;

      } else if (hasMultiple && !activePlaybook) {
        html += `<div class="nds-chat-window__welcome">
          <div class="nds-chat-window__welcome-icon">${ICON_CLIPBOARD}</div>
          <h3>Select a Playbook</h3>
          <p class="nds-chat-window__desc">Choose a playbook to open.</p>
          <div class="nds-option-buttons" style="margin-top:12px;">`;
        for (const pb of availablePlaybooks) {
          const label = pb.title || pb.file.replace('.json','').replace(/_/g,' ').replace(/-/g,' ');
          html += `<button class="nds-option-btn" data-action="pick-playbook" data-file="${esc(pb.file)}">${esc(label)}</button>`;
        }
        html += `</div></div>`;

      } else {
        // Messages
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
        if (loading) {
          html += `<div class="nds-typing"><span class="nds-dot"></span><span class="nds-dot"></span><span class="nds-dot"></span></div>`;
        }
        html += `</div>`;

        // Option buttons
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

    // FAB button
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

  // ── Event delegation ─────────────────────────────────────────
  container.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-action]");
    if (!btn) {
      if (e.target.closest(".nds-backdrop")) {
        toggleChat();
      }
      return;
    }
    const action = btn.dataset.action;
    if (action === "toggle") toggleChat();
    else if (action === "start") startChat();
    else if (action === "restart") { messages = []; buttons = []; render(); fetchNode("home"); }
    else if (action === "switch-playbook") { activePlaybook = null; messages = []; buttons = []; render(); }
    else if (action === "pick-playbook") {
      const file = btn.dataset.file;
      if (file) pickPlaybook(file);
    }
    else if (action === "option") {
      const idx = parseInt(btn.dataset.index, 10);
      const b = buttons[idx];
      if (b) selectOption(b.label, b.next);
    }
  });

  // Listen for toolbar icon click
  chrome.runtime.onMessage.addListener((msg) => {
    if (msg.action === "toggle_chatbot") {
      toggleChat();
    }
  });

  try {
    chrome.storage.onChanged.addListener((changes, area) => {
      if (area !== "sync" || !changes.ndsApiUrl) return;
      API_URL = normalizeApiUrl(changes.ndsApiUrl.newValue);
      fetchMeta().then(() => render());
    });
  } catch {}

  // ── Init ─────────────────────────────────────────────────────
  loadApiUrlFromStorage()
    .then(() => loadUiStateFromStorage())
    .then(() => fetchMeta())
    .then(() => render());
})();
