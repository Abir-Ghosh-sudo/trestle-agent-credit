# Trestle — Architecture Reference

**Stack:** Algorand (AVM) · Python 3.11+ · React 18 · x402  
**Network:** Algorand Testnet · App ID `<YOUR_APP_ID>`  
**SDK:** v0.2.0

---

## Table of Contents

1. [High-Level System Diagram](#1-high-level-system-diagram)
2. [Repository Map](#2-repository-map)
3. [On-Chain Layer — Smart Contracts](#3-on-chain-layer--smart-contracts)
   - 3.1 [Trestle Core Contract](#31-trestle-core-contract-contractspy)
   - 3.2 [TrestleIntentRouter Contract](#32-trestleintentrouter-contract-trestle_routerpy)
4. [SDK Layer — `trestle_sdk` Package](#4-sdk-layer--trestle_sdk-package)
   - 4.1 [Module Dependency Graph](#41-module-dependency-graph)
   - 4.2 [`criteria.py` — Tier System Constants](#42-criteriapy--tier-system-constants)
   - 4.3 [`hash_util.py` — Attestation Hash](#43-hash_utilpy--attestation-hash)
   - 4.4 [`chain.py` — ABI Call Wrappers](#44-chainpy--abi-call-wrappers)
   - 4.5 [`oracle.py` — LLM Risk Oracle](#45-oraclepy--llm-risk-oracle)
   - 4.6 [`agent.py` — TrestleCreditAgent](#46-agentpy--trestleckeditagent)
   - 4.7 [`exceptions.py` — Exception Hierarchy](#47-exceptionspy--exception-hierarchy)
   - 4.8 [`x402_client.py` — TrestleX402Client](#48-x402_clientpy--trestlex402client)
   - 4.9 [`intent_agent.py` — Intent Market Stack](#49-intent_agentpy--intent-market-stack)
   - 4.10 [`cli.py` — `trestle init` Command](#410-clipy--trestle-init-command)
   - 4.11 [`__init__.py` — Public Surface](#411-__init__py--public-surface)
5. [Frontend Layer — React Dashboard](#5-frontend-layer--react-dashboard)
6. [Data Flows](#6-data-flows)
   - 6.1 [Core Credit Flow: `draw()` → `repay()`](#61-core-credit-flow-draw--repay)
   - 6.2 [x402 HTTP-Native Payment Flow](#62-x402-http-native-payment-flow)
   - 6.3 [Intent Market Flow](#63-intent-market-flow)
7. [Tier System](#7-tier-system)
8. [Security Model](#8-security-model)
9. [Key Constants Cross-Reference](#9-key-constants-cross-reference)
10. [Deployment Checklist](#10-deployment-checklist)

---

## 1. High-Level System Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                          AI AGENT PROCESS                           │
│                                                                     │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │               trestle_sdk  (Python Package)                  │   │
│   │                                                             │   │
│   │  TrestleCreditAgent ──► RiskOracle ──► Venice AI / Anthropic │   │
│   │         │                   │              (LLM)            │   │
│   │         ▼                   ▼                               │   │
│   │      chain.py ◄── CriteriaEvaluation                       │   │
│   │         │                                                   │   │
│   │  TrestleX402Client ──► _TinymanSwap ──► Tinyman v2 Pool      │   │
│   │  (x402 payments)    _CredixAvmSigner                        │   │
│   │                                                             │   │
│   │  IntentListener ──► IntentBrain ──► IntentExecutor          │   │
│   │  (indexer poll)     (oracle eval)   (orchestrator)         │   │
│   └─────────────────────────────────────────────────────────────┘   │
│                │                    │                               │
└────────────────┼────────────────────┼───────────────────────────────┘
                 │                    │
     ┌───────────▼──────┐    ┌────────▼──────────────┐
     │  Algorand Testnet│    │  GoPlausible x402      │
     │                  │    │  Facilitator           │
     │  ┌────────────┐  │    │  facilitator.          │
     │  │  Trestle    │  │    │  goplausible.xyz       │
     │  │  Contract  │  │    │  POST /verify          │
     │  │  App ID:   │  │    │  POST /settle          │
     │  │ <YOUR_APP_ID>  │  │    └────────────────────────┘
     │  └────────────┘  │
     │  ┌────────────┐  │    ┌────────────────────────┐
     │  │  Intent    │  │    │  Algonode Indexer       │
     │  │  Router    │  │    │  testnet-idx.           │
     │  │  Contract  │  │    │  algonode.cloud         │
     │  └────────────┘  │    │  (REST polling)         │
     │  ┌────────────┐  │    └────────────────────────┘
     │  │  Tinyman   │  │
     │  │  v2 AMM    │  │    ┌────────────────────────┐
     │  │App:160363k │  │    │  Frontend (React)      │
     │  └────────────┘  │    │  Vite + Tailwind       │
     └──────────────────┘    │  Register / Dashboard  │
                             └────────────────────────┘
```

---

## 2. Repository Map

```
Trestle/
│
├── trestle_sdk/                  # Python package (pip install trestle-sdk)
│   ├── __init__.py              # Public surface + lazy __getattr__ for x402
│   ├── pyproject.toml           # Build config, dependencies, CLI entry point
│   ├── agent.py                 # TrestleCreditAgent — main public class
│   ├── oracle.py                # RiskOracle, CriteriaEvaluation, RiskDecision
│   ├── chain.py                 # All algosdk ABI calls (draw, repay, etc.)
│   ├── criteria.py              # Pure-Python tier constants (mirrors contract)
│   ├── hash_util.py             # Attestation hash + algod round query
│   ├── exceptions.py            # TrestleCreditError hierarchy + x402 errors
│   ├── x402_client.py           # TrestleX402Client, _TinymanSwap, _CredixAvmSigner
│   ├── intent_agent.py          # IntentListener, IntentBrain, IntentExecutor
│   ├── cli.py                   # `trestle init` CLI command (Click)
│   ├── py.typed                 # PEP 561 typed marker
│   └── README.md / CHANGELOG.md
│
├── contracts/
│   ├── contract.py              # Trestle ARC-4 contract (Puya / Algorand Python)
│   ├── trestle_router.py         # TrestleIntentRouter ARC-4 contract
│   ├── deploy.py                # Deployment script for core contract
│   ├── deploy_router.py         # Deployment script for Router
│   ├── demo_agent.py            # Interactive step-by-step setup script
│   ├── Trestle.approval.teal     # Compiled TEAL (approval program)
│   ├── Trestle.clear.teal        # Compiled TEAL (clear program)
│   └── Trestle.arc56.json        # ARC-56 interface descriptor
│
├── demo/
│   ├── x402_demo.py             # Live x402 payment demo (GoPlausible testnet)
│   ├── intent_demo.py           # End-to-end Intent Router demo
│   ├── demo_with_skill.py       # Combined skill + credit demo
│   └── demo_narration.md        # Demo video script & narration guide
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx              # React router root
│   │   ├── main.jsx             # Vite entry point
│   │   ├── index.css            # Global CSS (Tailwind-based)
│   │   ├── components/
│   │   │   ├── LandingPage.jsx  # Hero / marketing page
│   │   │   ├── Dashboard.jsx    # Agent position + draw UI
│   │   │   ├── Register.jsx     # Wallet registration wizard
│   │   │   ├── ScoreView.jsx    # Credit score visualisation
│   │   │   ├── Header.jsx       # Nav bar
│   │   │   ├── Footer.jsx       # Footer
│   │   │   └── TabBar.jsx       # Mobile tab navigation
│   │   ├── context/             # React context (wallet state)
│   │   └── utils/               # Algod / indexer helpers
│   ├── package.json             # Vite + Tailwind frontend
│   └── vite.config.js
│
├── skills/trestle-credit/
│   └── SKILL.md                 # Claude Skill definition (8 sections)
│
├── tests/                       # Unit and integration tests
│   ├── test_criteria.py         # Pure unit tests for criteria module
│   ├── test_sdk.py              # SDK integration tests
│   ├── test_oracle.py           # Oracle unit tests (Venice AI / Anthropic)
│   └── test_x402_client.py      # x402 client unit tests (24 tests)
│
├── README.md                    # Project overview
└── vercel.json                  # Frontend deployment config
```

---

## 3. On-Chain Layer — Smart Contracts

### 3.1 Trestle Core Contract (`contracts/contract.py`)

**Language:** Algorand Python (Puya compiler) → compiled to TEAL  
**ARC standard:** ARC-4 (ABI methods + events)  
**App ID (testnet):** `<YOUR_APP_ID>`

#### State Schema

| Scope | Key | Type | Description |
|-------|-----|------|-------------|
| **Global** | `treasury_balance` | UInt64 | Total ALGO held for draws |
| **Global** | `total_agents` | UInt64 | Number of registered agents |
| **Global** | `skip_attestation` | UInt64 | 1 = demo mode (bypass hash check) |
| **Global** | `protocol_signer` | Account | Address that signs attestation hashes |
| **Local** | `stake_amount` | UInt64 | ALGO staked by agent (microALGO) |
| **Local** | `payment_count` | UInt64 | Number of completed repayments |
| **Local** | `total_repaid` | UInt64 | Cumulative repayment amount |
| **Local** | `outstanding` | UInt64 | Current unpaid balance (principal + interest) |
| **Local** | `is_defaulted` | UInt64 | 1 = slashed/defaulted |
| **Local** | `last_payment_round` | UInt64 | Round of last payment |
| **Local** | `daily_drawn` | UInt64 | Amount drawn today (for daily cap) |
| **Local** | `day_start_round` | UInt64 | Round when current 24h window started |
| **Local** | `repay_by_round` | UInt64 | Repayment deadline (day_start + 86400) |

#### ABI Methods

| Method Signature | Description |
|-----------------|-------------|
| `opt_in()` (bare) | Initialise 9 local state slots to zero |
| `register(pay)void` | Stake ALGO ≥ 1 ALGO to open credit line |
| `record_payment(uint64)uint64` | Increment payment_count, return new tier |
| `draw(uint64,byte[32])void` | Draw credit; inner txn sends ALGO to agent |
| `repay(pay)void` | Repay outstanding via payment txn to escrow |
| `slash(account)void` | Anyone slashes delinquent agent (10% reward) |
| `get_position(address)(9×uint64)` | Read-only position query (simulate) |
| `seed_treasury(pay)void` | Creator-only: fund the draw pool |
| `set_signer(address)void` | Creator-only: set attestation signer |
| `enable_attestation()void` | Creator-only: disable demo bypass |

#### ARC-4 Events

| Event | Fields | Fired On |
|-------|--------|----------|
| `AgentRegistered` | agent, stake | `register()` |
| `PaymentRecorded` | agent, amount, tier | `record_payment()` |
| `CreditDrawn` | agent, amount, interest, outstanding | `draw()` |
| `Repaid` | agent, amount, outstanding | `repay()` |
| `AgentSlashed` | agent, stake_burned, caller_reward | `slash()` |

#### Attestation Verification (Production Mode)

When `skip_attestation == 0`, `draw()` verifies:
```
sha256(decode_address(sender) + itob(amount) + itob(current_round)) == attestation_hash
```
This hash must be computed off-chain in `hash_util.compute_attestation_hash()` and signed by the protocol signer (a Claude Skill in production, or `bytes(32)` in demo mode).

---

### 3.2 TrestleIntentRouter Contract (`contracts/trestle_router.py`)

**Language:** Algorand Python (Puya)  
**Storage:** BoxMap keyed by `b"I" + UInt64(intent_id).bytes`

#### Intent Struct (ARC-4, 192 bytes packed)

```
locker          arc4.Address    (32 bytes) — user who posted the intent
payment_amount  arc4.UInt64     ( 8 bytes) — ALGO locked in Router escrow
api_cost        arc4.UInt64     ( 8 bytes) — amount solver borrows from Trestle
expiry_round    arc4.UInt64     ( 8 bytes) — deadline round
task_hash       byte[32]        (32 bytes) — sha256 of task params
solver_address  arc4.Address    (32 bytes) — ONLY this address can fulfill
assigned_agent  arc4.Address    (32 bytes) — set when solver claims
result_hash     byte[32]        (32 bytes) — set on settle
state           arc4.UInt64     ( 8 bytes) — 0=open 1=assigned 2=settled 3=expired
```

#### Intent Lifecycle Methods

| Method | Actor | Description |
|--------|-------|-------------|
| `lock_intent(pay,byte[32],uint64,uint64,address)uint64` | User (locker) | Lock ALGO, create private order |
| `borrow_to_execute(uint64,string,uint64)bool` | Named solver only | Claim intent (state 0→1) |
| `settle(uint64,byte[32],string)bool` | Assigned solver | Atomic: repay Trestle + profit to solver + record_payment |
| `reclaim_expired(uint64)bool` | Locker | Reclaim funds after expiry; slash assigned solver if any |
| `get_intent(uint64)Intent` | Anyone (readonly) | Read full Intent struct |

#### `settle()` Inner Transaction Group

```
[0] itxn.Payment → Trestle app address   (repayment: api_cost + interest)
[1] itxn.Payment → Txn.sender (solver)  (profit: payment - repayment)
[2] itxn.ApplicationCall → Trestle       (record_payment to build solver tier)
```

---

## 4. SDK Layer — `trestle_sdk` Package

### 4.1 Module Dependency Graph

```
__init__.py
    ├── agent.py
    │     ├── oracle.py
    │     │     ├── criteria.py      (tier math)
    │     │     ├── hash_util.py     (attestation)
    │     │     └── exceptions.py
    │     └── chain.py               (all algosdk ABI)
    ├── exceptions.py
    ├── criteria.py
    └── [lazy] x402_client.py        (optional: pip install trestle-sdk[x402])
              ├── agent.py
              └── exceptions.py

intent_agent.py                       (standalone — no x402 dependency)
    ├── agent.py
    ├── criteria.py
    └── exceptions.py

cli.py                                (standalone CLI)
    └── chain.py
```

**Dependency layers (strict order, no cycles):**

| Layer | Modules | Imports |
|-------|---------|---------|
| 0 — Pure constants | `criteria.py` | stdlib only |
| 1 — Utilities | `hash_util.py`, `exceptions.py` | stdlib + algosdk |
| 2 — Chain | `chain.py` | algosdk + layer 1 |
| 3 — Oracle | `oracle.py` | openai/anthropic + layer 0-1 |
| 4 — Agent | `agent.py` | layers 2-3 |
| 5 — Clients | `x402_client.py`, `intent_agent.py` | layer 4 |
| 6 — Interface | `__init__.py`, `cli.py` | all layers |

---

### 4.2 `criteria.py` — Tier System Constants

**File:** `trestle_sdk/criteria.py`

Pure-Python constants that **must exactly mirror** the on-chain contract. No algosdk or LLM imports.

| Constant | Value |
|----------|-------|
| `TIER_THRESHOLDS` | `[0, 10, 50, 100]` — payment_count required |
| `TIER_MAX_DRAW` | `[100_000, 500_000, 2_000_000, 5_000_000]` μALGO |
| `TIER_DAILY_CAP` | `[500_000, 2_000_000, 10_000_000, 25_000_000]` μALGO |
| `TIER_APR_BPS` | `[2400, 1600, 900, 400]` basis points |
| `TIER_NAMES` | `["Fresh", "Trusted", "Veteran", "Elite"]` |
| `DAY_IN_ROUNDS` | `86_400` |
| `ROUNDS_PER_YEAR` | `31_536_000` |

**Interest formula (matches AVM floor division exactly):**
```python
interest = (amount * APR_bps * DAY_IN_ROUNDS) // (10_000 * ROUNDS_PER_YEAR)
```

**Functions:** `get_tier(payment_count)`, `max_draw(tier)`, `daily_cap(tier)`, `apr_bps(tier)`, `calculate_interest(amount, tier)`, `tier_name(tier)`

---

### 4.3 `hash_util.py` — Attestation Hash

**File:** `trestle_sdk/hash_util.py`

| Function | Description |
|----------|-------------|
| `get_current_round(algod_client)` | Query `algod.status()["last-round"]` |
| `compute_attestation_hash(sender, amount, round)` | `sha256(addr_bytes + itob(amount) + itob(round))` — matches on-chain formula |
| `demo_hash()` | Returns `bytes(32)` — used when `skip_attestation == 1` |

The 32-byte attestation hash is the only on-chain security mechanism that prevents unauthorized draws in production mode.

---

### 4.4 `chain.py` — ABI Call Wrappers

**File:** `trestle_sdk/chain.py`

**No LLM calls. No criteria logic. Pure algosdk mechanics.**

All ABI method objects are parsed once at module level:
```python
METHOD_REGISTER        = Method.from_signature("register(pay)void")
METHOD_RECORD_PAYMENT  = Method.from_signature("record_payment(uint64)uint64")
METHOD_DRAW            = Method.from_signature("draw(uint64,byte[32])void")
METHOD_REPAY           = Method.from_signature("repay(pay)void")
METHOD_GET_POSITION    = Method.from_signature("get_position(address)(9×uint64)")
```

| Function | How | Returns |
|----------|-----|---------|
| `make_algod_client(url)` | Direct | `AlgodClient` |
| `address_from_mnemonic(phrase)` | `mnemonic.to_private_key` | `str` |
| `private_key_from_mnemonic(phrase)` | `mnemonic.to_private_key` | `str` |
| `get_app_address(app_id)` | `logic.get_application_address` | `str` |
| `get_position(algod, app_id, addr, signer)` | **ATC simulate** (no fees) | `dict[str, int]` |
| `do_draw(algod, app_id, addr, key, amount, attest)` | ATC execute | `txid: str` |
| `do_repay(algod, app_id, addr, key, amount)` | ATC execute (pay txn) | `txid: str` |
| `do_record_payment(algod, app_id, addr, key, amount)` | ATC execute | `new_tier: int` |
| `do_register(algod, app_id, addr, key, stake)` | ATC execute (pay txn) | `txid: str` |

Note: `get_position()` uses `atc.simulate()` rather than `execute()` — this means it costs no fees and doesn't consume a round, so it's safe to call frequently.

---

### 4.5 `oracle.py` — LLM Risk Oracle

**File:** `trestle_sdk/oracle.py`

The oracle is the **immutable AI gatekeeper** — all four criteria are hardcoded. Agent developers cannot override them.

#### Provider Selection

```
ORACLE_PROVIDER=venice      → Venice AI  (llama-3.3-70b, OpenAI-compatible)
ORACLE_PROVIDER=anthropic   → Anthropic  (claude-haiku-4-5-20251001)
```

#### CriteriaEvaluation (Pydantic BaseModel)

All 7 fields are mandatory. The LLM fills them for every `evaluate()` call:

| Field | Type | Oracle Check |
|-------|------|-------------|
| `criterion_1_passed` | bool | `expected_return > amount + interest` |
| `criterion_2_passed` | bool | `estimated_rounds < 86_400` |
| `criterion_3_passed` | bool | `outstanding == 0` |
| `criterion_4_passed` | bool | task risk level is `low` or `medium` |
| `overall_approved` | bool | strict AND of all four |
| `task_risk_level` | str | `low / medium / high / critical` |
| `denial_reason` | str | which criterion failed |
| `risk_summary` | str | one-sentence log-friendly summary |

#### RiskDecision (dataclass)

Returned only when `overall_approved == True`. Contains `attestation_hash: bytes` (32 bytes) ready to pass directly to `chain.do_draw()`.

#### evaluate() Flow

```
1. Pre-flight tier cap check (no API cost if obviously over-limit)
2. Build user_message string with all draw parameters
3. _call_oracle(user_message) → CriteriaEvaluation
   Venice path:  openai.chat.completions.create() → parse raw JSON → Pydantic
   Anthropic path: client.beta.messages.parse(response_model=CriteriaEvaluation)
4. If not approved → raise TrestleCreditDenied(reason, criteria_results)
5. Compute attestation hash (demo_hash() in demo mode)
6. Return RiskDecision
```

---

### 4.6 `agent.py` — TrestleCreditAgent

**File:** `trestle_sdk/agent.py`

The **single public class** that wraps oracle + chain into one interface.

```python
agent = TrestleCreditAgent(mnemonic_phrase="...", app_id=<YOUR_APP_ID>)
```

#### Constructor Parameters

| Param | Default | Description |
|-------|---------|-------------|
| `mnemonic_phrase` | required | 25-word Algorand mnemonic |
| `app_id` | required | Trestle contract App ID |
| `algod_url` | `algonode testnet` | Algod REST endpoint |
| `demo_mode` | `True` | If True, attestation hash = `bytes(32)` |

#### Exposes

| Attribute | Type | Description |
|-----------|------|-------------|
| `address` | `str` | 58-char Algorand address |
| `private_key` | `str` | base64 private key |
| `algod_client` | `AlgodClient` | for external use (x402_client, intent_agent) |
| `signer` | `AccountTransactionSigner` | for ATC calls |
| `oracle` | `RiskOracle` | for intent_agent direct oracle access |
| `app_id` | `int` | Trestle contract App ID |

#### Methods

| Method | Description |
|--------|-------------|
| `get_position()` | Reads 9-field position dict from on-chain (simulate) |
| `draw(amount, task_desc, expected_return, rounds)` | Oracle eval + on-chain draw; returns result dict |
| `repay(amount)` | Pay back outstanding to contract escrow |
| `record_payment(amount=1000)` | Increment payment_count → tier advancement |

---

### 4.7 `exceptions.py` — Exception Hierarchy

**File:** `trestle_sdk/exceptions.py`

```
Exception
└── TrestleCreditError                   # base for all SDK errors
    ├── TrestleCreditDenied              # oracle denied; has .reason + .criteria_results
    ├── TrestleX402SpendLimitExceeded     # 402 price > max_spend_per_call; fires BEFORE draw()
    ├── TrestleX402PaymentError           # facilitator or network failure; fires AFTER draw()
    └── TrestleX402SetupError             # opt-in or auto-swap failed; fires BEFORE draw()
```

All four x402 errors inherit from `TrestleCreditError` so `except TrestleCreditError` catches everything.

---

### 4.8 `x402_client.py` — TrestleX402Client

**File:** `trestle_sdk/x402_client.py` (optional — requires `pip install "trestle-sdk[x402]"`)

**Three classes** with strict internal privacy:

#### `_TinymanSwap` (private)

Reads Tinyman v2 pool global state directly via algod, applies constant-product formula with 0.3% fee + 5% slippage buffer. Falls back to fixed 2.5× rate if pool is unreachable.

```
Pool App ID: 160_363_393 (ALGO/USDC v2 testnet)
Swap group:  [0] PaymentTxn  ALGO → pool address
             [1] ApplicationNoOpTxn  pool.swap(USDC_ASA, min_out)
```

#### `_CredixAvmSigner` (private)

Bridges Trestle's algosdk wallet to the `x402-avm` library's `ClientAvmSigner` protocol.

One subtlety here: `algosdk.encoding.msgpack_decode()` expects a base64 string, not raw bytes. The bridge converts back and forth:
```python
b64_str = base64.b64encode(txn_bytes).decode()   # raw → b64
txn_obj = encoding.msgpack_decode(b64_str)        # decode
signed_b64 = encoding.msgpack_encode(signed_txn)  # encode → b64
signed_bytes = base64.b64decode(signed_b64)        # b64 → raw
```

#### `TrestleX402Client` (public)

| Mode | Methods |
|------|---------|
| Sync (wraps asyncio) | `get(url)`, `post(url)`, `request(method, url)` |
| Async | `aget(url)`, `arequest(method, url)` |

**Payment lifecycle (`arequest`):**
```
1. HTTP request → 402?
   No  → return response
   Yes → parse paymentRequirements JSON
2. Spend guard   → if amount > max_spend_per_call → TrestleX402SpendLimitExceeded
3. USDC opt-in   → auto self-axfer if not opted-in (on __init__)
4. USDC balance  → auto Tinyman swap if insufficient (auto_swap=True)
5. agent.draw()  → record credit (accounting) + auto repay
6. _build_x_payment_header() → sign axfer, encode base64 JSON
7. Retry with X-PAYMENT header
8. 200 → agent.record_payment() → return response
   else → TrestleX402PaymentError
```

**X-PAYMENT header format:**
```json
base64(JSON({
  "x402Version": 1,
  "scheme": "exact",
  "payload": {
    "paymentGroup": ["<base64 signed axfer>", "<base64 fee payer>"],
    "paymentIndex": 0
  }
}))
```

**GoPlausible testnet constants:**

| Constant | Value |
|----------|-------|
| Facilitator URL | `https://facilitator.goplausible.xyz` |
| Testnet network (CAIP-2) | `algorand:SGO1GKSzyE7IEPItTxCByw9x8FmnrCDexi9/cOUJOiI=` |
| USDC ASA (testnet) | `10_458_941` |
| USDC ASA (mainnet) | `31_566_704` |
| Tinyman pool app | `160_363_393` |

---

### 4.9 `intent_agent.py` — Intent Market Stack

**File:** `trestle_sdk/intent_agent.py`

Three cooperating classes that implement a solver bot:

#### `IntentListener`

Polls Algonode indexer REST for `LogIntentLocked:` log prefix on the Router app. Decodes ARC-4 encoded Intent structs from box storage (192-byte fixed layout). Filters by `solver_address`.

```
Poll: GET /v2/transactions?application-id=ROUTER&note-prefix=base64(LogIntentLocked:)
Box:  GET /v2/applications/ROUTER/box?name=b64:SSxxxxxxxx
```

#### `IntentBrain`

Four pre-checks (in-memory, fast) before invoking the LLM oracle:

| Pre-check | Condition to reject |
|-----------|---------------------|
| Time window | `expiry - current_round <= time_buffer_rounds` |
| Profit ratio | `(payment - api_cost) / payment < min_profit_ratio` |
| No debt | `agent.get_position()["outstanding"] > 0` |
| Tier cap | `api_cost > TIER_MAX_DRAW[agent_tier]` |

If all pass → `agent.oracle.evaluate(...)` (LLM call).

#### `IntentExecutor`

Full orchestration loop:
```
1. IntentBrain.evaluate()           → should_exec, reason, borrow_amount
2. agent.draw()                     → credit draw (direct Trestle, not Router)
3. Router.borrow_to_execute()       → claim intent on-chain
4. task_handler(intent)             → user-supplied callable
5. Router.settle()                  → atomic inner txn group
```

**Usage:**
```python
listener = IntentListener(router_app_id=ROUTER_ID, solver_address=agent.address)
executor = IntentExecutor(agent, ROUTER_ID, task_handler=my_handler)
listener.run_forever(on_intent_callback=executor.handle_intent)
```

---

### 4.10 `cli.py` — `trestle init` Command

**File:** `trestle_sdk/cli.py`  
**Entry point:** `trestle = "trestle_sdk.cli:init"` (pyproject.toml)

6-step bootstrap:

```
[1] Generate keypair (algosdk.account.generate_account)
[2] Fund wallet (Algonode testnet faucet or manual for mainnet)
[3] Wait 6 rounds for confirmation
[4] Connect to algod
[5] Opt-in to Trestle contract (ApplicationOptInTxn)
[6] Register with Trestle (do_register → stake 1 ALGO)
→   Write .trestle.env
```

---

### 4.11 `__init__.py` — Public Surface

**File:** `trestle_sdk/__init__.py`

```python
# Always-available (no optional deps):
from .oracle     import RiskOracle, RiskDecision, CriteriaEvaluation
from .agent      import TrestleCreditAgent
from .exceptions import TrestleCreditDenied, TrestleCreditError
from .exceptions import TrestleX402PaymentError, TrestleX402SpendLimitExceeded, TrestleX402SetupError
from .criteria   import get_tier, calculate_interest, tier_name

# Lazy-loaded (requires pip install "trestle-sdk[x402]"):
def __getattr__(name):
    if name == "TrestleX402Client":
        from .x402_client import TrestleX402Client
        return TrestleX402Client
    raise AttributeError(...)
```

x402 exceptions are eagerly exported (no optional dep needed to catch them), but `TrestleX402Client` itself is lazy.

---

## 5. Frontend Layer — React Dashboard

**Stack:** React 18 + Vite + Tailwind CSS  
**Deployment:** Vercel (vercel.json)

| Component | File | Purpose |
|-----------|------|---------|
| `LandingPage` | `LandingPage.jsx` (17 KB) | Marketing hero, feature cards, CTA |
| `Register` | `Register.jsx` (13 KB) | Wallet connection + registration wizard |
| `Dashboard` | `Dashboard.jsx` (21 KB) | Credit position, draw UI, tier progress |
| `ScoreView` | `ScoreView.jsx` (12 KB) | Credit score visualisation |
| `Header` | `Header.jsx` (7 KB) | Navigation bar with wallet connect |
| `Footer` | `Footer.jsx` | Social links |
| `TabBar` | `TabBar.jsx` | Mobile bottom navigation |

The frontend communicates directly with the Algorand testnet via the Algonode API — no backend server. Wallet signing is done client-side (Pera Wallet / WalletConnect pattern expected from context/).

---

## 6. Data Flows

### 6.1 Core Credit Flow: `draw()` → `repay()`

```
Developer code
    │
    ▼
agent.draw(amount=50_000, task_desc="...", expected_return=80_000)
    │
    ├── 1. agent.get_position()
    │       └── chain.get_position() → ATC simulate → 9-tuple on-chain state
    │
    ├── 2. oracle.evaluate(...)
    │       ├── Pre-flight: amount > tier_max? → TrestleCreditDenied (no API call)
    │       ├── Build user_message string
    │       ├── _call_oracle(user_message)
    │       │       Venice: openai.chat.completions.create() → parse JSON
    │       │       Anthropic: client.beta.messages.parse(response_model=...)
    │       ├── validation.overall_approved? No → TrestleCreditDenied
    │       └── compute attestation_hash → return RiskDecision
    │
    ├── 3. chain.do_draw(amount, attestation_hash)
    │       └── ATC execute → AlgoNode testnet
    │             contract.draw() inner txn → ALGO sent to agent wallet
    │
    └── return {txid, amount, interest, total_repayable, tier, ...}

agent.repay(total_repayable)
    └── chain.do_repay() → PaymentTxn to contract escrow
```

---

### 6.2 x402 HTTP-Native Payment Flow

```
client.get("https://x402.goplausible.xyz/examples/weather")
    │
    ├── httpx GET → HTTP 402 {"amount": 1000, "asset": "10458941", ...}
    │
    ├── Spend guard: 1000 > max_spend_per_call (10_000)? No → continue
    │
    ├── _ensure_usdc_balance(1000)
    │       └── if USDC < 1000:
    │               _TinymanSwap.estimate_algo_for_usdc(1200)
    │                   pool state from algod → constant-product formula
    │               _TinymanSwap.swap_algo_to_usdc(...)
    │                   [pay→pool] + [appcall→pool.swap()] atomic group
    │
    ├── agent.draw(2_500 μALGO, "x402 API call: GET ...", ...)
    │       └── [full oracle + chain draw flow as above]
    │       └── agent.repay(total_repayable)  ← immediate auto-repay
    │
    ├── _build_x_payment_header(paymentRequirements)
    │       _CredixAvmSigner.sign_transactions([axfer_txn], [0])
    │           base64.b64encode(raw) → msgpack_decode → sign → msgpack_encode → b64decode
    │       return base64(JSON({x402Version:1, scheme:"exact", payload:{...}}))
    │
    ├── httpx GET (retry) + X-PAYMENT: <header>
    │       → GoPlausible facilitator: POST /verify → POST /settle
    │       → Algorand testnet: axfer USDC to merchant
    │
    ├── HTTP 200 → agent.record_payment() → payment_count++
    │
    └── return httpx.Response
```

---

### 6.3 Intent Market Flow

```
USER1 (locker)                           USER2 (solver / IntentExecutor)
─────────────────────────────────────   ──────────────────────────────────────

Router.lock_intent(                      IntentListener.run_forever()
    pay=200_000 μALGO,                       │
    task_hash=sha256("ALGO-USDC swap"),       ├── poll indexer every 3s
    expiry_rounds=300,                        │   GET /v2/transactions?app=ROUTER
    api_cost=50_000,                          │
    solver_address=agent2.address             ├── parse LogIntentLocked: log
)                                             ├── _fetch_intent_from_indexer(id)
→ intent_id = 42                              │   decode 192-byte ARC-4 struct
                                              │
                                         IntentBrain.evaluate(intent, round)
                                              ├── time window? ✓
                                              ├── profit ratio? ✓ (30%)
                                              ├── no debt? ✓
                                              ├── tier cap? ✓
                                              └── oracle.evaluate() → APPROVED

                                         agent2.draw(50_000 μALGO, ...)
                                             → Trestle.draw() on-chain

                                         Router.borrow_to_execute(42, ...)
                                             → intent state: 0 → 1

                                         task_handler(intent)
                                             → DEX swap / API call / etc.
                                             → (result_str, result_hash_bytes)

                                         Router.settle(42, result_hash, result)
                                         ├── [0] itxn.Payment → Trestle escrow (50_006 μA)
                                         ├── [1] itxn.Payment → solver (149_994 μA profit)
                                         └── [2] itxn.ApplicationCall → Trestle.record_payment()
                                             intent state: 1 → 2
```

---

## 7. Tier System

The tier system is the core incentive mechanism. Tiers are derived from `payment_count` at query time — not stored.

| Tier | Name | Min Payments | Max Draw | Daily Cap | APR |
|------|------|-------------|----------|-----------|-----|
| 0 | Fresh | 0 | 0.10 ALGO | 0.50 ALGO | 24% |
| 1 | Trusted | 10 | 0.50 ALGO | 2.00 ALGO | 16% |
| 2 | Veteran | 50 | 2.00 ALGO | 10.00 ALGO | 9% |
| 3 | Elite | 100 | 5.00 ALGO | 25.00 ALGO | 4% |

**Advancement path:**
```
register(stake ≥ 1 ALGO)
    → Tier 0 (Fresh, 24% APR)
    → 10 × record_payment()
    → Tier 1 (Trusted, 16% APR)
    → 50 × record_payment()
    → Tier 2 (Veteran, 9% APR)
    → 100 × record_payment()
    → Tier 3 (Elite, 4% APR)
```

**slash():** If `outstanding > 0` AND (`payment_count == 0` OR `last_payment_round > 30 rounds ago`): 90% of stake → treasury, 10% → caller reward. Sets `is_defaulted = 1`.

---

## 8. Security Model

### On-Chain Guards (enforced by AVM bytecode)

| Guard | Where | What |
|-------|-------|------|
| Minimum stake | `register()` | ≥ 1 ALGO required |
| No double registration | `register()` | `stake_amount == 0` check |
| No defaulted draws | `draw()` | `is_defaulted == 0` |
| Per-draw hard cap | `draw()` | Tier-dependent max (4 branches) |
| Daily cap | `draw()` | Rolling 24h window reset |
| Attestation hash | `draw()` | sha256 of (sender+amount+round) when `skip_attestation==0` |
| No loan stacking | oracle criterion 3 | `outstanding == 0` pre-checked by LLM |
| Private orders | `borrow_to_execute()` | `Txn.sender == intent.solver_address` |
| Delinquency trigger | `slash()` | 30+ rounds with outstanding debt |

### Off-Chain Guards (SDK)

| Guard | Where | What |
|-------|-------|------|
| Pre-flight tier cap | `oracle.evaluate()` | Saves API cost; fires before LLM call |
| 4-criteria evaluation | `oracle._call_oracle()` | Immutable LLM logic in system prompt |
| Spend limit | `x402_client.arequest()` | `amount_micro_usdc > max_spend_per_call` |
| ALGO reserve | `_ensure_usdc_balance()` | Keeps 0.5 ALGO for fees |

### Demo vs Production Mode

| Feature | Demo (`skip_attestation=1`) | Production (`skip_attestation=0`) |
|---------|----------------------------|-----------------------------------|
| Attestation hash | `bytes(32)` accepted | sha256 must match exactly |
| Oracle API key | Required | Required |
| Risk evaluation | Full LLM call | Full LLM call |
| On-chain enforcement | Tier caps only | Tier caps + hash verification |

---

## 9. Key Constants Cross-Reference

All three locations must stay in sync:

| Constant | `criteria.py` | `contract.py` | `trestle_router.py` |
|----------|--------------|---------------|-------------------|
| Tier 0 APR | `2400` | `TIER_0_APR_BPS = 2400` | `TIER_0_APR_BPS = UInt64(2400)` |
| Day in rounds | `86_400` | `DAY_IN_ROUNDS = 86_400` | `DAY_IN_ROUNDS = UInt64(86_400)` |
| Rounds/year | `31_536_000` | `ROUNDS_PER_YEAR = 31_536_000` | `ROUNDS_PER_YEAR = UInt64(31_536_000)` |
| Tier 0 max draw | `100_000` | `TIER_0_MAX_DRAW = 100_000` | *(not duplicated)* |

> **Warning:** If any of these values diverge, on-chain interest calculations will not match SDK calculations, causing repayment shortfalls or overpayments.

---

## 10. Deployment Checklist

### Core Contract

```bash
# 1. Compile
algokit compile py contracts/contract.py
# → Trestle.approval.teal, Trestle.clear.teal, Trestle.arc56.json

# 2. Deploy
python contracts/deploy.py

# 3. Fund MBR (~0.75 ALGO min balance required)
# 9 local uint×50_000 + 4 global×50_000 + base 100_000 = 750_000 μA

# 4. Seed treasury
atc.add_method_call(app_id, "seed_treasury", pay_txn, ...)

# 5. For production only:
#    a. call enable_attestation()   → skip_attestation = 0
#    b. call set_signer(addr)       → register Claude Skill signer
```

### SDK

```bash
pip install "trestle-sdk"              # core (oracle + chain)
pip install "trestle-sdk[anthropic]"   # + Anthropic oracle
pip install "trestle-sdk[x402]"        # + TrestleX402Client
pip install "trestle-sdk[all]"         # everything
```

### Agent Bootstrap

```bash
export VENICE_API_KEY=...
export TRESTLE_APP_ID=<YOUR_APP_ID>

trestle init --network testnet
# → generates .trestle.env with TRESTLE_MNEMONIC, TRESTLE_ADDRESS, etc.

python demo/x402_demo.py   # x402 live demo
python demo/intent_demo.py # Intent Router demo
```

### Environment Variables

| Variable | Required | Default | Used In |
|----------|----------|---------|---------|
| `VENICE_API_KEY` | Yes (venice) | — | `oracle.py` |
| `ANTHROPIC_API_KEY` | Yes (anthropic) | — | `oracle.py` |
| `ORACLE_PROVIDER` | No | `venice` | `oracle.py` |
| `AGENT_MNEMONIC` or `TRESTLE_MNEMONIC` | Yes | — | `agent.py`, demos |
| `TRESTLE_APP_ID` | Yes | `<YOUR_APP_ID>` | all |
| `ALGOD_URL` | No | algonode testnet | `chain.py` |
| `ROUTER_APP_ID` | Intent market | — | `intent_demo.py` |
| `AGENT1_MNEMONIC` / `AGENT2_MNEMONIC` | Intent demo | — | `intent_demo.py` |
