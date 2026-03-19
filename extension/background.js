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

  if (message.action === "get_gmail") {
    const interactive = message.interactive !== false;

    if (!interactive) {
      chrome.storage.local.get(["nds_cached_email"], (result) => {
        sendResponse({ email: result.nds_cached_email || null });
      });
      return true;
    }

    const clientId = "268855683186-j033gjjpgdmodkug7ibfaoqgtl5mdds7.apps.googleusercontent.com";
    const redirectUrl = chrome.identity.getRedirectURL();
    const authUrl = "https://accounts.google.com/o/oauth2/v2/auth"
      + "?client_id=" + encodeURIComponent(clientId)
      + "&response_type=token"
      + "&redirect_uri=" + encodeURIComponent(redirectUrl)
      + "&scope=" + encodeURIComponent("openid email profile")
      + "&prompt=select_account";

    chrome.identity.launchWebAuthFlow(
      { url: authUrl, interactive: true },
      (responseUrl) => {
        if (chrome.runtime.lastError || !responseUrl) {
          sendResponse({ email: null });
          return;
        }
        const tokenMatch = responseUrl.match(/access_token=([^&]+)/);
        if (!tokenMatch) {
          sendResponse({ email: null });
          return;
        }
        fetch("https://www.googleapis.com/oauth2/v3/userinfo", {
          headers: { Authorization: "Bearer " + tokenMatch[1] }
        })
          .then((res) => res.json())
          .then((info) => {
            const email = (info && info.email) ? info.email : null;
            if (email) {
              chrome.storage.local.set({ nds_cached_email: email });
            }
            sendResponse({ email: email });
          })
          .catch(() => {
            sendResponse({ email: null });
          });
      }
    );
    return true;
  }

  if (message.action === "sign_out") {
    chrome.storage.local.remove("nds_cached_email", () => {
      sendResponse({ ok: true });
    });
    return true;
  }
});
