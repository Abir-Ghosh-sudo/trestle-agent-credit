/**
 * contract.js — Single source of truth for Trestle contract config.
 *
 * APP_ID / APP_ADDRESS / USDC_APP_ID / USDC_APP_ADDRESS are read from
 * environment variables (set in frontend/.env) so this file never needs
 * hand-editing after you deploy your own contracts. See frontend/.env.example.
 *
 * ABI_METHODS mirror contract.py / trestle_usdc.py method signatures exactly.
 */

function requireEnvNumber(key, fallback) {
  const raw = import.meta.env[key];
  if (raw === undefined || raw === "") return fallback;
  const n = Number(raw);
  return Number.isFinite(n) ? n : fallback;
}

function requireEnvString(key, fallback) {
  const raw = import.meta.env[key];
  return raw && raw.length > 0 ? raw : fallback;
}

// Placeholder values — deploy your own contracts (see contracts/deploy.py,
// contracts/deploy_usdc.py) and set the real values in frontend/.env.
// The app still runs with placeholders, but on-chain calls will fail with a
// clear "app does not exist" error until you configure a real deployment.
export const APP_ID = requireEnvNumber("VITE_APP_ID", 768682767);

export const APP_ADDRESS = requireEnvString(
  "VITE_APP_ADDRESS",
  "XURVGE52BJOICKTSCLANKKKCHYAPGCBB7XC67OF54QPC6YJMEBDVJGIYMM"
);

export const USDC_APP_ID = requireEnvNumber("VITE_USDC_APP_ID", 0);

export const USDC_APP_ADDRESS = requireEnvString(
  "VITE_USDC_APP_ADDRESS",
  "<YOUR_USDC_APP_ADDRESS>"
);

export const USDC_CONFIGURED = USDC_APP_ID > 0;

if (import.meta.env.DEV && (APP_ID === 0 || USDC_APP_ID === 0)) {
  console.warn(
    "[Trestle] APP_ID / USDC_APP_ID are not fully configured. " +
    "Deploy your contracts or ensure VITE_APP_ID and VITE_USDC_APP_ID are set in frontend/.env."
  );
}

export const TESTNET_ALGOD    = "https://testnet-api.algonode.cloud";
export const TESTNET_INDEXER  = "https://testnet-idx.algonode.cloud";

// Default currency — USDC is the platform's primary currency
export const DEFAULT_CURRENCY = "USDC";

export const MIN_STAKE_MICROALGO = 1_000_000; // 1 ALGO

// ABI method signatures — must match contract.py exactly
export const ABI_METHODS = {
  register: {
    name: "register",
    args: [{ type: "pay", name: "pay" }],
    returns: { type: "void" },
  },
  record_payment: {
    name: "record_payment",
    args: [{ type: "uint64", name: "amount" }],
    returns: { type: "uint64" },
  },
  draw: {
    name: "draw",
    args: [
      { type: "uint64", name: "amount" },
      { type: "byte[32]", name: "attestation_hash" },
    ],
    returns: { type: "void" },
  },
  repay: {
    name: "repay",
    args: [{ type: "pay", name: "pay" }],
    returns: { type: "void" },
  },
  slash: {
    name: "slash",
    args: [{ type: "address", name: "agent" }],
    returns: { type: "void" },
  },
  get_position: {
    name: "get_position",
    args: [{ type: "address", name: "agent" }],
    returns: {
      type: "(uint64,uint64,uint64,uint64,uint64,uint64,uint64,uint64,uint64)",
    },
  },

  // ─── USDC contract methods ────────────────────────────────────────────────
  draw_usdc: {
    name: "draw_usdc",
    args: [
      { type: "uint64", name: "amount" },
      { type: "byte[32]", name: "attestation_hash" },
    ],
    returns: { type: "void" },
  },
  draw_and_pay: {
    name: "draw_and_pay",
    args: [
      { type: "uint64", name: "amount" },
      { type: "address", name: "payee" },
      { type: "byte[32]", name: "attestation_hash" },
    ],
    returns: { type: "void" },
  },
  repay_usdc: {
    name: "repay_usdc",
    args: [{ type: "axfer", name: "axfer" }],
    returns: { type: "void" },
  },
  get_usdc_position: {
    name: "get_usdc_position",
    args: [{ type: "address", name: "agent" }],
    returns: { type: "(uint64,uint64,uint64,uint64)" },
  },
  configure_usdc: {
    name: "configure_usdc",
    args: [{ type: "asset", name: "usdc_asset" }],
    returns: { type: "void" },
  },
  // seed_usdc_treasury — now open to ALL callers (not creator-only).
  // This enables the atomic Tinyman-swap + seed + draw flow.
  seed_usdc_treasury: {
    name: "seed_treasury",
    args: [{ type: "axfer", name: "axfer" }],
    returns: { type: "void" },
  },
};

