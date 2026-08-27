"""
tests/test_oracle.py

Tests for RiskOracle (approve/deny flows) and TrestleCreditAgent draw() behaviour.

Mock strategy:
  - RiskOracle._call_oracle() is patched to return a CriteriaEvaluation directly.
    This bypasses Venice AI / Anthropic entirely — no API key required.
  - trestle_sdk.oracle.OpenAI is patched so the RiskOracle constructor
    doesn't need a real VENICE_API_KEY at init time.
  - trestle_sdk.chain.get_position is patched to return a known agent state.
  - trestle_sdk.chain.do_draw is patched to return a fake txid.
  - algod_client.status() is patched to return a fixed round number.

Integration tests (require a real VENICE_API_KEY) are marked with
@pytest.mark.integration and skipped automatically when the key is absent.
Run them with: VENICE_API_KEY=your-key pytest -m integration
"""

import os
import pytest
from unittest.mock import patch, MagicMock, call

from trestle_sdk.oracle import (
    RiskOracle,
    RiskDecision,
    CriteriaEvaluation,
    ORACLE_SYSTEM_PROMPT,
)
from trestle_sdk.agent import TrestleCreditAgent
from trestle_sdk.exceptions import TrestleCreditDenied, TrestleCreditError


# ══════════════════════════════════════════════════════════════════
# Helpers — build CriteriaEvaluation objects for mocking
# ══════════════════════════════════════════════════════════════════

def approved_evaluation(
    risk_level: str = "low",
    risk_summary: str = "Low-risk deterministic API call.",
) -> CriteriaEvaluation:
    """Return a CriteriaEvaluation where all criteria pass."""
    return CriteriaEvaluation(
        criterion_1_passed=True,
        criterion_2_passed=True,
        criterion_3_passed=True,
        criterion_4_passed=True,
        overall_approved=True,
        task_risk_level=risk_level,
        denial_reason="",
        risk_summary=risk_summary,
    )


def denied_evaluation(
    failed_criterion: int,
    denial_reason: str,
    risk_level: str = "low",
) -> CriteriaEvaluation:
    """Return a CriteriaEvaluation where one criterion fails."""
    return CriteriaEvaluation(
        criterion_1_passed=(failed_criterion != 1),
        criterion_2_passed=(failed_criterion != 2),
        criterion_3_passed=(failed_criterion != 3),
        criterion_4_passed=(failed_criterion != 4),
        overall_approved=False,
        task_risk_level=risk_level,
        denial_reason=denial_reason,
        risk_summary=f"Denied: {denial_reason}",
    )


# ══════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════

FAKE_ADDRESS = "7XQ3XBZVGG4JVLXDTBSM6FVXRGJPTZZUQSZ3S5GVXZDA2HDQHKQA"
FAKE_TXID    = "TXID_ABCDEF1234567890ABCDEF1234567890ABCDEF1234567890ABCDEF"
FIXED_ROUND  = 12_345

# Standard agent position returned by mock get_position
CLEAN_POSITION = {
    "stake_amount":   1_000_000,
    "payment_count":  0,
    "tier_max_draw":  100_000,
    "outstanding":    0,
    "is_defaulted":   0,
    "tier":           0,
    "apr_bps":        2400,
    "daily_drawn":    0,
    "repay_by_round": 0,
}


@pytest.fixture
def mock_algod():
    """Algod client that returns a fixed round number."""
    client = MagicMock()
    client.status.return_value = {"last-round": FIXED_ROUND}
    return client


@pytest.fixture
def oracle(mock_algod):
    """RiskOracle with OpenAI constructor patched out (no API key needed)."""
    with patch("trestle_sdk.oracle.OpenAI"):
        return RiskOracle(algod_client=mock_algod, demo_mode=True)


@pytest.fixture
def agent():
    """
    TrestleCreditAgent with all on-chain calls patched out.
    Provides a clean agent instance for draw() and repay() testing.
    """
    with patch("trestle_sdk.oracle.OpenAI"), \
         patch("trestle_sdk.agent.make_algod_client") as mock_make_algod, \
         patch("trestle_sdk.agent.get_position", return_value=CLEAN_POSITION):

        mock_algod_instance = MagicMock()
        mock_algod_instance.status.return_value = {"last-round": FIXED_ROUND}
        mock_make_algod.return_value = mock_algod_instance

        yield TrestleCreditAgent(
            mnemonic_phrase=(
                "charge joke seat return blood indicate learn foot immune initial bid wide gift "
                "cry hood purchase sunset false return spring crunch artefact marine about fan"
            ),
            app_id=999999,  # dummy — algod/agent are mocked above, no real network calls
            demo_mode=True,
        )


