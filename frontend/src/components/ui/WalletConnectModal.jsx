/**
 * WalletConnectModal.jsx — Centered glass modal for wallet selection.
 *
 * Replaces the old inline navbar dropdown with a proper modal, matching
 * the "Connect Wallet" pattern used by premium Web3 products (Uniswap,
 * Coinbase Wallet, etc). Backdrop blur + spring entrance via Framer Motion.
 *
 * Wallet connection logic is untouched — this only changes presentation;
 * it calls the same connectPera / connectDefly functions from WalletState.
 */

import React, { useEffect } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { X, Wallet, ShieldCheck } from "lucide-react";

const WALLETS = [
  {
    id: "pera",
    name: "Pera Wallet",
    description: "The official Algorand mobile & web wallet",
    letter: "P",
  },
  {
    id: "defly",
    name: "Defly Wallet",
    description: "Advanced Algorand wallet with DeFi tools",
    letter: "D",
  },
];

export default function WalletConnectModal({ open, onClose, onSelectPera, onSelectDefly }) {
  // Close on Escape for keyboard accessibility
  useEffect(() => {
    if (!open) return;
    const handler = (e) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open, onClose]);

  const handlers = { pera: onSelectPera, defly: onSelectDefly };

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-[100] flex items-center justify-center p-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
        >
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/70 backdrop-blur-sm"
            onClick={onClose}
            aria-hidden="true"
          />

          {/* Modal panel */}
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-labelledby="wallet-modal-title"
            initial={{ opacity: 0, y: 24, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 12, scale: 0.97 }}
            transition={{ type: "spring", stiffness: 340, damping: 28 }}
            className="relative w-full max-w-[420px] float-card p-6 md:p-7"
          >
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-brand-gradient shadow-glow-accent flex items-center justify-center">
                  <Wallet size={18} className="text-white" strokeWidth={2.25} />
                </div>
                <h2 id="wallet-modal-title" className="font-display font-bold text-lg text-text-primary">
                  Connect a wallet
                </h2>
              </div>
              <button
                onClick={onClose}
                aria-label="Close"
                className="w-9 h-9 rounded-full flex items-center justify-center text-text-muted hover:text-text-primary hover:bg-elevated-2 transition-colors"
              >
                <X size={18} />
              </button>
            </div>

            <div className="flex flex-col gap-3">
              {WALLETS.map((w) => (
                <button
                  key={w.id}
                  id={`wallet-connect-${w.id}`}
                  onClick={() => handlers[w.id]?.()}
                  className="w-full flex items-center gap-4 p-4 rounded-xl bg-elevated border border-border hover:border-accent/50 hover:bg-elevated-2 hover:-translate-y-0.5 transition-all duration-200 text-left group"
                >
                  <span className="w-11 h-11 shrink-0 flex items-center justify-center rounded-xl text-sm font-bold bg-brand-gradient text-white shadow-soft-sm group-hover:shadow-glow-accent transition-shadow">
                    {w.letter}
                  </span>
                  <span className="flex-1 min-w-0">
                    <span className="block font-display font-semibold text-sm text-text-primary">
                      {w.name}
                    </span>
                    <span className="block font-body text-xs text-text-muted mt-0.5 truncate">
                      {w.description}
                    </span>
                  </span>
                </button>
              ))}
            </div>

            <div className="mt-6 flex items-center gap-2 justify-center text-text-muted">
              <ShieldCheck size={13} strokeWidth={2} />
              <span className="font-body text-xs">
                Your keys never leave your wallet app
              </span>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
