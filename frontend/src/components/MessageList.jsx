import { useEffect, useRef } from "react";
import "./MessageList.css";

import IconAlert from "./icons/IconAlert";

const WARNING_PREFIX_RE = /^WARNING:\s*/i;

function FormatText({ text }) {
  if (!text) return null;

  const lines = text.split("\n");
  const elements = [];
  let listItems = [];
  let listType = null;

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

    if (/^[•\-]\s/.test(trimmed)) {
      if (listType !== "ul") flushList();
      listType = "ul";
      listItems.push(<li key={i}>{formatInline(trimmed.replace(/^[•\-]\s*/, ""))}</li>);
      return;
    }

    const numMatch = trimmed.match(/^(\d+)\.\s(.+)/);
    if (numMatch) {
      if (listType !== "ol") flushList();
      listType = "ol";
      listItems.push(<li key={i}>{formatInline(numMatch[2])}</li>);
      return;
    }

    flushList();
    const isWarning = WARNING_PREFIX_RE.test(trimmed);
    const content = isWarning ? trimmed.replace(WARNING_PREFIX_RE, "") : trimmed;

    if (isWarning) {
      elements.push(
        <p key={i} className="msg-para msg-warning">
          <span className="msg-warning__icon" aria-hidden="true">
            <IconAlert className="msg-warning__icon-svg" />
          </span>
          <span className="msg-warning__text">{formatInline(content)}</span>
        </p>
      );
    } else {
      elements.push(
        <p key={i} className="msg-para">
          {formatInline(content)}
        </p>
      );
    }
  });

  flushList();
  return <>{elements}</>;
}

function CitationLine({ citation }) {
  if (!citation) return null;
  const source = citation.doc || "Unknown source";
  const heading = citation.heading || "";
  const match = citation.match || "";
  const label = heading ? `${source} - ${heading}` : source;

  return (
    <div className="msg-citation">
      <span className="msg-citation__label">Source:</span>
      <span className="msg-citation__value">{label}</span>
      {match && <span className="msg-citation__match">{match}</span>}
    </div>
  );
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
              <CitationLine citation={msg.citation} />
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
