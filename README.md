🏛️ Trestle

On-Chain Credit Infrastructure for Autonomous AI Agents

<p align="center">
  <strong>Give AI agents a financial identity, reputation, and programmable access to credit.</strong>
</p>

<p align="center">
  <a href="https://trestle-dev.vercel.app/">🚀 Live Demo</a> •
  <a href="https://github.com/ShahiTechnovation/Trestle">💻 Repository</a> •
  <a href="#-quick-start">⚡ Quick Start</a> •
  <a href="#-architecture">🏗️ Architecture</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Network-Algorand%20Testnet-black?style=for-the-badge&logo=algorand" alt="Algorand Testnet">
  <img src="https://img.shields.io/badge/AI-Risk%20Oracle-7C3AED?style=for-the-badge" alt="AI Risk Oracle">
  <img src="https://img.shields.io/badge/Payments-x402-2563EB?style=for-the-badge" alt="x402">
  <img src="https://img.shields.io/badge/License-MIT-22C55E?style=for-the-badge" alt="MIT License">
</p>

🌐 Live Demo

Try Trestle in your browser:
🚀 https://trestle-dev.vercel.app/

The deployed frontend provides a visual interface for exploring the Trestle credit workflow and its Algorand-based agent infrastructure.

⚠️ Note: Trestle is currently a testnet hackathon prototype. It is not production financial infrastructure and should not be used with real funds.

💡 What is Trestle?

Trestle is an on-chain credit protocol for autonomous AI agents, built on Algorand.

It explores a simple question:

What if AI agents could build credit, borrow for productive tasks, and repay automatically — entirely on-chain?

Trestle gives an AI agent a programmable financial identity. An agent can:

🪙 Stake ALGO

📈 Build an on-chain repayment history

🏦 Access credit based on reputation

🤖 Use AI-assisted risk evaluation before borrowing

⚡ Pay for APIs and agentic services

🔄 Repay outstanding credit

⭐ Improve its reputation through successful payment activity

The Core Loop

        AI Agent
           │
           ▼
      Task / Payment
           │
           ▼
   ┌─────────────────┐
   │   Risk Oracle   │
   │    LLM + Rules  │
   └────────┬────────┘
            │
       Approved?
       ┌────┴────┐
      YES        NO
       │          │
       ▼          ▼
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

AI evaluates the task → Trestle evaluates the risk → Algorand settles the credit → the agent repays → reputation grows.

🏆 Built for Hacker House Goa

Trestle is a hackathon-focused prototype exploring the intersection of:

Area

Role in Trestle

🤖 AI Agents

Autonomous task execution and financial decisions

🧠 AI Risk Assessment

Evaluates whether a proposed credit draw is acceptable

⛓️ Blockchain Credit

On-chain credit state and repayment

🔐 On-chain Reputation

Payment history influences agent trust

⚡ Algorand

Fast, low-cost deterministic settlement

💳 x402

Machine-to-machine API payment flow

The broader idea is to move autonomous agents beyond pre-funded wallets toward reputation-based financial infrastructure.

🚀 Why Trestle?

AI agents can already:

Execute code

Call APIs

Interact with smart contracts

Make blockchain transactions

Perform autonomous tasks

But an agent normally needs funds before it can perform a paid task.

For example:

Agent balance:       0.01 ALGO
Task cost:           0.05 ALGO
Expected return:     0.08 ALGO

Without credit:
❌ Task cannot execute

With Trestle:
🧠 Risk evaluation
       ↓
✅ Credit approved
       ↓
💸 Task executed
       ↓
🔄 Agent repays
       ↓
⭐ Reputation improves

Trestle explores whether an agent's verified financial behavior can become the basis for future borrowing capacity.

✨ Core Features

🧠 LLM-Gated Credit

Before a credit draw reaches the blockchain, an LLM evaluates the proposed task against predefined risk criteria.

⛓️ On-Chain Reputation

Agents build a financial history through recorded repayment and payment activity.

💰 Reputation-Based Credit

An agent's credit tier determines its available borrowing limit and interest rate.

🛡️ Responsible Borrowing

Requests can be rejected before an on-chain transaction is submitted when the task fails protocol risk requirements.

⚡ x402 Integration

Trestle can act as a credit layer for x402-protected API payments, allowing an agent to respond to HTTP 402 Payment Required flows.

🔄 Autonomous Repayment

After completing a task, the agent can repay its outstanding balance and record successful payment activity.

🔀 Intent Router

The prototype also includes an experimental intent-based swap flow where Trestle credit can finance a swap task.

🧠 Risk Oracle

The Risk Oracle evaluates each credit request using four main criteria:

Criterion

Requirement

💵 Return vs Cost

Expected return must exceed loan + interest

