/**
 * format.js — Display formatting utilities for Trestle.
 *
 * All ALGO values are stored as microALGO (BigInt or Number).
 * These helpers convert to human-readable display strings.
 */

/**
 * Format microALGO to display string: "1.000000"
 * @param {BigInt|number} micro — value in microALGO
 * @returns {string}
 */
export const fmtAlgo = (micro) => {
  const n = Number(micro) / 1e6;
  return n.toFixed(6);
};

/**
 * Format microALGO with ALGO suffix: "1.000000 ALGO"
 * @param {BigInt|number} micro
 * @returns {string}
 */
export const fmtAlgoFull = (micro) => {
  return fmtAlgo(micro) + " ALGO";
};

/**
 * Format credit score: clamped 0–100, 1 decimal
 * @param {number} n
 * @returns {string}
 */
export const fmtScore = (n) => Math.min(100, Math.max(0, n)).toFixed(1);

/**
 * Truncate an Algorand address: "ABCD...WXYZ"
 * @param {string} addr
 * @param {number} start — chars from start (default 4)
 * @param {number} end — chars from end (default 4)
 * @returns {string}
 */
export const fmtAddress = (addr, start = 4, end = 4) => {
  if (!addr || addr.length < start + end + 3) return addr || "";
  return `${addr.slice(0, start)}...${addr.slice(-end)}`;
};

/**
 * Format round number with # prefix
 * @param {number|BigInt} round
 * @returns {string}
 */
export const fmtRound = (round) => {
  return `#${Number(round).toLocaleString("en-US")}`;
};

/**
 * Format large micro numbers with thin space separators
 * @param {BigInt|number} micro
 * @returns {string}
 */
export const fmtMicro = (micro) => {
  const s = String(Number(micro));
  // Add thin spaces as thousands separator
  return s.replace(/\B(?=(\d{3})+(?!\d))/g, "\u2009");
};

/**
 * Calculate credit score from V2 position data.
 *
 * Score factors:
 *   1. Payment history → 0-70 pts (10 pmts=Trusted, 50=Veteran, 100=Elite)
 *   2. APR tier        → 0-30 pts (lower APR = higher tier = better score)
 *
 * @param {Object} position — from ContractContext
 * @returns {number} score in [0, 100]
 */
export const calcScore = (position) => {
  if (!position || position.stake === 0n) return 0;

  const payments = Number(position.paymentCount);
  const aprBps   = Number(position.aprBps);

  // Payment score: logarithmic ramp capped at 70
  let paymentScore = 0;
  if (payments >= 100)     paymentScore = 70;
  else if (payments >= 50) paymentScore = 55 + (payments - 50) * (15 / 50);
  else if (payments >= 10) paymentScore = 30 + (payments - 10) * (25 / 40);
  else                     paymentScore = payments * 3;

  // APR score: 30 pts at Elite (400 bps), 0 pts at Fresh (2400 bps)
  const aprScore = Math.max(0, Math.round(((2400 - aprBps) / 2000) * 30));

  return Math.min(100, Math.round(paymentScore + aprScore));
};
