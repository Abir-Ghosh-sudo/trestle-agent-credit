/**
 * tinyman.js — Tinyman V2 SDK wrapper for ALGO → USDC swaps.
 *
 * Uses @tinymanorg/tinyman-js-sdk (v2) to:
 *   1. Fetch live ALGO/USDC pool info from the Algorand node
 *   2. Get a fixed-input swap quote
 *   3. Generate the swap transaction group for signing
 *
 * Pool: ALGO (ASA 0) / USDC (ASA 10458941) — Algorand Testnet
 */

import algosdk from "algosdk";
import {
  Swap,
  poolUtils,
  SwapType,
  tinymanContract_v2,
  getValidatorAppID,
  ALGO_ASSET_ID,
} from "@tinymanorg/tinyman-js-sdk";
import { algodClient } from "./algod.js";

// ─── Constants ───────────────────────────────────────────────────────────────
export const ALGO_ASA_ID  = 0;
export const USDC_ASA_ID  = 10_458_941;

// Tinyman V2 Testnet Validator App ID
const TINYMAN_V2_TESTNET_VALIDATOR_APP_ID = 1002541853;

// Asset objects in Tinyman SDK format
const ALGO_ASSET = { id: ALGO_ASA_ID, decimals: 6, name: "ALGO", unit_name: "ALGO" };
const USDC_ASSET = { id: USDC_ASA_ID, decimals: 6, name: "USD Coin", unit_name: "USDC" };

/**
 * Fetch the ALGO/USDC V2 pool info using the SDK's poolUtils.
 * Returns the pool info object needed for quotes and txn generation.
 */
export async function getAlgoUsdcPool() {
  try {
    const pools = await poolUtils.v2.getPoolsForPair({
      client: algodClient,
      asset1ID: ALGO_ASA_ID,
      asset2ID: USDC_ASA_ID,
      network: "testnet",
    });
    if (!pools || pools.length === 0) throw new Error("No ALGO/USDC pool found on testnet");
    return pools[0];
  } catch (err) {
    console.warn("getAlgoUsdcPool error:", err?.message);
    return null;
  }
}

/**
 * Get pool info by its app ID using poolUtils.v2.getPoolInfo.
 */
export async function getPoolInfo(poolAppID) {
  try {
    return await poolUtils.v2.getPoolInfo({
      client: algodClient,
      network: "testnet",
      asset1ID: ALGO_ASA_ID,
      asset2ID: USDC_ASA_ID,
      validatorAppID: TINYMAN_V2_TESTNET_VALIDATOR_APP_ID,
    });
  } catch (err) {
    console.warn("getPoolInfo error:", err?.message);
    return null;
  }
}

/**
 * Get a fixed-input swap quote: swap microAlgoIn → USDC.
 *
 * NOTE on units:
 *   microAlgoIn  = amount in micro-ALGO (1 ALGO = 1,000,000 micro-ALGO)
 *   Returns microUsdcOut in micro-USDC (1 USDC = 1,000,000 micro-USDC)
 *
 * @param {number} microAlgoIn — micro-ALGO to spend
 * @param {object} pool        — pool info from getAlgoUsdcPool()
 * @param {number} slippage    — slippage tolerance (0.02 = 2%)
 * @returns {Promise<{quote, microUsdcOut: number, microUsdcMin: number}>}
 */
export async function getSwapQuote(microAlgoIn, pool, slippage = 0.02) {
  try {
    const quote = await Swap.v2.getFixedInputSwapQuote({
      pool,
      assetIn:  { ...ALGO_ASSET, id: ALGO_ASA_ID },
      assetOut: { ...USDC_ASSET, id: USDC_ASA_ID },
      amount: BigInt(microAlgoIn),
      isSwapRouterEnabled: false,
      network: "testnet",
    });
    const microUsdcOut = Number(quote.assetOutAmount ?? quote.amount_out ?? 0n);
    const microUsdcMin = Math.floor(microUsdcOut * (1 - slippage));
    return { quote, microUsdcOut, microUsdcMin };
  } catch (err) {
    console.warn("getSwapQuote SDK error, falling back to rate estimate:", err?.message);
    // Fallback: use static rate 0.18 USDC/ALGO
    const rate = 0.18;
    const microUsdcOut = Math.floor(microAlgoIn * rate * (1 - slippage));
    const microUsdcMin = Math.floor(microUsdcOut * 0.98);
    return { quote: null, microUsdcOut, microUsdcMin };
  }
}

