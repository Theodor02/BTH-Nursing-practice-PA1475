import { useState, useRef, useEffect } from "react";
import "./Calculator.css";

interface HistoryEntry {
  expression: string;
  result: string;
}

const BUTTONS = [
  ["7", "8", "9", "/"],
  ["4", "5", "6", "*"],
  ["1", "2", "3", "-"],
  ["0", ".", "=", "+"],
  ["C", "(", ")", "⌫"],
];

export default function Calculator() {
  const [display, setDisplay] = useState("");
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [justEvaluated, setJustEvaluated] = useState(false);
  const calcRef = useRef<HTMLDivElement>(null);

  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.scrollLeft = inputRef.current.scrollWidth;
    }
  }, [display]);

  const evaluate = (expr: string): string => {
    try {
      const sanitized = expr.replace(/[^0-9+\-*/().eE]/g, "");

      if (!sanitized) return "";

      const res = Function(`"use strict"; return (${sanitized})`)();

      if (!Number.isFinite(res)) return "Fel";

      // Large/small numbers -> scientific notation
      if (Math.abs(res) >= 1e15 || (Math.abs(res) < 1e-6 && res !== 0)) {
        return res.toExponential(6);
      }

      // Integers untouched
      if (Number.isInteger(res)) {
        return res.toString();
      }

      return parseFloat(res.toFixed(6)).toString();
    } catch {
      return "Fel";
    }
  };

  const handlePress = (val: string) => {
    if (val === "=") {
      if (!display.trim()) return;
      const res = evaluate(display);
      setHistory((h) => [...h, { expression: display, result: res }]);
      setDisplay(res !== "Fel" ? res : "");
      setJustEvaluated(true);
    } else if (val === "C") {
      setDisplay("");
      setJustEvaluated(false);
    } else if (val === "⌫") {
      setDisplay((d) => d.slice(0, -1));
      setJustEvaluated(false);
    } else {
      // If we just evaluated and user types a digit/dot/paren, start fresh
      if (justEvaluated && /[0-9.()]/.test(val)) {
        setDisplay(val);
      } else {
        // If user types an operator after evaluation, continue from result
        setDisplay((d) => d + val);
      }
      setJustEvaluated(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    const key = e.key;
    const validKeys = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", ".", "+", "-", "*", "/", "(", ")"];

    if (validKeys.includes(key)) {
      e.preventDefault(); // Prevents default browser behaviors like scrolling on space/etc if applicable
      handlePress(key);
    } else if (key === "Enter" || key === "=") {
      e.preventDefault();
      handlePress("=");
    } else if (key === "Backspace") {
      e.preventDefault();
      handlePress("⌫");
    } else if (key === "Escape" || key.toLowerCase() === "c") {
      e.preventDefault();
      handlePress("C");
    }
  };

  const handleFocusClick = () => {
    if (calcRef.current) {
      calcRef.current.focus();
    }
  };

  return (
    <div 
      ref={calcRef}
      className="card calculator"
      tabIndex={0} 
      onKeyDown={handleKeyDown}
      onClick={handleFocusClick}
      style={{ outline: "none" }} // Prevents the default browser focus ring
    >
      <div className="calc-header">Miniräknare</div>

      {/* History rows */}
      {history.length > 0 && (
        <div className="calc-history">
          {history.map((h, i) => (
            <div key={i} className="calc-history-row">
              <span className="calc-hist-expr">{h.expression}</span>
              <span className="calc-hist-eq">= {h.result}</span>
            </div>
          ))}
        </div>
      )}

      {/* Read-only display: Input is handled purely via container keydown events now */}
      <div className="calc-display">
        <input
          ref={inputRef}
          className="calc-input"
          type="text"
          value={display}
          readOnly
          placeholder="0"
          autoComplete="off"
          tabIndex={-1} // Removes input from the natural tab order
        />
      </div>

      <div className="calc-grid">
        {BUTTONS.flat().map((btn) => (
          <button
            key={btn}
            className={`calc-btn ${btn === "=" ? "calc-eq" : ""} ${["C", "⌫"].includes(btn) ? "calc-fn" : ""} ${["+", "-", "*", "/"].includes(btn) ? "calc-op" : ""}`}
            onClick={() => handlePress(btn)}
            tabIndex={-1} // Prevents buttons from stealing keyboard focus
          >
            {btn}
          </button>
        ))}
      </div>

      {history.length > 0 && (
        <button
          className="calc-clear-history"
          onClick={() => setHistory([])}
          tabIndex={-1}
        >
          Rensa historik
        </button>
      )}
    </div>
  );
}