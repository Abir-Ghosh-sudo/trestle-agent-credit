/**
 * ContractContext.jsx — All 6 Trestle contract method calls + position state.
 *
 * Exposes: {
 *   position, loading, error, activityLog, isOptedIn,
 *   fetchPosition, callRegister,
 *   callRecordPayment, callDraw,
 *   callRepay, callSlash
 * }
 *
 * Auto-refreshes position every 15 seconds when a wallet is connected.
 *
 * ── Key fixes (v2) ──
 * 1. Contract opt_in now initialises all local state keys → pc=262 resolved.
 * 2. fetchPosition / checkOptedIn use algodClient.accountApplicationInformation
 *    instead of raw fetch() — eliminates CORS and URL issues.
 * 3. sendRawTransaction response handled correctly for algosdk v3.
 * 4. makeSigner builds Pera/Defly-compatible signing payloads.
 * 5. ATC-based register and repay pass payment as TransactionWithSigner.
 */

import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useRef,
} from "react";
import algosdk from "algosdk";
import { useWallet } from "./WalletState.jsx";
import { algodClient } from "../lib/algod.js";
import {
  APP_ID,
  APP_ADDRESS,
  USDC_APP_ID,
  USDC_APP_ADDRESS,
  toMicroAlgo,
  ABI_METHODS,
  USDC_ASA_ID,
  DEFAULT_CURRENCY,
  getTierData,
} from "../lib/contract.js";
import {
  getAlgoUsdcRate,
  getAlgoUsdcPool,
  getSwapQuote,
  buildSwapTxns,
  microAlgoForUsdc,
} from "../lib/tinyman.js";

const ContractContext = createContext(null);

const DEFAULT_POSITION = {
  stake: 0n,
  paymentCount: 0n,
  outstanding: 0n,
  isDefaulted: false,
  // V2 fields — computed client-side from payment_count
  tierMaxDraw: 0n,   // daily cap (shown as "Draw Cap")
  perDrawCap: 0n,    // per-draw hard cap
  dailyCap: 0n,      // daily aggregate cap (same as tierMaxDraw)
  dailyDrawn: 0n,
  repayByRound: 0n,
  tier: 0n,
  aprBps: 0n,
  // USDC fields
  usdcStake:           0n,
  usdcPaymentCount:    0n,
  usdcOutstanding:     0n,
  usdcDailyDrawn:      0n,
  usdcTierMaxDraw:     0n,  // daily cap
  usdcPerDrawCap:      0n,  // per-draw cap
  usdcDailyCap:        0n,  // daily cap (alias)
  usdcTier:            0n,
  usdcAprBps:          0n,
  usdcTreasuryBalance: 0n,
  usdcAsaId:           0n,
  usdcIsOptedIn:       false,
};

/**
 * Parse raw contract/network errors into human-readable messages.
 */
function parseError(err) {
  const msg = err?.message || String(err);
  if (
    msg.includes("rejected") ||
    msg.includes("CONNECT_MODAL_CLOSED") ||
    msg.includes("cancelled") ||
    msg.includes("Cancelled") ||
    msg.includes("Connection Cancelled")
  )
    return "Transaction rejected by user";
  if (msg.includes("overspend") || msg.includes("insufficient funds"))
    return "Insufficient ALGO balance";

  // ARC56 pc mapping (from Trestle.arc56.json sourceInfo):
  //   pc=262 → "check self.stake_amount exists for account" (NOT opted in)
  //   pc=264 → "Agent already registered" (stake_amount > 0)
  if (msg.includes("pc=264") || msg.includes("Agent already registered"))
    return "You are already registered — try the Dashboard";
  if (
    msg.includes("pc=262") ||
    msg.includes("pc=261") ||
    msg.includes("cannot fetch key") ||
    msg.includes("has not opted in") ||
    msg.includes("check self.stake_amount exists")
  )
    return "Account not opted in — please try again";
  if (
    msg.includes("already registered")
  )
    return "Agent already registered";
  if (msg.includes("already opted in"))
    return "Already opted in — try registering";
  if (
    msg.includes("exceeds credit limit") ||
    msg.includes("Draw exceeds")
  )
    return "Amount exceeds available credit";
  if (
    msg.includes("not registered") ||
    msg.includes("Agent not registered")
  )
    return "Agent not registered";
  if (msg.includes("is defaulted") || msg.includes("Agent is defaulted"))
    return "Agent has been slashed";
  if (msg.includes("not delinquent"))
    return "Agent is not eligible for slashing";
  if (msg.includes("no outstanding"))
    return "Agent has no outstanding debt";
  if (
    (msg.includes("network") || msg.includes("fetch")) &&
    !msg.includes("cannot fetch key") &&
    !msg.includes("logic eval")
  )
    return "Network error — please retry";
  if (msg.includes("logic eval error")) {
    const match = msg.match(/logic eval error: (.+?)(?:\.|$)/);
    return match ? match[1] : "Transaction failed on-chain";
  }
  return msg.length > 120 ? msg.slice(0, 120) + "…" : msg;
}

/**
 * Parse USDC-specific contract errors into human-readable messages.
 */
function parseUsdcError(msg) {
  if (msg.includes("USDC not configured"))
    return "USDC not set up on this contract — call configure_usdc first";
  if (msg.includes("Repay USDC balance before drawing ALGO"))
    return "Repay your outstanding USDC loan before drawing ALGO";
  if (msg.includes("Repay ALGO balance before drawing USDC"))
    return "Repay your outstanding ALGO loan before drawing USDC";
  if (msg.includes("Insufficient USDC treasury"))
    return "Protocol USDC treasury is empty — contact admin";
  if (msg.includes("Exceeds USDC tier max draw"))
    return "Amount exceeds your USDC draw limit for this tier";
  if (msg.includes("Wrong ASA"))
    return "Wrong asset sent — must be USDC";
  if (msg.includes("unavailable Account") || msg.includes("unavailable account"))
    return "Payee account is not opted in to USDC asset — payee must opt in to receive funds";
  return null;
}

