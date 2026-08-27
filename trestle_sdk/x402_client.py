"""
x402_client.py — TrestleX402Client: HTTP-native payments via x402 + Trestle credit.

Requires:  pip install "trestle-sdk[x402]"

Public interface::

    from trestle_sdk import TrestleCreditAgent, TrestleX402Client

    agent  = TrestleCreditAgent(mnemonic_phrase="...", app_id=<YOUR_APP_ID>)
    client = TrestleX402Client(agent)          # auto opts-in to USDC ASA

    # One-liner pay-per-call:
    response = client.get("https://x402.goplausible.xyz/examples/weather")
    print(response.text)

Payment flow (hidden from caller):
    1. GET → server returns HTTP 402 + paymentRequirements JSON
    2. Spend-limit guard: raises TrestleX402SpendLimitExceeded if too expensive
    3. If wallet USDC < required: auto-swap ALGO → USDC via Tinyman testnet
    4. agent.draw() draws Trestle credit (microALGO equivalent, for accounting)
    5. _CredixAvmSigner signs the USDC asset-transfer (axfer) transaction
    6. X-PAYMENT header encoded, request retried
    7. GoPlausible facilitator: POST /verify → POST /settle → Algorand txn confirmed
    8. Server returns 200 OK
    9. agent.record_payment() → on-chain reputation update

Wire format (GoPlausible x402 v1):

    402 Response body (real GoPlausible format):
    {
      "x402Version": 1,
      "accepts": [
        {
          "scheme": "exact",
          "network": "algorand:SGO1GKSzyE7IEPItTxCByw9x8FmnrCDexi9/cOUJOiI=",
          "maxAmountRequired": "1000",
          "asset": "10458941",
          "payTo": "<merchant_address>",
          "extra": {
            "feePayer": "<facilitator_address>",
            "name": "USDC",
            "decimals": 6
          }
        }
      ],
      "error": "X402 Payment Required"
    }

    X-PAYMENT header value (base64-encoded JSON):
    {
      "x402Version": 1,
      "scheme": "exact",
      "network": "algorand:SGO1GKSzyE7IEPItTxCByw9x8FmnrCDexi9/cOUJOiI=",
      "payload": {
        "paymentGroup": ["<base64-signed-axfer>", "<base64-unsigned-feepayer-pay>"],
        "paymentIndex": 0
      }
    }
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
from typing import Any, Callable

import httpx
from algosdk import encoding, mnemonic, transaction
from algosdk.v2client import algod as algod_module

from .agent import TrestleCreditAgent
from .exceptions import (
    TrestleCreditDenied,
    TrestleCreditError,
    TrestleX402PaymentError,
    TrestleX402SetupError,
    TrestleX402SpendLimitExceeded,
)

logger = logging.getLogger(__name__)

# ── GoPlausible testnet constants ───────────────────────────────────────────────
_FACILITATOR_URL = "https://facilitator.goplausible.xyz"
_TESTNET_NETWORK = "algorand:SGO1GKSzyE7IEPItTxCByw9x8FmnrCDexi9/cOUJOiI="
_MAINNET_NETWORK = "algorand:wGHE2Pwdvd7S12BL5FaOP20EGYesN73ktiC1qzkkit8="
_TESTNET_USDC_ASA = 10_458_941      # USDC on Algorand testnet
_MAINNET_USDC_ASA = 31_566_704      # USDC on Algorand mainnet
_USDC_DECIMALS = 6

# Tinyman v2 testnet app IDs
_TINYMAN_TESTNET_APP_ID = 148_607_000   # Tinyman v2.0 testnet AMM app
_TINYMAN_TESTNET_VALIDATOR_APP_ID = 148_607_000

# Conservative fixed fallback rate (used if Tinyman pool quote fails)
# 1 USDC ≈ 0.4 ALGO on testnet → 1_000_000 μUSDC = 2_500_000 μALGO
_DEFAULT_MICRO_USDC_TO_MICRO_ALGO: float = 2.5

# ── Tinyman swap helper ─────────────────────────────────────────────────────────


class _TinymanSwap:
    """
    Minimal Tinyman v2 ALGO→USDC swap helper using raw algosdk.

    Does NOT require the tinyman-py-sdk package. Uses algosdk + direct
    Algorand network calls to:
    1. Read pool state from the Tinyman v2 AMM application
    2. Calculate the required ALGO input for a target USDC output
    3. Submit the atomic swap transaction group

    Tinyman v2 swap structure (2-txn atomic group):
        Txn[0]: pay — ALGO from user → Tinyman pool address, amount = algo_in + fee
        Txn[1]: appl — app call to Tinyman pool contract (method "swap")
        (pool sends USDC back via inner txn)

    Note: On error, falls back to a fixed-rate estimate without swapping.
    """

    # Tinyman v2 testnet pool for ALGO/USDC (ASA 10458941)
    # This is the well-known pool; addr can be derived but we cache it.
    POOL_APP_ID = 160_363_393   # ALGO/USDC v2 testnet pool app ID

    def __init__(self, algod_client: algod_module.AlgodClient) -> None:
        self._algod = algod_client

    def _get_pool_state(self) -> dict:
        """Read Tinyman pool global state to get reserves."""
        try:
            app_info = self._algod.application_info(self.POOL_APP_ID)
            state = {}
            for kv in app_info.get("params", {}).get("global-state", []):
                key = base64.b64decode(kv["key"]).decode("utf-8", errors="replace")
                val = kv["value"]
                if val["type"] == 1:
                    state[key] = val["bytes"]
                else:
                    state[key] = val["uint"]
            return state
        except Exception as exc:
            logger.warning("Tinyman pool state read failed: %s", exc)
            return {}

    def estimate_algo_for_usdc(self, target_micro_usdc: int) -> int:
        """
        Estimate how many microALGO to swap to get at least target_micro_usdc.

        Uses pool reserves if readable; falls back to fixed rate.

        Args:
            target_micro_usdc: How many microUSDC output we need.

        Returns:
            microALGO to send (includes 0.3% swap fee, 5% slippage buffer).
        """
        state = self._get_pool_state()

        # Tinyman v2 global state keys for ALGO and USDC reserves
        # Keys: "asset_1_reserves" (ALGO, ASA 0) and "asset_2_reserves" (USDC)
        algo_reserves = state.get("asset_1_reserves", 0)
        usdc_reserves = state.get("asset_2_reserves", 0)

        if algo_reserves > 0 and usdc_reserves > 0:
            # Constant product formula: x*y = k
            # algo_in = algo_reserves * usdc_out / (usdc_reserves - usdc_out) + 1
            # Add 0.3% protocol fee (multiply input by 1.003)
            usdc_out = target_micro_usdc
            if usdc_out >= usdc_reserves:
                logger.warning("Insufficient USDC reserves; using fallback rate")
            else:
                algo_in_raw = (algo_reserves * usdc_out) // (usdc_reserves - usdc_out) + 1
                algo_in_with_fee = int(algo_in_raw * 1.003)  # 0.3% fee
                algo_in_with_slippage = int(algo_in_with_fee * 1.05)  # 5% slippage
                logger.debug(
                    "Tinyman quote: %d μUSDC ← %d μALGO (reserves: %d ALGO / %d USDC)",
                    target_micro_usdc, algo_in_with_slippage, algo_reserves, usdc_reserves,
                )
                return max(algo_in_with_slippage, 10_000)  # min 0.01 ALGO

        # Fallback: fixed rate
        micro_algo = int(target_micro_usdc * _DEFAULT_MICRO_USDC_TO_MICRO_ALGO)
        logger.warning(
            "Tinyman pool unavailable; using fixed rate (%.1fx): %d μUSDC → %d μALGO",
            _DEFAULT_MICRO_USDC_TO_MICRO_ALGO, target_micro_usdc, micro_algo,
        )
        return max(micro_algo, 10_000)

    def swap_algo_to_usdc(
        self,
        sender_address: str,
        private_key: str,
        algo_in_micro: int,
        min_usdc_out_micro: int,
    ) -> str:
        """
        Execute ALGO→USDC swap on Tinyman v2 testnet.

        Builds and submits a 2-transaction atomic group:
          Txn[0]: pay ALGO to pool
          Txn[1]: app call swap() to Tinyman pool contract

        Args:
            sender_address:     Algorand address of the payer.
            private_key:        base64 private key string.
            algo_in_micro:      microALGO to send to pool.
            min_usdc_out_micro: Minimum microUSDC to receive (slippage protection).

        Returns:
            Transaction ID of the submitted group.

        Raises:
            TrestleX402SetupError: If swap fails.
        """
        try:
            sp = self._algod.suggested_params()
            sp.fee = 3_000   # cover all group fees
            sp.flat_fee = True

            # Pool address (Algorand application address)
            from algosdk import logic
            pool_address = logic.get_application_address(self.POOL_APP_ID)

            # Txn[0]: Pay ALGO to pool
            pay_txn = transaction.PaymentTxn(
                sender=sender_address,
                sp=sp,
                receiver=pool_address,
                amt=algo_in_micro,
            )

            # Txn[1]: App call to Tinyman pool — "swap" with min_output
            # Tinyman v2 swap args: ["swap", asset_id, min_output]
            # asset_id=0 means we're receiving ALGO; for USDC output it's the USDC ASA
            # ABI encoded: method selector + args
            sp2 = self._algod.suggested_params()
            sp2.fee = 0
            sp2.flat_fee = True

            app_args = [
                b"swap",
                _TESTNET_USDC_ASA.to_bytes(8, "big"),
                min_usdc_out_micro.to_bytes(8, "big"),
            ]

            app_txn = transaction.ApplicationNoOpTxn(
                sender=sender_address,
                sp=sp2,
                index=self.POOL_APP_ID,
                app_args=app_args,
                foreign_assets=[_TESTNET_USDC_ASA],
            )

            # Group the transactions
            group_id = transaction.calculate_group_id([pay_txn, app_txn])
            pay_txn.group = group_id
            app_txn.group = group_id

            # Sign both
            signed_pay = pay_txn.sign(private_key)
            signed_app = app_txn.sign(private_key)

            # Submit
            txid = self._algod.send_transactions([signed_pay, signed_app])
            transaction.wait_for_confirmation(self._algod, txid, 4)

            logger.info("Tinyman swap successful: txid=%s (%d μALGO → ≥%d μUSDC)",
                        txid, algo_in_micro, min_usdc_out_micro)
            return txid

        except Exception as exc:
            raise TrestleX402SetupError(
                f"Tinyman ALGO→USDC swap failed: {exc}. "
                "Ensure wallet has sufficient ALGO and is opted-in to USDC ASA."
            ) from exc


# ── Algorand signing bridge for x402-avm ───────────────────────────────────────


class _CredixAvmSigner:
    """
    ClientAvmSigner protocol implementation using Trestle's algosdk wallet.

    Bridges Trestle's existing ``AccountTransactionSigner`` into the
    ``x402.mechanisms.avm.signer.ClientAvmSigner`` protocol expected by
    the x402-avm library's ``ExactAvmScheme``.

    Critical algosdk v2.x encoding boundary:
    - ``encoding.msgpack_decode(s)`` expects a **base64 string**, not raw bytes.
    - ``encoding.msgpack_encode(obj)`` returns a **base64 string**, not raw bytes.
    - The x402-avm library internally passes raw msgpack bytes between methods.
    - Adapter: ``base64.b64encode(raw_bytes).decode()`` before calling msgpack_decode,
      then ``base64.b64decode(b64_str)`` after msgpack_encode.

    The ``pre_sign_callback`` is invoked with the payment requirements BEFORE
    signing any transactions. This is where Trestle's ``agent.draw()`` is called
    to record the credit draw for accounting purposes.
    """

    def __init__(
        self,
        private_key: str,
        address: str,
        pre_sign_callback: Callable[[dict], None] | None = None,
    ) -> None:
        """
        Args:
            private_key:         base64-encoded 64-byte algosdk private key.
            address:             58-character Algorand address.
            pre_sign_callback:   Called with paymentRequirements dict before
                                 signing. Use to trigger agent.draw().
        """
        self._private_key = private_key
        self._address = address
        self._pre_sign_callback = pre_sign_callback
        self._last_payment_requirements: dict | None = None

    @property
    def address(self) -> str:
        """Return the 58-character Algorand address."""
        return self._address

    def sign_transactions(
        self,
        unsigned_txns: list[bytes],
        indexes_to_sign: list[int],
    ) -> list[bytes | None]:
        """
        Sign the specified transactions in a group.

        Called by the x402-avm ExactAvmScheme after it builds the payment
        group (axfer + optional feePayer pay txn). We only sign the axfer;
        the feePayer slot is left None (facilitator signs it).

        Args:
            unsigned_txns:   List of raw msgpack-encoded transaction bytes.
            indexes_to_sign: Indexes of transactions this signer must sign.

        Returns:
            List parallel to unsigned_txns:
            - Signed raw msgpack bytes at positions in indexes_to_sign.
            - None at all other positions.
        """
        result: list[bytes | None] = []

        for i, txn_bytes in enumerate(unsigned_txns):
            if i not in indexes_to_sign:
                result.append(None)
                continue

            # CRITICAL: msgpack_decode expects base64 string, not raw bytes
            b64_str = base64.b64encode(txn_bytes).decode("utf-8")
            txn_obj = encoding.msgpack_decode(b64_str)

            # Sign with private key (algosdk expects base64 string)
            signed_txn = txn_obj.sign(self._private_key)

            # CRITICAL: msgpack_encode returns base64 string, convert back to raw
            signed_b64 = encoding.msgpack_encode(signed_txn)
            signed_bytes = base64.b64decode(signed_b64)

            result.append(signed_bytes)

        return result

    def notify_payment_requirements(self, payment_requirements: dict) -> None:
        """
        Store payment requirements and trigger the pre-sign callback.

        Called by TrestleX402Client._build_payment_header() before the signing
        step, so Trestle's agent.draw() fires before we commit to signing.

        Args:
            payment_requirements: Parsed dict from the 402 response body.
        """
        self._last_payment_requirements = payment_requirements
        if self._pre_sign_callback is not None:
            self._pre_sign_callback(payment_requirements)


# ── Core TrestleX402Client ────────────────────────────────────────────────────────


class TrestleX402Client:
    """
    HTTP client that pays x402-gated APIs using Trestle on-chain credit.

    Intercepts HTTP 402 Payment Required responses and automatically:
    1. Guards against overspend (raises TrestleX402SpendLimitExceeded)
    2. Auto opts-in wallet to USDC ASA if not yet opted in
    3. Auto-swaps ALGO → USDC via Tinyman if wallet balance is insufficient
    4. Calls agent.draw() to record credit draw for Trestle accounting
    5. Builds and signs the Algorand payment group (USDC axfer)
    6. Encodes X-PAYMENT header and retries the request
    7. On 200: calls agent.record_payment() to build on-chain reputation

    All of this happens transparently — the caller just does::

        response = client.get("https://x402.goplausible.xyz/examples/weather")

    Sync interface (wraps asyncio internally)::

        client.get(url)          → httpx.Response
        client.post(url, ...)    → httpx.Response
        client.request(...)      → httpx.Response

    Async interface (for use inside async code)::

        await client.aget(url)
        await client.arequest(method, url, ...)

    Example::

        import os
        from trestle_sdk import TrestleCreditAgent, TrestleX402Client

        agent  = TrestleCreditAgent(
            mnemonic_phrase=os.environ["AGENT_MNEMONIC"],
            app_id=<YOUR_APP_ID>,
        )
        client = TrestleX402Client(agent)

        resp = client.get("https://x402.goplausible.xyz/examples/weather")
        print(f"Status: {resp.status_code}")
        print(f"Data:   {resp.text}")

    Wire format:
        GoPlausible returns 402 with an ``accepts`` array. TrestleX402Client
        automatically finds the ``exact`` + Algorand scheme entry, parses
        ``maxAmountRequired``, ``payTo``, and ``extra.feePayer``, then builds
        the X-PAYMENT header with the correct ``network`` field.

    Raises:
        TrestleX402SetupError:         If auto opt-in or auto-swap fails.
        TrestleX402SpendLimitExceeded: If 402 amount > max_spend_per_call.
        TrestleX402PaymentError:       If facilitator rejects or network fails.
        TrestleCreditDenied:          If Trestle risk oracle denies the draw.
    """

    # ── GoPlausible testnet defaults ─────────────────────────────────────────
    FACILITATOR_URL  = _FACILITATOR_URL
    TESTNET_NETWORK  = _TESTNET_NETWORK
    TESTNET_USDC_ASA = _TESTNET_USDC_ASA

    def __init__(
        self,
        agent: TrestleCreditAgent,
        *,
        facilitator_url: str = _FACILITATOR_URL,
        network: str = _TESTNET_NETWORK,
        usdc_asa_id: int = _TESTNET_USDC_ASA,
        max_spend_per_call: int = 10_000,
        record_payment_on_success: bool = True,
        task_description_prefix: str = "x402 API call",
        usdc_to_algo_ratio: float = _DEFAULT_MICRO_USDC_TO_MICRO_ALGO,
        auto_opt_in: bool = True,
        auto_swap: bool = True,
        swap_buffer_ratio: float = 1.2,
    ) -> None:
        """
        Initialise TrestleX402Client.

        Args:
            agent:
                Fully initialised TrestleCreditAgent. The agent's wallet
                is used for signing and (optionally) ALGO→USDC swaps.

            facilitator_url:
                GoPlausible facilitator base URL. Default: production testnet.
                Override for local development or custom facilitators.

            network:
                CAIP-2 network identifier. Default: Algorand Testnet.
                Use ``TrestleX402Client.TESTNET_NETWORK`` or a custom value.
                Must match the ``network`` field in the 402 response.

            usdc_asa_id:
                Algorand Standard Asset ID for USDC. Default: 10458941 (testnet).

            max_spend_per_call:
                Maximum microUSDC to spend per API call. Default: 10_000 (0.01 USDC).
                Raises ``TrestleX402SpendLimitExceeded`` if the 402 price exceeds this.

            record_payment_on_success:
                If True (default), calls ``agent.record_payment()`` after every
                successful x402 payment to build on-chain Trestle reputation.

            task_description_prefix:
                Prefix for the task description passed to ``agent.draw()``.
                Full description: "{prefix}: GET {url}".

            usdc_to_algo_ratio:
                Conversion multiplier: microALGO = microUSDC × ratio.
                Used for Trestle ``draw()`` amount calculation only (not the swap).
                Default: 2.5 (1 USDC ≈ 0.4 ALGO).

            auto_opt_in:
                If True (default), automatically opt the wallet in to the USDC
                ASA if it is not already opted-in.

            auto_swap:
                If True (default), automatically swap ALGO → USDC via Tinyman
                testnet when the wallet has insufficient USDC balance.

            swap_buffer_ratio:
                Extra ALGO to request in swap to cover price drift.
                Default: 1.2 (20% buffer). Only used when auto_swap=True.
        """
        self.agent = agent
        self.facilitator_url = facilitator_url.rstrip("/")
        self.network = network
        self.usdc_asa_id = usdc_asa_id
        self.max_spend_per_call = max_spend_per_call
        self.record_payment_on_success = record_payment_on_success
        self.task_description_prefix = task_description_prefix
        self.usdc_to_algo_ratio = usdc_to_algo_ratio
        self.auto_opt_in = auto_opt_in
        self.auto_swap = auto_swap
        self.swap_buffer_ratio = swap_buffer_ratio

        self._tinyman = _TinymanSwap(agent.algod_client)
        self._signer = _CredixAvmSigner(
            private_key=agent.private_key,
            address=agent.address,
            pre_sign_callback=None,  # set during request handling
        )

        # Auto opt-in on construction
        if auto_opt_in:
            self._ensure_usdc_opted_in()

    # ── Sync public interface ──────────────────────────────────────────────────

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        """Send GET request, auto-paying any 402 with Trestle credit.

        Args:
            url:     Target URL.
            **kwargs: Forwarded to httpx.AsyncClient.get().

        Returns:
            httpx.Response with status 200 on success.

        Raises:
            TrestleX402SpendLimitExceeded: 402 price > max_spend_per_call.
            TrestleX402PaymentError:       Facilitator or network failure.
            TrestleCreditDenied:          Trestle risk oracle denial.
        """
        return _run_sync(self.aget(url, **kwargs))

    def post(self, url: str, **kwargs: Any) -> httpx.Response:
        """Send POST request, auto-paying any 402 with Trestle credit."""
        return _run_sync(self.arequest("POST", url, **kwargs))

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """Send an arbitrary HTTP request, auto-paying any 402."""
        return _run_sync(self.arequest(method, url, **kwargs))

    # ── Async public interface ─────────────────────────────────────────────────

    async def aget(self, url: str, **kwargs: Any) -> httpx.Response:
        """Async GET with x402 auto-payment."""
        return await self.arequest("GET", url, **kwargs)

    async def arequest(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """
        Async HTTP request with full x402 payment lifecycle.

        Flow:
            1. Attempt the request.
            2. If 200 → return.
            3. If 402 → parse requirements, guard, swap, draw, build header.
            4. Retry with X-PAYMENT header.
            5. If 200 → record_payment, return.
            6. Else → raise TrestleX402PaymentError.
        """
        async with httpx.AsyncClient(timeout=30.0) as http:
            # First attempt (no payment)
            response = await http.request(method, url, **kwargs)

            if response.status_code != 402:
                return response

            # ── Parse 402 requirements ──────────────────────────────────────
            raw_body = None
            if "payment-required" in response.headers:
                try:
                    raw_body = json.loads(base64.b64decode(response.headers["payment-required"]).decode("utf-8"))
                except Exception as e:
                    logger.warning("Failed to decode payment-required header: %s", e)

            if not raw_body:
                try:
                    raw_body = response.json()
                except Exception:
                    raise TrestleX402PaymentError(
                        "402 response body is not valid JSON and payment-required header is missing/invalid"
                    )

            # Normalize to flat internal format (handles both real GoPlausible
            # "accepts" array format AND simple flat test-server format)
            payment_requirements = self._parse_payment_requirements(raw_body)

            # ── Spend guard ─────────────────────────────────────────────────
            amount_micro_usdc = payment_requirements["amount"]
            if amount_micro_usdc > self.max_spend_per_call:
                raise TrestleX402SpendLimitExceeded(amount_micro_usdc, self.max_spend_per_call)

            # ── Ensure USDC balance / Credit Draw (no double spending loophole) ────
            task_desc = f"{self.task_description_prefix}: {method} {url}"
            current_usdc = self._get_usdc_balance()

            if current_usdc >= amount_micro_usdc:
                # 1. Wallet has enough USDC. Pay directly.
                logger.debug("Wallet has enough USDC. Paying directly from wallet balance.")
            else:
                # 2. Wallet does not have enough USDC. Check if USDC credit is available.
                usdc_credit_available = False
                try:
                    usdc_pos = self.agent.get_usdc_position()
                    usdc_registered = usdc_pos.get("stake_amount", 0) > 0
                    usdc_has_no_debt = usdc_pos.get("usdc_outstanding", 0) == 0
                    usdc_treasury_has_funds = usdc_pos.get("usdc_treasury_balance", 0) >= amount_micro_usdc
                    usdc_within_cap = amount_micro_usdc <= usdc_pos.get("usdc_tier_max_draw", 0)

                    usdc_credit_available = (
                        usdc_registered and
                        usdc_has_no_debt and
                        usdc_treasury_has_funds and
                        usdc_within_cap
                    )
                except Exception as e:
                    logger.warning("Failed to check USDC credit position: %s", e)

                if usdc_credit_available:
                    logger.info("USDC credit line is available. Drawing USDC credit...")
                    self.agent.draw_usdc(
                        amount_microusdc=amount_micro_usdc,
                        task_description=task_desc,
                        expected_return_microusdc=int(amount_micro_usdc * 1.5),
                    )
                else:
                    # 3. USDC credit not available. Fallback to ALGO credit.
                    logger.info("USDC credit line unavailable. Checking ALGO credit line...")
                    algo_needed = self._tinyman.estimate_algo_for_usdc(amount_micro_usdc)

                    algo_credit_available = False
                    try:
                        algo_pos = self.agent.get_position()
                        algo_registered = algo_pos.get("stake_amount", 0) > 0
                        algo_has_no_debt = algo_pos.get("outstanding", 0) == 0
                        algo_within_cap = algo_needed <= algo_pos.get("tier_max_draw", 0)

                        algo_credit_available = (
                            algo_registered and
                            algo_has_no_debt and
                            algo_within_cap
                        )
                    except Exception as e:
                        logger.warning("Failed to check ALGO credit position: %s", e)

                    if algo_credit_available:
                        logger.info("ALGO credit line is available. Drawing ALGO credit to swap to USDC...")
                        self.agent.draw(
                            amount_microalgo=algo_needed,
                            task_description=task_desc,
                            expected_return_microalgo=int(algo_needed * 1.5),
                        )
                        # Swap the drawn ALGO to USDC
                        self._tinyman.swap_algo_to_usdc(
                            sender_address=self.agent.address,
                            private_key=self.agent.private_key,
                            algo_in_micro=algo_needed,
                            min_usdc_out_micro=amount_micro_usdc - current_usdc,
                        )
                    else:
                        # 4. Fallback to swapping own ALGO if auto_swap=True
                        if self.auto_swap:
                            logger.warning("No credit available. Swapping own ALGO to USDC out-of-pocket...")
                            self._ensure_usdc_balance(amount_micro_usdc)
                        else:
                            raise TrestleCreditDenied("No credit line available (insufficient stake, outstanding debt, or cap exceeded) and auto-swap disabled.")

            # ── Build X-PAYMENT header ──────────────────────────────────────
            x_payment = await self._build_x_payment_header(
                payment_requirements=payment_requirements,
                http_client=http,
            )

            # ── Retry with payment ──────────────────────────────────────────
            headers = dict(kwargs.pop("headers", {}))
            headers["X-PAYMENT"] = x_payment

            retry_response = await http.request(
                method, url, headers=headers, **kwargs
            )

            # ── Post-success hooks ──────────────────────────────────────────
            if retry_response.status_code == 200:
                if self.record_payment_on_success:
                    self._do_record_payment(amount_micro_usdc)
                return retry_response

            # ── Payment rejected by server ──────────────────────────────────
            try:
                err_body = retry_response.json()
                reason = err_body.get("error", retry_response.text[:200])
            except Exception:
                reason = retry_response.text[:200]

            raise TrestleX402PaymentError(
                f"Server returned {retry_response.status_code} after payment: {reason}"
            )

    # ── Payment requirements parser ─────────────────────────────────────────────

    def _parse_payment_requirements(self, body: dict) -> dict:
        """
        Normalize x402 402 response body to an internal flat dict.

        Handles both:
        - Real GoPlausible format: body["accepts"][0] with maxAmountRequired
        - Flat test-server format: body["amount"] (legacy / simplified)

        Returns:
            {
              "scheme":   str,
              "amount":   int,    # microUSDC
              "asset":    int,    # ASA ID
              "payTo":    str,    # merchant Algorand address
              "network":  str,    # CAIP-2 network identifier
              "extra":    dict,   # feePayer, name, decimals, etc.
            }

        Raises:
            TrestleX402PaymentError: If no matching scheme/network is found.
        """
        if "accepts" in body and isinstance(body["accepts"], list):
            # Real GoPlausible x402 format
            for req in body["accepts"]:
                req_network = req.get("network", "")
                req_scheme = req.get("scheme", "")
                # Match on scheme=exact and network contains our chain identifier
                if req_scheme == "exact" and (
                    req_network == self.network
                    or self.network in req_network
                    or req_network in self.network
                ):
                    try:
                        amount = int(req.get("amount", req.get("maxAmountRequired", "0")))
                    except (ValueError, TypeError):
                        amount = 0

                    try:
                        asset = int(req.get("asset", self.usdc_asa_id))
                    except (ValueError, TypeError):
                        asset = self.usdc_asa_id

                    return {
                        "scheme": "exact",
                        "amount": amount,
                        "asset": asset,
                        "payTo": req.get("payTo", ""),
                        "network": req_network,
                        "extra": req.get("extra", {}),
                    }

            # No matching scheme found
            available = [
                f"{r.get('scheme','?')}/{r.get('network','?')}"
                for r in body["accepts"]
            ]
            raise TrestleX402PaymentError(
                f"No matching 'exact' Algorand scheme in 402 accepts. "
                f"Available: {available}. Expected network: {self.network}"
            )

        # Fallback: flat format (test servers, simple implementations)
        try:
            amount = int(body.get("amount", body.get("maxAmountRequired", "0")))
        except (ValueError, TypeError):
            amount = 0

        try:
            asset = int(body.get("asset", self.usdc_asa_id))
        except (ValueError, TypeError):
            asset = self.usdc_asa_id

        return {
            "scheme": body.get("scheme", "exact"),
            "amount": amount,
            "asset": asset,
            "payTo": body.get("payTo", ""),
            "network": body.get("network", self.network),
            "extra": body.get("extra", {}),
        }

    # ── USDC management ────────────────────────────────────────────────────────

    def _ensure_usdc_opted_in(self) -> None:
        """
        Opt the wallet into the USDC ASA if not already opted in.

        Called automatically on ``__init__`` when ``auto_opt_in=True``.
        An opt-in is a zero-amount self-transfer of the ASA. Costs ~0.1 ALGO
        minimum balance increase but only needs to happen once.

        Raises:
            TrestleX402SetupError: If the opt-in transaction fails.
        """
        if self._is_usdc_opted_in():
            logger.debug("Wallet already opted in to USDC ASA %d", self.usdc_asa_id)
            return

        logger.info(
            "Auto opt-in: wallet %s → USDC ASA %d",
            self.agent.address, self.usdc_asa_id,
        )
        try:
            sp = self.agent.algod_client.suggested_params()
            sp.fee = 1_000
            sp.flat_fee = True

            # Opt-in = axfer of 0 from self to self
            opt_in_txn = transaction.AssetTransferTxn(
                sender=self.agent.address,
                sp=sp,
                receiver=self.agent.address,
                amt=0,
                index=self.usdc_asa_id,
            )
            signed = opt_in_txn.sign(self.agent.private_key)
            txid = self.agent.algod_client.send_transaction(signed)
            transaction.wait_for_confirmation(self.agent.algod_client, txid, 4)
            logger.info("USDC ASA opt-in confirmed: txid=%s", txid)

        except Exception as exc:
            raise TrestleX402SetupError(
                f"Failed to opt-in wallet to USDC ASA {self.usdc_asa_id}: {exc}. "
                "Ensure the wallet has at least 0.2 ALGO for the opt-in min balance."
            ) from exc

    def _is_usdc_opted_in(self) -> bool:
        """Check if wallet is opted-in to the USDC ASA."""
        try:
            account_info = self.agent.algod_client.account_info(self.agent.address)
            assets = account_info.get("assets", [])
            return any(a.get("asset-id") == self.usdc_asa_id for a in assets)
        except Exception as exc:
            logger.warning("Could not check USDC opt-in status: %s", exc)
            return False

    def _get_usdc_balance(self) -> int:
        """Return wallet's current microUSDC balance (0 if not opted-in)."""
        try:
            account_info = self.agent.algod_client.account_info(self.agent.address)
            assets = account_info.get("assets", [])
            for asset in assets:
                if asset.get("asset-id") == self.usdc_asa_id:
                    return int(asset.get("amount", 0))
            return 0
        except Exception as exc:
            logger.warning("Could not read USDC balance: %s", exc)
            return 0

    def _ensure_usdc_balance(self, required_micro_usdc: int) -> None:
        """
        Ensure wallet has at least required_micro_usdc of USDC.

        If current balance is insufficient, triggers auto-swap ALGO→USDC
        via Tinyman v2 testnet. The swap amount includes a buffer ratio
        for slippage protection.

        Args:
            required_micro_usdc: Minimum USDC needed in microunits.

        Raises:
            TrestleX402SetupError: If swap fails or wallet has insufficient ALGO.
        """
        current = self._get_usdc_balance()
        if current >= required_micro_usdc:
            logger.debug("USDC balance sufficient: %d ≥ %d μUSDC", current, required_micro_usdc)
            return

        deficit = required_micro_usdc - current
        # Add buffer for slippage
        swap_target = int(deficit * self.swap_buffer_ratio)

        logger.info(
            "Insufficient USDC (%d μUSDC). Auto-swapping for %d μUSDC via Tinyman...",
            current, swap_target,
        )

        # Estimate ALGO needed for swap target
        algo_needed = self._tinyman.estimate_algo_for_usdc(swap_target)

        # Check ALGO balance (keep 0.5 ALGO reserve for fees)
        try:
            account_info = self.agent.algod_client.account_info(self.agent.address)
            algo_balance = int(account_info.get("amount", 0))
            algo_reserve = 500_000  # 0.5 ALGO reserve
            algo_available = max(0, algo_balance - algo_reserve)
        except Exception:
            algo_available = 0

        if algo_available < algo_needed:
            raise TrestleX402SetupError(
                f"Insufficient ALGO for auto-swap: need {algo_needed} μALGO "
                f"(available: {algo_available} μALGO after 0.5 ALGO reserve). "
                "Fund the wallet with ALGO at https://bank.testnet.algorand.network/"
            )

        # Execute swap — min output = deficit (not swap_target, to handle slippage)
        self._tinyman.swap_algo_to_usdc(
            sender_address=self.agent.address,
            private_key=self.agent.private_key,
            algo_in_micro=algo_needed,
            min_usdc_out_micro=deficit,
        )

        # Verify balance after swap
        new_balance = self._get_usdc_balance()
        if new_balance < required_micro_usdc:
            raise TrestleX402SetupError(
                f"Swap completed but USDC balance still insufficient: "
                f"{new_balance} < {required_micro_usdc} μUSDC"
            )

        logger.info("Auto-swap successful. New USDC balance: %d μUSDC", new_balance)

    # ── Trestle credit hooks ───────────────────────────────────────────────────

    def _do_credit_draw(self, micro_algo: int, task_description: str) -> None:
        """
        Draw Trestle credit for accounting/reputation purposes.

        The draw is in microALGO equivalent of the USDC payment. This creates
        an on-chain record of the AI agent's API spending behaviour.

        Note: The draw amount is intentionally conservative — the Trestle credit
        line is used for accounting, while the actual USDC transfer comes from
        the wallet's USDC balance (funded via auto-swap if needed).

        Security: Only ``TrestleCreditDenied`` causes the payment to abort.
        All other exceptions (network errors, etc.) are logged and the USDC
        payment continues — this is intentional for availability, but the
        failure IS logged at WARNING level so operators see it.

        Args:
            micro_algo:       microALGO equivalent of the USDC payment.
            task_description: Human-readable description for the risk oracle.

        Raises:
            TrestleCreditDenied: If the risk oracle denies the draw.
        """
        # Trestle Tier 0 minimum: 1_000 μALGO
        draw_amount = max(micro_algo, 1_000)

        try:
            result = self.agent.draw(
                amount_microalgo=draw_amount,
                task_description=task_description,
                expected_return_microalgo=draw_amount,   # break-even for API calls
                estimated_task_rounds=120,
            )
            logger.debug(
                "Trestle draw: %d μALGO | txid=%s | tier=%s",
                draw_amount, result.get("txid", "?"), result.get("tier_name", "?"),
            )
            # Auto-repay immediately (x402 calls are not "loans", they are expenses)
            self.agent.repay(result["total_repayable"])

        except TrestleCreditDenied:
            raise  # always propagate — credit denial must block payment

        except TrestleCreditError as exc:
            # Known SDK error (chain failure, etc.) — log clearly, continue payment
            logger.warning(
                "Trestle draw failed with TrestleCreditError (USDC payment continues): "
                "%s: %s", type(exc).__name__, exc,
            )

        except Exception as exc:
            # Unknown error (network timeout, etc.) — log clearly, continue payment
            logger.warning(
                "Trestle draw raised unexpected %s (USDC payment continues): %s",
                type(exc).__name__, exc,
            )

    def _do_record_payment(self, micro_usdc: int) -> None:
        """
        Call agent.record_payment_usdc() after a successful x402 payment.

        Records the payment on the USDC contract to build USDC tier history.

        Args:
            micro_usdc: microUSDC amount that was successfully paid.
        """
        try:
            new_tier = self.agent.record_payment_usdc(micro_usdc)
            logger.info(
                "record_payment_usdc: %d μUSDC paid → new USDC Trestle tier %d",
                micro_usdc, new_tier,
            )
        except Exception as exc:
            # Non-fatal: don't fail the response just because record_payment_usdc errored
            logger.warning("agent.record_payment_usdc() failed (non-fatal): %s", exc)

    # ── X-PAYMENT header construction ──────────────────────────────────────────

    async def _build_x_payment_header(
        self,
        payment_requirements: dict,
        http_client: httpx.AsyncClient,
    ) -> str:
        """
        Build the X-PAYMENT header value for the Algorand exact scheme.

        Constructs the Algorand atomic payment group:
          Txn[0] (paymentIndex=0): axfer — USDC from wallet to merchant
          Txn[1]: pay — feePayer → feePayer (0 ALGO, facilitator pays fees)

        Encodes as:
          base64(JSON({
              "x402Version": 1,
              "scheme": "exact",
              "network": "<CAIP-2 network>",
              "payload": {
                  "paymentGroup": [base64(msgpack(Txn0)), base64(msgpack(Txn1))],
                  "paymentIndex": 0
              }
          }))

        If the x402-avm library is installed, delegates to ExactAvmScheme.
        Otherwise falls back to manual construction.

        Args:
            payment_requirements: Parsed flat dict (from _parse_payment_requirements).
            http_client:          Active httpx client for facilitator calls.

        Returns:
            The encoded X-PAYMENT header string.

        Raises:
            TrestleX402PaymentError: If payment group construction fails.
        """
        try:
            from x402 import x402Client as X402CoreClient
            from x402.mechanisms.avm.exact import ExactAvmScheme
            return await self._build_via_x402_avm_lib(
                payment_requirements, http_client
            )
        except (ImportError, TypeError, Exception) as exc:
            logger.warning("x402-avm library fallback triggered: %s; falling back to manual header construction", exc)
            return self._build_manual_x_payment_header(payment_requirements)

    async def _build_via_x402_avm_lib(
        self,
        payment_requirements: dict,
        http_client: httpx.AsyncClient,
    ) -> str:
        """
        Use the x402-avm library's ExactAvmScheme to build the payment header.

        The library handles:
        - Fetching latest Algorand block params for txn validity window
        - Constructing the atomic group (axfer + feePayer pay)
        - Calling our _CredixAvmSigner.sign_transactions()
        - Encoding the PAYMENT-SIGNATURE header
        """
        from x402 import x402Client as X402CoreClient  # type: ignore[import]
        from x402.mechanisms.avm.exact import ExactAvmScheme  # type: ignore[import]

        x402_core = X402CoreClient()
        scheme = ExactAvmScheme(
            signer=self._signer,
            facilitator_url=self.facilitator_url,
            network=self.network,
        )
        x402_core.register(scheme)

        # ExactAvmScheme.create_payment_header builds the group and returns header value
        header_value = await scheme.create_payment_header(
            payment_requirements=payment_requirements,
            client=http_client,
        )
        return header_value

    def _build_manual_x_payment_header(
        self,
        payment_requirements: dict,
    ) -> str:
        """
        Fallback: manually construct X-PAYMENT header without x402-avm lib.

        Used when x402-avm is not installed. Builds the minimal Algorand
        exact scheme payment group manually using raw algosdk.

        This supports the GoPlausible testnet facilitator's expected format:
          base64(JSON({
            "x402Version": 1,
            "scheme": "exact",
            "network": "<CAIP-2 network>",   ← REQUIRED by GoPlausible
            "payload": {
              "paymentGroup": [...],
              "paymentIndex": 0
            }
          }))
        """
        sp = self.agent.algod_client.suggested_params()
        sp.fee = 0
        sp.flat_fee = True

        amount = payment_requirements["amount"]
        pay_to = payment_requirements["payTo"]
        asset_id = payment_requirements["asset"]
        fee_payer = payment_requirements.get("extra", {}).get("feePayer", "")
        network = payment_requirements.get("network", self.network)

        # Txn[0]: axfer USDC to merchant
        axfer_txn = transaction.AssetTransferTxn(
            sender=self.agent.address,
            sp=sp,
            receiver=pay_to,
            amt=amount,
            index=asset_id,
        )

        txns = [axfer_txn]
        has_fee_payer = bool(fee_payer)

        if has_fee_payer:
            # Txn[1]: feePayer pays fees for group (0-value pay to self)
            sp2 = self.agent.algod_client.suggested_params()
            sp2.fee = 2_000  # pool fees for both txns
            sp2.flat_fee = True
            fee_pay_txn = transaction.PaymentTxn(
                sender=fee_payer,
                sp=sp2,
                receiver=fee_payer,
                amt=0,
            )
            txns.append(fee_pay_txn)

        # Assign group ID
        if len(txns) > 1:
            gid = transaction.calculate_group_id(txns)
            for t in txns:
                t.group = gid

        # Sign txns (only sign index 0 — the axfer)
        unsigned_bytes = [
            base64.b64decode(encoding.msgpack_encode(t)) for t in txns
        ]
        signed_results = self._signer.sign_transactions(
            unsigned_txns=unsigned_bytes,
            indexes_to_sign=[0],
        )

        # Encode to base64 strings for JSON
        group_b64 = []
        for i, (raw, signed) in enumerate(zip(unsigned_bytes, signed_results)):
            if signed is not None:
                group_b64.append(base64.b64encode(signed).decode())
            else:
                group_b64.append(base64.b64encode(raw).decode())

        payload = {
            "x402Version": 1,
            "scheme": "exact",
            "network": network,          # REQUIRED: CAIP-2 network identifier
            "payload": {
                "paymentGroup": group_b64,
                "paymentIndex": 0,
            },
        }

        return base64.b64encode(json.dumps(payload).encode()).decode()

    # ── Facilitator verification (manual mode) ────────────────────────────────

    def verify_with_facilitator(
        self,
        payment_payload: dict,
        payment_requirements: dict,
    ) -> bool:
        """
        Manually call the GoPlausible facilitator's /verify endpoint.

        Normally called internally by the x402-avm library. Exposed for
        testing and debugging purposes.

        Returns:
            True if the facilitator returns isValid=True.

        Raises:
            TrestleX402PaymentError: On network error or isValid=False.
        """
        with httpx.Client(timeout=10.0) as http:
            resp = http.post(
                f"{self.facilitator_url}/verify",
                json={
                    "paymentPayload": payment_payload,
                    "paymentRequirements": payment_requirements,
                },
            )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("isValid", False):
            reason = data.get("invalidReason", "unknown")
            raise TrestleX402PaymentError(f"Facilitator verify failed: {reason}")
        return True

    def settle_with_facilitator(
        self,
        payment_payload: dict,
        payment_requirements: dict,
    ) -> str:
        """
        Manually call the GoPlausible facilitator's /settle endpoint.

        Normally called internally by the x402-avm library. Exposed for
        testing and debugging purposes.

        Returns:
            Transaction ID (txid) from Algorand settlement.

        Raises:
            TrestleX402PaymentError: On network error or settlement failure.
        """
        with httpx.Client(timeout=30.0) as http:
            resp = http.post(
                f"{self.facilitator_url}/settle",
                json={
                    "paymentPayload": payment_payload,
                    "paymentRequirements": payment_requirements,
                },
            )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success", False):
            reason = data.get("errorReason", "unknown")
            raise TrestleX402PaymentError(f"Facilitator settle failed: {reason}")

        txid = data.get("transaction", "")
        explorer = f"https://testnet.explorer.perawallet.app/tx/{txid}" if txid else ""
        logger.info("Settlement confirmed: txid=%s explorer=%s", txid, explorer)
        return txid

    def check_facilitator_health(self) -> dict:
        """
        Query the GoPlausible facilitator /health endpoint.

        Returns:
            Dict with keys: status, version, timestamp, networks, uptime.

        Raises:
            TrestleX402PaymentError: If facilitator is unreachable.
        """
        try:
            with httpx.Client(timeout=10.0) as http:
                resp = http.get(f"{self.facilitator_url}/health")
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            raise TrestleX402PaymentError(
                f"Facilitator health check failed: {exc}"
            ) from exc

    # ── Utility ───────────────────────────────────────────────────────────────

    def usdc_balance(self) -> int:
        """Return current wallet USDC balance in microunits."""
        return self._get_usdc_balance()

    def algo_balance(self) -> int:
        """Return current wallet ALGO balance in microALGO."""
        try:
            info = self.agent.algod_client.account_info(self.agent.address)
            return int(info.get("amount", 0))
        except Exception:
            return 0

    def __repr__(self) -> str:
        return (
            f"TrestleX402Client("
            f"address={self.agent.address[:8]}..., "
            f"max_spend={self.max_spend_per_call}μUSDC, "
            f"facilitator={self.facilitator_url})"
        )


# ── Async event-loop helper ───────────────────────────────────────────────────


def _run_sync(coro: Any) -> Any:
    """
    Run an async coroutine synchronously from sync context.

    Safe for Python 3.10+ (avoids deprecated get_event_loop()).
    Handles the case where a running loop already exists (e.g., Jupyter,
    FastAPI) by using a dedicated ThreadPoolExecutor.
    """
    try:
        # Check if there's a running event loop in the current thread
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop — safe to use asyncio.run()
        return asyncio.run(coro)

    # Running loop exists — run in a separate thread with its own loop
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(asyncio.run, coro)
        return future.result()
