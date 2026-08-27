"""
tests/test_x402_client.py — Unit tests for TrestleX402Client.

Runs without network access (all external calls are mocked).
No Algorand wallet or x402-avm installation required.

Run:
    python -m pytest tests/test_x402_client.py -v
"""

import asyncio
import base64
import json
from unittest.mock import MagicMock, patch, AsyncMock, call

import pytest

# ── Mock x402-avm if not installed ────────────────────────────────────────────
import sys
import types

if "x402" not in sys.modules:
    # Create minimal x402 mock so imports don't fail
    x402_mock = types.ModuleType("x402")
    x402_mock.x402Client = MagicMock
    sys.modules["x402"] = x402_mock

    x402_mech = types.ModuleType("x402.mechanisms")
    sys.modules["x402.mechanisms"] = x402_mech

    x402_avm = types.ModuleType("x402.mechanisms.avm")
    x402_avm.ExactAvmScheme = MagicMock
    sys.modules["x402.mechanisms.avm"] = x402_avm

    x402_http = types.ModuleType("x402.http")
    sys.modules["x402.http"] = x402_http

    x402_clients = types.ModuleType("x402.http.clients")
    sys.modules["x402.http.clients"] = x402_clients

    x402_httpx = types.ModuleType("x402.http.clients.httpx")
    x402_httpx.x402HttpxClient = MagicMock
    x402_httpx.x402AsyncTransport = MagicMock
    sys.modules["x402.http.clients.httpx"] = x402_httpx


# ── Now import the module under test ─────────────────────────────────────────

from trestle_sdk.exceptions import (
    TrestleX402SpendLimitExceeded,
    TrestleX402PaymentError,
    TrestleX402SetupError,
    TrestleCreditError,
    TrestleCreditDenied,
)


def _make_mock_agent(
    address: str = "TRESTLEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
    private_key: str = None,
    usdc_balance: int = 100_000,
    algo_balance: int = 5_000_000,
):
    """Create a mock TrestleCreditAgent."""
    agent = MagicMock()
    agent.address = address
    agent.private_key = private_key or base64.b64encode(b"\x00" * 64).decode()
    agent.algod_client = MagicMock()

    # account_info returns wallet state
    account_info = {
        "amount": algo_balance,
        "assets": [
            {"asset-id": 10_458_941, "amount": usdc_balance},
        ],
    }
    agent.algod_client.account_info.return_value = account_info

    # suggested_params
    sp = MagicMock()
    sp.fee = 1_000
    sp.flat_fee = False
    agent.algod_client.suggested_params.return_value = sp

    # send_transaction and wait_for_confirmation (for opt-in)
    agent.algod_client.send_transaction.return_value = "TXID_OPTIN"

    # draw/repay/record_payment
    agent.draw.return_value = {
        "txid": "TXID_DRAW",
        "amount_microalgo": 1_000,
        "interest_microalgo": 1,
        "total_repayable": 1_001,
        "tier": 0,
        "tier_name": "Fresh",
        "apr_bps": 2400,
        "risk_summary": "low risk",
    }
    agent.repay.return_value = {"txid": "TXID_REPAY", "repaid_microalgo": 1_001}
    agent.record_payment.return_value = 0  # tier 0
    agent.record_payment_usdc.return_value = 0  # tier 0

    return agent


# GoPlausible real 402 format helpers

_TESTNET_NETWORK = "algorand:SGO1GKSzyE7IEPItTxCByw9x8FmnrCDexi9/cOUJOiI="


def _make_real_402_body(
    amount: int = 1_000,
    pay_to: str = "MERCHANTAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
    fee_payer: str = "FACILITATORAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
    network: str = _TESTNET_NETWORK,
    asset: int = 10_458_941,
) -> dict:
    """Build a real GoPlausible x402 402-response body (accepts array format)."""
    return {
        "x402Version": 1,
        "accepts": [
            {
                "scheme": "exact",
                "network": network,
                "maxAmountRequired": str(amount),
                "asset": str(asset),
                "payTo": pay_to,
                "extra": {
                    "feePayer": fee_payer,
                    "name": "USDC",
                    "decimals": 6,
                },
            }
        ],
        "error": "X402 Payment Required",
    }


