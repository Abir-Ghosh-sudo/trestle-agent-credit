# Trestle 🏛️

### On-Chain Credit Infrastructure for Autonomous AI Agents

> **What if AI agents could build credit, borrow for productive tasks, and repay automatically — entirely on-chain?**

**Trestle** is an on-chain credit protocol for autonomous AI agents, built on **Algorand**.

It gives AI agents a programmable financial identity: agents can stake ALGO, build repayment history, access credit based on their reputation, and use that credit to pay for APIs and agentic services.

The key idea is simple:

**AI evaluates the task → Trestle evaluates the risk → Algorand settles the credit → the agent repays → reputation grows.**

---

## 🏆 Built for Hacker House Goa

Trestle is built as a hackathon-focused prototype exploring the intersection of:

* 🤖 **AI Agents**
* 💳 **Agentic Payments**
* ⛓️ **Blockchain Credit**
* 🔐 **On-chain Reputation**
* ⚡ **Algorand**
* 💰 **x402 Machine-to-Machine Payments**

The project demonstrates how autonomous agents could move beyond prepaid wallets toward **reputation-based financial infrastructure**.

---

## 🚀 Why Trestle?

AI agents can already:

* Execute code
* Call APIs
* Interact with smart contracts
* Make blockchain transactions
* Perform autonomous tasks

But they still have one major limitation:

> **An AI agent cannot easily access short-term capital when it runs out of funds.**

If an agent needs 0.05 ALGO to complete a profitable API task but only has 0.01 ALGO, the task stops.

Trestle introduces an on-chain credit layer that allows an agent to:

```text
        AI Agent
           │
           ▼
     Task / Payment
           │
           ▼
    ┌───────────────┐
    │ Risk Oracle   │
    │   LLM + Rules │
    └───────┬───────┘
            │
       Approved?
       ┌────┴────┐
       │         │
      YES        NO
       │         │
       ▼         ▼
  Draw Credit   Reject
       │
       ▼
  Pay / Execute
       │
       ▼
     Repay
       │
       ▼
  Build Reputation
```

---

# ✨ Core Features

### 🧠 LLM-Gated Credit

Before a credit draw reaches the blockchain, an LLM evaluates the proposed task against predefined risk criteria.

### ⛓️ On-Chain Reputation

Agents build a financial history through recorded repayments and payment activity.

### 💰 Reputation-Based Credit

An agent's tier determines its available credit limit and interest rate.

### 🛡️ Responsible Borrowing

Credit requests can be rejected before an on-chain transaction is submitted when the task fails the protocol's risk requirements.

### ⚡ x402 Integration

Trestle can act as the credit layer behind x402-powered API payments.

### 🔄 Autonomous Repayment

Agents can repay their outstanding balance after completing their task and record the successful payment as part of their reputation history.

### 🔀 Intent Router

The project also includes an experimental intent-based swap flow where an agent can use Trestle credit to finance a swap task.

---

# 🧠 The Risk Oracle

The oracle evaluates every credit request using four criteria.

| Criterion         | Requirement                                 |
| ----------------- | ------------------------------------------- |
| 💵 Return vs Cost | Expected return must exceed loan + interest |
| ⏱️ Time           | Task must fit within the repayment window   |
| 🔒 Existing Debt  | Agent cannot have outstanding debt          |
| ⚠️ Risk           | LLM risk level must be `low` or `medium`    |

### Decision Flow

```text
Credit Request
      │
      ▼
Expected Return > Cost?
      │
      ├── No ──► ❌ Denied
      │
      ▼
Task within repayment window?
      │
      ├── No ──► ❌ Denied
      │
      ▼
Outstanding debt?
      │
      ├── Yes ──► ❌ Denied
      │
      ▼
Risk acceptable?
      │
      ├── No ──► ❌ Denied
      │
      ▼
   ✅ Approved
      │
      ▼
 Submit on-chain draw
```

The LLM acts as a **risk assessment layer**, while the smart contract enforces the financial state and protocol rules.

---

# 🏦 Credit Tiers

Agents improve their credit profile through verified payment activity.

