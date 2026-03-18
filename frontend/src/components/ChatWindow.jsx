import MessageList from "./MessageList";
import OptionButtons from "./OptionButtons";
import "./ChatWindow.css";

export default function ChatWindow({
  messages,
  buttons,
  loading,
  started,
  meta,
  onStart,
  onSelect,
}) {
  const title = meta?.title || "NDS Client Management Playbook";
  const company = meta?.company || "National Data & Surveying Services";
  const version = meta?.version || "";

  return (
    <div className="chat-window">
      {/* Header */}
      <div className="chat-window__header">
        <div className="chat-window__header-left">
          <span className="chat-window__logo">NDS</span>
          <div className="chat-window__header-text">
            <span className="chat-window__title">CM Playbook</span>
            {version && <span className="chat-window__version">v{version}</span>}
          </div>
        </div>
        {started && (
          <button className="chat-window__restart" onClick={onStart}>
            ↻ Start Over
          </button>
        )}
      </div>

      {/* Body */}
      <div className="chat-window__body">
        {!started ? (
          <div className="chat-window__welcome">
            <div className="chat-window__welcome-icon">📋</div>
            <h3>{title}</h3>
            <p className="chat-window__company">{company}</p>
            <p className="chat-window__desc">
              Your interactive guide to account setup, mapping, estimation, pricing, PSU, study types, QC checklists, and more.
            </p>
            <button className="chat-window__start-btn" onClick={onStart}>
              Open Playbook
            </button>
          </div>
        ) : (
          <>
            <MessageList messages={messages} />
            {loading && (
              <div className="chat-window__typing">
                <span className="dot" />
                <span className="dot" />
                <span className="dot" />
              </div>
            )}
            <OptionButtons
              buttons={buttons}
              onSelect={onSelect}
              loading={loading}
            />
          </>
        )}
      </div>
    </div>
  );
}
