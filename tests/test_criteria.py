"""
tests/test_criteria.py

Pure unit tests for trestle_sdk/criteria.py.
No network calls. No API keys. No mocking.
All tests should pass offline in under 1 second.

Coverage:
  - get_tier()           all 4 tiers + every boundary value
  - calculate_interest() all 4 tiers + zero + exact formula verification
  - max_draw()           all 4 tiers
  - daily_cap()          all 4 tiers
  - apr_bps()            all 4 tiers
  - tier_name()          all 4 tiers
  - constants            DAY_IN_ROUNDS, ROUNDS_PER_YEAR, list lengths
"""

import pytest

from trestle_sdk.criteria import (
    get_tier,
    calculate_interest,
    max_draw,
    daily_cap,
    apr_bps,
    tier_name,
    TIER_THRESHOLDS,
    TIER_MAX_DRAW,
    TIER_DAILY_CAP,
    TIER_APR_BPS,
    TIER_NAMES,
    DAY_IN_ROUNDS,
    ROUNDS_PER_YEAR,
)


# ══════════════════════════════════════════════════════════════════
# get_tier() — payment_count → tier index
# ══════════════════════════════════════════════════════════════════

class TestGetTier:

    def test_zero_payments_is_tier_0(self):
        assert get_tier(0) == 0

    def test_nine_payments_still_tier_0(self):
        """9 payments is one below the Trusted threshold."""
        assert get_tier(9) == 0

    def test_ten_payments_is_tier_1(self):
        """10 payments is exactly the Trusted threshold."""
        assert get_tier(10) == 1

    def test_eleven_payments_is_tier_1(self):
        assert get_tier(11) == 1

    def test_49_payments_still_tier_1(self):
        """49 payments is one below the Veteran threshold."""
        assert get_tier(49) == 1

    def test_50_payments_is_tier_2(self):
        """50 payments is exactly the Veteran threshold."""
        assert get_tier(50) == 2

    def test_51_payments_is_tier_2(self):
        assert get_tier(51) == 2

    def test_99_payments_still_tier_2(self):
        """99 payments is one below the Elite threshold."""
        assert get_tier(99) == 2

    def test_100_payments_is_tier_3(self):
        """100 payments is exactly the Elite threshold."""
        assert get_tier(100) == 3

    def test_101_payments_is_tier_3(self):
        assert get_tier(101) == 3

    def test_large_payment_count_is_tier_3(self):
        """1,000 payments is still Elite."""
        assert get_tier(1_000) == 3

    def test_tier_values_are_0_through_3(self):
        """get_tier never returns a value outside [0, 3]."""
        for count in range(200):
            result = get_tier(count)
            assert 0 <= result <= 3, f"get_tier({count}) = {result}, expected 0-3"

    def test_thresholds_match_constants(self):
        """Tier boundaries match the published TIER_THRESHOLDS list."""
        assert TIER_THRESHOLDS == [0, 10, 50, 100]
        assert get_tier(TIER_THRESHOLDS[1] - 1) == 0   # 9 → tier 0
        assert get_tier(TIER_THRESHOLDS[1])     == 1   # 10 → tier 1
        assert get_tier(TIER_THRESHOLDS[2] - 1) == 1   # 49 → tier 1
        assert get_tier(TIER_THRESHOLDS[2])     == 2   # 50 → tier 2
        assert get_tier(TIER_THRESHOLDS[3] - 1) == 2   # 99 → tier 2
        assert get_tier(TIER_THRESHOLDS[3])     == 3   # 100 → tier 3


# ══════════════════════════════════════════════════════════════════
# calculate_interest() — matches on-chain formula exactly
# ══════════════════════════════════════════════════════════════════

