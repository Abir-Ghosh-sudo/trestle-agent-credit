/**
 * Button.jsx — Primary interactive control for Trestle (Obsidian theme).
 *
 * Dark glass / gradient surface with glow-on-hover and a spring lift,
 * powered by Framer Motion for the premium micro-interaction feel.
 *
 * Variants: primary | danger | ghost | outline
 * Sizes: sm | md | lg
 * States: idle, hover, loading, disabled
 */

import React from "react";
import { motion } from "framer-motion";
import { Loader2 } from "lucide-react";

const VARIANTS = {
  primary: {
    base: "bg-brand-gradient text-white shadow-soft-md",
    hover: "hover:shadow-glow-accent",
    disabled: "opacity-40 cursor-not-allowed",
  },
  danger: {
    base: "bg-elevated backdrop-blur border border-danger/40 text-danger shadow-soft-sm",
    hover: "hover:bg-danger hover:text-white hover:shadow-soft-md",
    disabled: "opacity-40 cursor-not-allowed",
  },
  ghost: {
    base: "bg-transparent text-text-secondary",
    hover: "hover:bg-elevated hover:text-text-primary hover:backdrop-blur",
    disabled: "opacity-40 cursor-not-allowed",
  },
  outline: {
    base: "bg-elevated backdrop-blur border border-border text-text-primary shadow-soft-xs",
    hover: "hover:border-accent hover:text-accent-hover hover:shadow-soft-sm",
    disabled: "opacity-40 cursor-not-allowed",
  },
};

const SIZES = {
  sm: "h-8 px-3.5 text-xs rounded-btn",
  md: "h-10 px-5 text-sm rounded-btn",
  lg: "h-12 px-7 text-sm rounded-btn",
};

export default function Button({
  variant = "primary",
  size = "md",
  loading = false,
  disabled = false,
  children,
  className = "",
  id,
  ...props
}) {
  const v = VARIANTS[variant] || VARIANTS.primary;
  const s = SIZES[size] || SIZES.md;
  const isDisabled = disabled && !loading;

  return (
    <motion.button
      id={id}
      disabled={isDisabled}
      whileHover={isDisabled ? {} : { y: -2, scale: 1.01 }}
      whileTap={isDisabled ? {} : { y: 0, scale: 0.97 }}
      transition={{ type: "spring", stiffness: 400, damping: 25 }}
      className={[
        "inline-flex items-center justify-center gap-2",
        "font-sans font-semibold",
        "transition-colors duration-200 ease-out",
        s,
        v.base,
        isDisabled ? v.disabled : v.hover,
        isDisabled && "pointer-events-none",
        className,
      ].filter(Boolean).join(" ")}
      {...props}
    >
      {loading ? (
        <>
          <Loader2 className="spinner" size={18} strokeWidth={2.5} />
          <span>Signing...</span>
        </>
      ) : (
        children
      )}
    </motion.button>
  );
}