# ══════════════════════════════════════════════════════════════════
# CriteriaEvaluation — structural tests (no LLM needed)
# ══════════════════════════════════════════════════════════════════

class TestCriteriaEvaluationModel:

    def test_approved_evaluation_all_true(self):
        ev = approved_evaluation()
        assert ev.criterion_1_passed is True
        assert ev.criterion_2_passed is True
        assert ev.criterion_3_passed is True
        assert ev.criterion_4_passed is True
        assert ev.overall_approved   is True

    def test_denied_evaluation_criterion_1(self):
        ev = denied_evaluation(1, "Return does not cover cost")
        assert ev.criterion_1_passed is False
        assert ev.overall_approved   is False

    def test_denied_evaluation_criterion_2(self):
        ev = denied_evaluation(2, "Task exceeds 86400 rounds")
        assert ev.criterion_2_passed is False
        assert ev.overall_approved   is False

    def test_denied_evaluation_criterion_3(self):
        ev = denied_evaluation(3, "Outstanding debt exists")
        assert ev.criterion_3_passed is False
        assert ev.overall_approved   is False

    def test_denied_evaluation_criterion_4(self):
        ev = denied_evaluation(4, "Task risk is critical", risk_level="critical")
        assert ev.criterion_4_passed is False
        assert ev.task_risk_level    == "critical"
        assert ev.overall_approved   is False

    def test_model_dump_has_all_expected_keys(self):
        ev = approved_evaluation()
        dumped = ev.model_dump()
        expected_keys = {
            "criterion_1_passed",
            "criterion_2_passed",
            "criterion_3_passed",
            "criterion_4_passed",
            "overall_approved",
            "task_risk_level",
            "denial_reason",
            "risk_summary",
        }
        assert expected_keys.issubset(set(dumped.keys()))

    def test_approved_has_empty_denial_reason(self):
        ev = approved_evaluation()
        assert ev.denial_reason == ""

    def test_denied_has_nonempty_denial_reason(self):
        ev = denied_evaluation(4, "Speculative task denied.")
        assert len(ev.denial_reason) > 0


# ══════════════════════════════════════════════════════════════════
# RiskOracle.evaluate() — pre-flight checks (no LLM call)
# ══════════════════════════════════════════════════════════════════

class TestOraclePreflightChecks:
    """
    evaluate() does one check BEFORE calling the LLM:
    if amount > max_draw(tier), raise TrestleCreditDenied immediately.
    These tests verify that behaviour without touching the LLM at all.
    """

    def test_exceeds_tier_0_cap_raises_denied(self, oracle):
        """Tier 0 cap is 100,000 uA. 100,001 uA should fail pre-flight."""
        with pytest.raises(TrestleCreditDenied) as exc_info:
            oracle.evaluate(
                agent_address=FAKE_ADDRESS,
                amount_microalgo=100_001,   # 1 uA over Tier 0 cap
                payment_count=0,            # → Tier 0
                outstanding_microalgo=0,
                task_description="Fetch price",
                expected_return_microalgo=200_000,
                estimated_task_rounds=120,
            )
        assert "100001" in exc_info.value.reason or "100_001" in exc_info.value.reason \
            or "max draw" in exc_info.value.reason.lower() \
            or "tier 0" in exc_info.value.reason.lower()

    def test_exceeds_tier_1_cap_raises_denied(self, oracle):
        """Tier 1 cap is 500,000 uA. 500,001 uA should fail pre-flight."""
        with pytest.raises(TrestleCreditDenied):
            oracle.evaluate(
                agent_address=FAKE_ADDRESS,
                amount_microalgo=500_001,
                payment_count=10,           # → Tier 1
                outstanding_microalgo=0,
                task_description="Fetch price",
                expected_return_microalgo=600_000,
                estimated_task_rounds=120,
            )

    def test_exactly_at_tier_cap_does_not_fail_preflight(self, oracle, mock_algod):
        """
        Exactly at the cap (100,000 uA for Tier 0) should pass pre-flight
        and proceed to the LLM call. We mock _call_oracle to avoid the API.
        """
        with patch.object(
            oracle, "_call_oracle",
            return_value=approved_evaluation()
        ):
            decision = oracle.evaluate(
                agent_address=FAKE_ADDRESS,
                amount_microalgo=100_000,   # exactly at Tier 0 cap
                payment_count=0,
                outstanding_microalgo=0,
                task_description="Deterministic price fetch",
                expected_return_microalgo=200_000,
                estimated_task_rounds=120,
            )
        assert decision.approved is True

    def test_preflight_denial_has_empty_criteria_results(self, oracle):
        """Pre-flight denials skip the LLM, so criteria_results is {}."""
        with pytest.raises(TrestleCreditDenied) as exc_info:
            oracle.evaluate(
                agent_address=FAKE_ADDRESS,
                amount_microalgo=999_999,   # way over Tier 0 cap
                payment_count=0,
                outstanding_microalgo=0,
                task_description="anything",
                expected_return_microalgo=1_000_000,
                estimated_task_rounds=120,
            )
        assert exc_info.value.criteria_results == {}