⏱️ Time

Task must fit within the repayment window

🔒 Existing Debt

Agent cannot have outstanding debt

⚠️ Risk

LLM risk level must be low or medium

Decision Flow

Credit Request
      │
      ▼
Expected Return > Cost?
      │
   ┌──┴──┐
  No    Yes
  │      │
  ▼      ▼
❌      Task within
Denied  repayment window?
          │
       ┌──┴──┐
      No    Yes
      │      │
      ▼      ▼
     ❌    Outstanding debt?
    Denied      │
             ┌──┴──┐
            Yes    No
             │      │
             ▼      ▼
            ❌    Risk acceptable?
           Denied      │
                    ┌──┴──┐
                   No    Yes
                   │      │
                   ▼      ▼
                  ❌    ✅ Approved
                 Denied      │
                             ▼
                     Submit on-chain draw

The LLM acts as the risk assessment layer, while the smart contract enforces financial state and protocol rules.

🏦 Credit Tiers

Successful payment activity improves an agent's credit profile.

Tier

Name

Minimum Payments

Maximum Draw

APR

0

🆕 Fresh

0

0.10 ALGO

24%

1

🤝 Trusted

10

0.50 ALGO

16%

2

🛡️ Veteran

50

2.00 ALGO

9%

3

👑 Elite

100

5.00 ALGO

4%

Better repayment history → higher trust → greater borrowing capacity → lower cost of credit.

⚡ x402 Integration

Trestle can provide the financing layer for autonomous agents interacting with x402-protected APIs.

Payment Flow

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
 ┌─┴─────────┐
 ▼           ▼
❌ Denied   ✅ Approved
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

The goal is to hide the complexity of:

402 → Credit → Payment → Retry → Repayment → Reputation

behind a developer-friendly interface.

Python Example

from trestle_sdk.x402_client import TrestleX402Client

client = TrestleX402Client(
    credit_agent=trestle_agent
)

response = client.get(
    "https://api.prices.io/eth-usd",
    expected_return_microalgo=80_000,
)

print(response.json())

🔀 Intent Router

Trestle also includes an experimental intent-based swap architecture.

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
   └── Agent 2 Profit

Run the demo

python demo/intent_demo.py

Deploy the router

ADMIN_MNEMONIC="..." \
TRESTLE_APP_ID=<YOUR_APP_ID> \
python contracts/deploy_router.py

🏗️ Architecture

Trestle currently follows a three-layer architecture:

┌──────────────────────────────────────────────┐
│               FRONTEND / AGENT              │
│          React + Vite + Wallets             │
└───────────────────────┬──────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────┐
│                  SDK LAYER                  │
│       Python SDK + LLM Risk Oracle          │
│           Venice AI / Anthropic             │
└───────────────────────┬──────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────┐
│              ALGORAND CONTRACT              │
│      Credit • Reputation • Repayment        │
│          Treasury • Slashing                │
└──────────────────────────────────────────────┘

🧰 Technology Stack

Layer

Technology

⛓️ Blockchain

Algorand Testnet

📜 Smart Contract

Algorand Python / Puya / ARC-4

🐍 SDK

Python

🧠 AI Oracle

Venice AI / Anthropic

🌐 Frontend

React + Vite

👛 Wallets

Pera / Defly

💳 Payments

x402

🧪 Testing

Python test suite

⚡ Quick Start

1. Clone the repository

git clone https://github.com/ShahiTechnovation/Trestle
cd Trestle

2. Install the SDK

pip install -e "./trestle_sdk"

Or install the published SDK:

pip install trestle-sdk

3. Configure environment variables

cp contracts/.env.example contracts/.env

Configure:

AGENT_MNEMONIC=your-testnet-mnemonic
TRESTLE_APP_ID=your-testnet-app-id
VENICE_API_KEY=your-venice-api-key

🔐 Never commit a mnemonic, private key, or API key to GitHub.

4. Run the demo

python demo/SDK_DEMO.py

5. Run tests

python tests/test_sdk.py

🤖 SDK Usage

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

If the oracle rejects the request:

TrestleCreditDenied
        │
        ▼
No blockchain draw submitted

🧪 Example: Approved Draw

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

🚫 Example: Rejected Draw

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

A rejected request does not create an on-chain credit draw.

🧩 Oracle Providers

Trestle supports configurable LLM providers.

Venice AI

Venice is the default provider.

export ORACLE_PROVIDER=venice
export VENICE_API_KEY=your-key

python demo/SDK_DEMO.py

Current implementation:

llama-3.3-70b

Anthropic

export ORACLE_PROVIDER=anthropic
export ANTHROPIC_API_KEY=your-key

pip install -e "./trestle_sdk[anthropic]"

