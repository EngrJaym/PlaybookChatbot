import { useEffect, useRef } from "react";
import "./MessageList.css";

/**
 * Renders newline-separated text with basic formatting:
 *  - Lines starting with • or - become list items
 *  - Lines starting with a number+period become numbered items
 *  - **bold** text is rendered bold
 *  - Lines starting with ⚠️ get a warning style
 */
function FormatText({ text }) {
  if (!text) return null;

  const lines = text.split("\n");
  const elements = [];
  let listItems = [];
  let listType = null; // "ul" or "ol"

  const flushList = () => {
    if (listItems.length > 0) {
      const Tag = listType === "ol" ? "ol" : "ul";
      elements.push(
        <Tag key={elements.length} className="msg-list">
          {listItems}
        </Tag>
      );
      listItems = [];
      listType = null;
    }
  };

  const formatInline = (str) => {
    // Bold: **text** or text between asterisks
    const parts = str.split(/\*\*(.+?)\*\*/g);
    return parts.map((part, i) =>
      i % 2 === 1 ? <strong key={i}>{part}</strong> : part
    );
  };

  lines.forEach((line, i) => {
    const trimmed = line.trim();
    if (!trimmed) {
      flushList();
      return;
    }

    // Bullet item
    if (/^[•\-]\s/.test(trimmed)) {
      if (listType !== "ul") flushList();
      listType = "ul";
      listItems.push(<li key={i}>{formatInline(trimmed.replace(/^[•\-]\s*/, ""))}</li>);
      return;
    }

    // Numbered item
    const numMatch = trimmed.match(/^(\d+)\.\s(.+)/);
    if (numMatch) {
      if (listType !== "ol") flushList();
      listType = "ol";
      listItems.push(<li key={i}>{formatInline(numMatch[2])}</li>);
      return;
    }

    // Regular line
    flushList();
    const isWarning = trimmed.startsWith("⚠️");
    elements.push(
      <p key={i} className={`msg-para ${isWarning ? "msg-warning" : ""}`}>
        {formatInline(trimmed)}
      </p>
    );
  });

  flushList();
  return <>{elements}</>;
}

export default function MessageList({ messages }) {
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="message-list">
      {messages.map((msg, i) => (
        <div key={i} className={`message message--${msg.role}`}>
          {msg.role === "bot" ? (
            <div className="message__bubble message__bubble--bot">
              {msg.title && <div className="msg-title">{msg.title}</div>}
              {msg.text && (
                <div className="msg-answer">
                  <FormatText text={msg.text} />
                </div>
              )}
            </div>
          ) : (
            <div className="message__bubble message__bubble--user">
              {msg.text}
            </div>
          )}
        </div>
      ))}
      <div ref={endRef} />
    </div>
  );
}
