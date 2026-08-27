# Changelog

All notable changes to `trestle-sdk` will be documented in this file.
This project adheres to [Semantic Versioning](https://semver.org/).

---

## [0.1.0] — 2026-05-15

### Added
- `TrestleCreditAgent` — one-liner interface wrapping oracle + chain calls
- `RiskOracle` — LLM-agnostic risk oracle with Venice AI (default) and Anthropic backends
- `RiskDecision` dataclass — structured oracle output with attestation hash ready for `draw()`
- `CriteriaEvaluation` Pydantic model — structured LLM output for all four criteria
- `TrestleCreditDenied` and `TrestleCreditError` custom exceptions
- Four-criteria risk gate: profitability, time-bounded, debt-free, task risk level
- Tier system: Fresh / Trusted / Veteran / Elite with dynamic APR and draw caps
- `chain.py` — all algosdk interactions (get_position, draw, repay, record_payment, register)
- `oracle.py` — Venice AI (OpenAI-compatible) and Anthropic structured-output paths
- `criteria.py` — pure-Python tier math matching on-chain AVM formulas exactly
- `hash_util.py` — attestation hash computation (SHA-256) and demo-mode zero hash
- `py.typed` marker — full PEP 561 type annotation support
- Demo mode (`demo_mode=True`) — zero-hash bypass for testnet without on-chain verification
- Production mode (`demo_mode=False`) — real SHA-256 attestation hash for mainnet

### Changed
- N/A (initial release)

### Fixed
- N/A (initial release)
