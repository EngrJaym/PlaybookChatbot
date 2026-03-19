const GOOGLE_CLIENT_ID = "268855683186-j033gjjpgdmodkug7ibfaoqgtl5mdds7.apps.googleusercontent.com"

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

  if (message.action === "google_sign_in") {
    const redirectUrl = chrome.identity.getRedirectURL();
    const authUrl = "https://accounts.google.com/o/oauth2/v2/auth"
      + "?client_id=" + encodeURIComponent(GOOGLE_CLIENT_ID)
      + "&response_type=id_token"
      + "&redirect_uri=" + encodeURIComponent(redirectUrl)
      + "&scope=" + encodeURIComponent("openid email profile")
      + "&nonce=" + Math.random().toString(36).slice(2)
      + "&prompt=select_account";

    chrome.identity.launchWebAuthFlow(
      { url: authUrl, interactive: true },
      (responseUrl) => {
        if (chrome.runtime.lastError || !responseUrl) {
          sendResponse({ id_token: null, error: chrome.runtime.lastError?.message || "cancelled" });
          return;
        }
        const match = responseUrl.match(/id_token=([^&]+)/);
        const idToken = match ? match[1] : null;
        if (idToken) {
          chrome.storage.local.set({ nds_id_token: idToken });
        }
        sendResponse({ id_token: idToken });
      }
    );
    return true;
  }

  if (message.action === "get_stored_token") {
    chrome.storage.local.get(["nds_id_token"], (result) => {
      sendResponse({ id_token: result.nds_id_token || null });
    });
    return true;
  }

  if (message.action === "sign_out") {
    chrome.storage.local.remove("nds_id_token");
    sendResponse({ ok: true });
    return true;
  }
});