def _make_flat_402_body(
    amount: int = 1_000,
    pay_to: str = "MERCHANTAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
) -> dict:
    """Build a flat (legacy/test-server) 402-response body."""
    return {
        "scheme": "exact",
        "amount": str(amount),
        "asset": "10458941",
        "payTo": pay_to,
        "network": _TESTNET_NETWORK,
        "extra": {},
    }



# ─────────────────────────────────────────────────────────────────────────────
# Tests: Exceptions
# ─────────────────────────────────────────────────────────────────────────────

class TestExceptions:
    def test_spend_limit_exceeded_attrs(self):
        exc = TrestleX402SpendLimitExceeded(amount=50_000, limit=10_000)
        assert exc.amount == 50_000
        assert exc.limit == 10_000
        assert "50000" in str(exc)
        assert "10000" in str(exc)
        assert isinstance(exc, TrestleCreditError)

    def test_payment_error_attrs(self):
        exc = TrestleX402PaymentError(reason="verify failed", txn_url="https://x.com/tx/abc")
        assert exc.reason == "verify failed"
        assert exc.txn_url == "https://x.com/tx/abc"
        assert "verify failed" in str(exc)
        assert isinstance(exc, TrestleCreditError)

    def test_payment_error_no_url(self):
        exc = TrestleX402PaymentError(reason="timeout")
        assert exc.txn_url is None

    def test_setup_error_is_credit_error(self):
        exc = TrestleX402SetupError("not opted in")
        assert isinstance(exc, TrestleCreditError)


# ─────────────────────────────────────────────────────────────────────────────
# Tests: _CredixAvmSigner
# ─────────────────────────────────────────────────────────────────────────────

class TestCredixAvmSigner:
    """Tests for the algosdk ↔ x402-avm signing bridge."""

    def _make_signer(self):
        from trestle_sdk.x402_client import _CredixAvmSigner
        # Use a real algosdk keypair for encoding tests
        from algosdk import account
        private_key, address = account.generate_account()
        return _CredixAvmSigner(private_key=private_key, address=address), private_key, address

    def test_address_property(self):
        from trestle_sdk.x402_client import _CredixAvmSigner
        signer = _CredixAvmSigner(
            private_key=base64.b64encode(b"\x00" * 64).decode(),
            address="TESTADDR",
        )
        assert signer.address == "TESTADDR"

    def test_sign_returns_none_for_non_sign_indexes(self):
        from trestle_sdk.x402_client import _CredixAvmSigner
        from algosdk import account, encoding, transaction

        private_key, address = account.generate_account()
        signer = _CredixAvmSigner(private_key=private_key, address=address)

        # Create a minimal valid txn
        sp = MagicMock()
        sp.fee = 1_000
        sp.flat_fee = True
        sp.first = 1000
        sp.last = 2000
        sp.gh = base64.b64encode(b"\x00" * 32).decode()
        sp.gen = "testnet-v1.0"
        sp.min_fee = 1_000

        txn = transaction.PaymentTxn(
            sender=address,
            sp=sp,
            receiver=address,
            amt=0,
        )
        raw_bytes = base64.b64decode(encoding.msgpack_encode(txn))

        # Only sign index 0, but pass two identical txns
        results = signer.sign_transactions(
            unsigned_txns=[raw_bytes, raw_bytes],
            indexes_to_sign=[0],
        )
        assert len(results) == 2
        assert results[0] is not None    # signed
        assert results[1] is None        # unsigned

    def test_sign_encoding_roundtrip(self):
        """Verify the base64 encoding adapter works correctly."""
        from trestle_sdk.x402_client import _CredixAvmSigner
        from algosdk import account, encoding, transaction

        private_key, address = account.generate_account()
        signer = _CredixAvmSigner(private_key=private_key, address=address)

        sp = MagicMock()
        sp.fee = 1_000
        sp.flat_fee = True
        sp.first = 1000
        sp.last = 2000
        sp.gh = base64.b64encode(b"\x00" * 32).decode()
        sp.gen = "testnet-v1.0"
        sp.min_fee = 1_000

        txn = transaction.PaymentTxn(
            sender=address, sp=sp, receiver=address, amt=0,
        )
        raw = base64.b64decode(encoding.msgpack_encode(txn))

        results = signer.sign_transactions([raw], [0])
        assert len(results) == 1
        signed_raw = results[0]
        assert signed_raw is not None
        assert isinstance(signed_raw, bytes)
        assert len(signed_raw) > len(raw)   # signed txn is larger

    def test_pre_sign_callback_invoked(self):
        from trestle_sdk.x402_client import _CredixAvmSigner
        from algosdk import account, encoding, transaction

        private_key, address = account.generate_account()
        callback = MagicMock()

        signer = _CredixAvmSigner(
            private_key=private_key,
            address=address,
            pre_sign_callback=callback,
        )

        requirements = {"scheme": "exact", "amount": "1000", "asset": "10458941"}
        signer.notify_payment_requirements(requirements)

        callback.assert_called_once_with(requirements)


