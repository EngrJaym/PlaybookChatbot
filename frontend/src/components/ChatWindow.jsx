import MessageList from "./MessageList";
import OptionButtons from "./OptionButtons";
import "./ChatWindow.css";
import IconClipboard from "./icons/IconClipboard";
import IconRefresh from "./icons/IconRefresh";

export default function ChatWindow({
  messages,
  buttons,
  loading,
  started,
  meta,
  onStart,
  onSelect,
  onDragHandlePointerDown,
  containerStyle,
  isDragging,
}) {
  const title = meta?.title || "NDS Client Management Playbook";
  const company = meta?.company || "National Data & Surveying Services";
  const version = meta?.version || "";

  return (
    <div
      className={`chat-window ${isDragging ? "chat-window--dragging" : ""}`}
      style={containerStyle}
    >
      <div className="chat-window__header" onPointerDown={onDragHandlePointerDown}>
        <div className="chat-window__header-left">
          <span className="chat-window__logo" aria-hidden="true">
            NDS
          </span>
          <div className="chat-window__header-text">
            <span className="chat-window__title">CM Playbook</span>
            <span className="chat-window__subtitle">{company}</span>
            {version && <span className="chat-window__version">v{version}</span>}
          </div>
        </div>
        {started && (
          <button className="chat-window__restart" onClick={onStart}>
            <IconRefresh className="chat-window__restart-icon" />
            <span>Start Over</span>
          </button>
        )}
      </div>

      <div className="chat-window__body">
        {!started ? (
          <div className="chat-window__welcome">
            <IconClipboard className="chat-window__welcome-icon" />
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
