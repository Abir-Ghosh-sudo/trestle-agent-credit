# Fix 03 — USDC_APP_ID=0 fallback fails silently

## Problem
In frontend/src/lib/contract.js:
  export const USDC_APP_ID = requireEnvNumber('VITE_USDC_APP_ID', 0);

The fallback is 0. When VITE_USDC_APP_ID is not set, every algosdk call
using USDC_APP_ID silently sends transactions to app ID 0 (which is invalid).
The app warns in dev mode, but the error appears only in the console.

## Fix
1. Change fallback to -1 (or throw) so the warning is more visible.
2. Add a runtime guard in ContractState.jsx: if USDC_APP_ID <= 0, skip USDC
   position fetch and show a user-visible banner instead of a silent error.
3. In the UI, show a disabled state / informational badge when USDC contract
   is not configured.

## Affected files
- frontend/src/lib/contract.js        [MODIFY]
- frontend/src/state/ContractState.jsx [MODIFY — guard fetchPosition]
