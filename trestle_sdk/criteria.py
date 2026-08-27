"""
criteria.py — Pure Python constants and tier logic for the Trestle credit protocol.

No algosdk or anthropic imports. All values must match the on-chain contract exactly.
"""

# ── Tier thresholds (payment_count) ────────────────────────────────────────────
TIER_THRESHOLDS: list[int] = [0, 10, 50, 100]

# ── Max single draw per tier (microALGO) ───────────────────────────────────────
TIER_MAX_DRAW: list[int] = [100_000, 500_000, 2_000_000, 5_000_000]

# ── Daily draw cap per tier (microALGO) ────────────────────────────────────────
TIER_DAILY_CAP: list[int] = [500_000, 2_000_000, 10_000_000, 25_000_000]

# ── Annual percentage rate in basis points per tier ────────────────────────────
TIER_APR_BPS: list[int] = [2400, 1600, 900, 400]

# ── Human-readable tier names ──────────────────────────────────────────────────
TIER_NAMES: list[str] = ["Fresh", "Trusted", "Veteran", "Elite"]

# ── Algorand timing constants ──────────────────────────────────────────────────
DAY_IN_ROUNDS: int = 86_400
ROUNDS_PER_YEAR: int = 31_536_000


def get_tier(payment_count: int) -> int:
    """Determine the agent's tier based on payment history.

    Tier thresholds (inclusive lower bound):
        Tier 3 (Elite):   payment_count >= 100
        Tier 2 (Veteran): payment_count >= 50
        Tier 1 (Trusted): payment_count >= 10
        Tier 0 (Fresh):   payment_count >= 0

    Args:
        payment_count: Number of completed repayments recorded on-chain.

    Returns:
        Integer tier index in range [0, 3].
    """
    if payment_count >= TIER_THRESHOLDS[3]:
        return 3
    if payment_count >= TIER_THRESHOLDS[2]:
        return 2
    if payment_count >= TIER_THRESHOLDS[1]:
        return 1
    return 0


def max_draw(tier: int) -> int:
    """Return the maximum single draw amount for a given tier.

    Args:
        tier: Tier index in range [0, 3].

    Returns:
        Maximum draw in microALGO.
    """
    return TIER_MAX_DRAW[tier]


def daily_cap(tier: int) -> int:
    """Return the daily draw cap for a given tier.

    Args:
        tier: Tier index in range [0, 3].

    Returns:
        Daily cap in microALGO.
    """
    return TIER_DAILY_CAP[tier]


def apr_bps(tier: int) -> int:
    """Return the annual percentage rate in basis points for a given tier.

    Args:
        tier: Tier index in range [0, 3].

    Returns:
        APR in basis points (e.g. 1600 = 16.00%).
    """
    return TIER_APR_BPS[tier]


def calculate_interest(amount_microalgo: int, tier: int) -> int:
    """Calculate interest for a one-day loan, matching the on-chain formula exactly.

    Formula:
        interest = (amount * APR_bps * DAY_IN_ROUNDS) // (10_000 * ROUNDS_PER_YEAR)

    The integer division matches the AVM's floor division. For small amounts the
    result will be 0 or 1 microALGO — this is correct and matches the contract.

    Args:
        amount_microalgo: Loan principal in microALGO.
        tier: Tier index in range [0, 3].

    Returns:
        Interest charge in microALGO (integer, floored).
    """
    return (amount_microalgo * TIER_APR_BPS[tier] * DAY_IN_ROUNDS) // (
        10_000 * ROUNDS_PER_YEAR
    )


def tier_name(tier: int) -> str:
    """Return the human-readable name for a tier.

    Args:
        tier: Tier index in range [0, 3].

    Returns:
        One of: "Fresh", "Trusted", "Veteran", "Elite".
    """
    return TIER_NAMES[tier]


# ── USDC denomination constants (micro-USDC, 6 decimals) ──────────────────────
# USDC has 6 decimal places. $1.00 = 1,000,000 micro-USDC.
# Caps are equivalent USD values to ALGO caps.

USDC_ASA_ID_TESTNET: int = 10_458_941
USDC_ASA_ID_MAINNET: int = 31_566_704

TIER_MAX_DRAW_USDC:  list[int] = [100_000, 500_000, 2_000_000, 5_000_000]
TIER_DAILY_CAP_USDC: list[int] = [500_000, 2_000_000, 10_000_000, 25_000_000]
# APR basis points are SHARED with ALGO (same TIER_APR_BPS list)


def max_draw_usdc(tier: int) -> int:
    """Return the maximum single USDC draw amount for a given tier.

    Args:
        tier: Tier index in range [0, 3].

    Returns:
        Maximum draw in micro-USDC.
    """
    return TIER_MAX_DRAW_USDC[tier]


def daily_cap_usdc(tier: int) -> int:
    """Return the daily USDC draw cap for a given tier.

    Args:
        tier: Tier index in range [0, 3].

    Returns:
        Daily cap in micro-USDC.
    """
    return TIER_DAILY_CAP_USDC[tier]


def calculate_interest_usdc(amount_microusdc: int, tier: int) -> int:
    """Calculate USDC interest for a one-day loan.

    Uses the identical formula to calculate_interest() but applied to
    micro-USDC amounts. APR basis points are shared (same tier system).

    Formula (matches on-chain AVM):
        interest = (amount * APR_bps * DAY_IN_ROUNDS) // (10_000 * ROUNDS_PER_YEAR)

    Args:
        amount_microusdc: Loan principal in micro-USDC.
        tier: Tier index in range [0, 3].

    Returns:
        Interest charge in micro-USDC (integer, floored).
    """
    return (amount_microusdc * TIER_APR_BPS[tier] * DAY_IN_ROUNDS) // (
        10_000 * ROUNDS_PER_YEAR
    )
