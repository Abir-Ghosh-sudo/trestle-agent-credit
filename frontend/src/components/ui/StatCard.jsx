/**
 * StatCard.jsx — Data stat display card.
 *
 * Shows a label, value, unit, with optional flash animation
 * when the value changes (green for increase, red for decrease).
 */

import React, { useRef, useEffect, useState } from "react";

export default function StatCard({
  label,
  value,
  unit,
  flash = false,
  flashType = "success",
  className = "",
}) {
  const prevValueRef = useRef(value);
  const [flashClass, setFlashClass] = useState("");

  useEffect(() => {
    if (prevValueRef.current !== value && flash) {
      setFlashClass(flashType === "danger" ? "flash-danger" : "flash-success");
      const timer = setTimeout(() => setFlashClass(""), 1500);
      prevValueRef.current = value;
      return () => clearTimeout(timer);
    }
    prevValueRef.current = value;
  }, [value, flash, flashType]);

  return (
    <div
      className={`glass-panel p-4 flex flex-col gap-1 ${className}`}
    >
      <span className="text-[11px] font-sans font-medium uppercase tracking-[0.1em] text-[var(--text-secondary)]">
        {label}
      </span>
      <span className={`num text-2xl font-semibold text-[var(--text-primary)] ${flashClass}`}>
        {value}
      </span>
      {unit && (
        <span className="text-[11px] font-mono text-[var(--text-muted)] uppercase">
          {unit}
        </span>
      )}
    </div>
  );
}