# ══════════════════════════════════════════════════════════════════
# RiskOracle.evaluate() — LLM approval / denial flows
# ══════════════════════════════════════════════════════════════════

class TestOracleApprovalFlow:

    def test_approved_returns_risk_decision(self, oracle):
        with patch.object(oracle, "_call_oracle", return_value=approved_evaluation()):
            decision = oracle.evaluate(
                agent_address=FAKE_ADDRESS,
                amount_microalgo=50_000,
                payment_count=0,
                outstanding_microalgo=0,
                task_description="Fetch ETH/USD price from CoinGecko",
                expected_return_microalgo=80_000,
                estimated_task_rounds=120,
            )
        assert isinstance(decision, RiskDecision)

    def test_approved_decision_is_true(self, oracle):
        with patch.object(oracle, "_call_oracle", return_value=approved_evaluation()):
            decision = oracle.evaluate(
                agent_address=FAKE_ADDRESS,
                amount_microalgo=50_000,
                payment_count=0,
                outstanding_microalgo=0,
                task_description="Fetch ETH/USD from CoinGecko",
                expected_return_microalgo=80_000,
                estimated_task_rounds=120,
            )
        assert decision.approved is True

    def test_approved_decision_contains_attestation_hash(self, oracle):
        """In demo_mode=True, attestation_hash must be bytes(32)."""
        with patch.object(oracle, "_call_oracle", return_value=approved_evaluation()):
            decision = oracle.evaluate(
                agent_address=FAKE_ADDRESS,
                amount_microalgo=50_000,
                payment_count=0,
                outstanding_microalgo=0,
                task_description="Fetch price",
                expected_return_microalgo=80_000,
                estimated_task_rounds=120,
            )
        assert isinstance(decision.attestation_hash, bytes)
        assert len(decision.attestation_hash) == 32

    def test_approved_demo_mode_hash_is_32_zero_bytes(self, oracle):
        with patch.object(oracle, "_call_oracle", return_value=approved_evaluation()):
            decision = oracle.evaluate(
                agent_address=FAKE_ADDRESS,
                amount_microalgo=50_000,
                payment_count=0,
                outstanding_microalgo=0,
                task_description="Fetch price",
                expected_return_microalgo=80_000,
                estimated_task_rounds=120,
            )
        assert decision.attestation_hash == bytes(32)

    def test_approved_decision_tier_matches_payment_count(self, oracle):
        """10 payments → Tier 1 (Trusted)."""
        with patch.object(oracle, "_call_oracle", return_value=approved_evaluation()):
            decision = oracle.evaluate(
                agent_address=FAKE_ADDRESS,
                amount_microalgo=50_000,
                payment_count=10,
                outstanding_microalgo=0,
                task_description="Fetch price",
                expected_return_microalgo=80_000,
                estimated_task_rounds=120,
            )
        assert decision.tier == 1
        assert decision.tier_name == "Trusted"
        assert decision.apr_bps == 1600

    def test_approved_decision_total_repayable(self, oracle):
        """total_repayable == amount + interest."""
        with patch.object(oracle, "_call_oracle", return_value=approved_evaluation()):
            decision = oracle.evaluate(
                agent_address=FAKE_ADDRESS,
                amount_microalgo=50_000,
                payment_count=0,
                outstanding_microalgo=0,
                task_description="Fetch price",
                expected_return_microalgo=80_000,
                estimated_task_rounds=120,
            )
        assert decision.total_repayable == decision.amount_microalgo + decision.interest_microalgo

    def test_approved_decision_interest_is_non_negative(self, oracle):
        with patch.object(oracle, "_call_oracle", return_value=approved_evaluation()):
            decision = oracle.evaluate(
                agent_address=FAKE_ADDRESS,
                amount_microalgo=50_000,
                payment_count=0,
                outstanding_microalgo=0,
                task_description="Fetch price",
                expected_return_microalgo=80_000,
                estimated_task_rounds=120,
            )
        assert decision.interest_microalgo >= 0

    def test_approved_decision_current_round_set(self, oracle):
        with patch.object(oracle, "_call_oracle", return_value=approved_evaluation()):
            decision = oracle.evaluate(
                agent_address=FAKE_ADDRESS,
                amount_microalgo=50_000,
                payment_count=0,
                outstanding_microalgo=0,
                task_description="Fetch price",
                expected_return_microalgo=80_000,
                estimated_task_rounds=120,
            )
        assert decision.current_round == FIXED_ROUND


