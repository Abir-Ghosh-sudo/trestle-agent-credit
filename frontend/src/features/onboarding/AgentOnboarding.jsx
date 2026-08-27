/**
 * Register.jsx — Agent registration & staking interface.
 *
 * Visual language rebuilt for the glassmorphic design system; all
 * registration logic (staking, USDC activation, tx status, error
 * handling) is unchanged from the original implementation.
 */

import React, { useState } from "react";
import { Wallet, Check, X, Gem, TrendingUp, Layers } from "lucide-react";
import { useWallet } from "../../state/WalletState.jsx";
import { useContract } from "../../state/ContractState.jsx";
import { useToast } from "../../components/ui/Toast.jsx";

function WalletIcon() {
  return (
    <div className="w-16 h-16 rounded-2xl bg-brand-gradient shadow-glow-accent flex items-center justify-center mb-2">
      <Wallet size={28} className="text-white" strokeWidth={2} />
    </div>
  );
}

function StepIndicator({ currentStep }) {
  const steps = [
    { num: 1, label: "Opt-in" },
    { num: 2, label: "Stake" },
    { num: 3, label: "Active" },
  ];
  return (
    <div className="flex items-center justify-center gap-2 my-4">
      {steps.map((step, i) => {
        const isCompleted = currentStep > step.num;
        const isCurrent = currentStep === step.num;
        const isActive = isCompleted || isCurrent;
        return (
          <React.Fragment key={step.num}>
            <div className="flex flex-col items-center gap-1.5">
              <div
                className={[
                  "w-9 h-9 rounded-full flex items-center justify-center font-pixel text-sm font-bold transition-all duration-300",
                  isActive ? "bg-brand-gradient text-white shadow-soft-sm" : "bg-elevated text-text-muted border border-border",
                ].join(" ")}
              >
                {isCompleted ? <Check size={16} strokeWidth={3} /> : step.num}
              </div>
              <span className={`font-sans text-xs font-medium ${isCurrent ? "text-text-primary" : "text-text-muted"}`}>
                {step.label}
              </span>
            </div>
            {i < steps.length - 1 && (
              <div className="w-8 h-0.5 rounded-full bg-border -mt-5" />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}

export default function AgentOnboarding({ onRegistered }) {
  const { address, connectPera, connectDefly } = useWallet();
  const { callRegisterUnified, loading, isOptedIn } = useContract();
  const { addToast } = useToast();
  const [stakeInput, setStakeInput] = useState("1");
  const [activateUsdc, setActivateUsdc] = useState(true);
  const [txStatus, setTxStatus] = useState("idle"); // idle | signing | submitting | confirming | success | error
  const [errorMsg, setErrorMsg] = useState("");

  const stakeValue = parseFloat(stakeInput) || 0;
  const isValid = stakeValue >= 1;
  const initialCredit = (stakeValue * 2).toFixed(6);
  const maxCredit = (stakeValue * 10).toFixed(6);

  const handleRegister = async () => {
    if (!isValid) return;
    setTxStatus("signing");
    setErrorMsg("");
    try {
      setTxStatus("submitting");
      await callRegisterUnified(stakeInput, activateUsdc);
      setTxStatus("success");
      const msg = activateUsdc
        ? `✓ Agent registered — ALGO + USDC credit lines active!`
        : `✓ Agent registered — Initial credit: ${initialCredit} ALGO`;
      addToast(msg, "success", 5000);
      if (onRegistered) {
        setTimeout(() => onRegistered(), 1200);
      }
    } catch (err) {
      setTxStatus("error");
      setErrorMsg(err.message);
      addToast(err.message, "error");
    }
  };

  const getButtonText = () => {
    switch (txStatus) {
      case "signing": return "Signing...";
      case "submitting": return "Sending...";
      case "confirming": return "Confirm...";
      default: return "Register →";
    }
  };

  const currentStep = !address ? 1 : txStatus === "success" ? 3 : 2;

  const fmtAddress = (addr, start, end) => {
    if (!addr) return "";
    return `${addr.substring(0, start)}...${addr.substring(addr.length - end)}`;
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-[calc(100vh-10rem)] px-4 py-10 relative overflow-hidden">

      <div className="floating-blob w-64 h-64 top-10 left-[6%] opacity-30" style={{ background: "linear-gradient(135deg,#6d5df6,#8b6ff8)" }} />
      <div className="floating-blob w-48 h-48 bottom-16 right-[8%] opacity-25" style={{ background: "linear-gradient(135deg,#00c2d1,#8b6ff8)", animationDelay: "2s" }} />

      {/* Hero title */}
      <div className="text-center mb-10 max-w-xl flex flex-col items-center relative z-10">
        <h1 className="font-display font-bold text-4xl md:text-6xl leading-tight mb-4 text-text-primary">
          Credit, <span className="gradient-text">built for agents.</span>
        </h1>
        <p className="font-body text-lg text-text-secondary">
          Stake. Build history. Unlock financing.
        </p>
      </div>

      {/* Registration card */}
      <div className="float-card w-full max-w-[460px] p-0 relative overflow-hidden z-10">
        <div className="p-8 flex flex-col items-center">

          {/* Stage 1: Connect wallet */}
          {!address && (
            <div className="flex flex-col items-center text-center">
              <WalletIcon />
              <h2 className="font-display font-bold text-2xl text-text-primary my-5">
                Identify yourself
              </h2>
              <p className="font-body text-text-secondary mb-8 px-4">
                Pera or Defly Wallet required for on-chain identity.
              </p>
              <div className="w-full flex flex-col gap-3">
                <button
                  id="register-connect-pera"
                  onClick={connectPera}
                  className="h-14 rounded-btn bg-elevated-2 border border-border shadow-soft-sm lift-hover flex items-center justify-center gap-3 font-display font-semibold text-sm text-text-primary transition-all"
                >
                  <span className="w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold bg-brand-gradient text-white">P</span>
                  Connect Pera Wallet
                </button>
                <button
                  id="register-connect-defly"
                  onClick={connectDefly}
                  className="h-14 rounded-btn bg-elevated-2 border border-border shadow-soft-sm lift-hover flex items-center justify-center gap-3 font-display font-semibold text-sm text-text-primary transition-all"
                >
                  <span className="w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold bg-brand-gradient text-white">D</span>
                  Connect Defly Wallet
                </button>
              </div>
            </div>
          )}

          {/* Stage 2: Stake form */}
          {address && txStatus !== "success" && (
            <div className="w-full flex flex-col gap-6">
              {/* Connected address */}
              <div className="flex items-center gap-3 px-4 py-2.5 rounded-full bg-success-dim border border-success/25">
                <span className="w-2.5 h-2.5 rounded-full bg-success pulse-dot" />
                <span className="font-pixel text-sm font-semibold text-text-primary truncate">
                  {fmtAddress(address, 6, 6)}
                </span>
                {isOptedIn && (
                  <span className="ml-auto font-pixel text-[10px] bg-elevated-2 px-2 py-0.5 rounded-full text-text-secondary">
                    Opted in
                  </span>
                )}
              </div>

              <div className="flex flex-col gap-2">
                <label className="font-sans font-semibold text-sm text-text-primary">Stake amount</label>
                <div className="relative">
                  <input
                    id="stake-input"
                    type="number"
                    value={stakeInput}
                    onChange={(e) => setStakeInput(e.target.value)}
                    className="w-full h-14 bg-elevated backdrop-blur-md border border-border rounded-input shadow-soft-xs px-4 font-mono text-xl text-text-primary focus:border-accent focus:shadow-glow-accent transition-all"
                    placeholder="1.000000"
                  />
                  <span className="absolute right-4 top-1/2 -translate-y-1/2 font-pixel text-sm font-semibold text-text-muted">ALGO</span>
                </div>
                {!isValid && stakeInput !== "" && (
                  <p className="font-sans text-sm font-medium text-danger">Min 1 ALGO required.</p>
                )}
              </div>

              {/* Live credit preview */}
              <div className="rounded-xl bg-accent-dim border border-accent/20 p-4 space-y-3">
                <div className="flex items-center justify-between border-b border-border pb-2.5">
                  <span className="font-sans text-sm text-text-secondary">ALGO draw cap</span>
                  <span className="font-pixel text-base font-bold text-text-primary">0.500000 ALGO</span>
                </div>
                <div className="flex items-center justify-between border-b border-border pb-2.5">
                  <span className="font-sans text-sm text-text-secondary">Per-draw limit</span>
                  <span className="font-pixel text-base font-bold text-text-primary">0.100000 ALGO</span>
                </div>
                <div className="flex items-center justify-between border-b border-border pb-2.5">
                  <span className="font-sans text-sm text-text-secondary">Multiplier</span>
                  <span className="bg-elevated px-2.5 py-0.5 rounded-full font-pixel text-sm font-bold text-text-primary">T0 → T3</span>
                </div>
                {activateUsdc && (
                  <div className="flex items-center justify-between pt-1">
                    <span className="font-sans text-sm text-text-secondary">USDC credit line</span>
                    <span className="font-pixel text-sm font-bold" style={{ color: "var(--usdc-primary)" }}>✓ Auto-activated</span>
                  </div>
                )}
              </div>

              {/* USDC auto-activation checkbox */}
              <label
                className="flex items-center gap-3 cursor-pointer px-4 py-3 rounded-xl bg-elevated border border-border lift-hover transition-all"
                htmlFor="activate-usdc-checkbox"
              >
                <input
                  id="activate-usdc-checkbox"
                  type="checkbox"
                  checked={activateUsdc}
                  onChange={(e) => setActivateUsdc(e.target.checked)}
                  className="w-5 h-5 accent-[var(--usdc-primary)] cursor-pointer"
                />
                <div className="flex-1">
                  <span className="font-sans font-semibold text-sm text-text-primary">Also activate USDC credit</span>
                  <p className="font-body text-xs text-text-muted mt-0.5">Auto-borrows 1 ALGO from your credit line to stake on the USDC contract. No extra cost.</p>
                </div>
                <span className="font-pixel text-xs px-2 py-0.5 rounded-full" style={{ background: "var(--usdc-primary)", color: "#fff" }}>$</span>
              </label>

              <StepIndicator currentStep={currentStep} />

              <button
                id="register-button"
                disabled={!isValid || loading || txStatus !== "idle"}
                onClick={handleRegister}
                className="h-14 w-full rounded-btn bg-brand-gradient text-white shadow-soft-md hover:shadow-glow-accent hover:-translate-y-0.5 disabled:opacity-50 disabled:translate-y-0 disabled:shadow-soft-md transition-all font-display font-semibold text-base"
              >
                {loading || txStatus !== "idle" ? getButtonText() : "Register Agent →"}
              </button>

              {/* Error */}
              {errorMsg && (
                <div className="rounded-xl bg-danger-dim border border-danger/25 p-4 flex items-start gap-3">
                  <X size={18} className="text-danger" strokeWidth={2.5} />
                  <p className="font-sans text-sm font-medium text-danger">
                    Error: {errorMsg}
                  </p>
                </div>
              )}
            </div>
          )}

          {/* Stage 3: Success */}
          {txStatus === "success" && (
            <div className="flex flex-col items-center text-center py-6">
              <div className="w-20 h-20 rounded-2xl bg-brand-gradient shadow-glow-accent flex items-center justify-center mb-6">
                <Check size={36} className="text-white" strokeWidth={2.5} />
              </div>
              <h2 className="font-display font-bold text-2xl text-text-primary mb-4">
                Agent active
              </h2>
              <div className="glass-panel p-6">
                <p className="font-sans text-base font-medium text-text-secondary mb-1">
                  {activateUsdc ? "ALGO + USDC Credit Lines" : "ALGO Credit Line"}
                </p>
                <p className="font-display text-2xl font-bold gradient-text">
                  Active ✓
                </p>
              </div>
              <p className="font-sans text-base font-medium text-accent mt-8 animate-pulse">
                Redirecting to Dashboard...
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Info cards below registration */}
      {!address && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-5 mt-14 max-w-[700px] w-full relative z-10">
          {[
            { icon: Gem, title: "Stake & Lock", desc: "Lock ALGO to build trust." },
            { icon: TrendingUp, title: "Build History", desc: "Record payments for score." },
            { icon: Layers, title: "Draw Credit", desc: "Borrow up to 10× stake." },
          ].map((f) => (
            <div key={f.title} className="float-card p-5 flex flex-col items-center text-center group">
              <div className="w-12 h-12 rounded-xl bg-brand-gradient shadow-soft-sm flex items-center justify-center mb-3 transition-transform group-hover:scale-110">
                <f.icon size={20} className="text-white" strokeWidth={2} />
              </div>
              <h3 className="font-display font-semibold text-base text-text-primary mb-1.5">{f.title}</h3>
              <p className="font-body text-sm text-text-secondary leading-snug">{f.desc}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
