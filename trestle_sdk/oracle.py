"""
oracle.py — LLM risk oracle supporting Venice AI (default) and Anthropic.
Provider controlled by ORACLE_PROVIDER env var.

This is the "AI Risk Skill" — the immutable risk gate that every draw() call
must pass before any on-chain transaction is submitted.

Venice AI (default):
    Uses the openai Python client (OpenAI-compatible API).
    Set VENICE_API_KEY in your environment.
    Model: llama-3.3-70b

Anthropic (optional):
    Uses the anthropic Python client with structured output.
    Set ANTHROPIC_API_KEY and ORACLE_PROVIDER=anthropic.
    Model: claude-haiku-4-5-20251001

Provider selection:
    ORACLE_PROVIDER=venice      → Venice AI, llama-3.3-70b (default)
    ORACLE_PROVIDER=anthropic   → Anthropic, claude-haiku-4-5-20251001
"""

import json
import os
from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

from pydantic import BaseModel, Field, ValidationError

# Venice AI uses the OpenAI-compatible client (always required)
from openai import OpenAI  # noqa: F401 — kept at module level for patch() in tests

# Anthropic is optional; imported here so tests can patch "trestle_sdk.oracle.Anthropic"
try:
    from anthropic import Anthropic  # noqa: F401
except ImportError:
    Anthropic = None  # type: ignore[assignment,misc]

VENICE_BASE_URL: str = "https://api.venice.ai/api/v1"

from .criteria import (
    get_tier,
    calculate_interest,
    max_draw,
    apr_bps as get_apr_bps,
    tier_name,
)
from .exceptions import TrestleCreditDenied, TrestleCreditError

if TYPE_CHECKING:
    from algosdk.v2client.algod import AlgodClient


# ── System prompt (module-level constant) ──────────────────────────────────────

ORACLE_SYSTEM_PROMPT = """
You are a risk assessment oracle for Trestle, an on-chain AI agent credit
protocol on Algorand. Your role is to evaluate whether an AI agent should
be granted a microloan to complete a specific task.

You evaluate EXACTLY four criteria. Apply them strictly.
The protocol's solvency depends on your accuracy.
Do not be lenient because amounts are small.

CRITERION 1 — Return must exceed cost:
Check: expected_return_microalgo > amount_microalgo + interest_microalgo
If expected_return <= amount + interest, FAIL. No exceptions.

CRITERION 2 — Task must fit repayment window:
Algorand produces ~1 round per second. Repayment window is 86,400 rounds
(approximately 24 hours). If estimated_task_rounds >= 86,400, FAIL.

CRITERION 3 — No outstanding debt:
Check: current_outstanding_microalgo == 0
If the agent has ANY unpaid balance, FAIL immediately.
Loan stacking is never permitted under any circumstances.

CRITERION 4 — Task risk level:
Evaluate the task description and assign a risk level:
  low:      deterministic, bounded tasks (API calls, data fetches, calculations)
  medium:   tasks with external dependencies but clear, verifiable success criteria
  high:     tasks with speculative outcomes, unclear success, or unverifiable results
  critical: financial speculation, untested contracts, rug risk, irreversible actions

PASS if risk level is low or medium.
FAIL if risk level is high or critical.

overall_approved must be the strict logical AND of all four criteria.
"""


# ── Pydantic model for structured output ───────────────────────────────────────