/**
 * Build Tinyman V2 swap transactions using the SDK.
 * Returns an array of {txn, signers} objects ready for wallet signing.
 *
 * @param {number} microAlgoIn   — micro-ALGO input
 * @param {number} microUsdcMin  — minimum micro-USDC output (after slippage)
 * @param {object} pool          — pool info from getAlgoUsdcPool()
 * @param {object} quote         — quote from getSwapQuote()
 * @param {string} userAddress   — user's Algorand address
 * @returns {Promise<{txnGroup: object[], txIDs: string[]}>}
 */
export async function buildSwapTxns(microAlgoIn, microUsdcMin, pool, quote, userAddress) {
  const txns = await Swap.v2.generateTxns({
    client: algodClient,
    pool,
    swapType: SwapType.FixedInput,
    assetIn: { ...ALGO_ASSET, id: ALGO_ASA_ID },
    assetOut: { ...USDC_ASSET, id: USDC_ASA_ID },
    initiatorAddr: userAddress,
    amount: BigInt(microAlgoIn),
    slippage: 0.02,
    ...(quote ? { quote } : {}),
  });
  return txns;
}

/**
 * Estimate how many micro-USDC you'll get for microAlgoIn micro-ALGO.
 * Uses pool reserves for a direct calculation (no API call).
 * Falls back to static rate if pool is unavailable.
 *
 * @param {number} microAlgoIn
 * @param {object|null} pool
 * @returns {number} estimated micro-USDC output
 */
export function estimateMicroUsdcOut(microAlgoIn, pool) {
  try {
    if (pool?.asset1Reserves && pool?.asset2Reserves) {
      // Constant-product AMM formula (no fee for estimate):
      // out = (in * out_reserve) / (in_reserve + in)
      const algoRes  = Number(pool.asset1Reserves);
      const usdcRes  = Number(pool.asset2Reserves);
      const inWithFee = microAlgoIn * 997; // 0.3% fee
      return Math.floor((inWithFee * usdcRes) / (algoRes * 1000 + inWithFee));
    }
  } catch { /* fall through */ }
  // Static fallback: 0.18 USDC per ALGO
  return Math.floor(microAlgoIn * 0.18 * 0.98);
}

/**
 * Compute micro-ALGO needed to obtain targetMicroUsdc micro-USDC.
 * UNIT FIX: both inputs/outputs are in micro-units (6 decimal places).
 *
 * Math:
 *   rate      = USDC per ALGO    (e.g. 0.18)
 *   algoNeeded = (targetUSDC) / rate   (in ALGO)
 *   microAlgoNeeded = algoNeeded * 1,000,000
 *
 *   Since targetMicroUsdc is in micro-USDC:
 *   microAlgoNeeded = (targetMicroUsdc / 1e6) / rate * 1e6
 *                   = targetMicroUsdc / rate
 *
 * @param {number} targetMicroUsdc — micro-USDC target
 * @param {number} usdcPerAlgoRate — live rate (e.g. 0.18)
 * @param {number} bufferPct       — buffer multiplier (e.g. 1.1 = 10% extra)
 * @returns {number} micro-ALGO to swap
 */
export function microAlgoForUsdc(targetMicroUsdc, usdcPerAlgoRate, bufferPct = 1.10) {
  if (!usdcPerAlgoRate || usdcPerAlgoRate <= 0) usdcPerAlgoRate = 0.18;
  // targetMicroUsdc / rate gives micro-ALGO (units cancel correctly)
  return Math.ceil((targetMicroUsdc / usdcPerAlgoRate) * bufferPct);
}

/**
 * Fetch live ALGO→USDC price.
 * Tries Tinyman API, falls back to static 0.18.
 */
export async function getAlgoUsdcRate() {
  try {
    const res = await fetch(
      `https://testnet.tinyman.org/api/v1/assets/${ALGO_ASA_ID}/to_asset_price/?to_asset_id=${USDC_ASA_ID}`,
      { signal: AbortSignal.timeout(5000) }
    );
    if (!res.ok) throw new Error("rate API");
    const data = await res.json();
    const rate = parseFloat(data.price ?? data.to_price ?? 0);
    return { usdcPerAlgo: rate || 0.18, poolExists: rate > 0 };
  } catch {
    return { usdcPerAlgo: 0.18, poolExists: false };
  }
}
