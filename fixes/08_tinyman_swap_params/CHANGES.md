# Fix 08 — buildSwapTxns ignores microAlgoIn parameter

## Problem (tinyman.js lines 118-130)
export async function buildSwapTxns(microAlgoIn, microUsdcMin, pool, quote, userAddress) {
  const txns = await Swap.v2.generateTxns({
    client: algodClient,
    pool,
    swapType: SwapType.FixedInput,
    assetIn:  { ...ALGO_ASSET, id: ALGO_ASA_ID },
    assetOut: { ...USDC_ASSET, id: USDC_ASA_ID },
    initiatorAddr: userAddress,
    slippage: 0.02,
    ...(quote ? { quote } : {}),
  });
  return txns;
}

The function signature accepts microAlgoIn and microUsdcMin as parameters,
but neither is passed to Swap.v2.generateTxns. When a quote is provided,
the SDK uses the quote's amount — that's correct. But when quote is null
(fallback path), no amount is specified at all, which causes the SDK to either
error or use a default of 0.

## Fix
Always pass the input amount to generateTxns. The Tinyman v2 SDK accepts
mount or uses the quote's amount — passing both is safe.

## Patch
