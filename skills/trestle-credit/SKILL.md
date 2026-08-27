# Trestle Credit — On-chain Credit Bureau for AI Agents

Draws undercollateralised microloans from an Algorand smart contract after an LLM risk oracle approves four hardcoded criteria. No draw reaches the chain without oracle approval.

---

## 1. Install

```bash
# From PyPI
pip install trestle-sdk

# From source
pip install -e ./trestle_sdk

# With Anthropic oracle support
pip install -e "./trestle_sdk[anthropic]"
```

### Environment Variables

| Variable           | Required | Notes                                      |
|--------------------|----------|--------------------------------------------|
| `AGENT_MNEMONIC`   | Yes      | 25-word Algorand mnemonic                  |
| `TRESTLE_APP_ID`    | Yes      | `<YOUR_APP_ID>` (testnet)                      |
| `VENICE_API_KEY`   | Default  | Venice AI oracle (default provider)        |
| `ORACLE_PROVIDER`  | No       | `"venice"` (default) or `"anthropic"`      |
| `ANTHROPIC_API_KEY`| Optional | Only if `ORACLE_PROVIDER=anthropic`        |

**.env example**

```env
AGENT_MNEMONIC=word1 word2 word3 ... word25
TRESTLE_APP_ID=<YOUR_APP_ID>
VENICE_API_KEY=your-venice-api-key
ORACLE_PROVIDER=venice
ANTHROPIC_API_KEY=
```

---

## 2. Bootstrap (one command)

```bash
trestle init --network testnet
```

What it does, in order:
- **Generates wallet** — creates a new Algorand keypair
- **Funds from faucet** — requests 3 ALGO from Algonode testnet faucet
- **Opts in** — submits `ApplicationOptInTxn` to Trestle contract (required before register)
- **Registers** — calls `register(pay)void`, staking 1 ALGO to establish credit identity
- **Writes `.trestle.env`** — saves address, mnemonic, network, app ID, and algod URL

Note: `trestle init` ships in v0.1.0.

---

## 3. Quick Start

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

---

## 4. ABI Methods Reference

| Method           | ARC-4 Signature                                                                              | Description                                         |
|------------------|----------------------------------------------------------------------------------------------|-----------------------------------------------------|
| `register`       | `register(pay)void`                                                                          | Stake ALGO, initialise agent identity               |
| `record_payment` | `record_payment(uint64)uint64`                                                               | Record repayment, increment payment count, return tier |
| `draw`           | `draw(uint64,byte[32])void`                                                                  | Draw credit; attestation hash verified on mainnet   |
| `repay`          | `repay(pay)void`                                                                             | Repay outstanding balance                           |
| `slash`          | `slash(account)void`                                                                         | Slash a delinquent agent after 30 rounds            |
| `get_position`   | `get_position(address)(uint64,uint64,uint64,uint64,uint64,uint64,uint64,uint64,uint64)`      | Read agent's full position (readonly, simulated)    |
| `seed_treasury`  | `seed_treasury(pay)void`                                                                     | Fund the contract treasury                          |
| `update_signer`  | `update_signer(account)void`                                                                 | Update the oracle signer address                    |
| `close_out`      | `close_out()void`                                                                            | Close out agent local state                         |

---

## 5. Tier Structure

| Tier | Name    | Min Payments | Max Draw (μA) | Max Draw (ALGO) | Daily Cap (μA) | APR  |
|------|---------|--------------|---------------|-----------------|----------------|------|
| 0    | Fresh   | 0            | 100,000       | 0.10 ALGO       | 500,000        | 24%  |
| 1    | Trusted | 10           | 500,000       | 0.50 ALGO       | 2,000,000      | 16%  |
| 2    | Veteran | 50           | 2,000,000     | 2.00 ALGO       | 10,000,000     | 9%   |
| 3    | Elite   | 100          | 5,000,000     | 5.00 ALGO       | 25,000,000     | 4%   |

**Interest formula (matches on-chain AVM integer arithmetic exactly):**

```
interest = (amount × APR_bps × 86400) ÷ (10000 × 31536000)
```

Example: 50,000 μA at Tier 0 (APR_bps=2400) for one day ≈ 1 μA.

---

## 6. Oracle Providers

### Venice AI (default)

```bash
export ORACLE_PROVIDER=venice   # or leave unset
export VENICE_API_KEY=your-key  # get free at https://api.venice.ai
```

- Model: `llama-3.3-70b`
- No extra install required (`openai` package already included)

### Anthropic (optional)

```bash
export ORACLE_PROVIDER=anthropic
export ANTHROPIC_API_KEY=sk-ant-...
pip install "./trestle_sdk[anthropic]"
```

- Model: `claude-haiku-4-5-20251001`
- Uses `client.beta.messages.parse()` for structured output

### The 4 Oracle Criteria

All four must pass before any draw reaches the chain:

1. **Return covers cost**: `expected_return > amount + interest`
2. **Task fits window**: `estimated_task_rounds < 86,400` (~24 hours)
3. **No outstanding debt**: `outstanding_microalgo == 0`
4. **Acceptable risk**: LLM assigns risk level `"low"` or `"medium"`

Risk levels: `low` / `medium` / `high` / `critical`. Draws with `high` or `critical` risk are always denied.

---

## 7. Common Errors and Fixes

### `TrestleCreditDenied`

- **Meaning**: Oracle denied the draw; no transaction was submitted, wallet balance unchanged.
- **Debug**: `print(e.reason)` and `print(e.criteria_results)` show which criterion failed.
- **Common causes**: task is too risky, agent has outstanding debt, expected return doesn't cover cost.

### `TrestleCreditError`

- **Meaning**: API or algod failure (network or configuration error).
- **Debug**: Check `VENICE_API_KEY` is set; verify algod URL is reachable (`https://testnet-api.algonode.cloud`).

