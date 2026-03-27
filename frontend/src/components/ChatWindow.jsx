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
  accessState,
  adUsername,
}) {
  const title   = meta?.title   || "NDS Client Management Playbook";
  const company = meta?.company || "National Data & Surveying Services";
  const version = meta?.version || "";

  const renderBody = () => {
    if (accessState === "checking") {
      return (
        <div className="chat-window__welcome">
          <IconClipboard className="chat-window__welcome-icon" />
          <p className="chat-window__desc">Verifying your access…</p>
        </div>
      );
    }

    if (accessState === "not_registered") {
      return (
        <div className="chat-window__welcome chat-window__welcome--denied">
          <div className="chat-window__lock-icon">🔒</div>
          <h3 className="chat-window__denied-title">Access Restricted</h3>
          <p className="chat-window__desc">
            {adUsername
              ? <>Hello <strong>{adUsername}</strong>, your account is not currently assigned to an authorised group for this playbook.</>
              : <>Your account is not currently assigned to an authorised group for this playbook.</>
            }
          </p>
          <div className="chat-window__denied-divider" />
          <p className="chat-window__desc chat-window__denied-hint">
            Please contact your team lead or IT to request access.
          </p>
        </div>
      );
    }

    if (accessState === "error") {
      return (
        <div className="chat-window__welcome chat-window__welcome--denied">
          <div className="chat-window__lock-icon">⚠️</div>
          <h3 className="chat-window__denied-title">Service Unavailable</h3>
          <p className="chat-window__desc">
            The playbook service could not be reached. Please make sure you are on the corporate network.
          </p>
          <div className="chat-window__denied-divider" />
          <p className="chat-window__desc chat-window__denied-hint">
            Contact IT support if this problem persists.
          </p>
        </div>
      );
    }

    // accessState === "allowed"
    if (!started) {
      return (
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
      );
    }

    return (
      <>
        <MessageList messages={messages} />
        {loading && (
          <div className="chat-window__typing">
            <span className="dot" /><span className="dot" /><span className="dot" />
          </div>
        )}
        <OptionButtons buttons={buttons} onSelect={onSelect} loading={loading} />
      </>
    );
  };

  return (
    <div
      className={`chat-window ${isDragging ? "chat-window--dragging" : ""}`}
      style={containerStyle}
    >
      <div className="chat-window__header" onPointerDown={onDragHandlePointerDown}>
        <div className="chat-window__header-left">
          <span className="chat-window__logo" aria-hidden="true">NDS</span>
          <div className="chat-window__header-text">
            <span className="chat-window__title">CM Playbook</span>
            <span className="chat-window__subtitle">{company}</span>
            {version && <span className="chat-window__version">v{version}</span>}
          </div>
        </div>
        {started && accessState === "allowed" && (
          <button className="chat-window__restart" onClick={onStart}>
            <IconRefresh className="chat-window__restart-icon" />
            <span>Start Over</span>
          </button>
        )}
      </div>

      <div className="chat-window__body">
        {renderBody()}
      </div>
    </div>
  );
}


