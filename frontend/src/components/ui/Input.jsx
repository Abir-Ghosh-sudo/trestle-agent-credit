/**
 * Input.jsx — Styled input primitive with label, suffix, error states.
 *
 * All value text uses monospace font.
 * Suffix (e.g. "ALGO") renders right-aligned inside the input.
 */

import React from "react";

export default function Input({
  value,
  onChange,
  label,
  suffix,
  placeholder,
  error,
  hint,
  id,
  type = "text",
  className = "",
  inputClassName = "",
  ...props
}) {
  return (
    <div className={`flex flex-col gap-1.5 ${className}`}>
      {/* Label row */}
      {(label || hint) && (
        <div className="flex items-center justify-between">
          {label && (
            <label
              htmlFor={id}
              className="text-[11px] font-sans font-medium uppercase tracking-[0.1em] text-[var(--text-secondary)]"
            >
              {label}
            </label>
          )}
          {hint && (
            <span className="text-[11px] font-mono text-[var(--text-muted)]">
              {hint}
            </span>
          )}
        </div>
      )}

      {/* Input field */}
      <div className="relative">
        <input
          id={id}
          type={type}
          value={value}
          onChange={onChange}
          placeholder={placeholder}
          className={[
            "w-full h-14",
            "bg-elevated backdrop-blur-md",
            "border border-border",
            "rounded-input",
            "px-4 text-[var(--text-primary)]",
            "font-mono text-xl",
            "shadow-soft-xs",
            "placeholder:text-[var(--text-muted)]",
            "transition-all duration-200",
            "focus:border-accent focus:shadow-glow-accent",
            error && "border-danger focus:border-danger focus:shadow-[0_0_0_1px_var(--danger),0_0_20px_rgba(251,113,133,0.25)]",
            suffix ? "pr-16" : "pr-4",
            inputClassName,
          ].filter(Boolean).join(" ")}
          {...props}
        />
        {suffix && (
          <span className="absolute right-4 top-1/2 -translate-y-1/2 text-sm font-mono text-[var(--text-muted)] pointer-events-none">
            {suffix}
          </span>
        )}
      </div>

      {/* Error message */}
      {error && (
        <p className="text-xs font-sans text-[var(--danger)]">{error}</p>
      )}
    </div>
  );
}
