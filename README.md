# Trestle — On-chain Credit for AI Agents

> **The first protocol where an LLM decides if an AI agent's loan is responsible before it's issued.**

**Algorand Testnet · App ID: `<YOUR_APP_ID>` (redeploy required — see below)**  
`<your-domain-here>`

---

## Quick Start

**Install**
```bash
pip install trestle-sdk
```

**One command to bootstrap your agent wallet**
```bash
trestle init --network testnet
```
*Generates a wallet, funds it from the testnet faucet, opts in,
stakes 1 ALGO, and writes `.trestle.env` — in under 30 seconds.*

**Draw credit in Python**
```python
import os
from dotenv import load_dotenv
from trestle_sdk import TrestleCreditAgent, TrestleCreditDenied

load_dotenv(".trestle.env")

agent = TrestleCreditAgent(
    mnemonic_phrase=os.environ["TRESTLE_MNEMONIC"],
    app_id=int(os.environ["TRESTLE_APP_ID"]),  # <YOUR_APP_ID> testnet
)

try:
    result = agent.draw(
        amount_microalgo=50_000,
        task_description="Fetch ETH/USD price from CoinGecko public API",
        expected_return_microalgo=80_000,
        estimated_task_rounds=120,
    )
    print(f"Approved — txid: {result['txid']}")
    print(f"Oracle: {result['risk_summary']}")

    # ... run your task here ...

    agent.repay(result["total_repayable"])
    agent.record_payment()  # builds on-chain tier history

except TrestleCreditDenied as e:
    print(f"Denied: {e.reason}")  # no transaction was submitted
```

**Run the full demo**
```bash
VENICE_API_KEY=your-key python demo/SDK_DEMO.py
```

---

## What Is Trestle?

AI agents can execute code, call APIs, and transact on-chain autonomously — but they cannot borrow money. There is no credit bureau for software bots. Today, if an agent runs out of funds mid-task, it stops. It cannot take out a microloan, complete its work, and repay automatically.

Trestle is an on-chain credit bureau for autonomous AI agents on Algorand. Agents stake ALGO to register an identity, record their transaction history on-chain to build reputation, and draw undercollateralised credit lines — up to 10× their original stake — based on that history. The credit limit, tier, and interest rate are all computed deterministically by the smart contract with no off-chain intervention. With x402 integration, Trestle becomes the credit layer for the emerging agentic commerce stack — agents borrow to pay for APIs, repay after the task, and build reputation through real commerce history.

What makes Trestle different is the risk oracle. Before any draw reaches the chain, an LLM evaluates four hardcoded criteria against the agent's stated task. If the task is speculative, the agent already has outstanding debt, the expected return doesn't cover the loan cost, or the task won't finish before the repayment deadline — the draw is denied and no transaction is ever submitted. The LLM is the guardrail, not the human.

---

## Live Demo Output

### Approved draw — ETH price fetch

```
trestle-agent v0.2.0 | testnet | app <YOUR_APP_ID>
agent: STOL...DEMO

fetching position...
  stake_amount:   1000000 uALGO
  payment_count:  22
  outstanding:    0
  tier:           1 (Trusted), APR 16%

oracle evaluating draw request (50000 uALGO)...
  criterion 1 (return > cost):       pass
  criterion 2 (rounds < 86400):      pass
  criterion 3 (no outstanding debt): pass
  criterion 4 (risk level = low):    pass
  decision: approved
  summary: Low-risk deterministic API call with clear profit margin.

submitting draw...
  txid:    FQJZX7KPNR4YVLBM2CWD8H6SAE3TU5G
  drawn:   50000 uALGO
  fee:     1 uALGO
  owed:    50001 uALGO

running task: fetching ETH/USD from CoinGecko...
  result: 2814.22

repaying 50001 uALGO...
  txid:    AQNZKM8JCPW6YHRLX4BF7TSVD2EU5GI
  outstanding: 0
```

### Denied draw — high-risk arbitrage

```
trestle-agent v0.2.0 | testnet | app <YOUR_APP_ID>
agent: STOL...DEMO

oracle evaluating draw request (500000 uALGO)...
  task: Speculative arbitrage on unaudited new DEX contracts
  criterion 1 (return > cost):       pass
  criterion 2 (rounds < 86400):      pass
  criterion 3 (no outstanding debt): pass
  criterion 4 (risk level = critical): FAIL
  decision: denied
  reason: task risk level is 'critical' - speculative arbitrage on an
          unaudited contract is not permitted at any tier.

TrestleCreditDenied raised. No transaction submitted.
```

---

## Architecture

### 3-Layer Stack