| Tier | Name    | Minimum Payments | Maximum Draw | APR |
| ---: | ------- | ---------------: | -----------: | --: |
|    0 | Fresh   |                0 |    0.10 ALGO | 24% |
|    1 | Trusted |               10 |    0.50 ALGO | 16% |
|    2 | Veteran |               50 |    2.00 ALGO |  9% |
|    3 | Elite   |              100 |    5.00 ALGO |  4% |

The tier system is designed around a simple principle:

> **Better repayment history → higher trust → greater borrowing capacity → lower cost of credit.**

---

# ⚡ x402 Integration

Trestle can provide the financing layer for autonomous agents interacting with **x402-protected APIs**.

### Payment Flow

```text
AI Agent
   │
   ▼
x402 Protected API
   │
   ▼
HTTP 402 Payment Required
   │
   ▼
Trestle Credit Request
   │
   ▼
LLM Risk Oracle
   │
   ├── ❌ Denied
   │
   └── ✅ Approved
           │
           ▼
      Draw Credit
           │
           ▼
      Pay API
           │
           ▼
      Retry Request
           │
           ▼
       Get Data
           │
           ▼
        Repay
           │
           ▼
   Record Payment
           │
           ▼
   Improve Reputation
```

### Python Example

```python
from trestle_sdk.x402_client import TrestleX402Client

client = TrestleX402Client(
    credit_agent=trestle_agent
)

response = client.get(
    "https://api.prices.io/eth-usd",
    expected_return_microalgo=80_000,
)

print(response.json())
```

The goal is to hide the complexity of:

```text
402 → Credit → Payment → Retry → Repayment → Reputation
```

behind a developer-friendly interface.

---

# 🔀 Intent Router

Trestle also includes an experimental intent-based swap architecture.

### Flow

```text
Agent 1
   │
   │ Lock ALGO
   ▼
Intent Router
   │
   ▼
Private Swap Intent
   │
   ▼
Agent 2
   │
   ▼
Risk Evaluation
   │
   ▼
Trestle Credit
   │
   ▼
Execute Swap
   │
   ▼
Atomic Settlement
   │
   ├── Trestle Repaid
   │
   └── Agent 2 Profit
```

Run the demo:

```bash
python demo/intent_demo.py
```

Deploy the router:

```bash
ADMIN_MNEMONIC="..." \
TRESTLE_APP_ID=<YOUR_APP_ID> \
python contracts/deploy_router.py
```

---

# 🏗️ Architecture

Trestle currently follows a three-layer architecture:

```text
┌─────────────────────────────────────────────┐
│              FRONTEND / AGENT               │
│         React + Vite + Wallets              │
└──────────────────────┬──────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────┐
│                 SDK LAYER                   │
│      Python SDK + LLM Risk Oracle           │
│         Venice AI / Anthropic                │
└──────────────────────┬──────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────┐
│             ALGORAND CONTRACT               │
│       Credit • Reputation • Repayment        │
│           Treasury • Slashing               │
└─────────────────────────────────────────────┘
```

### Technology Stack

| Layer          | Technology                     |
| -------------- | ------------------------------ |
| Blockchain     | Algorand Testnet               |
| Smart Contract | Algorand Python / Puya / ARC-4 |
| SDK            | Python                         |
| AI Oracle      | Venice AI / Anthropic          |
| Frontend       | React + Vite                   |
| Wallets        | Pera / Defly                   |
| Payments       | x402                           |
| Testing        | Python test suite              |

---

# ⚡ Quick Start

## 1. Clone the repository

```bash
git clone https://github.com/ShahiTechnovation/Trestle
cd Trestle
```

## 2. Install the SDK

```bash
pip install -e "./trestle_sdk"
```

Or install the published SDK:

```bash
pip install trestle-sdk
```

## 3. Configure environment variables

```bash
cp contracts/.env.example contracts/.env
```

Configure:

```env
AGENT_MNEMONIC=your-testnet-mnemonic
TRESTLE_APP_ID=your-testnet-app-id
VENICE_API_KEY=your-venice-api-key
```

> ⚠️ **Never commit a mnemonic, private key, or API key to GitHub.**

