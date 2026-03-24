const DEFAULT_API_URL = "http://127.0.0.1:8001/api";

chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.sync.get(["ndsApiUrl"], (result) => {
    const current = (result?.ndsApiUrl || "").trim();
    if (!current) {
      chrome.storage.sync.set({ ndsApiUrl: DEFAULT_API_URL });
    }
  });
});

chrome.action.onClicked.addListener((tab) => {
  chrome.tabs.sendMessage(tab.id, { action: "toggle_chatbot" });
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === "api_fetch") {
    const { url, options } = message;
    fetch(url, options)
      .then(async (res) => {
        let data = null;
        try { data = await res.json(); } catch {}
        sendResponse({ ok: true, status: res.status, data });
      })
      .catch((err) => {
        sendResponse({ ok: false, error: err.message });
      });
    return true;
  }
});
