"""
exceptions.py — Custom exceptions for the Trestle credit SDK.
"""


class TrestleCreditError(Exception):
    """Base exception for all Trestle SDK errors.

    Catch this to handle any SDK failure without distinguishing between
    a denial and a technical fault.
    """

    pass


class TrestleCreditDenied(TrestleCreditError):
    """Raised when the risk oracle denies a credit draw request.

    The oracle evaluates four immutable criteria before every draw. If any
    criterion fails, this exception is raised and the on-chain draw() call
    is never made.

    Attributes:
        reason: Plain-English description of which criterion failed and why.
        criteria_results: Full breakdown of all four criteria evaluations as
            a dict (from CriteriaEvaluation.model_dump()). Empty dict when
            the denial happens before the oracle call (e.g. tier cap exceeded).

    Example::

        try:
            result = agent.draw(...)
        except TrestleCreditDenied as e:
            print(f"Credit denied: {e.reason}")
            print(f"Criteria details: {e.criteria_results}")
    """

    def __init__(self, reason: str, criteria_results: dict) -> None:
        """Initialise the denial exception.

        Args:
            reason: Which criterion failed and the specific reason.
            criteria_results: Full dict from CriteriaEvaluation.model_dump(),
                or an empty dict for pre-flight denials (tier cap etc.).
        """
        self.reason = reason
        self.criteria_results = criteria_results
        super().__init__(reason)


# ── x402 exceptions ────────────────────────────────────────────────────────────


class TrestleX402SpendLimitExceeded(TrestleCreditError):
    """Raised when the 402 payment amount exceeds max_spend_per_call.

    This guard fires BEFORE agent.draw() is called — no credit is drawn
    and no USDC is spent when this exception is raised.

    Attributes:
        amount:   Requested amount in microUSDC from the 402 response.
        limit:    Configured max_spend_per_call in microUSDC.

    Example::

        client = TrestleX402Client(agent, max_spend_per_call=5_000)
        try:
            client.get("https://pricey.api.com/endpoint")  # costs 50_000 μUSDC
        except TrestleX402SpendLimitExceeded as e:
            print(f"Too expensive: {e.amount} > {e.limit} microUSDC")
    """

    def __init__(self, amount: int, limit: int) -> None:
        self.amount = amount
        self.limit = limit
        super().__init__(
            f"402 amount {amount} microUSDC exceeds max_spend_per_call={limit} microUSDC"
        )


class TrestleX402PaymentError(TrestleCreditError):
    """Raised when the x402 payment flow fails after the draw.

    Possible causes:
    - GoPlausible facilitator returned isValid=False
    - Facilitator settle failed (txn rejected on-chain)
    - Network timeout communicating with facilitator

    Attributes:
        reason:   Human-readable failure description.
        txn_url:  Algorand explorer URL for the failed txn (if available).

    Example::

        try:
            client.get("https://x402.goplausible.xyz/examples/weather")
        except TrestleX402PaymentError as e:
            print(f"Payment failed: {e.reason}")
    """

    def __init__(self, reason: str, txn_url: str | None = None) -> None:
        self.reason = reason
        self.txn_url = txn_url
        super().__init__(f"x402 payment failed: {reason}")


class TrestleX402SetupError(TrestleCreditError):
    """Raised when the wallet setup is incomplete for x402 payments.

    Common causes:
    - Wallet not opted-in to the USDC ASA
    - Insufficient USDC balance after auto-swap
    - Auto opt-in transaction failed

    Example::

        try:
            client = TrestleX402Client(agent)
        except TrestleX402SetupError as e:
            print(f"Setup incomplete: {e}")
    """

    pass

