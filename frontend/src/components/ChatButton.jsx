import "./ChatButton.css";

export default function ChatButton({ isOpen, onClick }) {
  return (
    <button
      className={`chat-fab ${isOpen ? "chat-fab--open" : ""}`}
      onClick={onClick}
      aria-label={isOpen ? "Close chat" : "Open chat"}
    >
      {isOpen ? "✕" : "💬"}
    </button>
  );
}