class TestOracleDenialFlow:

    def _deny(self, oracle, failed_criterion, reason, risk_level="low", **kwargs):
        """Helper: call evaluate() expecting a TrestleCreditDenied."""
        ev = denied_evaluation(failed_criterion, reason, risk_level)
        with patch.object(oracle, "_call_oracle", return_value=ev):
            with pytest.raises(TrestleCreditDenied) as exc_info:
                oracle.evaluate(**{
                    "agent_address": FAKE_ADDRESS,
                    "amount_microalgo": 50_000,
                    "payment_count": 0,
                    "outstanding_microalgo": 0,
                    "task_description": "some task",
                    "expected_return_microalgo": 80_000,
                    "estimated_task_rounds": 120,
                    **kwargs
                })
        return exc_info.value

    def test_criterion_1_denial_raises(self, oracle):
        """Expected return ≤ cost → denied."""
        exc = self._deny(oracle, 1, "Return does not cover loan cost")
        assert isinstance(exc, TrestleCreditDenied)

    def test_criterion_2_denial_raises(self, oracle):
        """Task duration ≥ 86,400 rounds → denied."""
        exc = self._deny(oracle, 2, "Task exceeds 24-hour window")
        assert isinstance(exc, TrestleCreditDenied)

    def test_criterion_3_denial_raises(self, oracle):
        """Outstanding debt > 0 → denied."""
        exc = self._deny(oracle, 3, "Agent has unpaid balance")
        assert isinstance(exc, TrestleCreditDenied)

    def test_criterion_4_denial_high_risk(self, oracle):
        """High-risk task description → denied."""
        exc = self._deny(
            oracle, 4, "Task risk level is high",
            risk_level="high",
            task_description="Speculative arbitrage on unknown contract",
        )
        assert isinstance(exc, TrestleCreditDenied)

    def test_criterion_4_denial_critical_risk(self, oracle):
        """Critical-risk task → denied."""
        exc = self._deny(
            oracle, 4,
            "Criterion 4 failed: task risk level is 'critical'",
            risk_level="critical",
            task_description="Rug pull on unaudited DEX",
        )
        assert isinstance(exc, TrestleCreditDenied)

    def test_denial_reason_is_nonempty_string(self, oracle):
        exc = self._deny(oracle, 4, "Task risk is critical", risk_level="critical")
        assert isinstance(exc.reason, str)
        assert len(exc.reason) > 0

    def test_denial_criteria_results_has_expected_keys(self, oracle):
        exc = self._deny(oracle, 4, "Denied")
        keys = set(exc.criteria_results.keys())
        required = {
            "criterion_1_passed",
            "criterion_2_passed",
            "criterion_3_passed",
            "criterion_4_passed",
            "overall_approved",
        }
        assert required.issubset(keys)

    def test_denial_criteria_results_overall_approved_false(self, oracle):
        exc = self._deny(oracle, 2, "Too slow")
        assert exc.criteria_results["overall_approved"] is False

    def test_denial_does_not_call_algod_status(self, oracle, mock_algod):
        """When oracle denies, we never reach the round-query step."""
        with patch.object(
            oracle, "_call_oracle",
            return_value=denied_evaluation(4, "risky")
        ):
            with pytest.raises(TrestleCreditDenied):
                oracle.evaluate(
                    agent_address=FAKE_ADDRESS,
                    amount_microalgo=50_000,
                    payment_count=0,
                    outstanding_microalgo=0,
                    task_description="risky task",
                    expected_return_microalgo=80_000,
                    estimated_task_rounds=120,
                )
        # algod.status() is called inside get_current_round() which is AFTER
        # the approval check — so it should NOT have been called on denial
        mock_algod.status.assert_not_called()


