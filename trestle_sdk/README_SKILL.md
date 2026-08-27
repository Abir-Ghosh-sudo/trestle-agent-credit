# Trestle SDK — LLM Risk Oracle

## What This Does

Install the Trestle SDK and your AI agent gets a credit line in one line of code. Call `agent.draw()` with a task description, expected return, and estimated duration. The SDK handles everything else: querying your on-chain position, running the risk oracle, computing interest, and submitting the Algorand transaction — or raising a clean exception if the oracle denies the loan.

The oracle reads your task description and applies four hardcoded criteria before any money moves. If the task is speculative, your expected return doesn't cover the loan cost, you already have an unpaid loan, or the task won't finish before the repayment deadline — the draw is denied. No transaction is ever submitted to the chain. The oracle is the guardrail.

---

## Install

```bash
# From repo root:
pip install -e "./trestle_sdk"

# With Anthropic support:
pip install -e "./trestle_sdk[anthropic]"

# Dev dependencies:
pip install -e "./trestle_sdk[dev]"
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `AGENT_MNEMONIC` | Yes | 25-word Algorand mnemonic for the agent wallet |
| `TRESTLE_APP_ID` | Yes | `<YOUR_APP_ID>` (Algorand Testnet) |
| `VENICE_API_KEY` | Default oracle | From [api.venice.ai](https://api.venice.ai) |
| `ORACLE_PROVIDER` | No | `"venice"` (default) or `"anthropic"` |
| `ANTHROPIC_API_KEY` | If `ORACLE_PROVIDER=anthropic` | Anthropic API key |

Create `.env` in your project root:

```env
AGENT_MNEMONIC=word1 word2 word3 ... word25
TRESTLE_APP_ID=<YOUR_APP_ID>
VENICE_API_KEY=your-venice-key
ORACLE_PROVIDER=venice
```

---

## One-Line Usage

```python
import os
from dotenv import load_dotenv
from trestle_sdk import TrestleCreditAgent, TrestleCreditDenied

load_dotenv()

agent = TrestleCreditAgent(
    mnemonic_phrase=os.environ["AGENT_MNEMONIC"],
    app_id=int(os.environ["TRESTLE_APP_ID"]),
)

try:
    result = agent.draw(
        amount_microalgo=50_000,
        task_description="Fetch ETH/USD price from CoinGecko and store it",
        expected_return_microalgo=80_000,
        estimated_task_rounds=120,
    )
    print(f"✅ Loan approved! txid={result['txid']}")

    # ... run your task here ...

    agent.repay(result["total_repayable"])

except TrestleCreditDenied as e:
    print(f"❌ Loan denied: {e.reason}")
```

---

## The 4 Oracle Criteria

Every `draw()` runs the oracle through four immutable checks. All four must pass:

1. **The task must earn more than it costs** — expected return must strictly exceed the loan principal plus interest. Breakeven is not enough.
2. **The task must complete within 24 hours** — estimated duration must be less than 86,400 Algorand rounds (~1 round/second).
3. **The agent must have no existing unpaid loans** — if `outstanding > 0`, the draw is denied. Loan stacking is never permitted.
4. **The task must be low or medium risk** — the oracle reads your task description and assigns: `low` (deterministic API calls), `medium` (external dependencies with clear success criteria), `high` (speculative or unverifiable), `critical` (financial speculation, irreversible actions). Only `low` and `medium` are approved.

---

## What Approved Looks Like

```python
result = agent.draw(...)
# {
#     "txid":               "TXID_ABC123...",
#     "amount_microalgo":   50000,
#     "interest_microalgo": 1,
#     "total_repayable":    50001,
#     "tier":               1,
#     "tier_name":          "Trusted",
#     "apr_bps":            1600,
#     "risk_summary":       "Low-risk deterministic API call with clear return."
# }
```

---

## What Denied Looks Like

```python
from trestle_sdk import TrestleCreditDenied

try:
    result = agent.draw(
        amount_microalgo=50_000,
        task_description="Speculative arbitrage on an unaudited new DEX",
        expected_return_microalgo=80_000,
        estimated_task_rounds=120,
    )
except TrestleCreditDenied as e:
    print(e.reason)
    # → "Criterion 4 failed: task risk level is 'critical' —
    #     financial speculation on an unaudited contract is never permitted."

    print(e.criteria_results)
    # → {
    #     "criterion_1_passed": True,
    #     "criterion_2_passed": True,
    #     "criterion_3_passed": True,
    #     "criterion_4_passed": False,
    #     "overall_approved": False,
    #     "task_risk_level": "critical",
    #     ...
    #   }
```

The on-chain `draw()` transaction is never submitted when the oracle denies.

---

## Advanced: Switching to the Anthropic Oracle

```bash
export ORACLE_PROVIDER=anthropic
export ANTHROPIC_API_KEY=sk-ant-...
pip install -e "./trestle_sdk[anthropic]"
python demo/demo_with_skill.py
```

Model: `claude-haiku-4-5-20251001`. Uses `client.beta.messages.parse()` for structured output. The returned `RiskDecision` object is identical regardless of provider.

---

## Note on Demo Mode

By default `demo_mode=True`, which means the attestation hash is `bytes(32)` and the contract does not verify it on-chain. This is safe for testnet. Set `demo_mode=False` for production deployments after calling `enable_attestation()` on the contract.
