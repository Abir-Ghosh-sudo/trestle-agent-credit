# Trestle — Bug-Fix and Improvement Folder

This folder tracks every bug, inconsistency, and missing feature found in a
full static analysis of the codebase. Each sub-folder contains a short
description and patched source file(s) with a CHANGES.md explaining why.

| # | Sub-folder | Severity | Area | Summary |
|---|------------|----------|------|---------|
| 1 | 01_tab_routing | HIGH | Frontend routing | PaymentGatewayPanel is unreachable — no tab entry |
| 2 | 02_env_secret_exposure | HIGH | Security | AGENT_MNEMONIC and VENICE_API_KEY in frontend/.env — leaked to bundle |
| 3 | 03_usdc_app_id_zero | HIGH | Frontend config | USDC_APP_ID=0 fallback passes silently, all USDC calls fail |
| 4 | 04_registration_redirect | MEDIUM | Frontend routing | AgentOnboarding says Redirecting but never actually redirects |
| 5 | 05_stale_closure | MEDIUM | ContractState | callAutoDrawUsdc references stale position state |
| 6 | 06_drawandpay_txnid | MEDIUM | ContractState | callDrawAndPay returns wrong txn ID (axfer instead of app-call) |
| 7 | 07_isdefaulted_parse | LOW | ContractState | isDefaulted parsed with === 1n, should be > 0n |
| 8 | 08_tinyman_swap_params | LOW | Tinyman | buildSwapTxns ignores microAlgoIn param |
| 9 | 09_missing_payment_tab | HIGH | Frontend UI | No Payment/x402 tab exposed in SegmentedTabs |