export function ContractProvider({ children }) {
  const { address, activeWallet } = useWallet();
  const [position, setPosition] = useState(DEFAULT_POSITION);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activityLog, setActivityLog] = useState([]);
  const [isOptedIn, setIsOptedIn] = useState(false);
  const [currency, setCurrency] = useState(DEFAULT_CURRENCY); // "USDC" | "ALGO"
  const [algoUsdcRate, setAlgoUsdcRate] = useState(0.18); // live ALGO→USDC rate
  const [walletBalance, setWalletBalance] = useState({ algo: 0, usdc: 0 }); // in micro units
  const refreshRef = useRef(null);
  const rateRef = useRef(null);

  const addActivity = useCallback((type, amount = null) => {
    setActivityLog((prev) => [
      { type, amount, round: null, timestamp: Date.now() },
      ...prev.slice(0, 19),
    ]);
  }, []);

  // ──────────────────────────────────────────
  // Live ALGO→USDC rate (refreshed every 60s)
  // ──────────────────────────────────────────
  useEffect(() => {
    const fetchRate = async () => {
      try {
        const { usdcPerAlgo } = await getAlgoUsdcRate();
        if (usdcPerAlgo > 0) setAlgoUsdcRate(usdcPerAlgo);
      } catch { /* keep existing rate */ }
    };
    fetchRate();
    rateRef.current = setInterval(fetchRate, 60_000);
    return () => clearInterval(rateRef.current);
  }, []);

  // ──────────────────────────────────────────
  // Helper — read a uint64 from TealKeyValue array.
  // algosdk v3 accountApplicationInformation returns objects with
  // camelCase or hyphenated keys depending on the endpoint.
  // ──────────────────────────────────────────
  const readLocalUint = (kvs, keyName) => {
    if (!kvs || kvs.length === 0) return 0n;
    const entry = kvs.find((kv) => {
      try {
        let decodedKey;
        if (typeof kv.key === "string") {
          // REST API / v3: key is base64 encoded
          decodedKey = atob(kv.key);
        } else if (kv.key instanceof Uint8Array) {
          // Model object: key is Uint8Array
          decodedKey = new TextDecoder().decode(kv.key);
        } else {
          decodedKey = String(kv.key);
        }
        return decodedKey === keyName;
      } catch {
        return false;
      }
    });
    if (!entry) return 0n;
    const val = entry.value?.uint ?? entry.value?.Uint ?? 0;
    return BigInt(val);
  };

  const readGlobalUint = (gvs, keyName) => {
    if (!gvs || gvs.length === 0) return 0n;
    const entry = gvs.find((kv) => {
      try {
        let decodedKey;
        if (typeof kv.key === "string") {
          decodedKey = atob(kv.key);
        } else if (kv.key instanceof Uint8Array) {
          decodedKey = new TextDecoder().decode(kv.key);
        } else {
          decodedKey = String(kv.key);
        }
        return decodedKey === keyName;
      } catch {
        return false;
      }
    });
    if (!entry) return 0n;
    const val = entry.value?.uint ?? entry.value?.Uint ?? 0;
    return BigInt(val);
  };

  // ──────────────────────────────────────────
  // fetchPosition — uses algodClient for reliability.
  // Queries both ALGO and USDC application states on Testnet.
  // ──────────────────────────────────────────
  // ──────────────────────────────────────────
  // fetchWalletBalance — reads ALGO + USDC balances from the wallet
  // ──────────────────────────────────────────
  const fetchWalletBalance = useCallback(async (addr) => {
    if (!addr) return;
    try {
      const accInfo = await algodClient.accountInformation(addr).do();
      const algoBalance = Number(accInfo.amount ?? accInfo["amount"] ?? 0);
      const assets = accInfo.assets ?? accInfo["assets"] ?? [];
      let usdcBalance = 0;
      for (const a of assets) {
        const assetId = Number(a["asset-id"] ?? a.assetId ?? 0);
        if (assetId === USDC_ASA_ID) {
          usdcBalance = Number(a.amount ?? a["amount"] ?? 0);
          break;
        }
      }
      setWalletBalance({ algo: algoBalance, usdc: usdcBalance });
    } catch (err) {
      console.warn("fetchWalletBalance:", err?.message);
    }
  }, []);

  const fetchPosition = useCallback(async (addr) => {
    if (!addr) return;
    setLoading(true);
    try {
      // 1. Fetch ALGO position from local state
      let algoOptedIn = false;
      let algoPos = {
        stake: 0n,
        paymentCount: 0n,
        outstanding: 0n,
        isDefaulted: false,
        tierMaxDraw: 0n,
        perDrawCap: 0n,
        dailyCap: 0n,
        dailyDrawn: 0n,
        repayByRound: 0n,
        tier: 0n,
        aprBps: 0n,
      };

      try {
        const appInfo = await algodClient
          .accountApplicationInformation(addr, APP_ID)
          .do();
        const appLocalState =
          appInfo["app-local-state"] ?? appInfo["appLocalState"] ?? null;
        if (appLocalState) {
          algoOptedIn = true;
          const kvs =
            appLocalState["key-value"] ??
            appLocalState["keyValue"] ??
            appLocalState.keyValue ??
            [];

          const paymentCount = readLocalUint(kvs, "payment_count");
          // Compute tier data client-side — the contract does NOT store
          // tier_max_draw, tier, or apr_bps in local state. It only
          // computes them on-the-fly in get_position(). We mirror that logic.
          const tierData = getTierData(paymentCount);

          algoPos = {
            stake:        readLocalUint(kvs, "stake_amount"),
            paymentCount,
            outstanding:  readLocalUint(kvs, "outstanding"),
            isDefaulted:  readLocalUint(kvs, "is_defaulted") > 0n,
            tierMaxDraw:  tierData.dailyCap,     // daily cap shown as "Draw Cap"
            perDrawCap:   tierData.perDrawCap,    // per-draw hard cap
            dailyCap:     tierData.dailyCap,      // daily aggregate cap
            dailyDrawn:   readLocalUint(kvs, "daily_drawn"),
            repayByRound: readLocalUint(kvs, "repay_by_round"),
            tier:         tierData.tier,
            aprBps:       tierData.aprBps,
          };
        }
      } catch (err) {
        console.warn("fetch ALGO position:", err?.message || err);
      }

      // 2. Fetch USDC position
      let usdcIsOptedIn = false;
      let usdcPos = {
        usdcStake: 0n,
        usdcPaymentCount: 0n,
        usdcOutstanding: 0n,
        usdcDailyDrawn: 0n,
        usdcTierMaxDraw: 0n,
        usdcPerDrawCap: 0n,
        usdcDailyCap: 0n,
        usdcTier: 0n,
        usdcAprBps: 0n,
        usdcTreasuryBalance: 0n,
        usdcAsaId: BigInt(USDC_ASA_ID),
      };

      try {
        const usdcAppInfo = await algodClient
          .accountApplicationInformation(addr, USDC_APP_ID)
          .do();
        const usdcLocalState =
          usdcAppInfo["app-local-state"] ?? usdcAppInfo["appLocalState"] ?? null;
        if (usdcLocalState) {
          usdcIsOptedIn = true;
          const usdcKvs =
            usdcLocalState["key-value"] ??
            usdcLocalState["keyValue"] ??
            usdcLocalState.keyValue ??
            [];

          const usdcStake = readLocalUint(usdcKvs, "stake_amount");
          const usdcPaymentCount = readLocalUint(usdcKvs, "payment_count");
          const usdcOutstanding = readLocalUint(usdcKvs, "usdc_outstanding");
          const usdcDailyDrawn = readLocalUint(usdcKvs, "daily_drawn");

          // Use unified getTierData helper
          const usdcTierData = getTierData(usdcPaymentCount);

          usdcPos = {
            usdcStake,
            usdcPaymentCount,
            usdcOutstanding,
            usdcDailyDrawn,
            usdcTierMaxDraw: usdcTierData.dailyCap,
            usdcPerDrawCap:  usdcTierData.perDrawCap,
            usdcDailyCap:    usdcTierData.dailyCap,
            usdcTier:        usdcTierData.tier,
            usdcAprBps:      usdcTierData.aprBps,
            usdcTreasuryBalance: 0n,
            usdcAsaId: BigInt(USDC_ASA_ID),
          };
        }
      } catch (err) {
        console.warn("fetch USDC position:", err?.message || err);
      }

      // 3. Fetch USDC global state
      try {
        const appGlobal = await algodClient.getApplicationByID(USDC_APP_ID).do();
        const globalKvs = appGlobal.params["global-state"] ?? [];
        usdcPos.usdcTreasuryBalance = readGlobalUint(globalKvs, "usdc_treasury_balance");
        const gAsaId = readGlobalUint(globalKvs, "usdc_asa_id");
        if (gAsaId > 0n) {
          usdcPos.usdcAsaId = gAsaId;
        }
      } catch (err) {
        console.warn("fetch USDC global state:", err?.message || err);
      }

      // 4. Fetch wallet balances
      await fetchWalletBalance(addr);

      setIsOptedIn(algoOptedIn);
      setPosition({
        ...algoPos,
        ...usdcPos,
        usdcIsOptedIn,
      });
      setError(null);
    } catch (err) {
      console.error("fetchPosition global error:", err);
      setError(parseError(err));
    } finally {
      setLoading(false);
    }
  }, [fetchWalletBalance]); // eslint-disable-line react-hooks/exhaustive-deps

  // ──────────────────────────────────────────
  // checkOptedIn — uses algodClient directly.
  // Returns true only if the account has app-local-state for APP_ID.
  // ──────────────────────────────────────────
  const checkOptedIn = useCallback(async (addr) => {
    if (!addr) return false;
    try {
      const appInfo = await algodClient
        .accountApplicationInformation(addr, APP_ID)
        .do();
      const hasLocalState = !!(
        appInfo["app-local-state"] ??
        appInfo["appLocalState"]
      );
      console.log(
        "checkOptedIn:",
        addr.slice(0, 8) + "...",
        "=>",
        hasLocalState,
      );
      return hasLocalState;
    } catch {
      // 404 = not opted in
      return false;
    }
  }, []);

  const checkUsdcOptedIn = useCallback(async (addr) => {
    if (!addr) return false;
    try {
      const appInfo = await algodClient
        .accountApplicationInformation(addr, USDC_APP_ID)
        .do();
      const hasLocalState = !!(
        appInfo["app-local-state"] ??
        appInfo["appLocalState"]
      );
      console.log(
        "checkUsdcOptedIn:",
        addr.slice(0, 8) + "...",
        "=>",
        hasLocalState,
      );
      return hasLocalState;
    } catch {
      // 404 = not opted in
      return false;
    }
  }, []);

  const checkAssetOptedIn = useCallback(async (addr, assetId) => {
    if (!addr) return false;
    try {
      const accInfo = await algodClient.accountInformation(addr).do();
      const assets = accInfo.assets ?? accInfo["assets"] ?? [];
      return assets.some(a => BigInt(a["asset-id"] ?? a.assetId) === BigInt(assetId));
    } catch {
      return false;
    }
  }, []);

  // ──────────────────────────────────────────
  // makeSigner — ATC-compatible TransactionSigner for Pera/Defly.
  //
  // ATC calls signer(txnGroup, indexesToSign):
  //   txnGroup: Transaction[]
  //   indexesToSign: number[]
  //
  // Pera/Defly signTransaction() expects:
  //   signTransaction([ [{ txn, signers }, ...] ])
  //   The outer array is for multiple txn groups.
  //   The inner array is the group (one entry per txn).
  //
  // Returns: Uint8Array[] aligned with txnGroup length.
  // ──────────────────────────────────────────
  const makeSigner = useCallback(() => {
    return async (txnGroup, indexesToSign) => {
      if (!activeWallet) throw new Error("No wallet connected");

      // Build the signing request format for Pera/Defly
      const txnsToSign = txnGroup.map((txn, idx) => ({
        txn,
        signers: indexesToSign.includes(idx) ? [address] : [],
      }));

      // signTransaction expects an array of groups: [[...group1]]
      const signedTxns = await activeWallet.signTransaction([txnsToSign]);

      // signedTxns is Uint8Array[] — already aligned with txnGroup
      return signedTxns;
    };
  }, [address, activeWallet]);

  // ──────────────────────────────────────────
  // callRegister — Two-step flow:
  //   Step 1 (if needed): Submit opt-in as a separate signed transaction.
  //   Step 2: ATC group with [payment, register] method call.
  //
  // The opt-in is separated from the ATC group because the contract's
  // register() method reads local state that must exist (set by opt-in).
  // ──────────────────────────────────────────
  const callRegister = useCallback(
    async (stakeAlgo) => {
      setLoading(true);
      setError(null);
      try {
        if (!activeWallet) throw new Error("No wallet connected");

        const signer = makeSigner();

        // ── Step 1: Opt-in (if not already opted in) ──
        const alreadyOptedIn = await checkOptedIn(address);
        console.log("callRegister: alreadyOptedIn =", alreadyOptedIn);

        if (!alreadyOptedIn) {
          console.log("callRegister: Submitting opt-in transaction...");
          const sp1 = await algodClient.getTransactionParams().do();
          const optInTxn = algosdk.makeApplicationOptInTxnFromObject({
            sender: address,
            appIndex: APP_ID,
            suggestedParams: { ...sp1, fee: 1000, flatFee: true },
          });

          // Sign via wallet
          const signedOptIn = await activeWallet.signTransaction([
            [{ txn: optInTxn, signers: [address] }],
          ]);

          // Submit — signedOptIn may be a single Uint8Array or array
          const rawToSend = Array.isArray(signedOptIn)
            ? signedOptIn.filter(Boolean)
            : [signedOptIn];
          await algodClient.sendRawTransaction(rawToSend).do();

          // Wait for confirmation using the txn ID
          const optInTxId = optInTxn.txID();
          console.log("callRegister: Opt-in submitted, txID:", optInTxId);
          await algosdk.waitForConfirmation(algodClient, optInTxId, 4);
          console.log("callRegister: Opt-in confirmed!");
        }

        // ── Step 2: Register via ATC (payment + register call) ──
        console.log("callRegister: Submitting register transaction...");
        const sp2 = await algodClient.getTransactionParams().do();
        const stakeAmt = toMicroAlgo(stakeAlgo);

        const atc = new algosdk.AtomicTransactionComposer();

        // Payment txn — TransactionWithSigner for the "pay" method arg
        const payTxn = algosdk.makePaymentTxnWithSuggestedParamsFromObject({
          sender: address,
          receiver: APP_ADDRESS,
          amount: stakeAmt,
          suggestedParams: { ...sp2, fee: 1000, flatFee: true },
        });
        const payTws = { txn: payTxn, signer };

        // App call — ATC places payment before this in the group
        atc.addMethodCall({
          appID: APP_ID,
          method: new algosdk.ABIMethod(ABI_METHODS.register),
          methodArgs: [payTws],
          sender: address,
          suggestedParams: { ...sp2, fee: 2000, flatFee: true },
          signer,
        });

        await atc.execute(algodClient, 4);
        console.log("callRegister: Register confirmed!");

        await fetchPosition(address);
        setIsOptedIn(true);
        addActivity("register", stakeAlgo);
      } catch (err) {
        console.error("callRegister error:", err);
        const msg = parseError(err);
        setError(msg);
        throw new Error(msg);
      } finally {
        setLoading(false);
      }
    },
    [address, activeWallet, makeSigner, fetchPosition, checkOptedIn, addActivity]
  );

  const callRegisterUsdc = useCallback(
    async (stakeAlgo) => {
      setLoading(true);
      setError(null);
      try {
        if (!activeWallet) throw new Error("No wallet connected");

        const signer = makeSigner();

        // ── Step 1: Opt-in (if not already opted in) ──
        const alreadyOptedIn = await checkUsdcOptedIn(address);
        console.log("callRegisterUsdc: alreadyOptedIn =", alreadyOptedIn);

        if (!alreadyOptedIn) {
          console.log("callRegisterUsdc: Submitting opt-in transaction...");
          const sp1 = await algodClient.getTransactionParams().do();
          const optInTxn = algosdk.makeApplicationOptInTxnFromObject({
            sender: address,
            appIndex: USDC_APP_ID,
            suggestedParams: { ...sp1, fee: 1000, flatFee: true },
          });

          // Sign via wallet
          const signedOptIn = await activeWallet.signTransaction([
            [{ txn: optInTxn, signers: [address] }],
          ]);

          // Submit
          const rawToSend = Array.isArray(signedOptIn)
            ? signedOptIn.filter(Boolean)
            : [signedOptIn];
          await algodClient.sendRawTransaction(rawToSend).do();

          // Wait for confirmation using the txn ID
          const optInTxId = optInTxn.txID();
          console.log("callRegisterUsdc: Opt-in submitted, txID:", optInTxId);
          await algosdk.waitForConfirmation(algodClient, optInTxId, 4);
          console.log("callRegisterUsdc: Opt-in confirmed!");
        }

        // ── Step 2: Register via ATC (payment + register call) ──
        console.log("callRegisterUsdc: Submitting register transaction...");
        const sp2 = await algodClient.getTransactionParams().do();
        const stakeAmt = toMicroAlgo(stakeAlgo);

        const atc = new algosdk.AtomicTransactionComposer();

        // Payment txn — TransactionWithSigner for the "pay" method arg
        const payTxn = algosdk.makePaymentTxnWithSuggestedParamsFromObject({
          sender: address,
          receiver: USDC_APP_ADDRESS,
          amount: stakeAmt,
          suggestedParams: { ...sp2, fee: 1000, flatFee: true },
        });
        const payTws = { txn: payTxn, signer };

        // App call — ATC places payment before this in the group
        atc.addMethodCall({
          appID: USDC_APP_ID,
          method: new algosdk.ABIMethod(ABI_METHODS.register),
          methodArgs: [payTws],
          sender: address,
          suggestedParams: { ...sp2, fee: 2000, flatFee: true },
          signer,
        });

        await atc.execute(algodClient, 4);
        console.log("callRegisterUsdc: Register confirmed!");

        await fetchPosition(address);
        addActivity("register_usdc", stakeAlgo);
      } catch (err) {
        console.error("callRegisterUsdc error:", err);
        const msg = parseError(err);
        setError(msg);
        throw new Error(msg);
      } finally {
        setLoading(false);
      }
    },
    [address, activeWallet, makeSigner, fetchPosition, checkUsdcOptedIn, addActivity]
  );

  // ──────────────────────────────────────────
  // callBorrowAndStakeUsdc — atomic ALGO borrow and stake on USDC contract
  // ──────────────────────────────────────────
  const callBorrowAndStakeUsdc = useCallback(
    async () => {
      setLoading(true);
      setError(null);
      try {
        if (!activeWallet) throw new Error("No wallet connected");

        const signer = makeSigner();

        // ── Step 1: Opt-in to USDC app if needed ──
        const alreadyOptedIn = await checkUsdcOptedIn(address);
        if (!alreadyOptedIn) {
          console.log("callBorrowAndStakeUsdc: Opting into USDC contract...");
          const sp1 = await algodClient.getTransactionParams().do();
          const optInTxn = algosdk.makeApplicationOptInTxnFromObject({
            sender: address,
            appIndex: USDC_APP_ID,
            suggestedParams: { ...sp1, fee: 1000, flatFee: true },
          });
          const signedOptIn = await activeWallet.signTransaction([
            [{ txn: optInTxn, signers: [address] }],
          ]);
          const rawToSend = Array.isArray(signedOptIn) ? signedOptIn.filter(Boolean) : [signedOptIn];
          await algodClient.sendRawTransaction(rawToSend).do();
          await algosdk.waitForConfirmation(algodClient, optInTxn.txID(), 4);
        }

        // ── Step 2: Build 3-txn atomic group ──
        console.log("callBorrowAndStakeUsdc: Submitting atomic borrow + stake...");
        const sp = await algodClient.getTransactionParams().do();
        const atc = new algosdk.AtomicTransactionComposer();
        const hashArr = new Uint8Array(32);

        // Draw 1 ALGO from main contract (APP_ID)
        atc.addMethodCall({
          appID: APP_ID,
          method: new algosdk.ABIMethod(ABI_METHODS.draw),
          methodArgs: [1_000_000n, hashArr],
          sender: address,
          suggestedParams: { ...sp, fee: 2000, flatFee: true },
          signer,
        });

        // Stake 1 ALGO (payment txn to USDC_APP_ADDRESS)
        const stakeTxn = algosdk.makePaymentTxnWithSuggestedParamsFromObject({
          sender: address,
          receiver: USDC_APP_ADDRESS,
          amount: 1_000_000n,
          suggestedParams: { ...sp, fee: 1000, flatFee: true },
        });
        const stakeTws = { txn: stakeTxn, signer };

        // Register on USDC contract (USDC_APP_ID)
        atc.addMethodCall({
          appID: USDC_APP_ID,
          method: new algosdk.ABIMethod(ABI_METHODS.register),
          methodArgs: [stakeTws],
          sender: address,
          suggestedParams: { ...sp, fee: 2000, flatFee: true },
          signer,
        });

        await atc.execute(algodClient, 4);
        console.log("callBorrowAndStakeUsdc: Borrow & Stake successful!");

        await fetchPosition(address);
        addActivity("borrow_and_stake_usdc", 1.0);
      } catch (err) {
        console.error("callBorrowAndStakeUsdc error:", err);
        const msg = parseError(err);
        setError(msg);
        throw new Error(msg);
      } finally {
        setLoading(false);
      }
    },
    [address, activeWallet, makeSigner, fetchPosition, checkUsdcOptedIn, addActivity]
  );

  // ──────────────────────────────────────────
  // callRegisterUnified — Single flow: register ALGO + auto-activate USDC
  //
  // 1. Register on ALGO contract (opt-in + stake)
  // 2. If alsoActivateUsdc: draw 1 ALGO credit → stake on USDC contract
  //
  // This means users only need 1 ALGO total for both credit lines.
  // ──────────────────────────────────────────
  const callRegisterUnified = useCallback(
    async (stakeAlgo, alsoActivateUsdc = true) => {
      setLoading(true);
      setError(null);
      try {
        if (!activeWallet) throw new Error("No wallet connected");

        // ── Step 1: Register on ALGO contract ──
        await callRegister(stakeAlgo);
        addActivity("register", stakeAlgo);

        // ── Step 2: Auto-activate USDC (borrow 1 ALGO + stake on USDC) ──
        if (alsoActivateUsdc) {
          try {
            await callRegisterUsdc("1");
            addActivity("register_usdc", 1.0);
          } catch (usdcErr) {
            console.warn("USDC registration failed:", usdcErr?.message);
            setError(
              `Registered on ALGO ✓ — USDC registration failed: ${parseError(usdcErr)}.`
            );
          }
        }

        await fetchPosition(address);
      } catch (err) {
        console.error("callRegisterUnified error:", err);
        const msg = parseError(err);
        setError(msg);
        throw new Error(msg);
      } finally {
        setLoading(false);
      }
    },
   [address, activeWallet, callRegister, callRegisterUsdc, fetchPosition, addActivity]
  );

  // ──────────────────────────────────────────
  // callRecordPayment
  // Contract: record_payment(amount: uint64) → uint64
  // ──────────────────────────────────────────
  const callRecordPayment = useCallback(
    async (amountAlgo) => {
      setLoading(true);
      setError(null);
      try {
        if (!activeWallet) throw new Error("No wallet connected");

        const atc = new algosdk.AtomicTransactionComposer();
        const sp = await algodClient.getTransactionParams().do();

        atc.addMethodCall({
          appID: APP_ID,
          method: new algosdk.ABIMethod(ABI_METHODS.record_payment),
          methodArgs: [toMicroAlgo(amountAlgo)],
          sender: address,
          suggestedParams: { ...sp, fee: 1000, flatFee: true },
          signer: makeSigner(),
        });

        const result = await atc.execute(algodClient, 4);
        // returnValue is ABI-decoded: BigInt (uint64)
        const newLimit = result.methodResults[0].returnValue;
        await fetchPosition(address);
        addActivity("payment", amountAlgo);
        return newLimit;
      } catch (err) {
        console.error("callRecordPayment error:", err);
        const msg = parseError(err);
        setError(msg);
        throw new Error(msg);
      } finally {
        setLoading(false);
      }
    },
    [address, activeWallet, makeSigner, fetchPosition, addActivity]
  );

  // ──────────────────────────────────────────
  // callDraw
  // Contract: draw(amount: uint64, attestation_hash: byte[32]) → void
  // skip_attestation=1 on testnet so hash value doesn't matter;
  // but the ABI argument must still be exactly 32 bytes.
  // Uses inner txn to send ALGO to caller → fee must be 2000.
  // ──────────────────────────────────────────
  const callDraw = useCallback(
    async (amountAlgo) => {
      setLoading(true);
      setError(null);
      try {
        if (!activeWallet) throw new Error("No wallet connected");

        const atc = new algosdk.AtomicTransactionComposer();
        const sp = await algodClient.getTransactionParams().do();
        const amountMicro = toMicroAlgo(amountAlgo);

        // Build attestation hash: sha256(sender_32 + amount_8 + round_8)
        // On testnet skip_attestation=1 so the value is ignored, but must be 32 bytes.
        const currentRound = BigInt(sp.firstValid);
        const senderBytes = algosdk.decodeAddress(address).publicKey; // 32 bytes
        const amountBytes = new Uint8Array(8);
        const roundBytes  = new Uint8Array(8);
        const amtView     = new DataView(amountBytes.buffer);
        const rndView     = new DataView(roundBytes.buffer);
        amtView.setBigUint64(0, amountMicro, false); // big-endian
        rndView.setBigUint64(0, currentRound,  false);
        const preimage = new Uint8Array(48);
        preimage.set(senderBytes,  0);
        preimage.set(amountBytes, 32);
        preimage.set(roundBytes,  40);

        // Safely use Web Crypto API (bypassing Vite bundle alias 'crypto')
        let hashArr;
        const subtleCrypto = typeof globalThis !== "undefined"
          ? (globalThis.crypto?.subtle || globalThis.crypto?.webcrypto?.subtle)
          : null;

        if (subtleCrypto) {
          try {
            const hashBuf = await subtleCrypto.digest("SHA-256", preimage);
            hashArr = new Uint8Array(hashBuf);
          } catch (digestErr) {
            console.warn("Subtle crypto digest failed, falling back to empty hash:", digestErr);
            hashArr = new Uint8Array(32);
          }
        } else {
          console.warn("Web Crypto API (crypto.subtle) not available. Using zero-hash fallback for testnet.");
          hashArr = new Uint8Array(32);
        }

        atc.addMethodCall({
          appID: APP_ID,
          method: new algosdk.ABIMethod(ABI_METHODS.draw),
          methodArgs: [amountMicro, hashArr],
          sender: address,
          suggestedParams: { ...sp, fee: 2000, flatFee: true },
          signer: makeSigner(),
        });

        await atc.execute(algodClient, 4);
        await fetchPosition(address);
        addActivity("draw", amountAlgo);
      } catch (err) {
        console.error("callDraw error:", err);
        const msg = parseError(err);
        setError(msg);
        throw new Error(msg);
      } finally {
        setLoading(false);
      }
    },
    [address, activeWallet, makeSigner, fetchPosition, addActivity]
  );

  // ──────────────────────────────────────────
  // callRepay
  // Contract: repay(pay: PaymentTransaction) → void
  // Same pattern as register: payment passed as TransactionWithSigner.
  // ──────────────────────────────────────────
  const callRepay = useCallback(
    async (amountAlgo) => {
      setLoading(true);
      setError(null);
      try {
        if (!activeWallet) throw new Error("No wallet connected");

        const atc = new algosdk.AtomicTransactionComposer();
        const sp = await algodClient.getTransactionParams().do();
        const signer = makeSigner();

        // Payment txn as TransactionWithSigner
        const payTxn = algosdk.makePaymentTxnWithSuggestedParamsFromObject({
          sender: address,
          receiver: APP_ADDRESS,
          amount: toMicroAlgo(amountAlgo),
          suggestedParams: { ...sp, fee: 1000, flatFee: true },
        });
        const payTws = { txn: payTxn, signer };

        atc.addMethodCall({
          appID: APP_ID,
          method: new algosdk.ABIMethod(ABI_METHODS.repay),
          methodArgs: [payTws],
          sender: address,
          suggestedParams: { ...sp, fee: 1000, flatFee: true },
          signer,
        });

        await atc.execute(algodClient, 4);
        await fetchPosition(address);
        addActivity("repay", amountAlgo);
      } catch (err) {
        console.error("callRepay error:", err);
        const msg = parseError(err);
        setError(msg);
        throw new Error(msg);
      } finally {
        setLoading(false);
      }
    },
    [address, activeWallet, makeSigner, fetchPosition, addActivity]
  );

  // ──────────────────────────────────────────
  // callSlash
  // Contract: slash(agent: address) → void
  // ──────────────────────────────────────────
  const callSlash = useCallback(
    async (agentAddress) => {
      setLoading(true);
      setError(null);
      try {
        if (!activeWallet) throw new Error("No wallet connected");

        const atc = new algosdk.AtomicTransactionComposer();
        const sp = await algodClient.getTransactionParams().do();

        atc.addMethodCall({
          appID: APP_ID,
          method: new algosdk.ABIMethod(ABI_METHODS.slash),
          methodArgs: [agentAddress],
          sender: address,
          suggestedParams: { ...sp, fee: 1000, flatFee: true },
          signer: makeSigner(),
        });

        await atc.execute(algodClient, 4);
        await fetchPosition(address);
        addActivity("slash");
      } catch (err) {
        console.error("callSlash error:", err);
        const msg = parseError(err);
        setError(msg);
        throw new Error(msg);
      } finally {
        setLoading(false);
      }
    },
    [address, activeWallet, makeSigner, fetchPosition, addActivity]
  );

  // ──────────────────────────────────────────
  // Auto-refresh position every 15 seconds
  // ──────────────────────────────────────────
  useEffect(() => {
    if (!address) {
      setPosition(DEFAULT_POSITION);
      setIsOptedIn(false);
      setError(null);
      clearInterval(refreshRef.current);
      return;
    }
    fetchPosition(address);
    refreshRef.current = setInterval(() => fetchPosition(address), 15_000);
    return () => clearInterval(refreshRef.current);
  }, [address, fetchPosition]);

  // ──────────────────────────────────────────
  // fetchUsdcPosition — reads usdc_outstanding from local state
  // ──────────────────────────────────────────
  const fetchUsdcPosition = useCallback(async (addr) => {
    if (!addr) return;
    try {
      const appInfo = await algodClient
        .accountApplicationInformation(addr, USDC_APP_ID)
        .do();
      const appLocalState =
        appInfo["app-local-state"] ?? appInfo["appLocalState"] ?? null;
      if (!appLocalState) return;
      const kvs =
        appLocalState["key-value"] ??
        appLocalState["keyValue"] ??
        appLocalState.keyValue ??
        [];
      setPosition(prev => ({
        ...prev,
        usdcOutstanding: readLocalUint(kvs, "usdc_outstanding"),
      }));
    } catch (err) {
      console.warn("fetchUsdcPosition:", err?.message);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ──────────────────────────────────────────
  // callDrawUsdc
  // Contract: draw_usdc(amount: uint64, attestation_hash: byte[32]) → void
  // ──────────────────────────────────────────
  const callDrawUsdc = useCallback(
    async (amountMicroUsdc) => {
      setLoading(true);
      setError(null);
      try {
        if (!activeWallet) throw new Error("No wallet connected");

        // ── Auto-opt-in to USDC ASA ──
        const optedIn = await checkAssetOptedIn(address, USDC_ASA_ID);
        if (!optedIn) {
          console.log("Opting account into USDC ASA...");
          const spOpt = await algodClient.getTransactionParams().do();
          const optTxn = algosdk.makeAssetTransferTxnWithSuggestedParamsFromObject({
            sender: address,
            receiver: address,
            amount: 0n,
            assetIndex: USDC_ASA_ID,
            suggestedParams: { ...spOpt, fee: 1000, flatFee: true },
          });
          const signedOpt = await activeWallet.signTransaction([
            [{ txn: optTxn, signers: [address] }],
          ]);
          const rawToSend = Array.isArray(signedOpt) ? signedOpt.filter(Boolean) : [signedOpt];
          await algodClient.sendRawTransaction(rawToSend).do();
          await algosdk.waitForConfirmation(algodClient, optTxn.txID(), 4);
          console.log("USDC ASA opt-in confirmed!");
        }

        const atc = new algosdk.AtomicTransactionComposer();
        const sp = await algodClient.getTransactionParams().do();
        const signer = makeSigner();

        atc.addMethodCall({
          appID:      USDC_APP_ID,
          method:     new algosdk.ABIMethod(ABI_METHODS.draw_usdc),
          sender:     address,
          suggestedParams: { ...sp, fee: 2000, flatFee: true },
          signer,
          methodArgs: [BigInt(amountMicroUsdc), new Uint8Array(32)],  // demo mode: 32 zero bytes
          foreignAssets: [USDC_ASA_ID],
        });

        const result = await atc.execute(algodClient, 4);
        addActivity(`USDC draw: ${amountMicroUsdc} micro-USDC`);
        await fetchPosition(address);
        return result.txIDs?.[0] ?? result.methodResults?.[0]?.txID;
      } catch (err) {
        console.error("callDrawUsdc error:", err);
        const usdcMsg = parseUsdcError(err?.message || String(err));
        const msg = usdcMsg || parseError(err);
        setError(msg);
        throw new Error(msg);
      } finally {
        setLoading(false);
      }
    },
    [address, activeWallet, makeSigner, fetchPosition, checkAssetOptedIn, addActivity]
  );

  // ──────────────────────────────────────────────────────────────────────────
  // callAutoDrawUsdc — THE ZERO-ADMIN AUTO-SWAP DRAW FLOW
  //
  // Full flow (always fresh treasury check):
  //   1. Fetch latest position to get real treasury balance.
  //   2. If treasury has enough USDC → direct draw_usdc call.
  //   3. If treasury is low:
  //      A. Draw ALGO credit from main contract (APP_ID).
  //      B. Opt-in to USDC ASA if needed.
  //      C. Fetch Tinyman pool + get swap quote.
  //      D. Sign & submit swap txns → ALGO leaves wallet, USDC arrives.
  //      E. Atomic group: seed_treasury(USDC axfer) + draw_usdc(amount).
  //         USDC is sent from the treasury directly to Txn.sender (user wallet).
  //
  // UNIT NOTE: microAlgoNeeded = targetMicroUsdc / usdcPerAlgo
  //   (micro-USDC / USDC-per-ALGO = micro-ALGO ✓)
  // ──────────────────────────────────────────────────────────────────────────
  const callAutoDrawUsdc = useCallback(
    async (amountMicroUsdc, onStep) => {
      setLoading(true);
      setError(null);
      try {
        if (!activeWallet) throw new Error("No wallet connected");

        // ── Always refresh position to get the latest treasury balance ──
        await fetchPosition(address);

        // NOTE: position is a React state snapshot — read from algod directly
        // to avoid stale closure issue.
        let liveTreasuryBal = 0;
        try {
          const appGlobal = await algodClient.getApplicationByID(USDC_APP_ID).do();
          const globalKvs = appGlobal.params?.["global-state"] ?? [];
          const entry = globalKvs.find(kv => {
            try { return atob(kv.key) === "usdc_treasury_balance"; } catch { return false; }
          });
          liveTreasuryBal = Number(entry?.value?.uint ?? 0);
        } catch {
          // If query fails, default to 0 to safely trigger swap/draw flow
          liveTreasuryBal = 0;
        }

        console.log("[autoSwap] liveTreasuryBal:", liveTreasuryBal, "need:", amountMicroUsdc);

        if (liveTreasuryBal >= amountMicroUsdc) {
          // Treasury has enough — direct draw, no swap needed
          onStep?.("drawing", null);
          return await callDrawUsdc(amountMicroUsdc);
        }

        // ── Treasury low — borrow ALGO credit, swap to USDC, seed + draw ──
        onStep?.("quoting", null);

        const microAlgoNeeded = microAlgoForUsdc(amountMicroUsdc, algoUsdcRate, 1.10);
        console.log(
          "[autoSwap] amountMicroUsdc:", amountMicroUsdc,
          "micro-USDC → microAlgoNeeded:", microAlgoNeeded, "micro-ALGO"
        );

        // ── Step 1: Draw ALGO credit from ALGO contract ──
        onStep?.("drawing_algo_credit", { microAlgoNeeded });
        const drawHashArr = new Uint8Array(32);
        const drawAtc = new algosdk.AtomicTransactionComposer();
        const spDraw = await algodClient.getTransactionParams().do();

        drawAtc.addMethodCall({
          appID: APP_ID,
          method: new algosdk.ABIMethod(ABI_METHODS.draw),
          methodArgs: [BigInt(microAlgoNeeded), drawHashArr],
          sender: address,
          suggestedParams: { ...spDraw, fee: 2000, flatFee: true },
          signer: makeSigner(),
        });

        await drawAtc.execute(algodClient, 4);
        addActivity("draw", microAlgoNeeded / 1e6);
        console.log("[autoSwap] ALGO credit drawn:", microAlgoNeeded, "micro-ALGO");

        // ── Step 2: Opt-in to USDC ASA if needed ──
        const optedIn = await checkAssetOptedIn(address, USDC_ASA_ID);
        if (!optedIn) {
          onStep?.("opting_in", null);
          const spOpt = await algodClient.getTransactionParams().do();
          const optTxn = algosdk.makeAssetTransferTxnWithSuggestedParamsFromObject({
            sender: address,
            receiver: address,
            amount: 0n,
            assetIndex: USDC_ASA_ID,
            suggestedParams: { ...spOpt, fee: 1000, flatFee: true },
          });
          const signedOpt = await activeWallet.signTransaction([
            [{ txn: optTxn, signers: [address] }],
          ]);
          const rawOpt = Array.isArray(signedOpt) ? signedOpt.filter(Boolean) : [signedOpt];
          await algodClient.sendRawTransaction(rawOpt).do();
          await algosdk.waitForConfirmation(algodClient, optTxn.txID(), 4);
        }

        // ── Fetch Tinyman pool (SDK) ──
        onStep?.("swapping", { microAlgoNeeded, microUsdcExpected: amountMicroUsdc });
        let pool = null;
        try {
          pool = await getAlgoUsdcPool();
        } catch { /* pool fetch failed */ }

        if (!pool) {
          const algoAmt = (microAlgoNeeded / 1e6).toFixed(6);
          throw new Error(
            `USDC treasury low and Tinyman pool unavailable. ` +
            `You need to manually swap ~${algoAmt} ALGO → USDC, ` +
            `then click Draw USDC again.`
          );
        }

        // Get swap quote
        const { quote, microUsdcOut, microUsdcMin } = await getSwapQuote(microAlgoNeeded, pool, 0.02);
        console.log("[autoSwap] quote: in", microAlgoNeeded, "microALGO, out", microUsdcOut, "microUSDC");

        // Build swap transactions via SDK
        const swapTxns = await buildSwapTxns(microAlgoNeeded, microUsdcMin, pool, quote, address);
        const swapTxnGroup = swapTxns.map(item => ({
          txn: item.txn ?? item,
          signers: item.signers ?? [address],
        }));

        // Sign swap group
        const signedSwap = await activeWallet.signTransaction([swapTxnGroup]);
        const rawSwap = Array.isArray(signedSwap) ? signedSwap.filter(Boolean) : [signedSwap];

        // Submit swap
        await algodClient.sendRawTransaction(rawSwap).do();
        const firstSwapTxn = swapTxns[0]?.txn ?? swapTxns[0];
        const swapTxId = typeof firstSwapTxn.txID === "function" ? firstSwapTxn.txID() : firstSwapTxn.txID;
        await algosdk.waitForConfirmation(algodClient, swapTxId, 8);
        addActivity(`Swapped ${(microAlgoNeeded/1e6).toFixed(6)} ALGO → ~${(microUsdcOut/1e6).toFixed(4)} USDC via Tinyman`);
        console.log("[autoSwap] swap confirmed:", swapTxId);

        // ── Step 4: Seed treasury + Draw USDC (atomic group) ──
        // The user now holds USDC received from Tinyman.
        // We send that USDC into the contract treasury, then draw_usdc
        // sends amountMicroUsdc back to Txn.sender (user's wallet).
        onStep?.("seeding", null);

        const actualSeed = microUsdcOut > 0 ? microUsdcOut : amountMicroUsdc;
        if (actualSeed <= 0) throw new Error("Swap returned 0 USDC — please retry");

        const signer = makeSigner();
        const spSeed = await algodClient.getTransactionParams().do();

        // AssetTransfer: user sends USDC to USDC contract (seeds the treasury)
        const seedAxfer = algosdk.makeAssetTransferTxnWithSuggestedParamsFromObject({
          sender: address,
          receiver: USDC_APP_ADDRESS,
          amount: BigInt(actualSeed),
          assetIndex: USDC_ASA_ID,
          suggestedParams: { ...spSeed, fee: 1000, flatFee: true },
        });
        const seedTws = { txn: seedAxfer, signer };

        const seedAndDrawAtc = new algosdk.AtomicTransactionComposer();

        // seed_treasury(axfer) — increments usdc_treasury_balance
        seedAndDrawAtc.addMethodCall({
          appID: USDC_APP_ID,
          method: new algosdk.ABIMethod(ABI_METHODS.seed_usdc_treasury),
          methodArgs: [seedTws],
          sender: address,
          suggestedParams: { ...spSeed, fee: 1000, flatFee: true },
          signer,
          foreignAssets: [USDC_ASA_ID],
        });

        // draw_usdc(amount, hash) — inner txn sends USDC to Txn.sender (user wallet)
        const drawAmt = Math.min(amountMicroUsdc, actualSeed);
        seedAndDrawAtc.addMethodCall({
          appID: USDC_APP_ID,
          method: new algosdk.ABIMethod(ABI_METHODS.draw_usdc),
          methodArgs: [BigInt(drawAmt), new Uint8Array(32)],
          sender: address,
          suggestedParams: { ...spSeed, fee: 2000, flatFee: true },
          signer,
          foreignAssets: [USDC_ASA_ID],
        });

        const seedDrawResult = await seedAndDrawAtc.execute(algodClient, 4);
        const finalTxId = seedDrawResult.txIDs?.[seedDrawResult.txIDs.length - 1];
        addActivity(`USDC draw: ${(drawAmt / 1e6).toFixed(4)} USDC delivered to wallet`);
        console.log("[autoSwap] seed+draw confirmed:", finalTxId);

        await fetchPosition(address);
        return finalTxId;
      } catch (err) {
        console.error("callAutoDrawUsdc error:", err);
        const usdcMsg = parseUsdcError(err?.message || String(err));
        const msg = usdcMsg || parseError(err);
        setError(msg);
        throw new Error(msg);
      } finally {
        setLoading(false);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [address, activeWallet, makeSigner, fetchPosition, checkAssetOptedIn, addActivity,
     algoUsdcRate, callDrawUsdc]
  );

  // ──────────────────────────────────────────────────────────────────────────
  // callDrawAndPay — x402 HTTP-native payment
  // Calls draw_and_pay(amount, payee, hash) to send USDC directly to a payee.
  // ──────────────────────────────────────────────────────────────────────────
  const callDrawAndPay = useCallback(
    async (amountMicroUsdc, payeeAddress) => {
      setLoading(true);
      setError(null);
      try {
        if (!activeWallet) throw new Error("No wallet connected");

        // Auto-opt-in to USDC ASA
        const optedIn = await checkAssetOptedIn(address, USDC_ASA_ID);
        if (!optedIn) {
          const spOpt = await algodClient.getTransactionParams().do();
          const optTxn = algosdk.makeAssetTransferTxnWithSuggestedParamsFromObject({
            sender: address,
            receiver: address,
            amount: 0n,
            assetIndex: USDC_ASA_ID,
            suggestedParams: { ...spOpt, fee: 1000, flatFee: true },
          });
          const signedOpt = await activeWallet.signTransaction([
            [{ txn: optTxn, signers: [address] }],
          ]);
          const rawToSend = Array.isArray(signedOpt) ? signedOpt.filter(Boolean) : [signedOpt];
          await algodClient.sendRawTransaction(rawToSend).do();
          await algosdk.waitForConfirmation(algodClient, optTxn.txID(), 4);
        }

        // Pre-flight check: verify payee account is opted in to USDC ASA
        const payeeOptedIn = await checkAssetOptedIn(payeeAddress, USDC_ASA_ID);
        if (!payeeOptedIn) {
          throw new Error(
            `Payee account (${payeeAddress.slice(0, 8)}...) is not opted in to USDC ASA ${USDC_ASA_ID}. Payee must opt in to receive USDC.`
          );
        }

        const atc = new algosdk.AtomicTransactionComposer();
        const sp = await algodClient.getTransactionParams().do();
        const signer = makeSigner();

        atc.addMethodCall({
          appID: USDC_APP_ID,
          method: new algosdk.ABIMethod(ABI_METHODS.draw_and_pay),
          sender: address,
          suggestedParams: { ...sp, fee: 2000, flatFee: true },
          signer,
          methodArgs: [BigInt(amountMicroUsdc), payeeAddress, new Uint8Array(32)],
          foreignAssets: [USDC_ASA_ID],
        });

        const result = await atc.execute(algodClient, 4);
        addActivity(`x402 pay: ${(amountMicroUsdc/1e6).toFixed(4)} USDC → ${payeeAddress.slice(0,8)}...`);
        await fetchPosition(address);
        return result.methodResults?.[0]?.txID ?? result.txIDs?.[0];
      } catch (err) {
        console.error("callDrawAndPay error:", err);
        const usdcMsg = parseUsdcError(err?.message || String(err));
        const msg = usdcMsg || parseError(err);
        setError(msg);
        throw new Error(msg);
      } finally {
        setLoading(false);
      }
    },
    [address, activeWallet, makeSigner, fetchPosition, checkAssetOptedIn, addActivity]
  );

  // ──────────────────────────────────────────
  // callRepayUsdc
  // Contract: repay_usdc(axfer: AssetTransferTransaction) → void
  // ──────────────────────────────────────────
  const callRepayUsdc = useCallback(
    async (amountMicroUsdc) => {
      setLoading(true);
      setError(null);
      try {
        if (!activeWallet) throw new Error("No wallet connected");

        const sp = await algodClient.getTransactionParams().do();
        const signer = makeSigner();
        const appAddress = USDC_APP_ADDRESS;

        // Build the AssetTransferTxn that sends USDC to the contract
        const axferTxn = algosdk.makeAssetTransferTxnWithSuggestedParamsFromObject({
          sender:    address,
          receiver:  appAddress,
          amount:    BigInt(amountMicroUsdc),
          assetIndex: USDC_ASA_ID,
          suggestedParams: { ...sp, fee: 1000, flatFee: true },
        });

        const atc = new algosdk.AtomicTransactionComposer();
        atc.addMethodCall({
          appID:      USDC_APP_ID,
          method:     new algosdk.ABIMethod(ABI_METHODS.repay_usdc),
          sender:     address,
          suggestedParams: { ...sp, fee: 1000, flatFee: true },
          signer,
          methodArgs: [{ txn: axferTxn, signer }],
          foreignAssets: [USDC_ASA_ID],
        });

        const result = await atc.execute(algodClient, 4);
        addActivity(`USDC repay: ${amountMicroUsdc} micro-USDC`);
        await fetchPosition(address);
        return result.txIDs?.[0] ?? result.methodResults?.[0]?.txID;
      } catch (err) {
        console.error("callRepayUsdc error:", err);
        const usdcMsg = parseUsdcError(err?.message || String(err));
        const msg = usdcMsg || parseError(err);
        setError(msg);
        throw new Error(msg);
      } finally {
        setLoading(false);
      }
    },
    [address, activeWallet, makeSigner, fetchPosition, addActivity]
  );

  return (
    <ContractContext.Provider
      value={{
        position,
        loading,
        error,
        activityLog,
        isOptedIn,
        currency,
        setCurrency,
        algoUsdcRate,
        walletBalance,
        fetchPosition,
        callRegister,
        callRegisterUnified,
        callRegisterUsdc,
        callBorrowAndStakeUsdc,
        callRecordPayment,
        callDraw,
        callRepay,
        callSlash,
        fetchUsdcPosition,
        callDrawUsdc,
        callAutoDrawUsdc,
        callDrawAndPay,
        callRepayUsdc,
      }}
    >
      {children}
    </ContractContext.Provider>
  );
}

export function useContract() {
  const ctx = useContext(ContractContext);
  if (!ctx) {
    throw new Error("useContract must be used inside ContractProvider");
  }
  return ctx;
}