class TestCalculateInterest:
    """
    Formula verified against the AVM contract:
        interest = (amount * APR_bps * DAY_IN_ROUNDS) // (10_000 * ROUNDS_PER_YEAR)

    Pre-computed expected values (verified with Python):
        50,000 uA × Tier 0 (2400 bps) → 32 uA
        50,000 uA × Tier 1 (1600 bps) → 21 uA
        50,000 uA × Tier 2  (900 bps) → 12 uA
        50,000 uA × Tier 3  (400 bps) →  5 uA
    """

    def test_zero_amount_always_zero_interest(self):
        for tier in range(4):
            assert calculate_interest(0, tier) == 0, \
                f"0 uA at tier {tier} should have 0 interest"

    def test_tier_0_interest_50k_microalgo(self):
        """Tier 0 (Fresh, 24% APR): 50,000 uA → 32 uA interest."""
        assert calculate_interest(50_000, 0) == 32

    def test_tier_1_interest_50k_microalgo(self):
        """Tier 1 (Trusted, 16% APR): 50,000 uA → 21 uA interest."""
        assert calculate_interest(50_000, 1) == 21

    def test_tier_2_interest_50k_microalgo(self):
        """Tier 2 (Veteran, 9% APR): 50,000 uA → 12 uA interest."""
        assert calculate_interest(50_000, 2) == 12

    def test_tier_3_interest_50k_microalgo(self):
        """Tier 3 (Elite, 4% APR): 50,000 uA → 5 uA interest."""
        assert calculate_interest(50_000, 3) == 5

    def test_tier_0_max_draw_interest(self):
        """Tier 0 max draw (100,000 uA) → 65 uA interest."""
        assert calculate_interest(100_000, 0) == 65

    def test_tier_1_max_draw_interest(self):
        """Tier 1 max draw (500,000 uA) → 219 uA interest."""
        assert calculate_interest(500_000, 1) == 219

    def test_tier_3_one_algo_interest(self):
        """Tier 3 Elite: 1,000,000 uA (1 ALGO) → 109 uA interest."""
        assert calculate_interest(1_000_000, 3) == 109

    def test_higher_tier_means_lower_interest(self):
        """Lower APR for better tiers means less interest at every amount."""
        amount = 200_000
        interests = [calculate_interest(amount, t) for t in range(4)]
        for i in range(3):
            assert interests[i] > interests[i + 1], (
                f"Tier {i} interest ({interests[i]}) should exceed "
                f"Tier {i+1} interest ({interests[i+1]})"
            )

    def test_interest_scales_with_amount(self):
        """Doubling the amount doubles the interest (integer division may truncate)."""
        interest_100k = calculate_interest(100_000, 0)
        interest_50k  = calculate_interest(50_000, 0)
        # With integer division, 2× amount should give ≥ 2× interest (not exact due to floor)
        assert interest_100k >= 2 * interest_50k

    def test_formula_matches_manual_calculation(self):
        """Verify the formula matches the on-chain AVM formula exactly."""
        amount = 75_000
        tier   = 1
        apr    = TIER_APR_BPS[tier]  # 1600
        expected = (amount * apr * DAY_IN_ROUNDS) // (10_000 * ROUNDS_PER_YEAR)
        assert calculate_interest(amount, tier) == expected

    def test_result_is_non_negative(self):
        """Interest is never negative."""
        for tier in range(4):
            for amount in [0, 1, 1000, 50_000, 100_000, 5_000_000]:
                result = calculate_interest(amount, tier)
                assert result >= 0, f"Negative interest: tier={tier} amount={amount}"


# ══════════════════════════════════════════════════════════════════
# max_draw() — per-tier single transaction cap
# ══════════════════════════════════════════════════════════════════