# ══════════════════════════════════════════════════════════════════
# ORACLE_SYSTEM_PROMPT — content sanity checks
# ══════════════════════════════════════════════════════════════════

class TestOracleSystemPrompt:
    """Verify the system prompt contains the criteria the protocol relies on."""

    def test_prompt_mentions_all_four_criteria(self):
        for n in ["CRITERION 1", "CRITERION 2", "CRITERION 3", "CRITERION 4"]:
            assert n in ORACLE_SYSTEM_PROMPT, f"Missing: {n}"

    def test_prompt_mentions_86400(self):
        """Repayment window must be explicitly stated."""
        assert "86,400" in ORACLE_SYSTEM_PROMPT or "86400" in ORACLE_SYSTEM_PROMPT

    def test_prompt_mentions_risk_levels(self):
        for level in ["low", "medium", "high", "critical"]:
            assert level in ORACLE_SYSTEM_PROMPT

    def test_prompt_is_nonempty(self):
        assert len(ORACLE_SYSTEM_PROMPT.strip()) > 100


# ══════════════════════════════════════════════════════════════════
# TrestleCreditAgent.draw() — integration with oracle and chain
# ══════════════════════════════════════════════════════════════════

class TestAgentDrawApproval:

    def test_draw_returns_dict_on_approval(self, agent):
        with patch.object(agent.oracle, "_call_oracle", return_value=approved_evaluation()), \
             patch("trestle_sdk.agent.do_draw", return_value=FAKE_TXID):
            result = agent.draw(
                amount_microalgo=50_000,
                task_description="Fetch ETH/USD price from CoinGecko",
                expected_return_microalgo=80_000,
                estimated_task_rounds=120,
            )
        assert isinstance(result, dict)

    def test_draw_result_has_all_required_keys(self, agent):
        required_keys = {
            "txid", "amount_microalgo", "interest_microalgo",
            "total_repayable", "tier", "tier_name", "apr_bps", "risk_summary",
        }
        with patch.object(agent.oracle, "_call_oracle", return_value=approved_evaluation()), \
             patch("trestle_sdk.agent.do_draw", return_value=FAKE_TXID):
            result = agent.draw(
                amount_microalgo=50_000,
                task_description="Fetch price",
                expected_return_microalgo=80_000,
                estimated_task_rounds=120,
            )
        assert required_keys.issubset(set(result.keys()))

    def test_draw_result_txid_matches_chain_return(self, agent):
        with patch.object(agent.oracle, "_call_oracle", return_value=approved_evaluation()), \
             patch("trestle_sdk.agent.do_draw", return_value=FAKE_TXID):
            result = agent.draw(
                amount_microalgo=50_000,
                task_description="Fetch price",
                expected_return_microalgo=80_000,
                estimated_task_rounds=120,
            )
        assert result["txid"] == FAKE_TXID

    def test_draw_result_amount_matches_request(self, agent):
        with patch.object(agent.oracle, "_call_oracle", return_value=approved_evaluation()), \
             patch("trestle_sdk.agent.do_draw", return_value=FAKE_TXID):
            result = agent.draw(
                amount_microalgo=50_000,
                task_description="Fetch price",
                expected_return_microalgo=80_000,
                estimated_task_rounds=120,
            )
        assert result["amount_microalgo"] == 50_000

    def test_draw_result_total_repayable_is_amount_plus_interest(self, agent):
        with patch.object(agent.oracle, "_call_oracle", return_value=approved_evaluation()), \
             patch("trestle_sdk.agent.do_draw", return_value=FAKE_TXID):
            result = agent.draw(
                amount_microalgo=50_000,
                task_description="Fetch price",
                expected_return_microalgo=80_000,
                estimated_task_rounds=120,
            )
        assert result["total_repayable"] == result["amount_microalgo"] + result["interest_microalgo"]

    def test_approved_draw_calls_do_draw_exactly_once(self, agent):
        with patch.object(agent.oracle, "_call_oracle", return_value=approved_evaluation()), \
             patch("trestle_sdk.agent.do_draw", return_value=FAKE_TXID) as mock_draw:
            agent.draw(
                amount_microalgo=50_000,
                task_description="Fetch price",
                expected_return_microalgo=80_000,
                estimated_task_rounds=120,
            )
        mock_draw.assert_called_once()

    def test_approved_draw_passes_correct_amount_to_chain(self, agent):
        with patch.object(agent.oracle, "_call_oracle", return_value=approved_evaluation()), \
             patch("trestle_sdk.agent.do_draw", return_value=FAKE_TXID) as mock_draw:
            agent.draw(
                amount_microalgo=50_000,
                task_description="Fetch price",
                expected_return_microalgo=80_000,
                estimated_task_rounds=120,
            )
        _, kwargs = mock_draw.call_args
        assert kwargs.get("amount_microalgo") == 50_000


