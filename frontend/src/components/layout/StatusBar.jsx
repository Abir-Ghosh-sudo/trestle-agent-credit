/**
 * Footer.jsx — Floating glass status bar.
 *
 * Left:   Live round number from algodClient.status()
 * Center: App ID with explorer link
 * Right:  Network indicator
 */

import React, { useState, useEffect, useRef } from "react";
import { motion } from "framer-motion";
import { algodClient } from "../../lib/algod.js";
import { APP_ID } from "../../lib/contract.js";
import { fmtRound } from "../../lib/format.js";

export default function StatusBar() {
  const [round, setRound] = useState(null);
  const [pulsing, setPulsing] = useState(false);
  const intervalRef = useRef(null);

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const status = await algodClient.status().do();
        const r = status["last-round"];
        setRound(r);
        setPulsing(true);
        setTimeout(() => setPulsing(false), 1000);
      } catch (err) {
        console.log("Footer status fetch:", err.message);
      }
    };

    fetchStatus();
    intervalRef.current = setInterval(fetchStatus, 10000);
    return () => clearInterval(intervalRef.current);
  }, []);

  return (
    <motion.footer
      initial={{ y: 24, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ type: "spring", stiffness: 260, damping: 28, delay: 0.1 }}
      className="fixed bottom-0 left-0 right-0 z-40 p-3 md:p-5 pointer-events-none"
    >
      <div className="max-w-[1240px] mx-auto pointer-events-auto h-11 glass-panel !rounded-full flex items-center justify-between px-5">
        <span
          className="font-pixel text-[13px] text-text-secondary font-semibold flex items-center gap-2 transition-opacity duration-200"
          style={{ opacity: pulsing ? 1 : 0.65 }}
        >
          <span className={`w-2 h-2 rounded-full ${pulsing ? "bg-success pulse-dot" : "bg-text-muted"}`} />
          {round ? `Round ${fmtRound(round)}` : "Connecting..."}
        </span>

        <a
          href={`https://testnet.explorer.perawallet.app/application/${APP_ID}/`}
          target="_blank"
          rel="noopener noreferrer"
          className="font-pixel text-[13px] text-text-secondary font-semibold flex items-center gap-1 px-2.5 py-1 rounded-full hover:bg-accent-dim hover:text-accent transition-all"
        >
          App {APP_ID}
        </a>

        <span className="font-pixel text-[13px] text-text-secondary font-semibold hidden sm:block bg-elevated px-3 py-1 rounded-full border border-border">
          Algorand Testnet
        </span>
      </div>
    </motion.footer>
  );
}
