const DEFAULT_API_URL = "http://127.0.0.1:8001/api";

const apiUrlInput = document.getElementById("apiUrl");
const saveBtn = document.getElementById("saveBtn");
const statusEl = document.getElementById("status");

function normalizeApiUrl(raw) {
  const cleaned = (raw || "").trim().replace(/\/+$/, "");
  return cleaned || DEFAULT_API_URL;
}

function setStatus(text) {
  statusEl.textContent = text;
  setTimeout(() => {
    if (statusEl.textContent === text) statusEl.textContent = "";
  }, 2500);
}

chrome.storage.sync.get(["ndsApiUrl"], (result) => {
  apiUrlInput.value = normalizeApiUrl(result?.ndsApiUrl);
});

saveBtn.addEventListener("click", () => {
  const value = normalizeApiUrl(apiUrlInput.value);
  chrome.storage.sync.set({ ndsApiUrl: value }, () => {
    apiUrlInput.value = value;
    setStatus("Settings saved.");
  });
});