// USDC ASA IDs
export const USDC_ASA_ID_TESTNET = 10_458_941;
export const USDC_ASA_ID_MAINNET = 31_566_704;
export const USDC_ASA_ID = USDC_ASA_ID_TESTNET;  // switch for mainnet

// ──────────────────────────────────────────────────────────────────────────────
// Tier constants — must match contract.py / trestle_usdc.py exactly
// ──────────────────────────────────────────────────────────────────────────────

export const TIER_THRESHOLDS = [0, 10, 50, 100]; // payment_count thresholds

// Per-draw hard caps (microALGO / micro-USDC)
export const TIER_PER_DRAW_CAPS = [
  100_000n,    // T0: $0.10
  500_000n,    // T1: $0.50
  2_000_000n,  // T2: $2.00
  5_000_000n,  // T3: $5.00
];

// Daily aggregate caps (microALGO / micro-USDC)
export const TIER_DAILY_CAPS = [
  500_000n,     // T0: $0.50
  2_000_000n,   // T1: $2.00
  10_000_000n,  // T2: $10.00
  25_000_000n,  // T3: $25.00
];

// APR in basis points (lower tier → higher APR)
export const TIER_APR_BPS = [2400n, 1600n, 900n, 400n];

/**
 * Derive tier data from payment_count — mirrors on-chain _get_tier exactly.
 * @param {BigInt|number} paymentCount
 * @returns {{ tier: bigint, perDrawCap: bigint, dailyCap: bigint, aprBps: bigint }}
 */
export function getTierData(paymentCount) {
  const pc = BigInt(paymentCount);
  let tier;
  if (pc >= 100n)     tier = 3;
  else if (pc >= 50n) tier = 2;
  else if (pc >= 10n) tier = 1;
  else                tier = 0;

  return {
    tier:       BigInt(tier),
    perDrawCap: TIER_PER_DRAW_CAPS[tier],
    dailyCap:   TIER_DAILY_CAPS[tier],
    aprBps:     TIER_APR_BPS[tier],
  };
}

// Minimum practical amounts
export const MIN_DRAW_MICROALGO = 1_000n;    // 0.001 ALGO
export const MIN_DRAW_MICRO_USDC = 10_000n;  // 0.01 USDC
export const MIN_REPAY_MICROALGO = 1_000n;
export const MIN_REPAY_MICRO_USDC = 10_000n;

// ──────────────────────────────────────────────────────────────────────────────

// USDC has 6 decimal places — same as microALGO
export const toMicroUsdc = (usdc) => Math.round(usdc * 1_000_000);
export const fromMicroUsdc = (micro) => micro / 1_000_000;

// Helper: microALGO -> ALGO display string
export const toAlgo = (microAlgo) =>
  (Number(microAlgo) / 1_000_000).toFixed(6);

// Helper: ALGO input string -> microALGO as BigInt
export const toMicroAlgo = (algo) =>
  BigInt(Math.round(parseFloat(algo) * 1_000_000));

// x402 GoPlausible facilitator (Algorand testnet)
export const X402_FACILITATOR_URL =
  "https://x402.goplausible.xyz";

// Demo protected resource endpoint
export const X402_DEMO_RESOURCE_URL =
  "https://x402.goplausible.xyz/examples/weather";