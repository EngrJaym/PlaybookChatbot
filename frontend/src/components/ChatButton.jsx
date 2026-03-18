import "./ChatButton.css";
import IconRobotFace from "./icons/IconRobotFace";
import IconX from "./icons/IconX";

export default function ChatButton({ isOpen, onClick }) {
  return (
    <button
      className={`chat-fab ${isOpen ? "chat-fab--open" : ""}`}
      onClick={onClick}
      type="button"
      aria-label={isOpen ? "Close chat" : "Open chat"}
    >
      {isOpen ? (
        <IconX className="chat-fab__icon chat-fab__icon--close" />
      ) : (
        <IconRobotFace className="chat-fab__icon chat-fab__icon--robot" />
      )}
    </button>
  );
}