class TestMaxDraw:

    def test_tier_0_max_draw(self):
        """Fresh agents: 100,000 uA = 0.10 ALGO."""
        assert max_draw(0) == 100_000

    def test_tier_1_max_draw(self):
        """Trusted agents: 500,000 uA = 0.50 ALGO."""
        assert max_draw(1) == 500_000

    def test_tier_2_max_draw(self):
        """Veteran agents: 2,000,000 uA = 2.00 ALGO."""
        assert max_draw(2) == 2_000_000

    def test_tier_3_max_draw(self):
        """Elite agents: 5,000,000 uA = 5.00 ALGO."""
        assert max_draw(3) == 5_000_000

    def test_max_draw_increases_with_tier(self):
        """Better tier always means higher draw cap."""
        for t in range(3):
            assert max_draw(t) < max_draw(t + 1)

    def test_max_draw_matches_tier_max_draw_constant(self):
        for t in range(4):
            assert max_draw(t) == TIER_MAX_DRAW[t]


# ══════════════════════════════════════════════════════════════════
# daily_cap() — 24-hour rolling cap
# ══════════════════════════════════════════════════════════════════

class TestDailyCap:

    def test_tier_0_daily_cap(self):
        assert daily_cap(0) == 500_000

    def test_tier_1_daily_cap(self):
        assert daily_cap(1) == 2_000_000

    def test_tier_2_daily_cap(self):
        assert daily_cap(2) == 10_000_000

    def test_tier_3_daily_cap(self):
        assert daily_cap(3) == 25_000_000

    def test_daily_cap_always_exceeds_max_draw(self):
        """Daily cap must be >= max single draw — otherwise the cap is pointless."""
        for t in range(4):
            assert daily_cap(t) >= max_draw(t), \
                f"Tier {t}: daily_cap {daily_cap(t)} < max_draw {max_draw(t)}"

    def test_daily_cap_increases_with_tier(self):
        for t in range(3):
            assert daily_cap(t) < daily_cap(t + 1)


# ══════════════════════════════════════════════════════════════════
# apr_bps() — annual percentage rate in basis points
# ══════════════════════════════════════════════════════════════════

class TestAprBps:

    def test_tier_0_apr(self):
        """Fresh: 2400 bps = 24.00% APR."""
        assert apr_bps(0) == 2400

    def test_tier_1_apr(self):
        """Trusted: 1600 bps = 16.00% APR."""
        assert apr_bps(1) == 1600

    def test_tier_2_apr(self):
        """Veteran: 900 bps = 9.00% APR."""
        assert apr_bps(2) == 900

    def test_tier_3_apr(self):
        """Elite: 400 bps = 4.00% APR."""
        assert apr_bps(3) == 400

    def test_apr_decreases_with_tier(self):
        """Higher tier = lower APR = reward for good repayment history."""
        for t in range(3):
            assert apr_bps(t) > apr_bps(t + 1), \
                f"Tier {t} APR ({apr_bps(t)}) should exceed Tier {t+1} APR ({apr_bps(t+1)})"

    def test_apr_matches_constant(self):
        for t in range(4):
            assert apr_bps(t) == TIER_APR_BPS[t]


# ══════════════════════════════════════════════════════════════════
# tier_name() — human-readable labels
# ══════════════════════════════════════════════════════════════════

class TestTierName:

    def test_tier_0_name(self):
        assert tier_name(0) == "Fresh"

    def test_tier_1_name(self):
        assert tier_name(1) == "Trusted"

    def test_tier_2_name(self):
        assert tier_name(2) == "Veteran"

    def test_tier_3_name(self):
        assert tier_name(3) == "Elite"

    def test_all_names_are_strings(self):
        for t in range(4):
            assert isinstance(tier_name(t), str)

    def test_all_names_are_nonempty(self):
        for t in range(4):
            assert len(tier_name(t)) > 0

    def test_names_are_unique(self):
        names = [tier_name(t) for t in range(4)]
        assert len(set(names)) == 4, "All tier names must be distinct"


# ══════════════════════════════════════════════════════════════════
# constants — must match on-chain contract values exactly
# ══════════════════════════════════════════════════════════════════

