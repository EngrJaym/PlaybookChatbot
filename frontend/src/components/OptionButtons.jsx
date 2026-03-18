import "./OptionButtons.css";

export default function OptionButtons({ buttons, onSelect, loading }) {
  if (!buttons || buttons.length === 0) return null;

  const isLargeSet = buttons.length > 6;

  return (
    <div className={`option-buttons ${isLargeSet ? "option-buttons--compact" : ""}`}>
      {buttons.map((btn, i) => {
        const isBack = btn.label.toLowerCase().includes("back") || btn.label.toLowerCase().includes("home");
        return (
          <button
            key={i}
            className={`option-btn ${isBack ? "option-btn--back" : ""}`}
            disabled={loading}
            onClick={() => onSelect(btn.label, btn.next)}
          >
            {btn.label}
          </button>
        );
      })}
    </div>
  );
}