class TestAgentDrawDenial:

    def test_denied_draw_raises_trestle_credit_denied(self, agent):
        ev = denied_evaluation(4, "Task is speculative", risk_level="high")
        with patch.object(agent.oracle, "_call_oracle", return_value=ev):
            with pytest.raises(TrestleCreditDenied):
                agent.draw(
                    amount_microalgo=50_000,
                    task_description="Speculative DEX arbitrage",
                    expected_return_microalgo=80_000,
                    estimated_task_rounds=120,
                )

    def test_denied_draw_never_calls_do_draw(self, agent):
        """The most important invariant: no transaction when oracle denies."""
        ev = denied_evaluation(4, "Critical risk task")
        with patch.object(agent.oracle, "_call_oracle", return_value=ev), \
             patch("trestle_sdk.agent.do_draw") as mock_draw:
            with pytest.raises(TrestleCreditDenied):
                agent.draw(
                    amount_microalgo=50_000,
                    task_description="Risky task",
                    expected_return_microalgo=80_000,
                    estimated_task_rounds=120,
                )
        mock_draw.assert_not_called()

    def test_denied_draw_exception_has_reason(self, agent):
        ev = denied_evaluation(3, "Agent has outstanding debt of 25000 microALGO")
        with patch.object(agent.oracle, "_call_oracle", return_value=ev):
            with pytest.raises(TrestleCreditDenied) as exc_info:
                agent.draw(
                    amount_microalgo=50_000,
                    task_description="Some task",
                    expected_return_microalgo=80_000,
                    estimated_task_rounds=120,
                )
        assert len(exc_info.value.reason) > 0

    def test_denied_draw_exception_has_criteria_results(self, agent):
        ev = denied_evaluation(1, "Return too low")
        with patch.object(agent.oracle, "_call_oracle", return_value=ev):
            with pytest.raises(TrestleCreditDenied) as exc_info:
                agent.draw(
                    amount_microalgo=50_000,
                    task_description="Unprofitable task",
                    expected_return_microalgo=50_010,
                    estimated_task_rounds=120,
                )
        results = exc_info.value.criteria_results
        assert isinstance(results, dict)
        assert "criterion_1_passed" in results
        assert results["criterion_1_passed"] is False

    def test_tier_cap_exceeded_raises_denied_without_llm(self, agent):
        """
        Amount > tier cap raises TrestleCreditDenied in evaluate() before
        _call_oracle() is even invoked.
        """
        with patch.object(agent.oracle, "_call_oracle") as mock_call:
            with pytest.raises(TrestleCreditDenied):
                agent.draw(
                    amount_microalgo=200_000,   # > Tier 0 cap of 100,000
                    task_description="Anything",
                    expected_return_microalgo=300_000,
                    estimated_task_rounds=120,
                )
        mock_call.assert_not_called()

    @pytest.mark.parametrize("outstanding,should_deny", [
        (0,      False),    # clean slate → allow through to LLM
        (1,      True),     # 1 uA outstanding → deny (but via LLM, not pre-flight)
        (25_000, True),     # meaningful debt
        (50_000, True),     # full outstanding loan
    ])
    def test_outstanding_debt_behaviour(self, agent, outstanding, should_deny):
        """
        When outstanding > 0, the oracle's criterion 3 check should deny.
        We simulate this by mocking the oracle to deny on criterion 3.
        """
        position = {**CLEAN_POSITION, "outstanding": outstanding}
        if should_deny:
            ev = denied_evaluation(3, f"Outstanding debt: {outstanding} uA")
        else:
            ev = approved_evaluation()

        with patch("trestle_sdk.agent.get_position", return_value=position), \
             patch.object(agent.oracle, "_call_oracle", return_value=ev), \
             patch("trestle_sdk.agent.do_draw", return_value=FAKE_TXID):
            if should_deny:
                with pytest.raises(TrestleCreditDenied):
                    agent.draw(50_000, "task", 80_000, 120)
            else:
                result = agent.draw(50_000, "task", 80_000, 120)
                assert result["txid"] == FAKE_TXID


