/**
 * algod.js — Algorand client instances and transaction utilities.
 *
 * Uses Algonode public testnet endpoints (no API key needed).
 * Compatible with algosdk v3 (camelCase response fields).
 */

import algosdk from "algosdk";
import { TESTNET_ALGOD, TESTNET_INDEXER } from "./contract.js";

// algosdk v3: pass token, server, port. Port as string or number both work.
export const algodClient = new algosdk.Algodv2("", TESTNET_ALGOD, "");

export const indexerClient = new algosdk.Indexer("", TESTNET_INDEXER, "");

/**
 * Wait for a transaction to be confirmed on-chain.
 * algosdk v3 uses camelCase field names in responses.
 */
export async function waitForConfirmation(txId) {
  const status = await algodClient.status().do();
  // v3: last-round is still hyphenated in status()
  let lastRound = status["last-round"];

  // eslint-disable-next-line no-constant-condition
  while (true) {
    const result = await algodClient.pendingTransactionInformation(txId).do();

    // algosdk v3 response uses camelCase
    const confirmedRound =
      result["confirmed-round"] ?? result["confirmedRound"];
    const poolError = result["pool-error"] ?? result["poolError"];

    if (confirmedRound && confirmedRound > 0) {
      return result;
    }
    if (poolError) {
      throw new Error(`Transaction failed: ${poolError}`);
    }
    await algodClient.statusAfterBlock(lastRound + 1).do();
    lastRound++;
  }
}

/**
 * Get full account info for an address.
 */
export async function getAccountInfo(address) {
  return algodClient.accountInformation(address).do();
}