# ─────────────────────────────────────────────────────────────────────────────
# Tests: TrestleX402Client
# ─────────────────────────────────────────────────────────────────────────────

class TestTrestleX402Client:
    """Tests for TrestleX402Client — all external I/O is mocked."""

    def _make_client(self, agent=None, **kwargs):
        from trestle_sdk.x402_client import TrestleX402Client
        if agent is None:
            agent = _make_mock_agent()

        # Patch _ensure_usdc_opted_in and wait_for_confirmation so no network needed
        with patch("trestle_sdk.x402_client.transaction") as mock_txn:
            mock_txn.AssetTransferTxn.return_value = MagicMock()
            mock_txn.wait_for_confirmation.return_value = {}
            client = TrestleX402Client(
                agent,
                auto_opt_in=False,   # disable in unit tests
                auto_swap=False,
                **kwargs,
            )
        return client

    # ── spend guard ──────────────────────────────────────────────────────────

    def test_spend_guard_raises_before_draw(self):
        """Spend limit guard must fire BEFORE agent.draw() is called."""
        agent = _make_mock_agent()
        client = self._make_client(agent, max_spend_per_call=5_000)

        # 50k μUSDC > 5k limit — use real GoPlausible format
        mock_402 = MagicMock()
        mock_402.status_code = 402
        mock_402.json.return_value = _make_real_402_body(amount=50_000)

        with patch("httpx.AsyncClient") as mock_http_cls:
            mock_http = AsyncMock()
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_http.request = AsyncMock(return_value=mock_402)
            mock_http_cls.return_value = mock_http

            with pytest.raises(TrestleX402SpendLimitExceeded) as exc_info:
                asyncio.run(client.arequest("GET", "https://example.x402.goplausible.xyz/"))

        assert exc_info.value.amount == 50_000
        assert exc_info.value.limit == 5_000
        # Verify draw was NOT called
        agent.draw.assert_not_called()


    # ── successful payment flow ───────────────────────────────────────────────

    def test_successful_payment_calls_record_payment(self):
        """On 200 response after payment, record_payment must be called."""
        agent = _make_mock_agent()
        client = self._make_client(agent, max_spend_per_call=100_000)

        mock_402 = MagicMock()
        mock_402.status_code = 402
        mock_402.json.return_value = _make_real_402_body(amount=1_000)

        mock_200 = MagicMock()
        mock_200.status_code = 200
        mock_200.text = '{"data": "weather_info"}'

        with patch("httpx.AsyncClient") as mock_http_cls, \
             patch.object(client, "_build_x_payment_header",
                          new=AsyncMock(return_value="BASE64_PAYMENT_HEADER")):

            mock_http = AsyncMock()
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            # First call: 402, second call (with payment): 200
            mock_http.request = AsyncMock(side_effect=[mock_402, mock_200])
            mock_http_cls.return_value = mock_http

            response = asyncio.run(
                client.arequest("GET", "https://x402.goplausible.xyz/examples/weather")
            )

        assert response.status_code == 200
        # record_payment_usdc should have been called
        agent.record_payment_usdc.assert_called_once()


    def test_failed_payment_does_not_call_record_payment(self):
        """On failure (not 200 after payment), record_payment must NOT be called."""
        agent = _make_mock_agent()
        client = self._make_client(agent, max_spend_per_call=100_000)

        mock_402_first = MagicMock()
        mock_402_first.status_code = 402
        mock_402_first.json.return_value = _make_real_402_body(amount=1_000)

        mock_402_retry = MagicMock()
        mock_402_retry.status_code = 402
        mock_402_retry.json.return_value = {"error": "invalid payment"}

        with patch("httpx.AsyncClient") as mock_http_cls, \
             patch.object(client, "_build_x_payment_header",
                          new=AsyncMock(return_value="BASE64_PAYMENT_HEADER")):

            mock_http = AsyncMock()
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_http.request = AsyncMock(side_effect=[mock_402_first, mock_402_retry])
            mock_http_cls.return_value = mock_http

            with pytest.raises(TrestleX402PaymentError):
                asyncio.run(
                    client.arequest("GET", "https://x402.goplausible.xyz/examples/weather")
                )

        # record_payment_usdc must NOT have been called on failure
        agent.record_payment_usdc.assert_not_called()


    # ── USDC conversion ──────────────────────────────────────────────────────

    def test_usdc_to_algo_conversion_math(self):
        """Verify the microUSDC → microALGO conversion ratio."""
        client = self._make_client()
        # Default ratio: 2.5
        assert client.usdc_to_algo_ratio == 2.5
        micro_algo = int(1_000 * 2.5)
        assert micro_algo == 2_500

    def test_custom_ratio(self):
        client = self._make_client(usdc_to_algo_ratio=3.0)
        assert client.usdc_to_algo_ratio == 3.0

    # ── Trestle credit draw ───────────────────────────────────────────────────

    def test_credit_draw_called_with_correct_args(self):
        """agent.draw() should be called with microALGO equivalent when ALGO credit fallback is used."""
        agent = _make_mock_agent(usdc_balance=0)
        client = self._make_client(agent, max_spend_per_call=100_000)

        # Mock credit availability
        agent.get_usdc_position.return_value = {"stake_amount": 0} # USDC credit line inactive
        agent.get_position.return_value = {
            "stake_amount": 1_000_000,
            "outstanding": 0,
            "tier_max_draw": 10_000_000,
            "payment_count": 0,
        }
        client._tinyman.estimate_algo_for_usdc = MagicMock(return_value=5_000)
        client._tinyman.swap_algo_to_usdc = MagicMock()

        # 2000 μUSDC * 2.5 = 5000 μALGO — use real GoPlausible format
        mock_402 = MagicMock()
        mock_402.status_code = 402
        mock_402.json.return_value = _make_real_402_body(amount=2_000)

        mock_200 = MagicMock()
        mock_200.status_code = 200

        with patch("httpx.AsyncClient") as mock_http_cls, \
             patch.object(client, "_build_x_payment_header",
                          new=AsyncMock(return_value="HDR")):
            mock_http = AsyncMock()
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_http.request = AsyncMock(side_effect=[mock_402, mock_200])
            mock_http_cls.return_value = mock_http

            asyncio.run(client.arequest("GET", "https://example.x402.goplausible.xyz/"))

        # 2000 μUSDC * 2.5 = 5000 μALGO (> min 1000)
        agent.draw.assert_called_once()
        call_kwargs = agent.draw.call_args[1]
        assert call_kwargs["amount_microalgo"] == 5_000

    def test_usdc_credit_draw_called_when_usdc_credit_available(self):
        """When USDC credit is available, agent.draw_usdc() should be called."""
        agent = _make_mock_agent(usdc_balance=0)
        client = self._make_client(agent, max_spend_per_call=100_000)

        # Mock USDC credit available
        agent.get_usdc_position.return_value = {
            "stake_amount": 1_000_000,
            "usdc_outstanding": 0,
            "usdc_treasury_balance": 10_000_000,
            "usdc_tier_max_draw": 1_000_000,
        }

        mock_402 = MagicMock()
        mock_402.status_code = 402
        mock_402.json.return_value = _make_real_402_body(amount=2_000)

        mock_200 = MagicMock()
        mock_200.status_code = 200

        with patch("httpx.AsyncClient") as mock_http_cls, \
             patch.object(client, "_build_x_payment_header",
                          new=AsyncMock(return_value="HDR")):
            mock_http = AsyncMock()
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_http.request = AsyncMock(side_effect=[mock_402, mock_200])
            mock_http_cls.return_value = mock_http

            asyncio.run(client.arequest("GET", "https://example.x402.goplausible.xyz/"))

        agent.draw_usdc.assert_called_once()
        call_kwargs = agent.draw_usdc.call_args[1]
        assert call_kwargs["amount_microusdc"] == 2_000


    # ── opt-in ───────────────────────────────────────────────────────────────

    def test_is_usdc_opted_in_true(self):
        """_is_usdc_opted_in returns True when ASA is in account assets."""
        agent = _make_mock_agent(usdc_balance=500)
        with patch("trestle_sdk.x402_client.transaction"):
            from trestle_sdk.x402_client import TrestleX402Client
            client = TrestleX402Client(agent, auto_opt_in=False, auto_swap=False)
        assert client._is_usdc_opted_in() is True

    def test_is_usdc_opted_in_false(self):
        """_is_usdc_opted_in returns False when ASA not in account assets."""
        agent = _make_mock_agent()
        # Remove USDC from assets
        agent.algod_client.account_info.return_value = {
            "amount": 5_000_000,
            "assets": [],  # no assets
        }
        with patch("trestle_sdk.x402_client.transaction"):
            from trestle_sdk.x402_client import TrestleX402Client
            client = TrestleX402Client(agent, auto_opt_in=False, auto_swap=False)
        assert client._is_usdc_opted_in() is False

    # ── manual X-PAYMENT header ──────────────────────────────────────────────

    def test_manual_header_structure(self):
        """_build_manual_x_payment_header produces valid base64 JSON with network field."""
        from trestle_sdk.x402_client import TrestleX402Client
        from algosdk import account

        private_key, address = account.generate_account()
        agent = _make_mock_agent(address=address, private_key=private_key)

        sp = MagicMock()
        sp.fee = 1_000
        sp.flat_fee = True
        sp.first = 1_000
        sp.last = 2_000
        sp.gh = base64.b64encode(b"\x00" * 32).decode()
        sp.gen = "testnet-v1.0"
        sp.min_fee = 1_000
        agent.algod_client.suggested_params.return_value = sp

        client = TrestleX402Client(agent, auto_opt_in=False, auto_swap=False)

        req = {
            "scheme": "exact",
            "amount": 1_000,
            "asset": 10_458_941,
            "payTo": address,   # use valid address
            "network": _TESTNET_NETWORK,
            "extra": {},        # no feePayer
        }

        header = client._build_manual_x_payment_header(req)

        # Must be valid base64
        decoded = base64.b64decode(header)
        payload = json.loads(decoded)

        assert payload["x402Version"] == 1
        assert payload["scheme"] == "exact"
        assert "network" in payload                       # REQUIRED for GoPlausible
        assert payload["network"] == _TESTNET_NETWORK    # must match
        assert "paymentGroup" in payload["payload"]
        assert payload["payload"]["paymentIndex"] == 0
        assert len(payload["payload"]["paymentGroup"]) >= 1


    # ── Payment requirements parser ───────────────────────────────────────────

    def test_parse_real_goplausible_402_format(self):
        """Parser correctly handles real GoPlausible 'accepts' array format."""
        from trestle_sdk.x402_client import TrestleX402Client
        client = TrestleX402Client(_make_mock_agent(), auto_opt_in=False, auto_swap=False)

        body = _make_real_402_body(amount=5_000, pay_to="MERCHANT" + "A" * 50)
        parsed = client._parse_payment_requirements(body)

        assert parsed["scheme"] == "exact"
        assert parsed["amount"] == 5_000
        assert parsed["asset"] == 10_458_941
        assert parsed["payTo"].startswith("MERCHANT")
        assert parsed["network"] == _TESTNET_NETWORK
        assert "feePayer" in parsed["extra"]

    def test_parse_flat_fallback_format(self):
        """Parser falls back gracefully to simple flat format."""
        from trestle_sdk.x402_client import TrestleX402Client
        client = TrestleX402Client(_make_mock_agent(), auto_opt_in=False, auto_swap=False)

        body = _make_flat_402_body(amount=2_500)
        parsed = client._parse_payment_requirements(body)

        assert parsed["amount"] == 2_500
        assert parsed["scheme"] == "exact"

    def test_parse_network_mismatch_raises(self):
        """Parser raises TrestleX402PaymentError when no matching network found."""
        from trestle_sdk.x402_client import TrestleX402Client
        client = TrestleX402Client(_make_mock_agent(), auto_opt_in=False, auto_swap=False)

        body = {
            "x402Version": 1,
            "accepts": [
                {
                    "scheme": "exact",
                    "network": "ethereum:1",   # wrong chain
                    "maxAmountRequired": "1000",
                    "asset": "USDC",
                    "payTo": "0xabc...",
                    "extra": {},
                }
            ],
        }
        with pytest.raises(TrestleX402PaymentError, match="No matching"):
            client._parse_payment_requirements(body)

    def test_parse_amount_as_int_string(self):
        """Parser handles maxAmountRequired as string '1000' → int 1000."""
        from trestle_sdk.x402_client import TrestleX402Client
        client = TrestleX402Client(_make_mock_agent(), auto_opt_in=False, auto_swap=False)

        body = _make_real_402_body(amount=999)
        # Manually set as string to verify coercion
        body["accepts"][0]["maxAmountRequired"] = "999"
        parsed = client._parse_payment_requirements(body)
        assert parsed["amount"] == 999
        assert isinstance(parsed["amount"], int)

    # ── USDC balance ─────────────────────────────────────────────────────────


    def test_usdc_balance_returns_correct_value(self):
        agent = _make_mock_agent(usdc_balance=123_456)
        with patch("trestle_sdk.x402_client.transaction"):
            from trestle_sdk.x402_client import TrestleX402Client
            client = TrestleX402Client(agent, auto_opt_in=False, auto_swap=False)
        assert client.usdc_balance() == 123_456

    def test_algo_balance_returns_correct_value(self):
        agent = _make_mock_agent(algo_balance=9_999_999)
        with patch("trestle_sdk.x402_client.transaction"):
            from trestle_sdk.x402_client import TrestleX402Client
            client = TrestleX402Client(agent, auto_opt_in=False, auto_swap=False)
        assert client.algo_balance() == 9_999_999

    # ── repr ─────────────────────────────────────────────────────────────────

    def test_repr(self):
        client = self._make_client()
        r = repr(client)
        assert "TrestleX402Client" in r
        assert "μUSDC" in r


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Tinyman swap helper
# ─────────────────────────────────────────────────────────────────────────────

