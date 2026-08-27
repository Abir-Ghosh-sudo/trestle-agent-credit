/**
 * Toast.jsx — Toast notification system.
 *
 * Fixed bottom-right, stacks vertically,
 * slides in from right, auto-dismisses.
 *
 * Usage:
 *   import { ToastProvider, useToast } from "./ui/Toast";
 *   const { addToast } = useToast();
 *   addToast("Message", "success"); // success | error | info
 */

import React, {
  createContext,
  useContext,
  useState,
  useCallback,
  useRef,
} from "react";

const ToastContext = createContext(null);

let toastCounter = 0;

const ICONS = {
  success: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <path d="M13.5 4.5L6.5 11.5L2.5 7.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  error: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <path d="M4.5 4.5L11.5 11.5M11.5 4.5L4.5 11.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
    </svg>
  ),
  info: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.5"/>
      <path d="M8 5.5V5.51M8 7V10.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  ),
};

const COLORS = {
  success: { border: "var(--success)", text: "var(--success)" },
  error:   { border: "var(--danger)",  text: "var(--danger)" },
  info:    { border: "var(--accent)",  text: "var(--accent)" },
};

function ToastItem({ toast, onRemove }) {
  const [exiting, setExiting] = React.useState(false);
  const timerRef = useRef(null);
  const c = COLORS[toast.type] || COLORS.info;

  React.useEffect(() => {
    timerRef.current = setTimeout(() => {
      setExiting(true);
      setTimeout(() => onRemove(toast.id), 300);
    }, toast.duration || 3000);
    return () => clearTimeout(timerRef.current);
  }, [toast, onRemove]);

  return (
    <div
      className={`${exiting ? "toast-exit" : "toast-enter"} flex items-start gap-3 px-4 py-3 rounded-md min-w-[280px] max-w-[400px] backdrop-blur-xl`}
      style={{
        background: "var(--bg-elevated)",
        borderLeft: `3px solid ${c.border}`,
        boxShadow: "var(--shadow-lg)",
        border: "1px solid var(--bg-border)",
        borderLeftWidth: "3px",
        borderLeftColor: c.border,
      }}
    >
      <span style={{ color: c.text }} className="mt-0.5 shrink-0">
        {ICONS[toast.type]}
      </span>
      <p className="text-sm font-sans text-[var(--text-primary)] leading-snug">
        {toast.message}
      </p>
    </div>
  );
}

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);

  const removeToast = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const addToast = useCallback((message, type = "info", duration = 3000) => {
    const id = ++toastCounter;
    setToasts((prev) => [...prev, { id, message, type, duration }]);
  }, []);

  return (
    <ToastContext.Provider value={{ addToast }}>
      {children}
      {/* Toast container */}
      <div
        className="fixed z-[9999] flex flex-col-reverse gap-2"
        style={{ bottom: 44, right: 16 }}
      >
        {toasts.map((t) => (
          <ToastItem key={t.id} toast={t} onRemove={removeToast} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be inside ToastProvider");
  return ctx;
}
