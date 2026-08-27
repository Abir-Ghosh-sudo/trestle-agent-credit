"""
tests/test_sdk.py — Offline unit tests for the Trestle SDK.

Runs without network access. Both the Venice API and the algod client are
fully mocked so tests pass in CI without any environment variables.

Tests:
  1. Approved draw — all 4 criteria pass.
  2. Denied — outstanding debt (criterion 3 fails).
  3. Denied — tier cap exceeded (pre-flight, oracle NOT called).
  4. Denied — high-risk task (criterion 4 fails).
  5. Interest calculation matches contract formula.
  6. Anthropic provider path — uses _anthropic_client instead of _openai_client.

Run with:
    python tests/test_sdk.py
or:
    python -m pytest tests/test_sdk.py -v
"""

import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch


# ══════════════════════════════════════════════════════════════════════════════
# Helpers — shared mock factories
# ══════════════════════════════════════════════════════════════════════════════

def _make_algod_mock(last_round: int = 42_000_000) -> MagicMock:
    """Build a mock AlgodClient that returns minimal plausible data."""
    mock = MagicMock()
    mock.status.return_value = {"last-round": last_round}
    mock.suggested_params.return_value = MagicMock()

    # get_position ATC result: 9 zeros (outstanding=0, payment_count varies)
    abi_result = MagicMock()
    abi_result.return_value = [0, 21, 500_000, 0, 0, 1, 1600, 0, 0]
    atc_result = MagicMock()
    atc_result.abi_results = [abi_result]
    mock._atc_execute_result = atc_result
    return mock


