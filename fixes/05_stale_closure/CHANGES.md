# Fix 05 — callAutoDrawUsdc reads stale position from React closure

## Problem (ContractState.jsx lines 1159-1169)
callAutoDrawUsdc has a comment acknowledging the issue:
  // NOTE: position is a React state snapshot — read from algod directly
  // to avoid stale closure issue.

But line 1168 still has a fallback:
  liveTreasuryBal = Number(position.usdcTreasuryBalance);

If the algod call fails, it falls back to the stale React state value of
position.usdcTreasuryBalance from the closure (which may be 0 from the initial
DEFAULT_POSITION or from a previous render). This can incorrectly trigger the
swap flow even when the treasury is adequately funded.

## Root cause
The useCallback dependency array on line 1331-1332 includes
position.usdcTreasuryBalance, which causes the callback to re-create on
every treasury balance update — but the stale value is still used as fallback.

## Fix
Remove position.usdcTreasuryBalance from the dependency array and use a ref
pattern, OR simply throw on algod failure rather than silently using stale data.

## Patch
