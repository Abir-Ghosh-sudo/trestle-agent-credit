__version__ = "0.2.0"

"""
Trestle SDK — LLM-gated credit for the Trestle AI agent protocol on Algorand.

LLM provider is selected via the ORACLE_PROVIDER environment variable:
    ORACLE_PROVIDER=venice      → Venice AI, llama-3.3-70b (default)
    ORACLE_PROVIDER=anthropic   → Anthropic, claude-haiku-4-5-20251001

Core public surface::

    from trestle_sdk import TrestleCreditAgent, TrestleCreditDenied

    agent = TrestleCreditAgent(mnemonic_phrase="...", app_id=<YOUR_APP_ID>)
    try:
        result = agent.draw(
            amount_microalgo=50_000,
            task_description="Fetch ETH/USD from CoinGecko",
            expected_return_microalgo=80_000,
        )
    except TrestleCreditDenied as e:
        print(e.reason)

x402 HTTP-native payments (requires: pip install "trestle-sdk[x402]")::

    from trestle_sdk import TrestleX402Client

    client = TrestleX402Client(agent)
    response = client.get("https://x402.goplausible.xyz/examples/weather")
    print(response.text)
"""

from .oracle import RiskOracle, RiskDecision, CriteriaEvaluation
from .agent import TrestleCreditAgent, ProtocolConfig
from .exceptions import (
    TrestleCreditDenied,
    TrestleCreditError,
    TrestleX402PaymentError,
    TrestleX402SpendLimitExceeded,
    TrestleX402SetupError,
)
from .criteria import (
    get_tier, calculate_interest, tier_name,
    calculate_interest_usdc, max_draw_usdc, daily_cap_usdc,
    USDC_ASA_ID_TESTNET, USDC_ASA_ID_MAINNET,
)


def __getattr__(name: str):
    """Lazy-load x402 client to avoid hard dependency on x402-avm package."""
    if name == "TrestleX402Client":
        try:
            from .x402_client import TrestleX402Client
            return TrestleX402Client
        except ImportError as exc:
            raise ImportError(
                "TrestleX402Client requires the x402 extra: "
                "pip install \"trestle-sdk[x402]\""
            ) from exc
    raise AttributeError(f"module 'trestle_sdk' has no attribute {name!r}")


__all__ = [
    # Core
    "TrestleCreditAgent",
    "ProtocolConfig",
    "RiskOracle",
    "RiskDecision",
    "CriteriaEvaluation",
    "TrestleCreditDenied",
    "TrestleCreditError",
    "get_tier",
    "calculate_interest",
    "tier_name",
    # USDC criteria
    "calculate_interest_usdc",
    "max_draw_usdc",
    "daily_cap_usdc",
    "USDC_ASA_ID_TESTNET",
    "USDC_ASA_ID_MAINNET",
    # x402 (lazy — requires pip install "trestle-sdk[x402]")
    "TrestleX402Client",
    "TrestleX402PaymentError",
    "TrestleX402SpendLimitExceeded",
    "TrestleX402SetupError",
]