def make_approved_response() -> MagicMock:
    """Build a mock Venice/OpenAI chat.completions.create() response for an approved draw."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps({
        "criterion_1_passed": True,
        "criterion_2_passed": True,
        "criterion_3_passed": True,
        "criterion_4_passed": True,
        "overall_approved": True,
        "task_risk_level": "low",
        "denial_reason": "",
        "risk_summary": "Low-risk API call with positive ROI.",
    })
    return mock_response


def make_denied_response(failing_criterion: int, reason: str, risk_level: str = "low") -> MagicMock:
    """Build a mock Venice/OpenAI response for a denied draw.

    Args:
        failing_criterion: Which criterion (1-4) to mark as False.
        reason: Denial reason string.
        risk_level: Task risk level string.

    Returns:
        MagicMock mimicking an OpenAI chat completion response.
    """
    data = {
        "criterion_1_passed": True,
        "criterion_2_passed": True,
        "criterion_3_passed": True,
        "criterion_4_passed": True,
        "overall_approved": False,
        "task_risk_level": risk_level,
        "denial_reason": reason,
        "risk_summary": f"Criterion {failing_criterion} failed.",
    }
    data[f"criterion_{failing_criterion}_passed"] = False
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps(data)
    return mock_response


def _make_criteria_evaluation(
    c1: bool = True,
    c2: bool = True,
    c3: bool = True,
    c4: bool = True,
    risk_level: str = "low",
    denial_reason: str = "",
    risk_summary: str = "Risk assessment passed.",
):
    """Build a real CriteriaEvaluation pydantic instance."""
    from trestle_sdk.oracle import CriteriaEvaluation

    overall = c1 and c2 and c3 and c4
    return CriteriaEvaluation(
        criterion_1_passed=c1,
        criterion_2_passed=c2,
        criterion_3_passed=c3,
        criterion_4_passed=c4,
        overall_approved=overall,
        task_risk_level=risk_level,
        denial_reason=denial_reason if not overall else "",
        risk_summary=risk_summary,
    )


# ══════════════════════════════════════════════════════════════════════════════
# Test suite
# ══════════════════════════════════════════════════════════════════════════════

class TestTrestleSdk(unittest.TestCase):

    def setUp(self) -> None:
        """Force Venice provider for all tests unless overridden."""
        os.environ["ORACLE_PROVIDER"] = "venice"
        os.environ["VENICE_API_KEY"] = "test-key"

    # ── TEST 1 — APPROVED draw ─────────────────────────────────────────────────
    def test_approved_draw(self) -> None:
        """Full approved draw: all 4 criteria pass, demo hash returned."""
        from trestle_sdk.oracle import RiskOracle, RiskDecision

        algod_mock = _make_algod_mock()

        with patch("trestle_sdk.oracle.OpenAI") as mock_openai_class:
            mock_instance = MagicMock()
            mock_openai_class.return_value = mock_instance
            mock_instance.chat.completions.create.return_value = make_approved_response()

            oracle = RiskOracle(
                algod_client=algod_mock,
                venice_api_key="test-key",
                demo_mode=True,
            )
            decision = oracle.evaluate(
                agent_address="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAY5HFKQ",
                amount_microalgo=50_000,
                payment_count=21,
                outstanding_microalgo=0,
                task_description="Fetch ETH price from CoinGecko",
                expected_return_microalgo=80_000,
                estimated_task_rounds=120,
            )

        self.assertIsInstance(decision, RiskDecision)
        self.assertTrue(decision.approved)
        # In demo mode the attestation hash must always be 32 zero bytes
        self.assertEqual(decision.attestation_hash, bytes(32))
        self.assertEqual(len(decision.attestation_hash), 32)
        self.assertEqual(decision.tier, 1)          # payment_count=21 → Trusted
        self.assertEqual(decision.tier_name, "Trusted")
        self.assertGreater(decision.total_repayable, decision.amount_microalgo)

    # ── TEST 2 — DENIED: criterion 3 (outstanding debt) ───────────────────────
    def test_denied_outstanding_debt(self) -> None:
        """Criterion 3 failure: agent has outstanding debt — loan stacking blocked."""
        from trestle_sdk.oracle import RiskOracle
        from trestle_sdk.exceptions import TrestleCreditDenied

        algod_mock = _make_algod_mock()
        denial_msg = (
            "Criterion 3 failed: outstanding debt of 149916 microALGO must be "
            "repaid before a new loan can be issued."
        )

        with patch("trestle_sdk.oracle.OpenAI") as mock_openai_class:
            mock_instance = MagicMock()
            mock_openai_class.return_value = mock_instance
            mock_instance.chat.completions.create.return_value = make_denied_response(
                3, denial_msg
            )

            oracle = RiskOracle(
                algod_client=algod_mock,
                venice_api_key="test-key",
                demo_mode=True,
            )
            with self.assertRaises(TrestleCreditDenied) as ctx:
                oracle.evaluate(
                    agent_address="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAY5HFKQ",
                    amount_microalgo=50_000,
                    payment_count=21,
                    outstanding_microalgo=149_916,
                    task_description="Fetch ETH price from CoinGecko",
                    expected_return_microalgo=80_000,
                    estimated_task_rounds=120,
                )

        exc = ctx.exception
        reason_lower = exc.reason.lower()
        self.assertTrue(
            "criterion 3" in reason_lower or "outstanding" in reason_lower,
            f"Expected 'criterion 3' or 'outstanding' in reason, got: {exc.reason!r}",
        )
        self.assertFalse(exc.criteria_results.get("criterion_3_passed", True))

    # ── TEST 3 — DENIED: tier cap exceeded (pre-flight, oracle NOT called) ─────
    def test_denied_tier_cap_exceeded(self) -> None:
        """Pre-flight tier cap check: amount > max_draw raises immediately, oracle not called."""
        from trestle_sdk.oracle import RiskOracle
        from trestle_sdk.exceptions import TrestleCreditDenied

        algod_mock = _make_algod_mock()

        with patch("trestle_sdk.oracle.OpenAI") as mock_openai_class:
            mock_instance = MagicMock()
            mock_openai_class.return_value = mock_instance

            oracle = RiskOracle(
                algod_client=algod_mock,
                venice_api_key="test-key",
                demo_mode=True,
            )
            with self.assertRaises(TrestleCreditDenied) as ctx:
                oracle.evaluate(
                    agent_address="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAY5HFKQ",
                    amount_microalgo=200_000,   # exceeds Tier 0 cap of 100_000
                    payment_count=0,            # Tier 0 — Fresh
                    outstanding_microalgo=0,
                    task_description="Any task",
                    expected_return_microalgo=999_999,
                    estimated_task_rounds=120,
                )

        # Venice must NOT have been called — we save API cost
        mock_instance.chat.completions.create.assert_not_called()
        reason_lower = ctx.exception.reason.lower()
        self.assertTrue(
            "200000" in reason_lower or "max" in reason_lower or "exceeds" in reason_lower,
            f"Expected cap language in reason, got: {ctx.exception.reason!r}",
        )

    # ── TEST 4 — DENIED: criterion 4 (high risk task) ─────────────────────────
    def test_denied_high_risk_task(self) -> None:
        """Criterion 4 failure: speculative arbitrage task classified as critical."""
        from trestle_sdk.oracle import RiskOracle
        from trestle_sdk.exceptions import TrestleCreditDenied

        algod_mock = _make_algod_mock()
        denial_msg = (
            "Criterion 4 failed: task risk level is 'critical' — speculative "
            "arbitrage on unaudited contracts is never approved."
        )

        with patch("trestle_sdk.oracle.OpenAI") as mock_openai_class:
            mock_instance = MagicMock()
            mock_openai_class.return_value = mock_instance
            mock_instance.chat.completions.create.return_value = make_denied_response(
                4, denial_msg, risk_level="critical"
            )

            oracle = RiskOracle(
                algod_client=algod_mock,
                venice_api_key="test-key",
                demo_mode=True,
            )
            with self.assertRaises(TrestleCreditDenied) as ctx:
                oracle.evaluate(
                    agent_address="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAY5HFKQ",
                    amount_microalgo=50_000,
                    payment_count=21,
                    outstanding_microalgo=0,
                    task_description="Speculative arbitrage on unaudited DEX contracts",
                    expected_return_microalgo=80_000,
                    estimated_task_rounds=120,
                )

        exc = ctx.exception
        self.assertFalse(exc.criteria_results.get("criterion_4_passed", True))
        self.assertEqual(exc.criteria_results.get("task_risk_level"), "critical")

    # ── TEST 5 — Interest calculation matches contract formula ─────────────────
    def test_interest_calculation_matches_contract(self) -> None:
        """calculate_interest must match the exact AVM formula."""
        from trestle_sdk.criteria import calculate_interest, TIER_APR_BPS, DAY_IN_ROUNDS, ROUNDS_PER_YEAR

        amount = 50_000
        tier = 1  # Trusted — APR 1600 bps

        expected = (amount * TIER_APR_BPS[tier] * DAY_IN_ROUNDS) // (10_000 * ROUNDS_PER_YEAR)
        actual = calculate_interest(amount, tier)

        self.assertEqual(actual, expected, (
            f"Interest mismatch: calculate_interest({amount}, {tier}) = {actual}, "
            f"expected {expected}"
        ))

        # Sanity-check: result is non-negative int
        self.assertIsInstance(actual, int)
        self.assertGreaterEqual(actual, 0)

        # Sanity-check a few more tiers
        for t in range(4):
            result = calculate_interest(amount, t)
            manual = (amount * TIER_APR_BPS[t] * DAY_IN_ROUNDS) // (10_000 * ROUNDS_PER_YEAR)
            self.assertEqual(result, manual, f"Mismatch at tier {t}")

    # ── TEST 6 — Anthropic provider path ──────────────────────────────────────
    def test_anthropic_provider_path(self) -> None:
        """When ORACLE_PROVIDER=anthropic, _anthropic_client is used, not _openai_client."""
        os.environ["ORACLE_PROVIDER"] = "anthropic"
        os.environ["ANTHROPIC_API_KEY"] = "test-anthropic-key"

        from trestle_sdk.oracle import RiskOracle, RiskDecision, CriteriaEvaluation

        algod_mock = _make_algod_mock()

        mock_anthropic_response = MagicMock()
        mock_anthropic_response.parsed_output = CriteriaEvaluation(
            criterion_1_passed=True,
            criterion_2_passed=True,
            criterion_3_passed=True,
            criterion_4_passed=True,
            overall_approved=True,
            task_risk_level="low",
            denial_reason="",
            risk_summary="Test approval via Anthropic path.",
        )

        with patch("trestle_sdk.oracle.Anthropic") as mock_anthropic_class:
            mock_ant_instance = MagicMock()
            mock_anthropic_class.return_value = mock_ant_instance
            mock_ant_instance.beta.messages.parse.return_value = mock_anthropic_response

            oracle = RiskOracle(
                algod_client=algod_mock,
                anthropic_api_key="test-anthropic-key",
                demo_mode=True,
            )

            # Verify provider selection
            self.assertEqual(oracle.provider, "anthropic")
            self.assertIsNone(oracle._openai_client)
            self.assertIsNotNone(oracle._anthropic_client)

            decision = oracle.evaluate(
                agent_address="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAY5HFKQ",
                amount_microalgo=50_000,
                payment_count=21,
                outstanding_microalgo=0,
                task_description="Fetch ETH price from CoinGecko",
                expected_return_microalgo=80_000,
                estimated_task_rounds=120,
            )

        self.assertIsInstance(decision, RiskDecision)
        self.assertTrue(decision.approved)
        self.assertEqual(decision.attestation_hash, bytes(32))
        # Anthropic parse must have been called, not OpenAI
        mock_ant_instance.beta.messages.parse.assert_called_once()

    def tearDown(self) -> None:
        """Restore default provider after each test."""
        os.environ["ORACLE_PROVIDER"] = "venice"


# ══════════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestTrestleSdk)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
