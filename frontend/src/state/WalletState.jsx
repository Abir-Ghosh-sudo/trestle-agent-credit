/**
 * WalletContext.jsx — Global Pera Wallet connection state.
 *
 * Exposes: { address, connectPera, connectDefly, disconnect, activeWallet }
 *
 * - Singleton PeraWalletConnect instance (avoids reconnect bugs
 *   on React re-render).
 * - Auto-reconnects session on page reload.
 * - Handles disconnect events from the wallet.
 */

import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
} from "react";
import { PeraWalletConnect } from "@perawallet/connect";
import { DeflyWalletConnect } from "@blockshake/defly-connect";

const WalletContext = createContext(null);

// Singleton — created once, reused across all renders
const peraWallet = new PeraWalletConnect({
  shouldShowSignTxnToast: true,
  network: "testnet",
});

const deflyWallet = new DeflyWalletConnect({
  shouldShowSignTxnToast: true,
  network: "testnet",
});

export function WalletProvider({ children }) {
  const [address, setAddress] = useState(null);
  const [activeWallet, setActiveWallet] = useState(null);

  const handleDisconnect = useCallback(() => {
    setAddress(null);
    setActiveWallet(null);
  }, []);

  // Reconnect existing session on mount
  useEffect(() => {
    peraWallet
      .reconnectSession()
      .then((accounts) => {
        peraWallet.connector?.on("disconnect", handleDisconnect);
        if (accounts.length > 0) {
          setAddress(accounts[0]);
          setActiveWallet(peraWallet);
        }
      })
      .catch((err) => {
        console.log("No existing Pera session:", err.message);
      });

    deflyWallet
      .reconnectSession()
      .then((accounts) => {
        deflyWallet.connector?.on("disconnect", handleDisconnect);
        if (accounts.length > 0) {
          setAddress(accounts[0]);
          setActiveWallet(deflyWallet);
        }
      })
      .catch((err) => {
        // Session expired or no previous session — that's fine
        console.log("No existing Defly session:", err.message);
      });
  }, [handleDisconnect]);

  const connectPera = useCallback(async () => {
    try {
      const accounts = await peraWallet.connect();
      peraWallet.connector?.on("disconnect", handleDisconnect);
      setAddress(accounts[0]);
      setActiveWallet(peraWallet);
      return accounts[0];
    } catch (err) {
      if (err?.data?.type !== "CONNECT_MODAL_CLOSED") {
        console.error("Pera connect error:", err);
        throw err;
      }
    }
  }, [handleDisconnect]);

  const connectDefly = useCallback(async () => {
    try {
      const accounts = await deflyWallet.connect();
      deflyWallet.connector?.on("disconnect", handleDisconnect);
      setAddress(accounts[0]);
      setActiveWallet(deflyWallet);
      return accounts[0];
    } catch (err) {
      // User closed the connect modal — not an error
      if (err?.data?.type !== "CONNECT_MODAL_CLOSED" && err?.message !== "Connection Cancelled") {
        console.error("Defly connect error:", err);
        throw err;
      }
    }
  }, [handleDisconnect]);

  const disconnect = useCallback(async () => {
    if (activeWallet) await activeWallet.disconnect();
    setAddress(null);
    setActiveWallet(null);
  }, [activeWallet]);

  return (
    <WalletContext.Provider
      value={{ address, connectPera, connectDefly, disconnect, activeWallet }}
    >
      {children}
    </WalletContext.Provider>
  );
}

export function useWallet() {
  const ctx = useContext(WalletContext);
  if (!ctx) {
    throw new Error("useWallet must be used inside WalletProvider");
  }
  return ctx;
}