## 4. Run the demo

```bash
python demo/SDK_DEMO.py
```

## 5. Run tests

```bash
python tests/test_sdk.py
```

---

# 🤖 SDK Usage

```python
import os

from trestle_sdk import (
    TrestleCreditAgent,
    TrestleCreditDenied
)

agent = TrestleCreditAgent(
    mnemonic_phrase=os.environ["AGENT_MNEMONIC"],
    app_id=int(os.environ["TRESTLE_APP_ID"]),
)

try:
    result = agent.draw(
        amount_microalgo=50_000,
        task_description="Fetch ETH/USD price from CoinGecko",
        expected_return_microalgo=80_000,
        estimated_task_rounds=120,
    )

    print("Approved:", result["txid"])

    # Execute the task...

    agent.repay(result["total_repayable"])

except TrestleCreditDenied as e:
    print("Credit denied:", e.reason)
```

If the oracle rejects the request:

```text
TrestleCreditDenied
        │
        ▼
No blockchain draw submitted
```

---

# 🧪 Example: Approved Draw

```text
trestle-agent v0.2.0 | testnet

stake_amount:   1000000 uALGO
payment_count:  22
outstanding:    0
tier:           1 (Trusted)
APR:            16%

oracle evaluating draw request...

✓ return > cost
✓ task fits repayment window
✓ no outstanding debt
✓ risk level acceptable

decision: APPROVED

drawn: 50000 uALGO
owed:  50001 uALGO

task: Fetch ETH/USD

result: 2814.22

repayment: 50001 uALGO
outstanding: 0
```

---

# 🚫 Example: Rejected Draw

```text
oracle evaluating draw request...

task:
Speculative arbitrage on unaudited new DEX contracts

✓ return > cost
✓ task fits repayment window
✓ no outstanding debt
✗ risk level = critical

decision: DENIED

reason:
Critical-risk speculative activity is not permitted.

No transaction submitted.
```

This is an important part of the design:

> **A rejected request does not create an on-chain credit draw.**

---

# 🧩 Oracle Providers

Trestle supports configurable LLM providers.

## Venice AI

Venice is the default provider.

```bash
export ORACLE_PROVIDER=venice
export VENICE_API_KEY=your-key

python demo/SDK_DEMO.py
```

The current implementation uses:

```text
llama-3.3-70b
```

## Anthropic

```bash
export ORACLE_PROVIDER=anthropic
export ANTHROPIC_API_KEY=your-key

pip install -e "./trestle_sdk[anthropic]"

python demo/SDK_DEMO.py
```

The current implementation uses:

```text
claude-haiku-4-5-20251001
```

---

# ⛓️ Smart Contract

**Network:** Algorand Testnet

**Application ID:** `<YOUR_APP_ID>`

> Replace `<YOUR_APP_ID>` after deploying your own contract instance.

### Contract Methods

| Method               | Purpose                          |
| -------------------- | -------------------------------- |
| `opt_in`             | Bootstrap local agent state      |
| `register`           | Register an agent and stake ALGO |
| `record_payment`     | Record payment activity          |
| `draw`               | Draw credit                      |
| `repay`              | Repay outstanding credit         |
| `slash`              | Slash a delinquent agent         |
| `get_position`       | Read agent credit position       |
| `enable_attestation` | Enable attestation verification  |
| `fund`               | Fund the protocol treasury       |

---

# 📦 Agent State

The smart contract tracks:

| State                | Description                        |
| -------------------- | ---------------------------------- |
| `stake_amount`       | Agent's staked ALGO                |
| `payment_count`      | Recorded payment count             |
| `total_repaid`       | Lifetime repayment amount          |
| `outstanding`        | Current unpaid balance             |
| `credit_limit`       | Current credit limit               |
| `is_defaulted`       | Whether the agent has been slashed |
| `last_payment_round` | Last recorded payment round        |

---

# 🔐 Security Model

Trestle separates **AI decision-making** from **on-chain enforcement**.

### Off-chain

The LLM evaluates:

* Task description
* Expected return
* Estimated execution time
* Risk level

