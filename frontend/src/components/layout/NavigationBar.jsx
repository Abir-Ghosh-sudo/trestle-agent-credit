/**
 * NavigationBar.jsx — Floating dark-glass navigation bar.
 *
 * Left:   Trestle logo mark + wordmark + Docs link
 * Center: Network status pill (gradient dot + network name)
 * Right:  "Connect Wallet" → opens WalletConnectModal, or balance +
 *         address pill + disconnect once connected.
 *
 * Wallet connection logic (useWallet) is unchanged — only presentation.
 */

import React, { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { LogOut, Radio } from "lucide-react";
import { useWallet } from "../../state/WalletState.jsx";
import { fmtAddress } from "../../lib/format.js";
import { algodClient } from "../../lib/algod.js";
import logoMark from "../../assets/logo-mark.svg";
import WalletConnectModal from "../ui/WalletConnectModal.jsx";

export default function NavigationBar({ onLogoClick, onAppClick, onDocsClick, activeView }) {
  const { address, connectPera, connectDefly, disconnect } = useWallet();
  const [modalOpen, setModalOpen] = useState(false);
  const [balance, setBalance] = useState(null);

  // Fetch ALGO balance
  useEffect(() => {
    if (!address) { setBalance(null); return; }
    const fetchBal = async () => {
      try {
        const info = await algodClient.accountInformation(address).do();
        setBalance((Number(info.amount) / 1e6).toFixed(2));
      } catch {}
    };
    fetchBal();
    const iv = setInterval(fetchBal, 15000);
    return () => clearInterval(iv);
  }, [address]);

  const handleSelectPera = () => { connectPera(); setModalOpen(false); };
  const handleSelectDefly = () => { connectDefly(); setModalOpen(false); };

  return (
    <>
      <motion.header
        initial={{ y: -24, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ type: "spring", stiffness: 260, damping: 28 }}
        className="fixed top-0 left-0 right-0 z-50 p-3 md:p-5 pointer-events-none"
      >
        <div className="max-w-[1240px] mx-auto pointer-events-auto h-16 glass-panel !rounded-full flex items-center justify-between px-3 md:px-5">

          <div className="flex items-center gap-4 md:gap-8">
            <button
              onClick={onLogoClick}
              className="flex items-center gap-2.5 transition-transform duration-200 hover:scale-[1.02] active:scale-[0.98]"
            >
              <img src={logoMark} alt="Trestle" className="w-8 h-8 rounded-lg shadow-soft-sm" />
              <span className="font-display font-bold text-xl tracking-tight text-text-primary">
                Trestle
              </span>
            </button>

            {/* Docs nav link */}
            <button
              onClick={onDocsClick}
              className={[
                "hidden md:flex items-center gap-1.5 px-4 py-1.5 rounded-full font-display font-semibold text-xs uppercase tracking-wider transition-all duration-200",
                activeView === "docs"
                  ? "bg-brand-gradient text-white shadow-glow-accent"
                  : "text-text-secondary hover:text-text-primary hover:bg-elevated",
              ].join(" ")}
            >
              Docs
            </button>
          </div>

          {/* Center — Network pill */}
          <div className="hidden lg:flex items-center gap-2 px-4 py-1.5 rounded-full bg-elevated backdrop-blur border border-border font-pixel text-[13px]">
            <Radio size={12} className="text-success" strokeWidth={2.5} />
            <span className="uppercase text-text-secondary font-semibold tracking-wide">
              Algorand Testnet
            </span>
          </div>

          {/* Right — Wallet */}
          <div className="flex items-center gap-2">
            {address ? (
              <>
                {balance && (
                  <span className="hidden md:inline font-pixel font-semibold text-[13px] text-text-secondary bg-elevated backdrop-blur px-3 py-1.5 rounded-full border border-border">
                    {balance} ALGO
                  </span>
                )}
                <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-elevated-2 backdrop-blur border border-border shadow-soft-xs cursor-default">
                  <span className="w-2 h-2 rounded-full bg-success" />
                  <span className="font-pixel font-semibold text-[13px] text-text-primary">
                    {fmtAddress(address)}
                  </span>
                </div>
                <button
                  id="wallet-disconnect"
                  onClick={disconnect}
                  aria-label="Disconnect wallet"
                  className="w-10 h-10 flex items-center justify-center rounded-full bg-danger-dim text-danger transition-all duration-200 hover:bg-danger hover:text-white hover:-translate-y-0.5"
                  title="Disconnect wallet"
                >
                  <LogOut size={16} strokeWidth={2.25} />
                </button>
              </>
            ) : (
              <button
                id="wallet-connect"
                onClick={() => setModalOpen(true)}
                className="h-10 px-6 rounded-full bg-brand-gradient text-white shadow-soft-md transition-all duration-200 hover:shadow-glow-accent hover:-translate-y-0.5 active:translate-y-0 font-display font-semibold text-sm"
              >
                Connect Wallet
              </button>
            )}
          </div>
        </div>
      </motion.header>

      <WalletConnectModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onSelectPera={handleSelectPera}
        onSelectDefly={handleSelectDefly}
      />
    </>
  );
}