class CriteriaEvaluation(BaseModel):
    """Structured output returned by the LLM oracle during risk assessment.

    All fields are mandatory.  The model fills them based on the user message
    that contains the draw request details.
    """

    criterion_1_passed: bool = Field(
        description=(
            "True if expected_return_microalgo strictly exceeds "
            "amount_microalgo plus interest_microalgo. "
            "False if return <= cost."
        )
    )
    criterion_2_passed: bool = Field(
        description=(
            "True if estimated_task_rounds is strictly less than "
            "86400 (one day in Algorand rounds). "
            "False if task may not complete before repayment deadline."
        )
    )
    criterion_3_passed: bool = Field(
        description=(
            "True if current_outstanding_microalgo is exactly 0. "
            "False if agent already has an unpaid loan. "
            "Loan stacking is never permitted."
        )
    )
    criterion_4_passed: bool = Field(
        description=(
            "True if the task risk level is 'low' or 'medium'. "
            "False if task risk level is 'high' or 'critical'. "
            "Risk levels: "
            "low=deterministic API calls or data fetching; "
            "medium=external dependency with clear success condition; "
            "high=speculative or unverifiable outcome; "
            "critical=financial speculation, rug risk, or irreversible action."
        )
    )
    overall_approved: bool = Field(
        description=(
            "True ONLY if all four criteria are True. "
            "Must be the logical AND of all four. "
            "No exceptions."
        )
    )
    task_risk_level: str = Field(
        description="One of: low, medium, high, critical"
    )
    denial_reason: str = Field(
        description=(
            "If overall_approved is False: state exactly which criterion "
            "failed and the specific reason. "
            "If overall_approved is True: empty string."
        )
    )
    risk_summary: str = Field(
        description=(
            "One sentence plain-English summary of the risk assessment. "
            "Suitable for logging."
        )
    )


# ── RiskDecision dataclass ─────────────────────────────────────────────────────

@dataclass
class RiskDecision:
    """Full result from a successful risk oracle evaluation.

    Returned by :meth:`RiskOracle.evaluate` when ``overall_approved`` is
    ``True``.  The ``attestation_hash`` field is ready to pass directly to
    the ``draw()`` ATC method call.

    Attributes:
        approved: Always ``True`` for this dataclass (denial raises instead).
        tier: Agent's current tier index (0–3).
        tier_name: Human-readable tier name.
        amount_microalgo: Requested draw principal.
        interest_microalgo: Interest charged for one-day loan.
        total_repayable: Principal + interest.
        apr_bps: Annual percentage rate in basis points.
        criteria: Full structured evaluation from the oracle.
        attestation_hash: 32-byte hash ready to pass to draw().
        current_round: Algorand round at evaluation time.
    """

    approved: bool
    tier: int
    tier_name: str
    amount_microalgo: int
    interest_microalgo: int
    total_repayable: int
    apr_bps: int
    criteria: CriteriaEvaluation
    attestation_hash: bytes       # exactly 32 bytes — pass directly to draw()
    current_round: int


# ── RiskOracle class ───────────────────────────────────────────────────────────

