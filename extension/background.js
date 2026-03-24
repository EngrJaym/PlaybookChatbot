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

  if (message.action === "get_ad_user") {
    chrome.storage.local.get(
      ["nds_ad_username", "nds_ad_groups", "nds_ad_team", "nds_ad_playbooks", "nds_ad_playbook_titles"],
      (result) => {
        sendResponse({
          username:        result.nds_ad_username        || null,
          groups:          result.nds_ad_groups          || [],
          team:            result.nds_ad_team            || null,
          playbooks:       result.nds_ad_playbooks       || [],
          playbook_titles: result.nds_ad_playbook_titles || {},
        });
      }
    );
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

  if (message.action === "clear_ad_user") {
    chrome.storage.local.remove(
      ["nds_ad_username", "nds_ad_groups", "nds_ad_team", "nds_ad_playbooks", "nds_ad_playbook_titles"],
      () => sendResponse({ ok: true })
    );
    return true;
  }
});