### On-chain

The smart contract maintains:

* Agent identity
* Stake
* Credit limit
* Outstanding debt
* Repayment history
* Default state
* Treasury balance

This architecture allows the AI layer to assess intent while the blockchain remains the source of truth for financial state.

---

# ⚠️ Current Limitations

Trestle is currently a **testnet hackathon prototype**, so several components are intentionally simplified.

### 1. Testnet Environment

The system currently targets Algorand Testnet and should not be treated as production financial infrastructure.

### 2. Payment History

`payment_count` can currently be self-reported.

A future version should require bilateral verification from the payment counterparty.

### 3. Attestation

The current testnet configuration can skip attestation verification.

Attestation verification should be enabled before production deployment.

### 4. Treasury

The protocol treasury must currently be funded manually.

### 5. Slash Window

The prototype uses a short slash window suitable for demonstrations.

A production implementation should use a substantially longer repayment period.

---

# 🗺️ Roadmap

## V2

* [ ] USDC / ASA-denominated credit
* [ ] Verifiable / ZK oracle attestations
* [ ] Bilateral payment verification
* [ ] Automated treasury liquidity management
* [ ] Treasury insurance pool
* [ ] Persistent agent identity registry
* [ ] Cross-chain deployment
* [ ] Production-grade repayment windows
* [ ] Stronger x402 integrations

### Long-Term Vision

```text
Today
 │
 ├── Testnet credit
 ├── AI risk assessment
 └── x402 prototype
        │
        ▼
V2
 │
 ├── Verifiable AI decisions
 ├── Stablecoin credit
 ├── Verified reputation
 └── Automated liquidity
        │
        ▼
Future
 │
 └── Open credit infrastructure
     for autonomous agents
```

---

# 💡 The Bigger Idea

Trestle is not simply a lending contract.

It explores a new primitive:

> **Creditworthiness for software agents.**

Human financial systems use credit histories to determine who can borrow.

Autonomous agents need a similar mechanism.

Instead of:

```text
Human
  ↓
Bank
  ↓
Credit Score
  ↓
Loan
```

Trestle explores:

```text
AI Agent
  ↓
On-chain Reputation
  ↓
LLM Risk Assessment
  ↓
Smart Contract
  ↓
Credit
  ↓
Task
  ↓
Repayment
  ↓
Better Reputation
```

This creates the possibility of a future where autonomous agents can participate in machine-to-machine commerce without requiring a human to manually fund every transaction.

---

# 🧑‍💻 Project Structure

```text
Trestle/
│
├── contracts/
│   ├── deploy.py
│   ├── deploy_router.py
│   └── .env.example
│
├── trestle_sdk/
│   ├── trestle_sdk/
│   └── ...
│
├── demo/
│   ├── SDK_DEMO.py
│   └── intent_demo.py
│
├── tests/
│   └── test_sdk.py
│
├── frontend/
│   └── ...
│
└── README.md
```

---

# 🛠️ Development

Install the SDK in editable mode:

```bash
pip install -e "./trestle_sdk"
```

Run the SDK demo:

```bash
python demo/SDK_DEMO.py
```

Run tests:

```bash
python tests/test_sdk.py
```

Run the intent demo:

```bash
python demo/intent_demo.py
```

---

# 🤝 Contributing

Contributions are welcome.

If you want to improve Trestle:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add or update tests
5. Open a pull request

Example:

```bash
git checkout -b feature/my-feature
git add .
git commit -m "feat: add my feature"
git push origin feature/my-feature
```

---

# 📜 License

This project is released under the **MIT License**.

---

## 🌐 Built on Algorand

Trestle uses Algorand for fast, low-cost, deterministic on-chain settlement and state management.

---

# 🏆 Hackathon Project

**Trestle**
*On-Chain Credit for Autonomous AI Agents*

Built for **Hacker House Goa** with the goal of exploring how blockchain-based reputation and AI-driven risk assessment can enable a more autonomous machine economy.

---

### ⭐ If you find the idea interesting

Give the repository a star, explore the demos, and help us rethink what **credit for AI agents** could look like.