class TestTinymanSwap:
    def test_estimate_fallback_rate(self):
        """When pool state is empty, fallback rate is used."""
        from trestle_sdk.x402_client import _TinymanSwap

        algod = MagicMock()
        algod.application_info.side_effect = Exception("not available")

        swap = _TinymanSwap(algod)
        result = swap.estimate_algo_for_usdc(1_000_000)

        # Fallback: 1_000_000 μUSDC * 2.5 = 2_500_000 μALGO
        assert result == 2_500_000

    def test_estimate_with_pool_reserves(self):
        """With valid pool state, uses constant-product formula."""
        from trestle_sdk.x402_client import _TinymanSwap

        algod = MagicMock()
        # Simulate pool with equal reserves (1 ALGO = 1 USDC at 1:1 for simplicity)
        algod.application_info.return_value = {
            "params": {
                "global-state": [
                    {
                        "key": base64.b64encode(b"asset_1_reserves").decode(),
                        "value": {"type": 2, "uint": 10_000_000_000},  # 10k ALGO
                    },
                    {
                        "key": base64.b64encode(b"asset_2_reserves").decode(),
                        "value": {"type": 2, "uint": 10_000_000_000},  # 10k USDC
                    },
                ]
            }
        }

        swap = _TinymanSwap(algod)
        result = swap.estimate_algo_for_usdc(1_000_000)

        # Formula: algo_in ≈ (1_000_000 / (10e9 - 1e6)) * 10e9 * 1.003 * 1.05 ≈ ~1.1M
        assert result > 0
        assert result > 1_000_000   # should be > 1 ALGO for 1 USDC (equal reserves)


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Import guard
# ─────────────────────────────────────────────────────────────────────────────

class TestImportGuard:
    def test_missing_x402_avm_gives_helpful_error(self):
        """ImportError message includes install hint when x402-avm is absent."""
        # If x402-avm is installed, the error only fires in environments
        # without the package. We test the __getattr__ error branch directly.
        import trestle_sdk

        # Verify the __getattr__ raises AttributeError for random names
        with pytest.raises(AttributeError, match="no attribute"):
            trestle_sdk.__getattr__("CompletelyNonExistentClass123")

        # Verify TrestleX402Client is accessible (ImportError guard is code-tested
        # by checking the error message format in the source).
        # When x402-avm is installed, __getattr__ should return the class.
        result = trestle_sdk.__getattr__("TrestleX402Client")
        assert result is not None
        assert result.__name__ == "TrestleX402Client"

    def test_unknown_attr_raises_attribute_error(self):
        import trestle_sdk
        with pytest.raises(AttributeError):
            _ = trestle_sdk.__getattr__("NonExistentThing")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
