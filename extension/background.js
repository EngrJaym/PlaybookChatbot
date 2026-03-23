chrome.action.onClicked.addListener((tab) => {
  chrome.tabs.sendMessage(tab.id, { action: "toggle_chatbot" });
});

function getNativeWindowsUsername() {
  return new Promise((resolve) => {
    try {
      const port = chrome.runtime.connectNative("com.nds.whoami");
      let resolved = false;

      port.onMessage.addListener((msg) => {
        resolved = true;
        port.disconnect();
        resolve({
          username: (msg && msg.username) ? msg.username.trim().toLowerCase() : null,
          groups:   (msg && msg.groups)   ? msg.groups : [],
        });
      });

      port.onDisconnect.addListener(() => {
        if (!resolved) {
          resolved = true;
          resolve({ username: null, groups: [] });
        }
      });

      port.postMessage({
        ad_server: "samba-ad.ad.one-nds.net",
        base_dn:   "DC=ad,DC=one-nds,DC=net",
      });

      setTimeout(() => {
        if (!resolved) {
          resolved = true;
          try { port.disconnect(); } catch {}
          resolve({ username: null, groups: [] });
        }
      }, 5000);
    } catch {
      resolve({ username: null, groups: [] });
    }
  });
}

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

  if (message.action === "get_windows_username") {
    getNativeWindowsUsername().then((result) => sendResponse(result));
    return true;
  }

  if (message.action === "get_ad_user") {
    chrome.storage.local.get(["nds_ad_username", "nds_ad_groups", "nds_ad_team", "nds_ad_playbooks", "nds_ad_playbook_titles"], (result) => {
      sendResponse({
        username:        result.nds_ad_username        || null,
        groups:          result.nds_ad_groups          || [],
        team:            result.nds_ad_team            || null,
        playbooks:       result.nds_ad_playbooks       || [],
        playbook_titles: result.nds_ad_playbook_titles || {},
      });
    });
    return true;
  }

  if (message.action === "save_ad_user") {
    chrome.storage.local.set({
      nds_ad_username:        message.username,
      nds_ad_groups:          message.groups || [],
      nds_ad_team:            message.team,
      nds_ad_playbooks:       message.playbooks,
      nds_ad_playbook_titles: message.playbook_titles,
    }, () => sendResponse({ ok: true }));
    return true;
  }
});
