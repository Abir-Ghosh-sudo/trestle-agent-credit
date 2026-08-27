/**
 * Dashboard.jsx — USDC-first position overview + action panels.
 *
 * USDC is the primary currency. ALGO is secondary (accessible via toggle).
 * The "Draw USDC" button uses the auto-swap flow when the treasury is empty.
 */

import React, { useState, useEffect } from "react";
import { useWallet } from "../../state/WalletState.jsx";
import { useContract } from "../../state/ContractState.jsx";
import { useToast } from "../../components/ui/Toast.jsx";
import Button from "../../components/ui/Button.jsx";
import Input from "../../components/ui/Input.jsx";
import { fmtAlgo, fmtAddress } from "../../lib/format.js";
import { SkeletonStatCard } from "../../components/ui/Skeleton.jsx";
import { USDC_ASA_ID, fromMicroUsdc, toMicroUsdc, toMicroAlgo } from "../../lib/contract.js";
import PaymentGatewayPanel from "../payments/PaymentGatewayPanel.jsx";

/* ── Utilisation Bar ── */
function UtilisationBar({ percent }) {
  const barColor =
    percent > 80 ? "var(--danger)"
    : percent > 60 ? "var(--warning)"
    : "var(--success)";

  return (
    <div className="flex items-center gap-3">
      <div
        className="flex-1 h-1.5 rounded-full overflow-hidden"
        style={{ background: "var(--bg-elevated)" }}
      >
        <div
          className="h-full rounded-full animate-grow"
          style={{
            width: `${Math.min(percent, 100)}%`,
            background: barColor,
            transition: "background-color 0.3s ease",
          }}
        />
      </div>
      <span
        className="num text-xs font-semibold shrink-0"
        style={{ color: barColor }}
      >
        {percent}% used
      </span>
    </div>
  );
}

/* ── Tier badge ── */
const TIER_LABELS = ["Fresh", "Trusted", "Veteran", "Elite"];
const TIER_COLORS = ["var(--text-muted)", "var(--accent)", "var(--warning)", "var(--success)"];
const TIER_THRESHOLDS = [0, 10, 50, 100];

function TierBadge({ tier }) {
  const idx = Number(tier);
  return (
    <span
      className="text-[10px] font-mono font-bold uppercase px-2 py-0.5 rounded-full"
      style={{
        color: TIER_COLORS[idx],
        background: `${TIER_COLORS[idx]}22`,
        border: `1px solid ${TIER_COLORS[idx]}44`,
      }}
    >
      T{idx} · {TIER_LABELS[idx]}
    </span>
  );
}

/* ── USDC badge ── */
function UsdcBadge({ size = "sm" }) {
  const sz = size === "lg" ? "w-7 h-7 text-base" : "w-5 h-5 text-xs";
  return (
    <span
      className={`${sz} rounded-full inline-flex items-center justify-center font-bold`}
      style={{ background: "#2775CA", color: "#fff" }}
    >
      $
    </span>
  );
}

/* ── Live rate ticker ── */
function RateTicker({ algoUsdcRate }) {
  const [blink, setBlink] = useState(false);
  useEffect(() => {
    setBlink(true);
    const t = setTimeout(() => setBlink(false), 400);
    return () => clearTimeout(t);
  }, [algoUsdcRate]);

  return (
    <div
      className="flex items-center gap-1.5 px-2 py-1 rounded-full text-[11px] font-mono transition-all duration-300"
      style={{
        background: blink ? "rgba(38,161,123,0.15)" : "var(--bg-elevated)",
        border: "1px solid var(--bg-border)",
        color: "var(--text-secondary)",
      }}
    >
      <span style={{ color: "#26A17B" }}>●</span>
      <span>1 ALGO</span>
      <span style={{ color: "var(--text-muted)" }}>≈</span>
      <span style={{ color: "#26A17B" }}>{algoUsdcRate.toFixed(4)} USDC</span>
    </div>
  );
}

/* ── Auto-swap step indicator ── */
function SwapStepBadge({ step }) {
  const labels = {
    drawing_algo_credit: "Borrowing ALGO credit…",
    quoting:   "Getting live quote…",
    opting_in: "Opting into USDC ASA…",
    swapping:  "Swapping ALGO → USDC via Tinyman…",
    seeding:   "Seeding treasury + drawing USDC…",
    drawing:   "Drawing USDC…",
  };
  if (!step || step === "idle") return null;
  return (
    <div
      className="mt-3 rounded-[8px] px-3 py-2 text-[11px] font-sans flex items-center gap-2 animate-pulse"
      style={{ background: "rgba(39,117,202,0.08)", border: "1px solid rgba(39,117,202,0.2)", color: "#2775CA" }}
    >
      <span>⟳</span>
      <span>{labels[step] ?? step}</span>
    </div>
  );
}