| Layer | Technology | Description |
|---|---|---|
| **Smart Contract** | Algorand Python · ARC-4 · Puya | On-chain credit bureau, slashing, state management |
| **Python SDK** | `trestle_sdk` · Venice AI / Anthropic | LLM-gated draw, four-criteria risk oracle |
| **Frontend** | React · Vite · Pera/Defly Wallets | Agent terminal, position dashboard, live chain data |

### Oracle Criteria (immutable — cannot be overridden by agent code)

1. **Return must exceed cost**: `expected_return > loan + interest`
2. **Task fits repayment window**: `estimated_rounds < 86,400` (~24 hours)
3. **No outstanding debt**: `outstanding == 0` (no loan stacking, ever)
4. **Task risk is acceptable**: LLM assigns `low` or `medium` risk. `high` and `critical` are always denied.

## x402 Integration

Trestle is the credit layer that finances x402 API payments for autonomous agents.

x402 is an HTTP payment standard: a protected API returns HTTP 402 with payment requirements, the client pays on-chain, retries, and gets the resource. The problem is agents need capital to pay. That's exactly what Trestle solves.

**The flow:**
1. Agent hits an x402-protected endpoint → gets HTTP 402 with amount + receiver
2. Agent calls `TrestleCreditAgent.draw()` with the 402 amount as the draw amount and the resource URL as the task description
3. Trestle's LLM risk oracle evaluates the x402 resource (same 4 criteria — return must exceed cost + interest, task fits within 24h, no outstanding debt, low/medium risk endpoint)
4. If approved: agent submits ALGO payment to the x402 receiver, retries with X-PAYMENT header, gets the data
5. After task completes: agent repays Trestle + calls `record_payment()` — the x402 call becomes on-chain reputation
6. Repeat. 10 verified x402 payments = Tier 1. 100 = Tier 3 (Elite). The tier history is a provable log of real agentic commerce.

**Python — one import away:**

```python
from trestle_sdk.x402_client import TrestleX402Client

client = TrestleX402Client(credit_agent=trestle_agent)

# hits x402-protected price feed, funds it via Trestle credit automatically
response = client.get(
    "https://api.prices.io/eth-usd",
    expected_return_microalgo=80_000,
)
print(response.json())  # {"price": 2814.22}
# payment_count++ on-chain. one step closer to Tier 1.
```

**Tier caps map to x402 pricing tiers:**

| Tier | payments | max draw | x402 use case |
|------|----------|----------|---------------|
| 0 — Fresh   | 0   | 0.10 ALGO | sub-cent API calls, price feeds |
| 1 — Trusted | 10  | 0.50 ALGO | standard data APIs |
| 2 — Veteran | 50  | 2.00 ALGO | premium compute endpoints |
| 3 — Elite   | 100 | 5.00 ALGO | high-value inference, oracle calls |

**Install the x402-avm Python package alongside the Trestle SDK:**

```bash
pip install trestle-sdk "x402-avm[avm,httpx]"
```

The `TrestleX402Client` handles the 402 → draw → pay → retry → repay → record_payment loop automatically. The developer never touches algosdk directly.

---

## Intent Router — Algorand's First Intent-Based Swap with Agent Credit

Inspired by NEAR Intents ($7B+ volume) and Across Protocol. Built natively
on Algorand with Trestle as the credit layer.

**Flow:**
1. Agent1 locks ALGO into the Router contract for a swap task
2. Agent2 detects the private order (assigned to their address only)
3. Agent2's Trestle oracle evaluates profitability and risk
4. Agent2 draws credit from Trestle to fund the swap
5. Atomic settlement: Trestle repaid + Agent2 profit in one transaction group

**Run the demo:**
```bash
python demo/intent_demo.py
```

**Deploy the Router:**
```bash
ADMIN_MNEMONIC="..." TRESTLE_APP_ID=<YOUR_APP_ID> python contracts/deploy_router.py
```

**No equivalent exists on Algorand.** Tinyman, Pact, and Folks Finance are AMMs
and lending protocols. None have an intent-based solver market. Trestle Intent
Router is the first.

---

### Tier System

| Tier | Name | Min Payments | Max Draw | APR |
|---|---|---|---|---|
| 0 | Fresh | 0 | 0.10 ALGO | 24% |
| 1 | Trusted | 10 | 0.50 ALGO | 16% |
| 2 | Veteran | 50 | 2.00 ALGO | 9% |
| 3 | Elite | 100 | 5.00 ALGO | 4% |

---

## Quick Start

```bash
# Clone
git clone https://github.com/ShahiTechnovation/Trestle
cd Trestle

# Install SDK
pip install -e "./trestle_sdk"

# Set environment variables
cp contracts/.env.example contracts/.env
# Fill in: AGENT_MNEMONIC, TRESTLE_APP_ID=<YOUR_APP_ID>, VENICE_API_KEY

# Run demo
python demo/SDK_DEMO.py

# Run tests
python tests/test_sdk.py
```