class RiskOracle:
    """LLM risk oracle supporting Venice AI (default) and Anthropic.
    Provider controlled by ORACLE_PROVIDER env var.

    Calls the configured LLM provider using structured outputs to evaluate
    four hardcoded criteria before any credit draw.  The four criteria are
    immutable — agent developers cannot override them.

    Provider selection:
        ORACLE_PROVIDER=venice     → Venice AI, llama-3.3-70b (default)
        ORACLE_PROVIDER=anthropic  → Anthropic, claude-haiku-4-5-20251001

    Example::

        oracle = RiskOracle(algod_client=my_algod)
        try:
            decision = oracle.evaluate(
                agent_address="ALGO...",
                amount_microalgo=50_000,
                payment_count=21,
                outstanding_microalgo=0,
                task_description="Fetch ETH/USD price from CoinGecko",
                expected_return_microalgo=80_000,
                estimated_task_rounds=120,
            )
            # decision.attestation_hash is ready to pass to draw()
        except TrestleCreditDenied as e:
            print(e.reason)
    """

    def __init__(
        self,
        algod_client: "AlgodClient",
        venice_api_key: Optional[str] = None,
        anthropic_api_key: Optional[str] = None,
        demo_mode: bool = True,
    ) -> None:
        """Initialise the risk oracle.

        Args:
            algod_client: Algosdk AlgodClient connected to testnet or mainnet.
            venice_api_key: Venice AI key. Defaults to the VENICE_API_KEY
                environment variable if not provided.
            anthropic_api_key: Anthropic key. Defaults to the ANTHROPIC_API_KEY
                environment variable if not provided.
            demo_mode: If True, the attestation_hash in the returned
                RiskDecision will be bytes(32) regardless of what the oracle
                computes. Set to False for production deployments where the
                contract verifies the hash on-chain.

        Provider selection:
            Set ORACLE_PROVIDER env var to control which LLM is used.
            ORACLE_PROVIDER=venice     → Venice AI, llama-3.3-70b (default)
            ORACLE_PROVIDER=anthropic  → Anthropic, claude-haiku-4-5-20251001
        """
        self.algod_client = algod_client
        self.demo_mode = demo_mode
        self.provider = os.environ.get("ORACLE_PROVIDER", "venice").lower()

        if self.provider == "anthropic":
            if Anthropic is None:
                raise ImportError(
                    "anthropic package is required for ORACLE_PROVIDER=anthropic. "
                    "Install with: pip install -e './trestle_sdk[anthropic]'"
                )
            self.model = "claude-haiku-4-5-20251001"
            self._anthropic_client = Anthropic(
                api_key=anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY")
            )
            self._openai_client = None
        else:
            # Venice (default) — OpenAI-compatible API
            self.model = "llama-3.3-70b"
            self._openai_client = OpenAI(
                api_key=venice_api_key or os.environ.get("VENICE_API_KEY"),
                base_url=VENICE_BASE_URL,
            )
            self._anthropic_client = None

    def _call_oracle(self, user_message: str) -> CriteriaEvaluation:
        """Call the configured LLM provider and return a validated CriteriaEvaluation.

        Venice path:
            Uses openai client (OpenAI-compatible).
            Prompts for raw JSON. Parses and validates with Pydantic.

        Anthropic path:
            Uses client.beta.messages.parse() with response_model=CriteriaEvaluation.
            Returns validated CriteriaEvaluation directly via parsed_output.

        Both paths return an identical CriteriaEvaluation object.
        Both paths raise TrestleCreditError on API failure.

        Args:
            user_message: Formatted draw request string to send to the oracle.

        Returns:
            Validated CriteriaEvaluation with all fields populated.

        Raises:
            TrestleCreditError: If the API call fails or returns invalid JSON.
        """
        try:
            if self.provider == "anthropic":
                response = self._anthropic_client.beta.messages.parse(
                    model=self.model,
                    max_tokens=512,
                    system=ORACLE_SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": user_message}],
                    response_model=CriteriaEvaluation,
                )
                return response.parsed_output

            else:
                # Venice / OpenAI-compatible path
                json_instruction = (
                    "\n\nRESPONSE FORMAT: You MUST respond with ONLY valid JSON. "
                    "No preamble. No markdown. No code fences. Raw JSON only. "
                    "Schema: {\"criterion_1_passed\": bool, "
                    "\"criterion_2_passed\": bool, "
                    "\"criterion_3_passed\": bool, "
                    "\"criterion_4_passed\": bool, "
                    "\"overall_approved\": bool, "
                    "\"task_risk_level\": \"low|medium|high|critical\", "
                    "\"denial_reason\": \"string (empty if approved)\", "
                    "\"risk_summary\": \"string\"}"
                )
                response = self._openai_client.chat.completions.create(
                    model=self.model,
                    max_tokens=512,
                    messages=[
                        {"role": "system", "content": ORACLE_SYSTEM_PROMPT + json_instruction},
                        {"role": "user", "content": user_message},
                    ],
                )
                raw = response.choices[0].message.content.strip()
                # Strip markdown fences if model adds them
                if raw.startswith("```"):
                    parts = raw.split("```")
                    raw = parts[1]
                    if raw.startswith("json"):
                        raw = raw[4:]
                    raw = raw.strip()
                parsed = json.loads(raw)
                return CriteriaEvaluation(**parsed)

        except json.JSONDecodeError as exc:
            raise TrestleCreditError(f"Oracle returned invalid JSON: {exc}") from exc
        except Exception as exc:
            raise TrestleCreditError(f"Oracle API call failed: {exc}") from exc

    def evaluate(
        self,
        agent_address: str,
        amount_microalgo: int,
        payment_count: int,
        outstanding_microalgo: int,
        task_description: str,
        expected_return_microalgo: int,
        estimated_task_rounds: int,
    ) -> RiskDecision:
        """Run the four-criteria risk assessment and return a RiskDecision.

        Pre-flight check (before calling the AI oracle):
            If ``amount_microalgo`` exceeds the tier's ``max_draw`` cap, raise
            :class:`TrestleCreditDenied` immediately without consuming API credits.

        Then calls the configured LLM oracle via :meth:`_call_oracle` for
        structured risk evaluation.

        Args:
            agent_address: Algorand address of the agent wallet.
            amount_microalgo: Requested draw amount in microALGO.
            payment_count: Number of completed repayments, from
                ``get_position()[1]`` on-chain.
            outstanding_microalgo: Current unpaid balance, from
                ``get_position()[3]`` on-chain.
            task_description: Plain-English description of what the agent will
                do with the borrowed credit.
            expected_return_microalgo: Agent's expected revenue from completing
                the task, in microALGO.
            estimated_task_rounds: How many Algorand rounds the task will take.
                Must be < 86,400 to pass criterion 2.

        Returns:
            :class:`RiskDecision` with ``attestation_hash`` ready for
            ``draw()``.

        Raises:
            TrestleCreditDenied: Any criterion fails (pre-flight or oracle).
            TrestleCreditError: LLM API or algod call failed.
        """
        tier = get_tier(payment_count)
        interest = calculate_interest(amount_microalgo, tier)
        tier_max = max_draw(tier)

        # ── Pre-flight: hard tier cap ──────────────────────────────────────────
        # Check before calling the oracle to save API cost on obvious failures.
        if amount_microalgo > tier_max:
            raise TrestleCreditDenied(
                reason=(
                    f"Amount {amount_microalgo} microALGO exceeds tier {tier} "
                    f"({tier_name(tier)}) max draw of {tier_max} microALGO"
                ),
                criteria_results={},
            )

        # ── Build the user message for the oracle ─────────────────────────────
        user_message = (
            f"Evaluate this AI agent credit draw request:\n\n"
            f"AGENT ADDRESS: {agent_address}\n"
            f"REQUESTED DRAW: {amount_microalgo} microALGO\n"
            f"INTEREST CHARGE: {interest} microALGO\n"
            f"TOTAL TO REPAY: {amount_microalgo + interest} microALGO\n"
            f"CURRENT OUTSTANDING DEBT: {outstanding_microalgo} microALGO\n"
            f"PAYMENT HISTORY: {payment_count} repayments — Tier {tier} ({tier_name(tier)})\n"
            f"EXPECTED RETURN FROM TASK: {expected_return_microalgo} microALGO\n"
            f"ESTIMATED TASK DURATION: {estimated_task_rounds} rounds\n"
            f"REPAYMENT WINDOW: 86400 rounds\n\n"
            f"TASK DESCRIPTION:\n{task_description}\n\n"
            f"Evaluate all 4 criteria and return your structured assessment."
        )

        # ── Call the oracle ───────────────────────────────────────────────────
        evaluation: CriteriaEvaluation = self._call_oracle(user_message)

        # ── Raise on denial ───────────────────────────────────────────────────
        if not evaluation.overall_approved:
            raise TrestleCreditDenied(
                reason=evaluation.denial_reason,
                criteria_results=evaluation.model_dump(),
            )

        # ── Compute attestation hash ──────────────────────────────────────────
        from .hash_util import get_current_round, compute_attestation_hash, demo_hash

        try:
            current_round = get_current_round(self.algod_client)
        except Exception as exc:
            raise TrestleCreditError(
                f"Failed to query algod for current round: {exc}"
            ) from exc

        if self.demo_mode:
            # Contract skips hash verification when skip_attestation == 1.
            attestation = demo_hash()
        else:
            attestation = compute_attestation_hash(
                sender_address=agent_address,
                amount_microalgo=amount_microalgo,
                current_round=current_round,
            )

        return RiskDecision(
            approved=True,
            tier=tier,
            tier_name=tier_name(tier),
            amount_microalgo=amount_microalgo,
            interest_microalgo=interest,
            total_repayable=amount_microalgo + interest,
            apr_bps=get_apr_bps(tier),
            criteria=evaluation,
            attestation_hash=attestation,
            current_round=current_round,
        )