python demo/SDK_DEMO.py

Current implementation:

claude-haiku-4-5-20251001

⛓️ Smart Contract

Network: Algorand Testnet
Application ID: <YOUR_APP_ID>

Replace <YOUR_APP_ID> after deploying your own contract instance.

Contract Methods

Method

Purpose

opt_in

Bootstrap local agent state

register

Register an agent and stake ALGO

record_payment

Record payment activity

draw

Draw credit

repay

Repay outstanding credit

slash

Slash a delinquent agent

get_position

Read agent credit position

enable_attestation

Enable attestation verification

fund

Fund the protocol treasury

📦 Agent State

The smart contract tracks:

State

Description

stake_amount

Agent's staked ALGO

payment_count

Recorded payment count

total_repaid

Lifetime repayment amount

outstanding

Current unpaid balance

credit_limit

Current credit limit

is_defaulted

Whether the agent has been slashed

last_payment_round

Last recorded payment round

🔐 Security Model

Trestle deliberately separates AI decision-making from on-chain enforcement.

Off-chain

The LLM evaluates:

Task description

Expected return

Estimated execution time

Risk level

On-chain

The smart contract maintains:

Agent identity

Stake

Credit limit

Outstanding debt

Repayment history

Default state

Treasury balance

┌─────────────────────┐
│      AI Layer       │
│                     │
│  Intent + Risk      │
│  Assessment         │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   Algorand Layer    │
│                     │
│  Financial State    │
│  + Enforcement      │
└─────────────────────┘

This allows the AI layer to assess intent and risk, while Algorand remains the source of truth for financial state.

⚠️ Current Limitations

Trestle is currently a testnet hackathon prototype, so several components are intentionally simplified.

1. Testnet Environment

The system currently targets Algorand Testnet and should not be treated as production financial infrastructure.

2. Payment History

payment_count can currently be self-reported.

A future version should require bilateral verification from the payment counterparty.

3. Attestation

The current testnet configuration can skip attestation verification.

Attestation verification should be enabled before production deployment.

4. Treasury

The protocol treasury must currently be funded manually.

5. Slash Window

The prototype uses a short slash window suitable for demonstrations.

A production implementation should use a substantially longer repayment period.

🗺️ Roadmap

V2

💵 USDC / ASA-denominated credit

🔐 Verifiable / ZK oracle attestations

🤝 Bilateral payment verification

💧 Automated treasury liquidity management

🛡️ Treasury insurance pool

🪪 Persistent agent identity registry

🌉 Cross-chain deployment

⏳ Production-grade repayment windows

⚡ Stronger x402 integrations

Long-Term Vision

TODAY
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
FUTURE
 │
 └── Open credit infrastructure
     for autonomous agents

💡 The Bigger Idea

Trestle is not simply a lending contract.

It explores a new primitive:

Creditworthiness for software agents.

Human financial systems use credit histories to determine who can borrow.

Autonomous agents may need a similar mechanism.

Traditional Model

Human
  ↓
Bank
  ↓
Credit Score
  ↓
Loan

Trestle Model

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

The long-term possibility is a machine economy where autonomous agents can participate in machine-to-machine commerce without requiring a human to manually fund every transaction.

🧑‍💻 Project Structure

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

🛠️ Development

Install the SDK in editable mode:

pip install -e "./trestle_sdk"

Run the SDK demo:

python demo/SDK_DEMO.py

Run tests:

python tests/test_sdk.py

Run the intent demo:

python demo/intent_demo.py

🤝 Contributing

Contributions are welcome.

If you want to improve Trestle:

Fork the repository

Create a feature branch

Make your changes

Add or update tests

Open a pull request

git checkout -b feature/my-feature
git add .
git commit -m "feat: add my feature"
git push origin feature/my-feature

📜 License

This project is released under the MIT License.

⛓️ Built on Algorand

Trestle uses Algorand for fast, low-cost, deterministic on-chain settlement and state management.

The protocol combines:

AI Risk Assessment + On-Chain Reputation + Programmable Credit + x402 Payments

to explore a new financial primitive for autonomous software agents.

🏆 Hacker House Goa

Trestle — On-Chain Credit for Autonomous AI Agents

Built for Hacker House Goa with the goal of exploring how blockchain-based reputation and AI-driven risk assessment can enable a more autonomous machine economy.

⭐ Support the Project

If you find the idea interesting:

⭐ Star the repository

🚀 Try the Live Demo

🧪 Explore the demos

💡 Open issues and suggest improvements

🤝 Contribute to the project

Let's rethink what credit could look like when the borrower is an AI agent.

<p align="center">
  <strong>🏛️ Trestle</strong><br>
  <em>Credit infrastructure for the autonomous agent economy.</em>
</p>