### `"draw_exceeds_limit"` (pre-flight tier cap)

- **Meaning**: `amount > TIER_MAX_DRAW[current_tier]`
- **Fix**: Lower the draw amount, or call `agent.record_payment()` repeatedly to build tier.

### `"outstanding_debt"`

- **Meaning**: A previous draw has not been repaid.
- **Fix**: Call `agent.repay(agent.get_position()["outstanding"])` to clear the balance first.

### `"not_opted_in"` or algod error on first use

- **Fix**: Run `trestle init` to handle opt-in automatically, or run `contracts/demo_agent.py` for manual step-by-step setup.

---

## 8. x402 Integration — TrestleX402Client

`TrestleX402Client` intercepts HTTP 402 responses, draws Trestle credit, pays x402-gated APIs using Algorand USDC, and calls `record_payment()` — turning every paid API call into on-chain reputation.

**Version**: Introduced in v0.2.0

### Install

```bash
pip install "trestle-sdk[x402]"
```

### Prerequisites

Your Trestle wallet must have:
- **ALGO** for transactions (get testnet ALGO at https://bank.testnet.algorand.network/)
- The client auto opts-in to USDC ASA `10458941` on first use
- The client auto-swaps ALGO → USDC via Tinyman testnet when USDC balance is insufficient

### Quick Start

```python
import os
from trestle_sdk import TrestleCreditAgent, TrestleX402Client

agent = TrestleCreditAgent(
    mnemonic_phrase=os.environ["AGENT_MNEMONIC"],
    app_id=<YOUR_APP_ID>,  # testnet
)

# auto_opt_in=True  → opt-in to USDC ASA on first use
# auto_swap=True    → swap ALGO → USDC via Tinyman if wallet needs it
client = TrestleX402Client(agent)

# One-liner — full x402 payment flow is transparent:
response = client.get("https://x402.goplausible.xyz/examples/weather")
print(response.text)
```

### Payment Flow (What Happens Under the Hood)

```
1. GET request → server returns HTTP 402 + paymentRequirements JSON
2. Spend guard → raises TrestleX402SpendLimitExceeded if price > max_spend_per_call
3. Auto opt-in → opts wallet into USDC ASA 10458941 (once per wallet)
4. Auto-swap  → swaps ALGO → USDC via Tinyman if wallet has insufficient USDC
5. agent.draw() → draws Trestle credit (microALGO equivalent, for accounting)
6. Sign → _CredixAvmSigner signs the Algorand USDC axfer transaction
7. X-PAYMENT header → encodes payment group, retries request
8. GoPlausible facilitator → POST /verify → POST /settle → Algorand txn confirmed
9. Server returns 200 OK
10. agent.record_payment() → on-chain Trestle reputation update
```

### Constructor Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `agent` | TrestleCreditAgent | required | The Trestle agent (wallet + credit) |
| `facilitator_url` | str | GoPlausible | x402 facilitator URL |
| `network` | str | Algorand Testnet | CAIP-2 network ID |
| `usdc_asa_id` | int | `10458941` | Testnet USDC ASA ID |
| `max_spend_per_call` | int | `10_000` | Max microUSDC per request |
| `record_payment_on_success` | bool | `True` | Build Trestle reputation on success |
| `auto_opt_in` | bool | `True` | Auto opt-in to USDC ASA |
| `auto_swap` | bool | `True` | Auto swap ALGO→USDC via Tinyman |
| `usdc_to_algo_ratio` | float | `2.5` | microALGO = microUSDC × ratio |

### GoPlausible Testnet Endpoints

| Endpoint | URL |
|----------|-----|
| Example resource | `https://example.x402.goplausible.xyz/` |
| Weather API | `https://x402.goplausible.xyz/examples/weather` |
| Facilitator | `https://facilitator.goplausible.xyz` |

### Live Demo

```bash
export AGENT_MNEMONIC="word1 word2 ... word25"
export TRESTLE_APP_ID=<YOUR_APP_ID>
export VENICE_API_KEY=your-key

python demo/SDK_DEMO.py
```

### Error Reference

| Exception | Fires Before Draw? | Cause | Fix |
|-----------|-------------------|-------|-----|
| `TrestleX402SpendLimitExceeded` | ✓ Yes | 402 price > `max_spend_per_call` | Raise `max_spend_per_call` or choose cheaper resource |
| `TrestleX402SetupError` | ✓ Yes | Opt-in or auto-swap failed | Fund wallet with ALGO |
| `TrestleCreditDenied` | ✓ Yes | Trestle risk oracle denied draw | Clear outstanding debt, lower risk |
| `TrestleX402PaymentError` | ✗ No | Facilitator rejected or network error | Check `facilitator.goplausible.xyz/health` |

### Network and USDC Reference

| Network | CAIP-2 ID | USDC ASA |
|---------|-----------|----------|
| Algorand Testnet | `algorand:SGO1GKSzyE7IEPItTxCByw9x8FmnrCDexi9/cOUJOiI=` | `10458941` |
| Algorand Mainnet | `algorand:wGHE2Pwdvd7S12BL5FaOP20EGYesN73ktiC1qzkkit8=` | `31566704` |

Reference: [x402 on Algorand](https://dev.algorand.co/resources/x402-on-algorand/)

---

## 9. Links

- **PyPI**: https://pypi.org/project/trestle-sdk/
- **GitHub**: https://github.com/ShahiTechnovation/Trestle
- **Contract Explorer**: https://testnet.explorer.perawallet.app/application/<YOUR_APP_ID>
- **Live Site**: https://trestle.xyz
- **Algorand Foundation x402**: https://algorand.co/solutions/agentic-commerce