class TestConstants:

    def test_day_in_rounds(self):
        """86,400 rounds = 24 hours at ~1 round/second."""
        assert DAY_IN_ROUNDS == 86_400

    def test_rounds_per_year(self):
        """31,536,000 rounds = 365 days × 86,400 rounds/day."""
        assert ROUNDS_PER_YEAR == 365 * DAY_IN_ROUNDS

    def test_all_tier_lists_same_length(self):
        assert len(TIER_THRESHOLDS) == 4
        assert len(TIER_MAX_DRAW)   == 4
        assert len(TIER_DAILY_CAP)  == 4
        assert len(TIER_APR_BPS)    == 4
        assert len(TIER_NAMES)      == 4

    def test_tier_thresholds_are_ascending(self):
        for i in range(3):
            assert TIER_THRESHOLDS[i] < TIER_THRESHOLDS[i + 1]

    def test_tier_max_draw_ascending(self):
        for i in range(3):
            assert TIER_MAX_DRAW[i] < TIER_MAX_DRAW[i + 1]

    def test_tier_apr_bps_descending(self):
        """APR decreases as tier improves."""
        for i in range(3):
            assert TIER_APR_BPS[i] > TIER_APR_BPS[i + 1]

    def test_all_max_draws_positive(self):
        assert all(v > 0 for v in TIER_MAX_DRAW)

    def test_all_apr_bps_positive(self):
        assert all(v > 0 for v in TIER_APR_BPS)


# ══════════════════════════════════════════════════════════════════
# USDC criteria tests
# ══════════════════════════════════════════════════════════════════

from trestle_sdk.criteria import (
    max_draw_usdc, daily_cap_usdc, calculate_interest_usdc,
    TIER_MAX_DRAW_USDC, TIER_DAILY_CAP_USDC,
    USDC_ASA_ID_TESTNET, USDC_ASA_ID_MAINNET,
)


class TestUsdcConstants:

    def test_usdc_testnet_asa_id(self):
        assert USDC_ASA_ID_TESTNET == 10_458_941

    def test_usdc_mainnet_asa_id(self):
        assert USDC_ASA_ID_MAINNET == 31_566_704

    def test_usdc_max_draw_same_usd_as_algo(self):
        """USDC and ALGO caps have the same USD value (both use 6 decimals)."""
        assert TIER_MAX_DRAW_USDC == TIER_MAX_DRAW

    def test_usdc_daily_cap_same_usd_as_algo(self):
        assert TIER_DAILY_CAP_USDC == TIER_DAILY_CAP

    def test_all_tier_lists_same_length(self):
        assert len(TIER_MAX_DRAW_USDC)  == 4
        assert len(TIER_DAILY_CAP_USDC) == 4


class TestMaxDrawUsdc:

    def test_tier_0_usdc_max_draw(self):
        assert max_draw_usdc(0) == 100_000

    def test_tier_1_usdc_max_draw(self):
        assert max_draw_usdc(1) == 500_000

    def test_tier_2_usdc_max_draw(self):
        assert max_draw_usdc(2) == 2_000_000

    def test_tier_3_usdc_max_draw(self):
        assert max_draw_usdc(3) == 5_000_000

    def test_increases_with_tier(self):
        for t in range(3):
            assert max_draw_usdc(t) < max_draw_usdc(t + 1)


class TestCalculateInterestUsdc:

    def test_zero_amount_zero_interest(self):
        for tier in range(4):
            assert calculate_interest_usdc(0, tier) == 0

    def test_formula_matches_algo_formula_for_same_amount(self):
        """Same formula, same amount → same interest regardless of denomination."""
        for tier in range(4):
            assert calculate_interest_usdc(50_000, tier) == calculate_interest(50_000, tier)

    def test_higher_tier_lower_interest(self):
        amount = 100_000
        interests = [calculate_interest_usdc(amount, t) for t in range(4)]
        for i in range(3):
            assert interests[i] >= interests[i + 1]

    def test_non_negative(self):
        for tier in range(4):
            assert calculate_interest_usdc(500_000, tier) >= 0
