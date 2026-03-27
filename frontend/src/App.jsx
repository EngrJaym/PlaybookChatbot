import { useEffect, useRef, useState } from "react";
import ChatButton from "./components/ChatButton";
import ChatWindow from "./components/ChatWindow";
import useChat from "./hooks/useChat";
import "./App.css";

function App() {
  const [isOpen, setIsOpen] = useState(false);
  const [dragPosition, setDragPosition] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const userSelectPrevRef = useRef("");
  const rafRef = useRef(null);
  const latestPosRef = useRef(null);
  const { messages, buttons, loading, started, meta, startChat, selectOption,
          accessState, adUsername } = useChat();

  const toggleChat = () => {
    setIsOpen((prev) => {
      const next = !prev;
      if (prev && !next) {
        setDragPosition(null);
        setIsDragging(false);
      }
      return next;
    });
  };

  const clamp = (v, min, max) => Math.min(max, Math.max(min, v));

  const onDragHandlePointerDown = (e) => {
    if (e.pointerType === "mouse" && e.button !== 0) return;
    if (e.target && e.target.closest && e.target.closest("button")) return;

    const chatEl = e.currentTarget.closest(".chat-window");
    if (!chatEl) return;

    const rect = chatEl.getBoundingClientRect();
    const margin = 8;
    const start = {
      clientX: e.clientX,
      clientY: e.clientY,
      left: rect.left,
      top: rect.top,
    };

    e.preventDefault();
    e.stopPropagation();

    userSelectPrevRef.current = document.body.style.userSelect;
    document.body.style.userSelect = "none";

    setIsDragging(true);
    setDragPosition({ left: start.left, top: start.top });

    let width = rect.width;
    let height = rect.height;
    const maxLeft = () => window.innerWidth - width - margin;
    const maxTop = () => window.innerHeight - height - margin;

    const applyLatest = () => {
      rafRef.current = null;
      if (!latestPosRef.current) return;
      setDragPosition(latestPosRef.current);
    };

    const schedule = (left, top) => {
      latestPosRef.current = { left, top };
      if (rafRef.current) return;
      rafRef.current = window.requestAnimationFrame(applyLatest);
    };

    const onMove = (ev) => {
      const nextLeft = start.left + (ev.clientX - start.clientX);
      const nextTop = start.top + (ev.clientY - start.clientY);

      const left = clamp(nextLeft, margin, maxLeft());
      const top = clamp(nextTop, margin, maxTop());
      schedule(left, top);
    };

    const endDrag = () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", endDrag);
      window.removeEventListener("pointercancel", endDrag);
      if (rafRef.current) window.cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
      latestPosRef.current = null;
      setIsDragging(false);
      document.body.style.userSelect = userSelectPrevRef.current;
    };

    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", endDrag, { once: true });
    window.addEventListener("pointercancel", endDrag, { once: true });
  };

  useEffect(() => {
    return () => {
      if (rafRef.current) window.cancelAnimationFrame(rafRef.current);
      document.body.style.userSelect = userSelectPrevRef.current;
    };
  }, []);

  const containerStyle =
    dragPosition && isOpen
      ? {
          left: `${dragPosition.left}px`,
          top: `${dragPosition.top}px`,
          right: "auto",
          bottom: "auto",
        }
      : undefined;

  return (
    <>
      {isOpen && <div className="chat-backdrop" onClick={toggleChat} aria-hidden="true" />}
      {isOpen && (
        <ChatWindow
          messages={messages}
          buttons={buttons}
          loading={loading}
          started={started}
          meta={meta}
          onStart={startChat}
          onSelect={selectOption}
          onDragHandlePointerDown={onDragHandlePointerDown}
          containerStyle={containerStyle}
          isDragging={isDragging}
          accessState={accessState}
          adUsername={adUsername}
        />
      )}
      <ChatButton isOpen={isOpen} onClick={toggleChat} />
    </>
  );
}

export default App;
