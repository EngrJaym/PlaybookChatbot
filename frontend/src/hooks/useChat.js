import { useState, useCallback, useEffect } from "react";

const API_URL = "http://localhost:8001/api";

export default function useChat() {
  const [messages, setMessages] = useState([]);
  const [buttons, setButtons] = useState([]);
  const [loading, setLoading] = useState(false);
  const [started, setStarted] = useState(false);
  const [meta, setMeta] = useState(null);

  // Fetch playbook metadata on mount
  useEffect(() => {
    fetch(`${API_URL}/meta`)
      .then((res) => res.json())
      .then(setMeta)
      .catch(() => {});
  }, []);

  const fetchNode = useCallback(async (nodeId, userLabel = null) => {
    setLoading(true);

    // If user clicked a button, add their choice as a "user" message
    if (userLabel) {
      setMessages((prev) => [...prev, { role: "user", text: userLabel }]);
    }

    // Clear current buttons while loading
    setButtons([]);

    try {
      const res = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ node_id: nodeId }),
      });

      if (!res.ok) throw new Error("Failed to fetch");

      const data = await res.json();

      // Build the bot message: title (message) + detailed answer
      const botMsg = {
        role: "bot",
        title: data.message,
        text: data.answer || null,
        nodeId: data.id,
      };

      setMessages((prev) => [...prev, botMsg]);
      setButtons(data.buttons);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: "bot",
          title: "Connection Error",
          text: "WARNING: Could not reach the server. Make sure the backend is running on port 8001.",
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
    (label, nextNodeId) => {
      fetchNode(nextNodeId, label);
    },
    [fetchNode]
  );

  return { messages, buttons, loading, started, meta, startChat, selectOption };
}
