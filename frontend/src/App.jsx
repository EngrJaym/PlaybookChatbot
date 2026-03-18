import { useState } from "react";
import ChatButton from "./components/ChatButton";
import ChatWindow from "./components/ChatWindow";
import useChat from "./hooks/useChat";
import "./App.css";

function App() {
  const [isOpen, setIsOpen] = useState(false);
  const { messages, buttons, loading, started, meta, startChat, selectOption } =
    useChat();

  const toggleChat = () => setIsOpen((prev) => !prev);

  return (
    <>
      {isOpen && (
        <ChatWindow
          messages={messages}
          buttons={buttons}
          loading={loading}
          started={started}
          meta={meta}
          onStart={startChat}
          onSelect={selectOption}
        />
      )}
      <ChatButton isOpen={isOpen} onClick={toggleChat} />
    </>
  );
}

export default App;
