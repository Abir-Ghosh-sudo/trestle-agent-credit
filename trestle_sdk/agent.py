"""
agent.py — TrestleCreditAgent: the one-liner public interface for the Trestle SDK.

Wraps RiskOracle (Venice AI Risk Skill) + algosdk chain calls into a single draw()
method.  The Venice AI risk assessment runs internally on every draw() call —
the developer never controls it or bypasses it.

Environment variables:
    TRESTLE_ENV:   "production" or "mainnet" → demo_mode=False (safe default)
                  anything else             → demo_mode=True  (testnet/demo)
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Literal

from .oracle import RiskOracle, RiskDecision
from .exceptions import TrestleCreditDenied, TrestleCreditError
from .chain import (
    make_algod_client,
    address_from_mnemonic,
    private_key_from_mnemonic,
    get_app_address,
    get_position,
    do_draw,
    do_repay,
    do_record_payment,
    get_usdc_position,
    do_draw_usdc,
    do_repay_usdc,
    ensure_usdc_opted_in,
    AccountTransactionSigner,
)

logger = logging.getLogger(__name__)


# ── ProtocolConfig ─────────────────────────────────────────────────────────────


@dataclass
class ProtocolConfig:
    """Protocol-level configuration for TrestleCreditAgent.

    Controls whether attestation hashes are real (production) or zero-bytes
    (demo/testnet).  The safest workflow is to leave ``demo_mode`` at its
    default and set ``TRESTLE_ENV=production`` in your deployment environment.

    Attributes:
        network:    "testnet" or "mainnet".  Controls which algod URL is
                    used by default.
        demo_mode:  If True, the RiskOracle sends ``bytes(32)`` as the
                    attestation hash so the contract skips on-chain
                    verification.  NEVER use True in production.
        algod_url:  Algod REST endpoint.  Defaults to Algonode testnet.

    Example::

        # Explicit production config
        cfg = ProtocolConfig(network="mainnet", demo_mode=False,
                             algod_url="https://mainnet-api.algonode.cloud")
        agent = TrestleCreditAgent(mnemonic_phrase="...", app_id=..., config=cfg)

        # Let env-var drive the config (recommended in CI/CD)
        #   TRESTLE_ENV=production python myapp.py
        agent = TrestleCreditAgent(mnemonic_phrase="...", app_id=...)
    """

    network: Literal["testnet", "mainnet"] = "testnet"
    demo_mode: bool = True
    algod_url: str = "https://testnet-api.algonode.cloud"

    @classmethod
    def from_env(cls) -> "ProtocolConfig":
        """Build a ProtocolConfig from environment variables.

        Reads ``TRESTLE_ENV`` (default: "demo").
        - "production" / "mainnet" → demo_mode=False, mainnet algod URL
        - anything else            → demo_mode=True,  testnet algod URL
        """
        env = os.environ.get("TRESTLE_ENV", "demo").lower()
        is_production = env in ("production", "mainnet")
        return cls(
            network="mainnet" if is_production else "testnet",
            demo_mode=not is_production,
            algod_url=(
                "https://mainnet-api.algonode.cloud"
                if is_production
                else "https://testnet-api.algonode.cloud"
            ),
        )


# ── TrestleCreditAgent ──────────────────────────────────────────────────────────


# USDC ASA IDs for reference. Pass the correct one to draw_usdc().
USDC_ASA_ID_TESTNET: int = 10_458_941
USDC_ASA_ID_MAINNET: int = 31_566_704


class TrestleCreditAgent:
    """One-liner credit interface for the Trestle protocol.

    Wraps :class:`~trestle_sdk.oracle.RiskOracle` (the Claude Skill) and all
    algosdk chain calls into a single :meth:`draw` method.  The Claude risk
    assessment runs internally on every :meth:`draw` call — the developer does
    not control it or bypass it.

    Configuration is driven by :class:`ProtocolConfig`.  The simplest safe
    deployment pattern is to set ``TRESTLE_ENV=production`` in your environment
    and pass only ``mnemonic_phrase`` and ``app_id``::

        agent = TrestleCreditAgent(
            mnemonic_phrase=os.environ["AGENT_MNEMONIC"],
            app_id=int(os.environ["TRESTLE_APP_ID"]),
        )
        # One line — Claude Skill runs internally, on-chain draw follows
        result = agent.draw(
            amount_microalgo=50_000,
            task_description="Fetching ETH/USD price from CoinGecko API",
            expected_return_microalgo=80_000,
            estimated_task_rounds=120,
        )
        # Repay after task completes
        agent.repay(result["total_repayable"])

        # Draw USDC credit (same oracle, same tier, different denomination)
        result_usdc = agent.draw_usdc(
            amount_microusdc=100_000,  # $0.10 USDC
            task_description="Fetch ETH/USD price from CoinGecko",
            expected_return_microusdc=150_000,
        )
        agent.repay_usdc(result_usdc["total_repayable_usdc"])
    """

    def __init__(
        self,
        mnemonic_phrase: str,
        app_id: int,
        algod_url: str = "https://testnet-api.algonode.cloud",
        demo_mode: bool | None = None,
        config: ProtocolConfig | None = None,
        usdc_app_id: int | None = None,
    ) -> None:
        """Initialise the credit agent.

        Args:
            mnemonic_phrase:
                25-word Algorand mnemonic for the agent wallet.
            app_id:
                Trestle contract application ID on testnet (<YOUR_APP_ID>) or
                mainnet.
            algod_url:
                Algod REST endpoint.  Ignored if ``config`` is supplied.
                Defaults to Algonode testnet.
            demo_mode:
                **Deprecated** — prefer ``config=`` or ``TRESTLE_ENV``.
                When ``True``, passes ``bytes(32)`` as the attestation hash so
                the contract skips on-chain verification.  Set to ``False`` for
                production deployments.  If ``None`` (default), the value is
                read from ``TRESTLE_ENV``.
            config:
                Optional :class:`ProtocolConfig`.  If supplied, ``algod_url``
                and ``demo_mode`` arguments are ignored.
        """
        # ── Resolve ProtocolConfig ─────────────────────────────────────────
        if config is not None:
            self.config = config
        else:
            # Build from env, then override with explicit demo_mode if given
            self.config = ProtocolConfig.from_env()
            if demo_mode is not None:
                self.config = ProtocolConfig(
                    network=self.config.network,
                    demo_mode=demo_mode,
                    algod_url=algod_url,
                )
            else:
                # algod_url arg may differ from env default
                self.config = ProtocolConfig(
                    network=self.config.network,
                    demo_mode=self.config.demo_mode,
                    algod_url=algod_url,
                )

        # ── Safety warning ─────────────────────────────────────────────────
        if self.config.demo_mode:
            logger.warning(
                "TrestleCreditAgent: DEMO MODE ACTIVE — attestation hashes are "
                "zero-bytes. Do NOT use demo_mode=True in production. "
                "Set TRESTLE_ENV=production to disable."
            )

        # ── Wallet + chain ──────────────────────────────────────────────────
        self.app_id = app_id
        self.usdc_app_id = usdc_app_id if usdc_app_id is not None else app_id
        self.private_key = private_key_from_mnemonic(mnemonic_phrase)
        self.address = address_from_mnemonic(mnemonic_phrase)
        self.algod_client = make_algod_client(self.config.algod_url)
        self.signer = AccountTransactionSigner(self.private_key)
        self.oracle = RiskOracle(
            algod_client=self.algod_client,
            demo_mode=self.config.demo_mode,
        )

    # ── Read ──────────────────────────────────────────────────────────────────

    def get_position(self) -> dict:
        """Read the agent's current on-chain credit position.

        Returns:
            Dict with keys: ``stake_amount``, ``payment_count``,
            ``tier_max_draw``, ``outstanding``, ``is_defaulted``, ``tier``,
            ``apr_bps``, ``daily_drawn``, ``repay_by_round`` — all ``int``.
        """
        return get_position(
            self.algod_client, self.app_id, self.address, self.signer
        )

    # ── Write ─────────────────────────────────────────────────────────────────

    def draw(
        self,
        amount_microalgo: int,
        task_description: str,
        expected_return_microalgo: int,
        estimated_task_rounds: int = 300,
    ) -> dict:
        """Run the risk oracle then draw credit from the protocol.

        Internal steps (all hidden from the caller):

        1. :meth:`get_position` — fetch ``payment_count`` and ``outstanding``
           from on-chain state.
        2. :meth:`~trestle_sdk.oracle.RiskOracle.evaluate` — call Claude and
           evaluate four immutable criteria.
        3. If approved: :func:`~trestle_sdk.chain.do_draw` — submit the ATC
           transaction.
        4. Return summary dict.

        Args:
            amount_microalgo: How much credit to draw in microALGO.
            task_description: Plain-English description of what the agent will
                do with the credit.  Claude evaluates the risk level from this.
            expected_return_microalgo: Agent's expected revenue from completing
                the task, in microALGO.  Must exceed ``amount + interest``.
            estimated_task_rounds: How many Algorand rounds the task will take.
                Must be < 86,400 (one day) to pass criterion 2.

        Returns:
            Dict with keys:
                ``txid``, ``amount_microalgo``, ``interest_microalgo``,
                ``total_repayable``, ``tier``, ``tier_name``, ``apr_bps``,
                ``risk_summary``.

        Raises:
            TrestleCreditDenied: The risk oracle denied the request.  The
                on-chain ``draw()`` is never called.
            TrestleCreditError: A chain or API failure occurred.
        """
        position = self.get_position()

        decision: RiskDecision = self.oracle.evaluate(
            agent_address=self.address,
            amount_microalgo=amount_microalgo,
            payment_count=int(position["payment_count"]),
            outstanding_microalgo=int(position["outstanding"]),
            task_description=task_description,
            expected_return_microalgo=expected_return_microalgo,
            estimated_task_rounds=estimated_task_rounds,
        )

        txid = do_draw(
            algod_client=self.algod_client,
            app_id=self.app_id,
            agent_address=self.address,
            private_key=self.private_key,
            amount_microalgo=amount_microalgo,
            attestation_hash=decision.attestation_hash,
        )

        return {
            "txid": txid,
            "amount_microalgo": amount_microalgo,
            "interest_microalgo": decision.interest_microalgo,
            "total_repayable": decision.total_repayable,
            "tier": decision.tier,
            "tier_name": decision.tier_name,
            "apr_bps": decision.apr_bps,
            "risk_summary": decision.criteria.risk_summary,
        }

    def repay(self, amount_microalgo: int) -> dict:
        """Repay outstanding credit to the protocol.

        Args:
            amount_microalgo: Amount to repay in microALGO.  Use
                ``result["total_repayable"]`` from the last draw for exact
                repayment.

        Returns:
            Dict with keys: ``txid``, ``repaid_microalgo``.
        """
        txid = do_repay(
            algod_client=self.algod_client,
            app_id=self.app_id,
            agent_address=self.address,
            private_key=self.private_key,
            amount_microalgo=amount_microalgo,
        )
        return {"txid": txid, "repaid_microalgo": amount_microalgo}

    def record_payment(self, amount_microalgo: int = 1000) -> int:
        """Record an off-chain payment to increment the payment count.

        Calling this enough times upgrades the agent's tier, unlocking
        higher draw limits and lower APR.

        Args:
            amount_microalgo: Payment amount to record in microALGO.
                Defaults to 1000 (1 milliALGO).

        Returns:
            New tier number (0–3) as returned by the contract.
        """
        return do_record_payment(
            algod_client=self.algod_client,
            app_id=self.app_id,
            agent_address=self.address,
            private_key=self.private_key,
            amount_microalgo=amount_microalgo,
        )

    # ── USDC methods ────────────────────────────────────────────────────────────────────

    def get_usdc_position(self) -> dict:
        """Read the agent's current USDC credit position.

        Returns:
            Dict with keys: ``usdc_outstanding``, ``usdc_treasury_balance``,
            ``usdc_asa_id``, ``usdc_tier_max_draw`` — all ``int``.
        """
        return get_usdc_position(
            self.algod_client, self.usdc_app_id, self.address, self.signer
        )

    def draw_usdc(
        self,
        amount_microusdc: int,
        task_description: str,
        expected_return_microusdc: int,
        estimated_task_rounds: int = 300,
        usdc_asa_id: int = USDC_ASA_ID_TESTNET,
        auto_optin: bool = True,
    ) -> dict:
        """Run the risk oracle then draw USDC credit from the protocol.

        Identical flow to draw() but in USDC denomination:
          1. get_usdc_position() — fetch usdc_outstanding
          2. get_position()      — fetch payment_count and outstanding (ALGO)
          3. oracle.evaluate()   — same 4 criteria, USDC amounts
          4. ensure_usdc_opted_in() — opt agent into USDC ASA if auto_optin=True
          5. do_draw_usdc()      — submit the ATC transaction

        Args:
            amount_microusdc: How much USDC credit to draw in micro-USDC.
            task_description: Plain-English description for oracle risk evaluation.
            expected_return_microusdc: Agent's expected revenue in micro-USDC.
                Must exceed amount + interest to pass criterion 1.
            estimated_task_rounds: How many Algorand rounds the task will take.
                Must be < 86,400 to pass criterion 2.
            usdc_asa_id: USDC ASA ID. Defaults to testnet (10_458_941).
            auto_optin: If True, automatically opt the agent into the USDC ASA
                before drawing if they haven't already. Requires one extra txn.

        Returns:
            Dict with keys:
                ``txid``, ``amount_microusdc``, ``interest_microusdc``,
                ``total_repayable_usdc``, ``tier``, ``tier_name``,
                ``apr_bps``, ``risk_summary``, ``usdc_asa_id``.

        Raises:
            TrestleCreditDenied: Oracle denied the request.
            TrestleCreditError: Chain or API failure.
        """
        # Read both positions to check cross-denomination stacking
        usdc_pos  = self.get_usdc_position()
        algo_pos  = self.get_position()

        # The oracle evaluates against USDC amounts but same 4 criteria
        decision: RiskDecision = self.oracle.evaluate(
            agent_address=self.address,
            amount_microalgo=amount_microusdc,          # oracle uses generic "amount"
            payment_count=int(algo_pos["payment_count"]),
            outstanding_microalgo=int(usdc_pos["usdc_outstanding"]),  # USDC outstanding
            task_description=f"[USDC draw] {task_description}",
            expected_return_microalgo=expected_return_microusdc,
            estimated_task_rounds=estimated_task_rounds,
        )

        # Ensure agent is opted into USDC ASA before receiving the draw
        if auto_optin:
            ensure_usdc_opted_in(
                self.algod_client, self.address, self.private_key, usdc_asa_id
            )

        txid = do_draw_usdc(
            algod_client=self.algod_client,
            app_id=self.usdc_app_id,
            agent_address=self.address,
            private_key=self.private_key,
            amount_microusdc=amount_microusdc,
            attestation_hash=decision.attestation_hash,
            usdc_asa_id=usdc_asa_id,
        )

        return {
            "txid":                  txid,
            "amount_microusdc":      amount_microusdc,
            "interest_microusdc":    decision.interest_microalgo,  # reuse field
            "total_repayable_usdc":  decision.total_repayable,
            "tier":                  decision.tier,
            "tier_name":             decision.tier_name,
            "apr_bps":               decision.apr_bps,
            "risk_summary":          decision.criteria.risk_summary,
            "usdc_asa_id":           usdc_asa_id,
        }

    def repay_usdc(
        self,
        amount_microusdc: int,
        usdc_asa_id: int = USDC_ASA_ID_TESTNET,
    ) -> dict:
        """Repay outstanding USDC credit to the protocol.

        Args:
            amount_microusdc: Amount to repay in micro-USDC. Use
                ``result["total_repayable_usdc"]`` from the last draw_usdc
                for exact repayment.
            usdc_asa_id: USDC ASA ID. Defaults to testnet (10_458_941).

        Returns:
            Dict with keys: ``txid``, ``repaid_microusdc``.
        """
        txid = do_repay_usdc(
            algod_client=self.algod_client,
            app_id=self.usdc_app_id,
            agent_address=self.address,
            private_key=self.private_key,
            amount_microusdc=amount_microusdc,
            usdc_asa_id=usdc_asa_id,
        )
        return {"txid": txid, "repaid_microusdc": amount_microusdc}

    def record_payment_usdc(self, amount_microusdc: int = 1000) -> int:
        """Record an off-chain USDC payment to increment the USDC payment count.

        Calling this enough times upgrades the agent's USDC credit tier, unlocking
        higher USDC draw limits and lower USDC APR.

        Args:
            amount_microusdc: Payment amount to record in micro-USDC.
                Defaults to 1000.

        Returns:
            New tier number (0–3) as returned by the contract.
        """
        return do_record_payment(
            algod_client=self.algod_client,
            app_id=self.usdc_app_id,
            agent_address=self.address,
            private_key=self.private_key,
            amount_microalgo=amount_microusdc,
        )
