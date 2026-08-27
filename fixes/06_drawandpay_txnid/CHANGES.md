# Fix 06 — callDrawAndPay returns the wrong txn ID

## Problem (ContractState.jsx line 1390)
  return result.txIDs?.[0];

When an AtomicTransactionComposer (ATC) group is executed, esult.txIDs lists
IDs in the order the transactions were added. In callDrawAndPay, the ONLY
transaction added is the addMethodCall for draw_and_pay. However, the inner
transaction (the USDC asset transfer issued by the contract) is a separate
inner txn and does NOT appear in esult.txIDs.

esult.txIDs[0] is therefore the ID of the app-call outer txn — which is
correct — BUT PaymentGatewayPanel then constructs a Pera explorer link:
  https://testnet.explorer.perawallet.app/tx/
This link correctly points to the outer app-call txn. ?

The real risk: if there are multiple txns in the group (e.g. an auto-opt-in
that was added), txIDs[0] would be the opt-in txn, not the draw_and_pay txn.

## Fix
Use esult.methodResults[0]?.txID which always returns the method-call txn ID
regardless of group position, rather than positional 	xIDs[0].

## Patch
