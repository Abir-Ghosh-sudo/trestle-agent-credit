# Notice

Trestle is derived from **Bloopa**, originally created by ShahiTechnovation and
released under the MIT License. The original license terms and copyright
notice are preserved in `trestle_sdk/LICENSE` as required.

## What changed in this fork

- Full rebrand: Bloopa -> Credixa -> Trestle (naming, metadata, on-chain contract
  labels in source -- see note below on compiled artifacts)
- Complete UI rebuild: new component architecture, new design system
  (glassmorphism / soft-3D / gradient visual language), new typography,
  new color system, new iconography and illustration placeholders
- Codebase reorganized into a feature-based structure with renamed
  files, components, and functions for clarity
- Business logic (wallet connection, contract calls, scoring/credit flow,
  x402 payment flow) preserved functionally -- renamed for clarity but not
  behaviorally altered

## Known limitation

The compiled `.teal` contract bytecode and ARC-56 ABI under `contracts/`
still reflect the actually-deployed testnet contract (it cannot be safely
renamed post-compilation without redeploying). Source files (`trestle_router.py`,
`trestle_usdc.py`) are renamed and ready to redeploy under the new brand --
run `contracts/deploy.py` to mint a fresh App ID under this identity.

## Frontend architecture (post-transformation)

```
frontend/src/
  App.jsx, main.jsx, index.css   — app shell & design tokens
  assets/                        — logo mark, static images
  components/
    layout/                      — NavigationBar, StatusBar, SegmentedTabs
    ui/                          — Button, Input, Toast, StatCard, Skeleton
  features/
    marketing/    MarketingHome.jsx
    onboarding/   AgentOnboarding.jsx
    dashboard/    CreditPositionDashboard.jsx
    credit-score/ CreditScorePanel.jsx
    payments/     PaymentGatewayPanel.jsx
    docs/         DocsEntry / DocsShellLayout / DocsContent / OracleReferenceDocs
  state/                         — WalletState.jsx, ContractState.jsx (wallet + on-chain logic)
  lib/                           — algod.js, contract.js, format.js, tinyman.js, crypto-shim.js
```

`state/` and `lib/` contain the actual wallet-connection and contract-call logic —
these were relocated and had their surrounding files renamed for clarity, but
the exported hook/function names (`useWallet`, `useContract`, etc.) and their
internal behavior were intentionally left unchanged, since this is the layer
that talks to the real Algorand contracts and can't be safely rewritten
without a live testnet to verify against.

Original project: https://github.com/<original-org>/Bloopa