---

## SDK Usage

```python
import os
from trestle_sdk import TrestleCreditAgent, TrestleCreditDenied

agent = TrestleCreditAgent(
    mnemonic_phrase=os.environ["AGENT_MNEMONIC"],
    app_id=<YOUR_APP_ID>,
)

# Oracle runs internally — Venice AI or Anthropic evaluates 4 criteria
try:
    result = agent.draw(
        amount_microalgo=50_000,
        task_description="Fetch ETH/USD price from CoinGecko",
        expected_return_microalgo=80_000,
        estimated_task_rounds=120,
    )
    # {"txid": "...", "amount_microalgo": 50000, "interest_microalgo": 1,
    #  "tier": 1, "tier_name": "Trusted", "risk_summary": "..."}

    agent.repay(result["total_repayable"])

except TrestleCreditDenied as e:
    print(f"Denied: {e.reason}")
    # No on-chain transaction was submitted
```

---

## Oracle Providers

The LLM provider is controlled by the `ORACLE_PROVIDER` environment variable.

### Venice AI (default)

```bash
export ORACLE_PROVIDER=venice
export VENICE_API_KEY=your-venice-key
python demo/SDK_DEMO.py
```

Model: `llama-3.3-70b`. No extra install required (`openai` package already included).

### Anthropic

```bash
export ORACLE_PROVIDER=anthropic
export ANTHROPIC_API_KEY=sk-ant-...
pip install -e "./trestle_sdk[anthropic]"
python demo/SDK_DEMO.py
```

Model: `claude-haiku-4-5-20251001`. Uses `client.beta.messages.parse()` for structured output.

---

## Contract Reference

**Deployed:** Algorand Testnet · App ID: `<YOUR_APP_ID>` (deploy your own instance — see `contracts/deploy.py`)  
[View on Pera Explorer →](https://testnet.explorer.perawallet.app/application/<YOUR_APP_ID>)

### ABI Methods

| Method | Signature | Description |
|---|---|---|
| `opt_in` | bare (OptIn) | Bootstrap local state for new agent wallet |
| `register` | `register(pay)→void` | Stake ALGO, initialise agent identity |
| `record_payment` | `record_payment(uint64)→uint64` | Record off-chain M2M payment, boost credit limit |
| `draw` | `draw(uint64,byte[32])→void` | Draw credit; attestation hash verified on mainnet |
| `repay` | `repay(pay)→void` | Repay outstanding balance |
| `slash` | `slash(address)→void` | Anyone can slash a delinquent agent after 30 rounds |
| `get_position` | `get_position(address)→(uint64×5)` | Read agent's full position (readonly) |
| `enable_attestation` | `enable_attestation()→void` | Turn on on-chain hash verification (mainnet) |
| `fund` | bare (NoOp) | Fund the contract treasury |

### State Schema

| Scope | Key | Type | Description |
|---|---|---|---|
| Global | `treasury_balance` | uint64 | Total ALGO held by contract |
| Global | `total_agents` | uint64 | Number of registered agents |
| Local | `stake_amount` | uint64 | Agent's staked ALGO |
| Local | `payment_count` | uint64 | Number of recorded repayments |
| Local | `total_repaid` | uint64 | Lifetime repayment total |
| Local | `outstanding` | uint64 | Current unpaid balance |
| Local | `credit_limit` | uint64 | Current computed credit limit |
| Local | `is_defaulted` | uint64 | 1 if agent has been slashed |
| Local | `last_payment_round` | uint64 | Last round a payment was made |

---

## V2 Roadmap

- **USDC/ASA denomination** — Real dollar-denominated microloans for production use
- **ZK proof attestation** — Decentralise the oracle with verifiable computation
- **Base L2 + Solana deployment** — Reach the broader AI agent ecosystem
- **Bilateral payment verification** — Prevent fake history inflation, require counterparty signatures
- **Treasury insurance pool** — Absorb defaults automatically without manual top-ups
- **Agent identity registry** — Persistent credit history across wallet rekeys

---

## Known Limitations

Trestle is a testnet prototype built at AlgoBharat Hack Series 3.0.

- **Slash window is 30 rounds (~30 seconds)** — short enough for a demo run. Production should use `DAY_IN_ROUNDS` (86,400 rounds ≈ 24 hours).
- **`payment_count` is self-reported** — any agent can call `record_payment()` without a real counterparty. V2 requires bilateral signing from both parties.
- **`skip_attestation=1` on testnet** — `draw()` does not verify the attestation hash in demo mode. Call `enable_attestation()` before mainnet deployment.
- **Treasury funded manually** — the contract must be seeded with ALGO before any draw can succeed. V2 will add automated liquidity management.

---

## License

MIT License.  
Built at **AlgoBharat Hack Series 3.0** on Algorand.