/* ── Position Overview Card ── */
function PositionCard({ position, isLoading, currency, algoUsdcRate }) {
  const isAlgo = currency === "ALGO";

  const stake        = isAlgo ? fmtAlgo(position.stake) : fmtAlgo(position.usdcStake);
  const tierMaxDraw  = isAlgo ? fmtAlgo(position.tierMaxDraw) : fromMicroUsdc(Number(position.usdcTierMaxDraw)).toFixed(4);
  const outstanding  = isAlgo ? fmtAlgo(position.outstanding) : fromMicroUsdc(Number(position.usdcOutstanding)).toFixed(4);
  const dailyDrawn   = isAlgo ? fmtAlgo(position.dailyDrawn) : fromMicroUsdc(Number(position.usdcDailyDrawn)).toFixed(4);

  const drawMax = isAlgo ? position.tierMaxDraw : position.usdcTierMaxDraw;
  const drawn = isAlgo ? position.dailyDrawn : position.usdcDailyDrawn;
  const perDraw = isAlgo ? (position.perDrawCap ?? position.tierMaxDraw) : (position.usdcPerDrawCap ?? position.usdcTierMaxDraw);

  // Safe subtraction using Number to prevent BigInt underflow
  const dailyRemainNum = Math.max(0, Number(drawMax) - Number(drawn));
  const dailyRemain = isAlgo
    ? (dailyRemainNum / 1e6).toFixed(6)
    : fromMicroUsdc(dailyRemainNum).toFixed(4);

  const aprPct       = isAlgo ? Number(position.aprBps) / 100 : Number(position.usdcAprBps) / 100;
  const aprBps       = isAlgo ? Number(position.aprBps) : Number(position.usdcAprBps);

  const utilization =
    Number(drawMax) > 0
      ? Math.min(100, Math.round((Number(drawn) / Number(drawMax)) * 100))
      : 0;

  const unit = isAlgo ? "ALGO" : "USDC";
  const paymentCount = isAlgo ? position.paymentCount : position.usdcPaymentCount;
  const tier = isAlgo ? position.tier : position.usdcTier;

  if (isLoading) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => <SkeletonStatCard key={i} />)}
      </div>
    );
  }

  return (
    <div
      className="glass-panel p-6 transition-all duration-300"
      style={{
        borderColor: position.isDefaulted ? "var(--danger)" : !isAlgo ? "rgba(39,117,202,0.2)" : undefined,
        boxShadow: position.isDefaulted
          ? "0 0 0 1px var(--danger), 0 4px 24px rgba(0,0,0,0.4), 0 0 20px rgba(239,68,68,0.1)"
          : !isAlgo ? "0 0 0 1px rgba(39,117,202,0.15), 0 4px 24px rgba(0,0,0,0.3)"
          : undefined,
      }}
    >
      {/* Header row */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          {!isAlgo && <UsdcBadge />}
          <span
            className="text-[11px] font-sans font-medium uppercase tracking-[0.1em]"
            style={{ color: "var(--text-secondary)" }}
          >
            {unit} Position
          </span>
          <TierBadge tier={tier} />
        </div>
        <div className="flex items-center gap-2">
          <span
            className="w-2 h-2 rounded-full"
            style={{
              background: position.isDefaulted ? "var(--danger)" : "var(--success)",
            }}
          />
          <span
            className="text-xs font-sans font-semibold uppercase"
            style={{
              color: position.isDefaulted ? "var(--danger)" : "var(--success)",
            }}
          >
            {position.isDefaulted ? "DEFAULTED" : "ACTIVE"}
          </span>
        </div>
      </div>

      {/* Main metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 mb-6">
        <div>
          <p className="text-[11px] font-sans font-medium uppercase tracking-[0.1em] mb-1" style={{ color: "var(--text-secondary)" }}>
            Draw Cap (per draw)
          </p>
          <p className="num text-[28px] font-semibold text-[var(--text-primary)] leading-tight">
            {tierMaxDraw}
          </p>
          <p className="text-[11px] font-mono uppercase" style={{ color: "var(--text-muted)" }}>{unit}</p>
        </div>
        <div>
          <p className="text-[11px] font-sans font-medium uppercase tracking-[0.1em] mb-1" style={{ color: "var(--text-secondary)" }}>
            Outstanding
          </p>
          <p className="num text-[28px] font-semibold text-[var(--text-primary)] leading-tight">
            {outstanding}
          </p>
          <p className="text-[11px] font-mono uppercase" style={{ color: "var(--text-muted)" }}>{unit}</p>
        </div>
        <div>
          <p className="text-[11px] font-sans font-medium uppercase tracking-[0.1em] mb-1" style={{ color: "var(--text-secondary)" }}>
            Daily Remaining
          </p>
          <p className="num text-[28px] font-semibold leading-tight" style={{ color: "var(--success)" }}>
            {dailyRemain}
          </p>
          <p className="text-[11px] font-mono uppercase" style={{ color: "var(--text-muted)" }}>{unit}</p>
        </div>
      </div>

      {/* Daily utilisation bar */}
      <div className="mb-2">
        <div className="flex items-center justify-between mb-1">
          <span className="text-[10px] font-sans uppercase" style={{ color: "var(--text-muted)" }}>Daily drawn</span>
          <span className="num text-[10px]" style={{ color: "var(--text-secondary)" }}>{dailyDrawn} / {tierMaxDraw} {unit}</span>
        </div>
        <UtilisationBar percent={utilization} />
      </div>

      {/* Secondary metrics */}
      <div className="grid grid-cols-2 gap-4 mt-6 pt-6" style={{ borderTop: "1px solid var(--bg-border)" }}>
        <div>
          <p className="text-[11px] font-sans font-medium uppercase tracking-[0.1em] mb-1" style={{ color: "var(--text-secondary)" }}>
            Stake Locked
          </p>
          <p className="num text-lg font-semibold text-[var(--text-primary)]">
            {stake} <span className="text-xs" style={{ color: "var(--text-muted)" }}>ALGO</span>
          </p>
        </div>
        <div>
          <p className="text-[11px] font-sans font-medium uppercase tracking-[0.1em] mb-1" style={{ color: "var(--text-secondary)" }}>
            APR
          </p>
          <p className="num text-lg font-semibold text-[var(--text-primary)]">
            {aprPct.toFixed(0)}% <span className="text-xs" style={{ color: "var(--text-muted)" }}>({aprBps} bps)</span>
          </p>
        </div>
        <div>
          <p className="text-[11px] font-sans font-medium uppercase tracking-[0.1em] mb-1" style={{ color: "var(--text-secondary)" }}>
            Payments Made
          </p>
          <p className="num text-lg font-semibold text-[var(--text-primary)]">
            {paymentCount.toString()} <span className="text-xs" style={{ color: "var(--text-muted)" }}>payments</span>
          </p>
        </div>
        <div>
          <p className="text-[11px] font-sans font-medium uppercase tracking-[0.1em] mb-1" style={{ color: "var(--text-secondary)" }}>
            {isAlgo ? "Repay By Round" : "Treasury Balance"}
          </p>
          {isAlgo ? (
            <p className="num text-lg font-semibold" style={{ color: position.repayByRound > 0n ? "var(--warning)" : "var(--text-muted)" }}>
              {position.repayByRound > 0n ? `#${position.repayByRound.toString()}` : "—"}
            </p>
          ) : (
            <p className="num text-lg font-semibold" style={{ color: Number(position.usdcTreasuryBalance) > 0 ? "var(--success)" : "var(--warning)" }}>
              ${fromMicroUsdc(Number(position.usdcTreasuryBalance)).toFixed(2)} <span className="text-xs" style={{ color: "var(--text-muted)" }}>USDC</span>
              {Number(position.usdcTreasuryBalance) === 0 && (
                <span className="ml-1 text-[10px]" style={{ color: "var(--warning)" }}>⚡ Auto-swap active</span>
              )}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

/* ── Panel wrapper ── */
function PanelHeader({ title, badge }) {
  return (
    <div className="flex items-center gap-2 mb-4">
      {badge}
      <p
        className="text-[11px] font-sans font-medium uppercase tracking-[0.1em]"
        style={{ color: "var(--text-secondary)" }}
      >
        {title}
      </p>
    </div>
  );
}

export default function CreditPositionDashboard() {
  const { address } = useWallet();
  const {
    position,
    loading,
    currency,
    setCurrency,
    algoUsdcRate,
    walletBalance,
    callRecordPayment,
    callDraw,
    callRepay,
    callSlash,
    callRegisterUsdc,
    callBorrowAndStakeUsdc,
    callDrawUsdc,
    callAutoDrawUsdc,
    callRepayUsdc,
  } = useContract();
  const { addToast } = useToast();

  const [usdcStakeInput, setUsdcStakeInput] = useState("1");
  const [recordInput, setRecordInput] = useState("");
  const [drawInput, setDrawInput] = useState("");
  const [repayInput, setRepayInput] = useState("");
  const [slashInput, setSlashInput] = useState("");
  const [activeAction, setActiveAction] = useState(null);
  const [swapStep, setSwapStep] = useState(null);

  const isAlgo = currency === "ALGO";

  // ── Safe available credit calculation ──
  // Uses Number arithmetic to avoid BigInt underflow when dailyDrawn > dailyCap
  const dailyCapNum = isAlgo
    ? Number(position.tierMaxDraw)
    : Number(position.usdcTierMaxDraw);
  const dailyDrawnNum = isAlgo
    ? Number(position.dailyDrawn)
    : Number(position.usdcDailyDrawn);
  const perDrawCapNum = isAlgo
    ? Number(position.perDrawCap ?? position.tierMaxDraw)
    : Number(position.usdcPerDrawCap ?? position.usdcTierMaxDraw);

  // Available = min(per-draw cap, daily remaining), never negative
  // For USDC, drawing is blocked if there is any outstanding USDC debt.
  const dailyRemaining = Math.max(0, dailyCapNum - dailyDrawnNum);
  const effectiveMaxDraw = (!isAlgo && position.usdcOutstanding > 0n)
    ? 0
    : Math.min(perDrawCapNum, dailyRemaining);

  // Convert to display units
  const available = isAlgo
    ? effectiveMaxDraw / 1e6
    : fromMicroUsdc(effectiveMaxDraw);

  const outstandingNum = isAlgo
    ? Number(position.outstanding) / 1e6
    : fromMicroUsdc(Number(position.usdcOutstanding));

  const treasuryBal = Number(position.usdcTreasuryBalance);
  const treasuryLow = !isAlgo && treasuryBal < toMicroUsdc(parseFloat(drawInput) || 0);

  // Wallet balance in display units
  const walletAlgo = (walletBalance?.algo ?? 0) / 1e6;
  const walletUsdc = fromMicroUsdc(walletBalance?.usdc ?? 0);

  // --- Action Handlers ---
  const handleRecord = async () => {
    const amt = parseFloat(recordInput);
    if (!amt || amt <= 0) return;
    setActiveAction("record");
    try {
      const newLimit = await callRecordPayment(recordInput);
      addToast(`↑ Credit limit increased to ${fmtAlgo(newLimit)} ALGO`, "success");
      setRecordInput("");
    } catch (err) {
      addToast(err.message || "Record failed", "error");
    }
    setActiveAction(null);
  };

  const handleDraw = async () => {
    const amt = parseFloat(drawInput);
    if (!amt || amt <= 0) return;
    // Validate: amount must not exceed available
    if (amt > available + 0.000001) {
      addToast(`Maximum drawable: ${available.toFixed(isAlgo ? 6 : 4)} ${isAlgo ? "ALGO" : "USDC"}`, "error");
      return;
    }
    setActiveAction("draw");
    setSwapStep(null);
    try {
      if (isAlgo) {
        await callDraw(drawInput);
        addToast(`→ ${amt.toFixed(6)} ALGO sent to wallet`, "success");
      } else {
        const microUsdc = toMicroUsdc(amt);
        await callAutoDrawUsdc(microUsdc, (step, data) => {
          setSwapStep(step);
          if (step === "drawing_algo_credit" && data) {
            addToast(
              `💳 Borrowing ${(data.microAlgoNeeded/1e6).toFixed(4)} ALGO credit for swap`,
              "info",
              3000
            );
          }
          if (step === "swapping" && data) {
            addToast(
              `⚡ Treasury low — swapping ${(data.microAlgoNeeded/1e6).toFixed(4)} ALGO via Tinyman`,
              "info",
              4000
            );
          }
          if (step === "seeding") {
            addToast("🌱 Seeding treasury and drawing USDC…", "info", 3000);
          }
        });
        addToast(`→ ${amt.toFixed(4)} USDC drawn to wallet`, "success");
      }
      setDrawInput("");
    } catch (err) {
      addToast(err.message || "Draw failed", "error");
    }
    setSwapStep(null);
    setActiveAction(null);
  };

  const handleRepay = async () => {
    const amt = parseFloat(repayInput);
    if (!amt || amt <= 0) return;
    // Cap at outstanding to prevent overpayment
    const cappedAmt = Math.min(amt, outstandingNum);
    if (cappedAmt <= 0) {
      addToast("No outstanding debt to repay", "error");
      return;
    }
    // Validate wallet has enough
    if (isAlgo && cappedAmt > walletAlgo - 0.2) {
      addToast(`Insufficient ALGO balance (need ~0.2 ALGO for fees)`, "error");
      return;
    }
    if (!isAlgo && cappedAmt > walletUsdc) {
      addToast(`Insufficient USDC balance`, "error");
      return;
    }
    setActiveAction("repay");
    try {
      if (isAlgo) {
        await callRepay(String(cappedAmt));
        addToast(`← Repaid ${cappedAmt.toFixed(6)} ALGO`, "success");
      } else {
        const microUsdc = toMicroUsdc(cappedAmt);
        await callRepayUsdc(microUsdc);
        addToast(`← Repaid ${cappedAmt.toFixed(4)} USDC`, "success");
      }
      setRepayInput("");
    } catch (err) {
      addToast(err.message || "Repayment failed", "error");
    }
    setActiveAction(null);
  };

  const handleSlash = async () => {
    if (!slashInput || slashInput.length < 58) return;
    setActiveAction("slash");
    try {
      await callSlash(slashInput);
      addToast(`Agent ${fmtAddress(slashInput)} slashed. Stake burned.`, "error", 5000);
      setSlashInput("");
    } catch (err) {
      addToast(err.message || "Slash failed", "error");
    }
    setActiveAction(null);
  };

  const handleActivateUsdc = async () => {
    const stakeVal = parseFloat(usdcStakeInput);
    if (!stakeVal || stakeVal < 1) {
      addToast("Minimum stake is 1 ALGO", "error");
      return;
    }
    setActiveAction("activate_usdc");
    try {
      await callRegisterUsdc(usdcStakeInput);
      addToast("✓ USDC Credit Line Activated!", "success");
    } catch (err) {
      addToast(err.message || "Activation failed", "error");
    }
    setActiveAction(null);
  };

  const handleBorrowAndStakeUsdc = async () => {
    setActiveAction("borrow_and_stake_usdc");
    try {
      await callBorrowAndStakeUsdc();
      addToast("✓ USDC Credit Line Activated via ALGO loan!", "success");
    } catch (err) {
      addToast(err.message || "Activation failed", "error");
    }
    setActiveAction(null);
  };

  const recordAmt = parseFloat(recordInput) || 0;
  const TIER_LABEL_THRESHOLDS = [0, 10, 50, 100];
  const paymentsToNextTier = TIER_LABEL_THRESHOLDS[Math.min(Number(position.tier) + 1, 3)];
  const currentLimitAlgo = Number(position.tierMaxDraw) / 1e6;

  const repayAmt = parseFloat(repayInput) || 0;
  const cappedRepayAmt = Math.min(repayAmt, outstandingNum);
  const outAfterRepay = Math.max(0, outstandingNum - cappedRepayAmt);
  const isSelfSlash = slashInput === address;
  const drawAmt = parseFloat(drawInput) || 0;
  const drawExceedsLimit = drawAmt > available + 0.000001;
  const repayExceedsOutstanding = repayAmt > outstandingNum + 0.000001;

  // ── Currency toggle header ──
  const currencyHeader = (
    <div
      className="flex justify-between items-center p-4 rounded-[12px]"
      style={{
        background: "var(--bg-surface)",
        border: "1px solid var(--bg-border)",
      }}
    >
      <div className="flex items-center gap-3">
        <UsdcBadge size="lg" />
        <div>
          <p className="font-semibold text-sm" style={{ color: "var(--text-primary)" }}>
            Trestle Credit Protocol
          </p>
          <p className="text-[11px]" style={{ color: "var(--text-muted)" }}>
            {isAlgo ? "ALGO (native)" : "USDC — Primary Currency"}
          </p>
        </div>
      </div>
      <div className="flex items-center gap-3">
        <RateTicker algoUsdcRate={algoUsdcRate} />
        {/* Currency toggle */}
        <div
          className="flex rounded-[8px] p-0.5 gap-0.5"
          style={{ background: "var(--bg-elevated)", border: "1px solid var(--bg-border)" }}
        >
          {["USDC", "ALGO"].map(c => (
            <button
              key={c}
              onClick={() => setCurrency(c)}
              className="px-3 py-1.5 rounded-[6px] text-xs font-semibold transition-all duration-200"
              style={{
                background: currency === c ? (c === "USDC" ? "#2775CA" : "var(--accent)") : "transparent",
                color: currency === c ? "#fff" : "var(--text-secondary)",
              }}
            >
              {c}
            </button>
          ))}
        </div>
      </div>
    </div>
  );

  // ── USDC activation screen ──
  if (!isAlgo && position.usdcStake === 0n) {
    return (
      <div className="flex flex-col gap-6">
        {currencyHeader}
        <PositionCard position={position} isLoading={loading && position.stake === 0n} currency={currency} algoUsdcRate={algoUsdcRate} />

        <div className="glass-panel p-8 flex flex-col items-center text-center max-w-[520px] mx-auto w-full">
          <div
            className="w-16 h-16 rounded-full flex items-center justify-center text-2xl mb-4"
            style={{ background: "rgba(39,117,202,0.1)", border: "2px solid rgba(39,117,202,0.2)" }}
          >
            💳
          </div>
          <h2 className="text-xl font-bold mb-2" style={{ color: "var(--text-primary)" }}>
            Activate USDC Credit Line
          </h2>
          <p className="text-sm mb-6" style={{ color: "var(--text-secondary)" }}>
            Stake ALGO to open your USDC credit line. Your stake acts as collateral for
            undercollateralised stablecoin loans. When the treasury is empty, Trestle
            auto-swaps ALGO via Tinyman to ensure you always get USDC.
          </p>

          <div className="w-full space-y-4">
            <div>
              <label className="text-[11px] font-medium uppercase tracking-[0.1em] mb-1.5 block" style={{ color: "var(--text-secondary)" }}>
                Stake Amount
              </label>
              <Input
                type="number"
                suffix="ALGO"
                value={usdcStakeInput}
                onChange={(e) => setUsdcStakeInput(e.target.value)}
                placeholder="1.000000"
              />
            </div>

            <div
              className="rounded-[8px] p-4 space-y-2 text-sm"
              style={{ background: "var(--bg-elevated)", border: "1px solid var(--bg-border)" }}
            >
              <div className="flex justify-between">
                <span style={{ color: "var(--text-secondary)" }}>Initial USDC draw cap</span>
                <span style={{ color: "#26A17B" }}>$0.10 USDC (Tier 0)</span>
              </div>
              <div className="flex justify-between">
                <span style={{ color: "var(--text-secondary)" }}>APR</span>
                <span style={{ color: "var(--text-primary)" }}>24% (improves with payments)</span>
              </div>
              <div className="flex justify-between">
                <span style={{ color: "var(--text-secondary)" }}>Auto-swap</span>
                <span style={{ color: "#2775CA" }}>⚡ Tinyman ALGO→USDC</span>
              </div>
              <div className="flex justify-between">
                <span style={{ color: "var(--text-secondary)" }}>x402 payments</span>
                <span style={{ color: "#2775CA" }}>✓ GoPlausible</span>
              </div>
            </div>

            <div className="flex flex-col sm:flex-row gap-3 w-full">
              <Button
                variant="primary"
                size="lg"
                className="flex-1"
                onClick={handleActivateUsdc}
                loading={activeAction === "activate_usdc"}
                disabled={parseFloat(usdcStakeInput) < 1}
                style={{ background: "#2775CA" }}
              >
                Stake ALGO
              </Button>
              <Button
                variant="outline"
                size="lg"
                className="flex-1"
                onClick={handleBorrowAndStakeUsdc}
                loading={activeAction === "borrow_and_stake_usdc"}
                disabled={!(position.stake > 0n && (position.tierMaxDraw - position.outstanding) >= 1000000n)}
              >
                Borrow & Stake 1 ALGO
              </Button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      {currencyHeader}
      <PositionCard position={position} isLoading={loading && position.stake === 0n} currency={currency} algoUsdcRate={algoUsdcRate} />

      {/* Action panels */}
      {isAlgo ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Panel A: Record Payment */}
          <div className="glass-panel p-6">
            <PanelHeader title="Record Payment" />
            <Input
              id="record-amount"
              type="number"
              suffix="ALGO"
              value={recordInput}
              onChange={(e) => setRecordInput(e.target.value)}
              placeholder="0.000000"
            />
            {recordAmt > 0 && (
              <div className="mt-3 rounded-[8px] px-3 py-2.5 text-xs space-y-1" style={{ background: "var(--accent-dim)", border: "1px solid rgba(99,102,241,0.15)" }}>
                <div className="flex justify-between">
                  <span className="font-sans" style={{ color: "var(--text-secondary)" }}>Payments recorded</span>
                  <span className="num" style={{ color: "var(--text-primary)" }}>{position.paymentCount.toString()}</span>
                </div>
                <div className="flex justify-between">
                  <span className="font-sans" style={{ color: "var(--text-secondary)" }}>Next tier at</span>
                  <span className="num" style={{ color: "var(--accent)" }}>{paymentsToNextTier} payments</span>
                </div>
                <div className="flex justify-between">
                  <span className="font-sans" style={{ color: "var(--text-secondary)" }}>Draw cap</span>
                  <span className="num" style={{ color: "var(--success)" }}>{currentLimitAlgo.toFixed(6)} ALGO / draw</span>
                </div>
              </div>
            )}
            <Button
              id="record-button"
              variant="primary"
              size="lg"
              className="w-full mt-4"
              onClick={handleRecord}
              loading={activeAction === "record"}
              disabled={!recordInput || parseFloat(recordInput) <= 0}
            >
              Record Payment
            </Button>
          </div>

          {/* Panel B: Draw ALGO */}
          <div className="glass-panel p-6">
            <PanelHeader title="Draw Credit" />
            <div className="flex items-center justify-between text-xs mb-1">
              <span className="font-sans" style={{ color: "var(--text-secondary)" }}>Available (max per draw)</span>
              <span className="num" style={{ color: "var(--success)" }}>{available.toFixed(6)} ALGO</span>
            </div>
            <div className="flex items-center justify-between text-[10px] mb-3">
              <span style={{ color: "var(--text-muted)" }}>Daily remaining: {(dailyRemaining / 1e6).toFixed(6)} · Per-draw cap: {(perDrawCapNum / 1e6).toFixed(6)}</span>
            </div>
            <Input
              id="draw-amount"
              type="number"
              suffix="ALGO"
              value={drawInput}
              onChange={(e) => setDrawInput(e.target.value)}
              placeholder="0.000000"
              error={drawExceedsLimit ? `Max: ${available.toFixed(6)} ALGO` : ""}
            />
            <div className="flex gap-2 mt-3">
              {[25, 50, "MAX"].map((pct) => {
                const val = pct === "MAX" ? available : available * (pct / 100);
                return (
                  <button
                    key={pct}
                    onClick={() => setDrawInput(Math.max(0, val).toFixed(6))}
                    className="flex-1 h-8 rounded-[6px] text-xs font-mono font-medium transition-all duration-150 hover:border-[var(--accent)] hover:text-[var(--accent)]"
                    style={{ background: "var(--bg-elevated)", border: "1px solid var(--bg-border)", color: "var(--text-secondary)" }}
                  >
                    {pct === "MAX" ? "MAX" : `${pct}%`}
                  </button>
                );
              })}
            </div>
            {/* Wallet balance indicator */}
            <div className="mt-2 text-[10px]" style={{ color: "var(--text-muted)" }}>
              Wallet: {walletAlgo.toFixed(4)} ALGO
            </div>
            <Button
              id="draw-button"
              variant="primary"
              size="lg"
              className="w-full mt-4"
              onClick={handleDraw}
              loading={activeAction === "draw"}
              disabled={!drawInput || parseFloat(drawInput) <= 0 || drawExceedsLimit || available <= 0}
            >
              {available <= 0 ? "No Credit Available" : "Draw ALGO"}
            </Button>
          </div>

          {/* Panel C: Repay ALGO */}
          <div className="glass-panel p-6">
            <PanelHeader title="Repay Outstanding" />
            <div className="flex items-center justify-between text-xs mb-3">
              <span className="font-sans" style={{ color: "var(--text-secondary)" }}>Outstanding</span>
              <span className="num" style={{ color: "var(--text-primary)" }}>{outstandingNum.toFixed(6)} ALGO</span>
            </div>
            <Input
              id="repay-amount"
              type="number"
              suffix="ALGO"
              value={repayInput}
              onChange={(e) => setRepayInput(e.target.value)}
              placeholder="0.000000"
            />
            <button
              onClick={() => setRepayInput(outstandingNum.toFixed(6))}
              className="mt-2 text-[11px] font-mono px-2 py-1 rounded-[4px] transition-colors duration-150 hover:text-[var(--accent)]"
              style={{ color: "var(--text-muted)", background: "var(--bg-elevated)" }}
            >
              MAX ({outstandingNum.toFixed(6)})
            </button>
            {repayAmt > 0 && (
              <div className="mt-3 space-y-2">
                {repayExceedsOutstanding && (
                  <div className="flex items-center gap-1 text-[11px]" style={{ color: "var(--warning)" }}>
                    <span>⚠</span>
                    <span>Capped at outstanding: {outstandingNum.toFixed(6)} ALGO</span>
                  </div>
                )}
                <div className="flex items-center justify-between text-xs">
                  <span className="font-sans" style={{ color: "var(--text-secondary)" }}>After repay</span>
                  <span className="num" style={{ color: "var(--success)" }}>{outAfterRepay.toFixed(6)} ALGO</span>
                </div>
              </div>
            )}
            {/* Wallet balance */}
            <div className="mt-2 text-[10px]" style={{ color: "var(--text-muted)" }}>
              Wallet: {walletAlgo.toFixed(4)} ALGO
            </div>
            <Button
              id="repay-button"
              variant="primary"
              size="lg"
              className="w-full mt-4"
              onClick={handleRepay}
              loading={activeAction === "repay"}
              disabled={!repayInput || parseFloat(repayInput) <= 0 || outstandingNum <= 0}
            >
              {outstandingNum <= 0 ? "No Outstanding Debt" : "Repay ALGO"}
            </Button>
          </div>

          {/* Panel D: Slash */}
          <div className="glass-panel p-6" style={{ borderColor: "var(--danger)" }}>
            <div className="flex items-center justify-between mb-4">
              <span className="text-[11px] font-sans font-medium uppercase tracking-[0.1em]" style={{ color: "var(--danger)" }}>
                ⚠ Slash Agent
              </span>
            </div>
            <Input
              id="slash-address"
              type="text"
              value={slashInput}
              onChange={(e) => setSlashInput(e.target.value)}
              placeholder="ALGORAND ADDRESS..."
              inputClassName="text-sm"
              error={isSelfSlash ? "Cannot slash yourself" : ""}
            />
            <Button
              id="slash-button"
              variant="danger"
              size="lg"
              className="w-full mt-4"
              onClick={handleSlash}
              loading={activeAction === "slash"}
              disabled={!slashInput || slashInput.length < 58 || isSelfSlash}
            >
              Slash Agent
            </Button>
          </div>
        </div>
      ) : (
        /* USDC MODE */
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Panel A: Draw USDC (primary action) */}
          <div
            className="glass-panel p-6"
            style={{
              border: "1px solid rgba(39,117,202,0.25)",
              background: "linear-gradient(135deg, rgba(39,117,202,0.03) 0%, transparent 100%)",
            }}
          >
            <PanelHeader
              title="Draw USDC Credit"
              badge={<UsdcBadge />}
            />

            {/* Treasury status banner */}
            {treasuryLow && parseFloat(drawInput) > 0 && (
              <div
                className="rounded-[8px] px-3 py-2 mb-3 text-[11px] flex items-center gap-2"
                style={{ background: "rgba(234,179,8,0.08)", border: "1px solid rgba(234,179,8,0.25)", color: "var(--warning)" }}
              >
                <span>⚡</span>
                <span>Treasury low — will auto-swap ALGO→USDC via Tinyman ({algoUsdcRate.toFixed(4)} USDC/ALGO)</span>
              </div>
            )}

            <div className="flex items-center justify-between text-xs mb-1">
              <span className="font-sans" style={{ color: "var(--text-secondary)" }}>Available (max per draw)</span>
              <span className="num" style={{ color: "var(--success)" }}>${available.toFixed(4)} USDC</span>
            </div>
            <div className="flex items-center justify-between text-[10px] mb-3">
              <span style={{ color: "var(--text-muted)" }}>Daily remaining: ${(fromMicroUsdc(dailyRemaining)).toFixed(4)} · Per-draw cap: ${(fromMicroUsdc(perDrawCapNum)).toFixed(4)}</span>
            </div>

            <Input
              id="draw-amount"
              type="number"
              suffix="USDC"
              value={drawInput}
              onChange={(e) => setDrawInput(e.target.value)}
              placeholder="0.0000"
              error={drawExceedsLimit ? `Max: ${available.toFixed(4)} USDC` : ""}
            />

            <div className="flex gap-2 mt-3">
              {[25, 50, "MAX"].map((pct) => {
                const val = pct === "MAX" ? available : available * (pct / 100);
                return (
                  <button
                    key={pct}
                    onClick={() => setDrawInput(Math.max(0, val).toFixed(4))}
                    className="flex-1 h-8 rounded-[6px] text-xs font-mono font-medium transition-all duration-150"
                    style={{ background: "var(--bg-elevated)", border: "1px solid var(--bg-border)", color: "var(--text-secondary)" }}
                  >
                    {pct === "MAX" ? "MAX" : `${pct}%`}
                  </button>
                );
              })}
            </div>

            <SwapStepBadge step={swapStep} />

            {/* ALGO cost estimate when auto-swap needed */}
            {treasuryLow && parseFloat(drawInput) > 0 && !swapStep && (
              <div className="mt-2 text-[11px]" style={{ color: "var(--text-muted)" }}>
                ~{((toMicroUsdc(parseFloat(drawInput)) / algoUsdcRate) / 1e6).toFixed(4)} ALGO needed for swap
              </div>
            )}

            {/* Wallet balance */}
            <div className="mt-2 text-[10px]" style={{ color: "var(--text-muted)" }}>
              Wallet: {walletUsdc.toFixed(4)} USDC · {walletAlgo.toFixed(4)} ALGO
            </div>

            <Button
              id="draw-button"
              variant="primary"
              size="lg"
              className="w-full mt-4"
              onClick={handleDraw}
              loading={activeAction === "draw"}
              disabled={!drawInput || parseFloat(drawInput) <= 0 || drawExceedsLimit || available <= 0}
              style={{ background: "#2775CA" }}
            >
              {available <= 0
                ? "No Credit Available"
                : treasuryLow && parseFloat(drawInput) > 0
                  ? "⚡ Auto-Swap & Draw USDC"
                  : "Draw USDC"}
            </Button>
          </div>

          {/* Panel B: Repay USDC */}
          <div className="glass-panel p-6">
            <PanelHeader title="Repay USDC Outstanding" badge={<UsdcBadge />} />
            <div className="flex items-center justify-between text-xs mb-3">
              <span className="font-sans" style={{ color: "var(--text-secondary)" }}>Outstanding</span>
              <span className="num" style={{ color: "var(--text-primary)" }}>${outstandingNum.toFixed(4)} USDC</span>
            </div>
            <Input
              id="repay-amount"
              type="number"
              suffix="USDC"
              value={repayInput}
              onChange={(e) => setRepayInput(e.target.value)}
              placeholder="0.0000"
            />
            <button
              onClick={() => setRepayInput(outstandingNum.toFixed(4))}
              className="mt-2 text-[11px] font-mono px-2 py-1 rounded-[4px] transition-colors duration-150 hover:text-[var(--accent)]"
              style={{ color: "var(--text-muted)", background: "var(--bg-elevated)" }}
            >
              MAX ({outstandingNum.toFixed(4)})
            </button>
            {repayAmt > 0 && (
              <div className="mt-3">
                {repayExceedsOutstanding && (
                  <div className="flex items-center gap-1 text-[11px] mb-2" style={{ color: "var(--warning)" }}>
                    <span>⚠</span>
                    <span>Capped at outstanding: ${outstandingNum.toFixed(4)} USDC</span>
                  </div>
                )}
                <div className="flex items-center justify-between text-xs">
                  <span style={{ color: "var(--text-secondary)" }}>After repay</span>
                  <span className="num" style={{ color: "var(--success)" }}>${outAfterRepay.toFixed(4)} USDC</span>
                </div>
              </div>
            )}
            {/* Wallet balance */}
            <div className="mt-2 text-[10px]" style={{ color: "var(--text-muted)" }}>
              Wallet: {walletUsdc.toFixed(4)} USDC
            </div>
            <Button
              id="repay-button"
              variant="primary"
              size="lg"
              className="w-full mt-4"
              onClick={handleRepay}
              loading={activeAction === "repay"}
              disabled={!repayInput || parseFloat(repayInput) <= 0 || outstandingNum <= 0}
            >
              {outstandingNum <= 0 ? "No Outstanding Debt" : "Repay USDC"}
            </Button>
          </div>

          {/* Panel C: x402 Payment (full-width) */}
          <div className="md:col-span-2">
            <PaymentGatewayPanel />
          </div>
        </div>
      )}
    </div>
  );
}