# ══════════════════════════════════════════════════════════════════
# TrestleCreditException structure
# ══════════════════════════════════════════════════════════════════

class TestExceptionStructure:

    def test_trestle_credit_denied_is_exception(self):
        exc = TrestleCreditDenied("test reason", {})
        assert isinstance(exc, Exception)

    def test_trestle_credit_denied_has_reason_attr(self):
        exc = TrestleCreditDenied("test reason", {"key": "value"})
        assert exc.reason == "test reason"

    def test_trestle_credit_denied_has_criteria_results_attr(self):
        results = {"criterion_1_passed": True, "overall_approved": False}
        exc = TrestleCreditDenied("reason", results)
        assert exc.criteria_results == results

    def test_trestle_credit_denied_str_is_reason(self):
        exc = TrestleCreditDenied("loan denied because risky", {})
        assert "loan denied because risky" in str(exc)

    def test_trestle_credit_error_is_exception(self):
        exc = TrestleCreditError("api failed")
        assert isinstance(exc, Exception)

    def test_trestle_credit_denied_is_subclass_of_error(self):
        """TrestleCreditDenied should be catchable as TrestleCreditError."""
        exc = TrestleCreditDenied("denied", {})
        assert isinstance(exc, TrestleCreditError)


# ══════════════════════════════════════════════════════════════════
# Integration tests — real Venice AI (skipped without API key)
# ══════════════════════════════════════════════════════════════════

@pytest.mark.integration
@pytest.mark.skipif(
    not os.environ.get("VENICE_API_KEY"),
    reason="VENICE_API_KEY not set — skipping live oracle test"
)
class TestOracleIntegration:
    """
    Real end-to-end oracle calls against Venice AI.
    Run with: VENICE_API_KEY=your-key pytest -m integration -v
    """

    @pytest.fixture
    def live_oracle(self):
        algod = MagicMock()
        algod.status.return_value = {"last-round": FIXED_ROUND}
        return RiskOracle(algod_client=algod, demo_mode=True)

    def test_low_risk_task_approved(self, live_oracle):
        """A clear, deterministic API call should be approved."""
        decision = live_oracle.evaluate(
            agent_address=FAKE_ADDRESS,
            amount_microalgo=50_000,
            payment_count=0,
            outstanding_microalgo=0,
            task_description=(
                "Fetch the current ETH/USD price from the CoinGecko public API "
                "and return the price as a float."
            ),
            expected_return_microalgo=80_000,
            estimated_task_rounds=120,
        )
        assert decision.approved is True
        assert decision.criteria.criterion_4_passed is True
        assert decision.criteria.task_risk_level in ("low", "medium")

    def test_outstanding_debt_denied(self, live_oracle):
        """Oracle criterion 3: outstanding debt → always denied."""
        with pytest.raises(TrestleCreditDenied) as exc_info:
            live_oracle.evaluate(
                agent_address=FAKE_ADDRESS,
                amount_microalgo=50_000,
                payment_count=5,
                outstanding_microalgo=25_000,   # has unpaid loan
                task_description="Fetch ETH price from CoinGecko",
                expected_return_microalgo=80_000,
                estimated_task_rounds=120,
            )
        assert exc_info.value.criteria_results.get("criterion_3_passed") is False

    def test_speculative_task_denied(self, live_oracle):
        """Oracle criterion 4: speculative task → denied."""
        with pytest.raises(TrestleCreditDenied) as exc_info:
            live_oracle.evaluate(
                agent_address=FAKE_ADDRESS,
                amount_microalgo=50_000,
                payment_count=0,
                outstanding_microalgo=0,
                task_description=(
                    "Execute speculative arbitrage between two unaudited "
                    "new DEX contracts with unknown liquidity, hoping to profit."
                ),
                expected_return_microalgo=80_000,
                estimated_task_rounds=120,
            )
        assert exc_info.value.criteria_results.get("criterion_4_passed") is False
