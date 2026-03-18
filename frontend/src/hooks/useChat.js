import { useState, useCallback, useEffect } from "react";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8001/api";

export default function useChat() {
  const [messages, setMessages]     = useState([]);
  const [buttons, setButtons]       = useState([]);
  const [loading, setLoading]       = useState(false);
  const [started, setStarted]       = useState(false);
  const [meta, setMeta]             = useState(null);
  const [flags, setFlags]           = useState(null);
  const [maintenance, setMaintenance] = useState(false);

  useEffect(() => {
    fetch(`${API_URL}/meta`)
      .then((res) => res.json())
      .then(setMeta)
      .catch(() => {});

    fetch(`${API_URL}/flags`)
      .then((res) => res.json())
      .then((data) => {
        setFlags(data);
        if (data?.maintenance_mode) {
          setMaintenance(true);
        }
      })
      .catch(() => {});
  }, []);

  const fetchNode = useCallback(async (nodeId, userLabel = null) => {
    setLoading(true);

    if (userLabel) {
      setMessages((prev) => [...prev, { role: "user", text: userLabel }]);
    }
    setButtons([]);

    try {
      const res = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ node_id: nodeId }),
      });

      // Handle maintenance mode (503)
      if (res.status === 503) {
        const err = await res.json();
        setMaintenance(true);
        setMessages((prev) => [
          ...prev,
          {
            role: "bot",
            title: "🔧 Under Maintenance",
            text: err?.detail?.message || "The playbook is currently under maintenance. Please try again shortly.",
          },
        ]);
        setButtons([]);
        return;
      }

      if (res.status === 404) {
        const err = await res.json();
        setMessages((prev) => [
          ...prev,
          {
            role: "bot",
            title: "Feature Unavailable",
            text: err?.detail || "This feature is currently disabled.",
          },
        ]);
        setButtons([{ label: "🏠 Back to Home", next: "home" }]);
        return;
      }

      if (!res.ok) throw new Error("Failed to fetch");

      const data = await res.json();
      setMaintenance(false);

      setMessages((prev) => [
        ...prev,
        {
          role:   "bot",
          title:  data.message,
          text:   data.answer || null,
          nodeId: data.id,
        },
      ]);
      setButtons(data.buttons);

    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role:  "bot",
          title: "Connection Error",
          text:  "⚠️ Could not reach the server. Make sure the backend is running on port 8001.",
        },
      ]);
      setButtons([{ label: "Try Again", next: "home" }]);
    } finally {
      setLoading(false);
    }
  }, []);

  const startChat = useCallback(() => {
    setMessages([]);
    setButtons([]);
    setStarted(true);
    fetchNode("home");
  }, [fetchNode]);

  const selectOption = useCallback(
    (label, nextNodeId) => fetchNode(nextNodeId, label),
    [fetchNode]
  );

  return {
    messages, buttons, loading, started,
    meta, flags, maintenance,
    startChat, selectOption,
  };
}
