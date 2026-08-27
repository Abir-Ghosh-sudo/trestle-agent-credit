"""
TrestleUSDC — Standalone USDC credit contract for AI agents.

A standalone Algorand ARC-4 contract that issues USDC (Circle, ASA 10458941
on testnet / 31566704 on mainnet) credit lines to registered agents.

This contract is INDEPENDENT of the main Trestle ALGO contract.
  - Agents stake ALGO to open a USDC credit line (same tier system)
  - Draws send USDC to the calling agent OR directly to a third-party
    payee (for x402 HTTP-native payments via GoPlausible facilitator)
  - Repayments are made by returning USDC to the contract address

Compile and deploy separately from contract.py:
    puyapy contracts/trestle_usdc.py --out-dir contracts/
    python contracts/deploy_usdc.py

Local state schema:  5 × uint64, 0 × bytes
Global state schema: 4 × uint64, 0 × bytes

(Fits comfortably under the 2048-byte bytecode limit per page.)
"""

import typing

import algopy
from algopy import (
    Account,
    Asset,
    Global,
    GlobalState,
    LocalState,
    Txn,
    UInt64,
    arc4,
    gtxn,
    itxn,
    op,
)

# ──────────────────────────────────────────────────────────────────────────────
# Tier thresholds — same as main Trestle contract (payment_count gates tier)
# ──────────────────────────────────────────────────────────────────────────────

TIER_1_THRESHOLD = 10
TIER_2_THRESHOLD = 50
TIER_3_THRESHOLD = 100

# ──────────────────────────────────────────────────────────────────────────────
# Per-draw hard caps — micro-USDC (6 decimals, same USD value as ALGO caps)
# ──────────────────────────────────────────────────────────────────────────────

TIER_0_MAX_DRAW = 100_000    # $0.10
TIER_1_MAX_DRAW = 500_000    # $0.50
TIER_2_MAX_DRAW = 2_000_000  # $2.00
TIER_3_MAX_DRAW = 5_000_000  # $5.00

# ──────────────────────────────────────────────────────────────────────────────
# Daily draw caps — micro-USDC
# ──────────────────────────────────────────────────────────────────────────────

TIER_0_DAILY_CAP = 500_000     # $0.50
TIER_1_DAILY_CAP = 2_000_000   # $2.00
TIER_2_DAILY_CAP = 10_000_000  # $10.00
TIER_3_DAILY_CAP = 25_000_000  # $25.00

# ──────────────────────────────────────────────────────────────────────────────
# APR in basis points (1 bps = 0.01%).  Lower tier → higher APR.
# ──────────────────────────────────────────────────────────────────────────────

TIER_0_APR_BPS = 2400  # 24%
TIER_1_APR_BPS = 1600  # 16%
TIER_2_APR_BPS = 900   # 9%
TIER_3_APR_BPS = 400   # 4%

# ──────────────────────────────────────────────────────────────────────────────
# Time constants (1 round ≈ 1 second on Algorand)
# ──────────────────────────────────────────────────────────────────────────────

DAY_IN_ROUNDS   = 86_400
ROUNDS_PER_YEAR = 31_536_000


# ──────────────────────────────────────────────────────────────────────────────
# ARC-4 Event Structs
# ──────────────────────────────────────────────────────────────────────────────


class UsdcDrawn(arc4.Struct):
    agent:       arc4.Address
    amount:      arc4.UInt64
    interest:    arc4.UInt64
    outstanding: arc4.UInt64


class UsdcX402Paid(arc4.Struct):
    """Emitted when draw_and_pay() sends USDC directly to a payee."""
    agent:       arc4.Address
    payee:       arc4.Address
    amount:      arc4.UInt64
    outstanding: arc4.UInt64


class UsdcRepaid(arc4.Struct):
    agent:       arc4.Address
    amount:      arc4.UInt64
    outstanding: arc4.UInt64


class AgentRegistered(arc4.Struct):
    agent: arc4.Address
    stake: arc4.UInt64


class UsdcPaymentRecorded(arc4.Struct):
    agent: arc4.Address
    amount: arc4.UInt64
    tier: arc4.UInt64


# ──────────────────────────────────────────────────────────────────────────────
# Contract
# ──────────────────────────────────────────────────────────────────────────────


class TrestleUSDC(arc4.ARC4Contract):
    """
    Standalone USDC credit contract.

    Global state schema: 4 × uint64
      usdc_asa_id, usdc_treasury_balance, skip_attestation, total_agents

    Local state schema: 5 × uint64
      stake_amount, payment_count, usdc_outstanding, daily_drawn, day_start_round
    """

    # ── Global State ──
    usdc_asa_id:           GlobalState[UInt64]
    usdc_treasury_balance: GlobalState[UInt64]
    skip_attestation:      GlobalState[UInt64]  # 1 = demo mode
    total_agents:          GlobalState[UInt64]

    # ── Local State (per opted-in agent) ──
    stake_amount:    LocalState[UInt64]
    payment_count:   LocalState[UInt64]
    usdc_outstanding: LocalState[UInt64]
    daily_drawn:     LocalState[UInt64]
    day_start_round: LocalState[UInt64]

    def __init__(self) -> None:
        self.usdc_asa_id           = GlobalState(UInt64(0))
        self.usdc_treasury_balance = GlobalState(UInt64(0))
        self.skip_attestation      = GlobalState(UInt64(1))  # demo by default
        self.total_agents          = GlobalState(UInt64(0))

        self.stake_amount    = LocalState(UInt64)
        self.payment_count   = LocalState(UInt64)
        self.usdc_outstanding = LocalState(UInt64)
        self.daily_drawn     = LocalState(UInt64)
        self.day_start_round = LocalState(UInt64)

    # ──────────────────────────────────────────────────────────────────────────
    # Bare method — Opt-In
    # ──────────────────────────────────────────────────────────────────────────

    @arc4.baremethod(allow_actions=["OptIn"])
    def opt_in(self) -> None:
        """Initialise all 5 local state slots to zero."""
        self.stake_amount[Txn.sender]    = UInt64(0)
        self.payment_count[Txn.sender]   = UInt64(0)
        self.usdc_outstanding[Txn.sender] = UInt64(0)
        self.daily_drawn[Txn.sender]     = UInt64(0)
        self.day_start_round[Txn.sender] = UInt64(0)

    # ──────────────────────────────────────────────────────────────────────────
    # ABI Method 1 — register
    # ──────────────────────────────────────────────────────────────────────────

    @arc4.abimethod
    def register(self, pay: gtxn.PaymentTransaction) -> None:
        """
        Stake ALGO (≥ 1 ALGO) to open a USDC credit line.

        Preconditions:
          - pay.receiver == application address
          - pay.amount >= 1_000_000 (1 ALGO)
          - stake_amount[sender] == 0 (not already registered)

        Mutates:
          - stake_amount[sender] = pay.amount
          - total_agents += 1
        """
        assert (
            pay.receiver == Global.current_application_address
        ), "Payment must be to application"
        assert pay.amount >= UInt64(1_000_000), "Minimum stake is 1 ALGO"
        assert (
            self.stake_amount[Txn.sender] == UInt64(0)
        ), "Already registered"

        self.stake_amount[Txn.sender]     = pay.amount
        self.payment_count[Txn.sender]    = UInt64(0)
        self.usdc_outstanding[Txn.sender] = UInt64(0)
        self.daily_drawn[Txn.sender]      = UInt64(0)
        self.day_start_round[Txn.sender]  = op.Global.round
        self.total_agents.value          += UInt64(1)

        arc4.emit(
            AgentRegistered(
                agent=arc4.Address(Txn.sender),
                stake=arc4.UInt64(pay.amount),
            )
        )

    # ──────────────────────────────────────────────────────────────────────────
    # ABI Method 2 — configure_usdc  (creator-only, one-time)
    # ──────────────────────────────────────────────────────────────────────────

    @arc4.abimethod
    def configure_usdc(self, usdc_asset: Asset) -> None:
        """
        Opt the contract into the USDC ASA and store its ID.

        Must be called once by the creator before any draws are possible.
        Fund the contract with an extra 0.2 ALGO for the ASA opt-in MBR
        before calling this method.

        Preconditions:
          - Txn.sender == Global.creator_address
          - usdc_asa_id == 0 (not yet configured)

        Mutates:
          - usdc_asa_id = usdc_asset.id
          - inner AssetTransfer opt-in (0 amount, self-to-self)
        """
        assert (
            Txn.sender == Global.creator_address
        ), "Only creator"
        assert (
            self.usdc_asa_id.value == UInt64(0)
        ), "Already configured"

        itxn.AssetTransfer(
            xfer_asset=usdc_asset.id,
            asset_receiver=Global.current_application_address,
            asset_amount=UInt64(0),
            fee=Global.min_txn_fee,
        ).submit()

        self.usdc_asa_id.value = usdc_asset.id

    # ──────────────────────────────────────────────────────────────────────────
    # ABI Method 3 — seed_treasury  (creator-only)
    # ──────────────────────────────────────────────────────────────────────────

    @arc4.abimethod
    def seed_treasury(self, axfer: gtxn.AssetTransferTransaction) -> None:
        """
        Fund the USDC treasury so agents can draw from it.

        Open to any caller — this allows the auto-swap flow where an agent
        swaps ALGO→USDC via Tinyman and immediately seeds the treasury
        in the same atomic transaction group as their draw.

        Preconditions:
          - axfer.xfer_asset.id == usdc_asa_id
          - axfer.asset_receiver == application address
          - axfer.asset_amount > 0
        """
        assert (
            self.usdc_asa_id.value > UInt64(0)
        ), "Call configure_usdc first"
        assert (
            axfer.xfer_asset.id == self.usdc_asa_id.value
        ), "Wrong ASA"
        assert (
            axfer.asset_receiver == Global.current_application_address
        ), "Must send to contract"
        assert axfer.asset_amount > UInt64(0), "Amount must be > 0"

        self.usdc_treasury_balance.value += axfer.asset_amount

    # ──────────────────────────────────────────────────────────────────────────
    # ABI Method 4 — draw_usdc
    # Draws USDC credit and sends it to Txn.sender.
    # ──────────────────────────────────────────────────────────────────────────

    @arc4.abimethod
    def draw_usdc(
        self,
        amount: arc4.UInt64,
        attestation_hash: arc4.StaticArray[arc4.Byte, typing.Literal[32]],
    ) -> None:
        """
        Draw undercollateralised USDC credit.
        Sends `amount` micro-USDC to Txn.sender via inner AssetTransfer.

        Interest is calculated at the agent's tier APR for one day.
        Total repayable = amount + interest is tracked in usdc_outstanding.

        Preconditions:
          - usdc_asa_id > 0 (contract configured)
          - stake_amount[sender] > 0 (registered)
          - usdc_outstanding[sender] == 0 (no existing USDC debt)
          - amount <= tier per-draw cap
          - daily_drawn[sender] + amount <= tier daily cap
          - usdc_treasury_balance >= amount
        """
        assert (
            self.usdc_asa_id.value > UInt64(0)
        ), "USDC not configured"
        assert (
            self.stake_amount[Txn.sender] > UInt64(0)
        ), "Not registered"
        assert (
            self.usdc_outstanding[Txn.sender] == UInt64(0)
        ), "Outstanding USDC debt — repay first"

        draw_amt = amount.native
        current_round = op.Global.round

        # ── Attestation (skip in demo mode) ──
        if self.skip_attestation.value == UInt64(0):
            expected = op.sha256(
                Txn.sender.bytes
                + amount.bytes
                + op.itob(current_round)
            )
            assert attestation_hash.bytes == expected, "Invalid attestation"

        # ── Daily window reset ──
        elapsed = current_round - self.day_start_round[Txn.sender]
        if elapsed >= DAY_IN_ROUNDS:
            self.daily_drawn[Txn.sender]     = UInt64(0)
            self.day_start_round[Txn.sender] = current_round

        tier = self._get_tier(self.payment_count[Txn.sender])

        # ── Per-draw cap ──
        if tier == UInt64(3):
            assert draw_amt <= TIER_3_MAX_DRAW, "Exceeds draw cap"
        elif tier == UInt64(2):
            assert draw_amt <= TIER_2_MAX_DRAW, "Exceeds draw cap"
        elif tier == UInt64(1):
            assert draw_amt <= TIER_1_MAX_DRAW, "Exceeds draw cap"
        else:
            assert draw_amt <= TIER_0_MAX_DRAW, "Exceeds draw cap"

        # ── Daily cap ──
        new_daily = self.daily_drawn[Txn.sender] + draw_amt
        if tier == UInt64(3):
            assert new_daily <= TIER_3_DAILY_CAP, "Exceeds daily cap"
        elif tier == UInt64(2):
            assert new_daily <= TIER_2_DAILY_CAP, "Exceeds daily cap"
        elif tier == UInt64(1):
            assert new_daily <= TIER_1_DAILY_CAP, "Exceeds daily cap"
        else:
            assert new_daily <= TIER_0_DAILY_CAP, "Exceeds daily cap"

        assert (
            self.usdc_treasury_balance.value >= draw_amt
        ), "Insufficient treasury"

        # ── Interest ──
        if tier == UInt64(3):
            apr = UInt64(TIER_3_APR_BPS)
        elif tier == UInt64(2):
            apr = UInt64(TIER_2_APR_BPS)
        elif tier == UInt64(1):
            apr = UInt64(TIER_1_APR_BPS)
        else:
            apr = UInt64(TIER_0_APR_BPS)

        interest = (draw_amt * apr * DAY_IN_ROUNDS) // (
            UInt64(10_000) * ROUNDS_PER_YEAR
        )

        # ── Inner transfer: send USDC to agent ──
        itxn.AssetTransfer(
            xfer_asset=self.usdc_asa_id.value,
            asset_receiver=Txn.sender,
            asset_amount=draw_amt,
            fee=Global.min_txn_fee,
        ).submit()

        # ── Update state ──
        self.daily_drawn[Txn.sender]      = new_daily
        self.usdc_outstanding[Txn.sender] = draw_amt + interest
        self.usdc_treasury_balance.value -= draw_amt

        arc4.emit(
            UsdcDrawn(
                agent=arc4.Address(Txn.sender),
                amount=arc4.UInt64(draw_amt),
                interest=arc4.UInt64(interest),
                outstanding=arc4.UInt64(draw_amt + interest),
            )
        )

    # ──────────────────────────────────────────────────────────────────────────
    # ABI Method 5 — draw_and_pay  (x402 payment hook)
    #
    # Draws USDC credit AND immediately sends it to a third-party payee.
    # This is the x402 HTTP-native payment method: instead of receiving
    # USDC yourself and then sending it, the contract atomically draws
    # credit and forwards USDC to the merchant/payee in one transaction.
    #
    # The GoPlausible facilitator expects an axfer from the agent's wallet
    # to the merchant. This method emits that axfer as an inner transaction.
    # ──────────────────────────────────────────────────────────────────────────

    @arc4.abimethod
    def draw_and_pay(
        self,
        amount: arc4.UInt64,
        payee: arc4.Address,
        attestation_hash: arc4.StaticArray[arc4.Byte, typing.Literal[32]],
    ) -> None:
        """
        Draw USDC credit and send it directly to `payee` in one atomic step.

        This is the x402 payment primitive: the contract acts as the USDC
        sender, forwarding `amount` micro-USDC from the treasury to `payee`
        while charging the debt to Txn.sender's credit line.

        Preconditions:
          - All the same as draw_usdc
          - payee must be a valid, opted-in Algorand address

        x402 flow:
          1. Agent calls draw_and_pay(amount, merchant_address, hash)
          2. Contract forwards USDC to merchant via inner AssetTransfer
          3. Agent has usdc_outstanding += amount + interest
          4. Agent repays later via repay_usdc()
        """
        assert (
            self.usdc_asa_id.value > UInt64(0)
        ), "USDC not configured"
        assert (
            self.stake_amount[Txn.sender] > UInt64(0)
        ), "Not registered"
        assert (
            self.usdc_outstanding[Txn.sender] == UInt64(0)
        ), "Outstanding USDC debt — repay first"

        draw_amt = amount.native
        current_round = op.Global.round

        # ── Attestation ──
        if self.skip_attestation.value == UInt64(0):
            expected = op.sha256(
                Txn.sender.bytes
                + amount.bytes
                + op.itob(current_round)
            )
            assert attestation_hash.bytes == expected, "Invalid attestation"

        # ── Daily window reset ──
        elapsed = current_round - self.day_start_round[Txn.sender]
        if elapsed >= DAY_IN_ROUNDS:
            self.daily_drawn[Txn.sender]     = UInt64(0)
            self.day_start_round[Txn.sender] = current_round

        tier = self._get_tier(self.payment_count[Txn.sender])

        # ── Per-draw cap ──
        if tier == UInt64(3):
            assert draw_amt <= TIER_3_MAX_DRAW, "Exceeds draw cap"
        elif tier == UInt64(2):
            assert draw_amt <= TIER_2_MAX_DRAW, "Exceeds draw cap"
        elif tier == UInt64(1):
            assert draw_amt <= TIER_1_MAX_DRAW, "Exceeds draw cap"
        else:
            assert draw_amt <= TIER_0_MAX_DRAW, "Exceeds draw cap"

        # ── Daily cap ──
        new_daily = self.daily_drawn[Txn.sender] + draw_amt
        if tier == UInt64(3):
            assert new_daily <= TIER_3_DAILY_CAP, "Exceeds daily cap"
        elif tier == UInt64(2):
            assert new_daily <= TIER_2_DAILY_CAP, "Exceeds daily cap"
        elif tier == UInt64(1):
            assert new_daily <= TIER_1_DAILY_CAP, "Exceeds daily cap"
        else:
            assert new_daily <= TIER_0_DAILY_CAP, "Exceeds daily cap"

        assert (
            self.usdc_treasury_balance.value >= draw_amt
        ), "Insufficient treasury"

        # ── Interest ──
        if tier == UInt64(3):
            apr = UInt64(TIER_3_APR_BPS)
        elif tier == UInt64(2):
            apr = UInt64(TIER_2_APR_BPS)
        elif tier == UInt64(1):
            apr = UInt64(TIER_1_APR_BPS)
        else:
            apr = UInt64(TIER_0_APR_BPS)

        interest = (draw_amt * apr * DAY_IN_ROUNDS) // (
            UInt64(10_000) * ROUNDS_PER_YEAR
        )

        # ── Inner transfer: send USDC to PAYEE (not sender) ──
        itxn.AssetTransfer(
            xfer_asset=self.usdc_asa_id.value,
            asset_receiver=payee.native,
            asset_amount=draw_amt,
            fee=Global.min_txn_fee,
        ).submit()

        # ── Update state ──
        self.daily_drawn[Txn.sender]      = new_daily
        self.usdc_outstanding[Txn.sender] = draw_amt + interest
        self.usdc_treasury_balance.value -= draw_amt

        arc4.emit(
            UsdcX402Paid(
                agent=arc4.Address(Txn.sender),
                payee=payee,
                amount=arc4.UInt64(draw_amt),
                outstanding=arc4.UInt64(draw_amt + interest),
            )
        )

    # ──────────────────────────────────────────────────────────────────────────
    # ABI Method 6 — repay_usdc
    # ──────────────────────────────────────────────────────────────────────────

    @arc4.abimethod
    def repay_usdc(self, axfer: gtxn.AssetTransferTransaction) -> None:
        """
        Repay outstanding USDC credit by sending USDC to the contract.

        Preconditions:
          - axfer.xfer_asset.id == usdc_asa_id
          - axfer.asset_receiver == application address
          - axfer.asset_amount > 0

        Mutates:
          - usdc_outstanding[sender] -= repay_amt (floor 0)
          - usdc_treasury_balance += repay_amt
          - payment_count[sender] += 1 (if debt fully cleared)
        """
        assert (
            axfer.xfer_asset.id == self.usdc_asa_id.value
        ), "Wrong ASA"
        assert (
            axfer.asset_receiver == Global.current_application_address
        ), "Must send to contract"
        assert axfer.asset_amount > UInt64(0), "Amount must be > 0"

        repay_amt = axfer.asset_amount
        current_outstanding = self.usdc_outstanding[Txn.sender]

        if repay_amt >= current_outstanding:
            self.usdc_outstanding[Txn.sender] = UInt64(0)
            # Increment payment_count when debt is fully cleared
            self.payment_count[Txn.sender] += UInt64(1)
        else:
            self.usdc_outstanding[Txn.sender] = current_outstanding - repay_amt

        self.usdc_treasury_balance.value += repay_amt

        arc4.emit(
            UsdcRepaid(
                agent=arc4.Address(Txn.sender),
                amount=arc4.UInt64(repay_amt),
                outstanding=arc4.UInt64(self.usdc_outstanding[Txn.sender]),
            )
        )

    # ──────────────────────────────────────────────────────────────────────────
    # ABI Method 6b — record_payment
    # ──────────────────────────────────────────────────────────────────────────

    @arc4.abimethod
    def record_payment(self, amount: arc4.UInt64) -> arc4.UInt64:
        """
        Record a USDC payment to build reputation.

        Preconditions:
          - Agent is registered (stake_amount > 0)

        Mutates:
          - payment_count[sender] += 1

        Emits: UsdcPaymentRecorded
        Returns: current tier number (0-3) as arc4.UInt64
        """
        assert (
            self.stake_amount[Txn.sender] > UInt64(0)
        ), "Not registered"

        self.payment_count[Txn.sender] += UInt64(1)
        tier = self._get_tier(self.payment_count[Txn.sender])

        arc4.emit(
            UsdcPaymentRecorded(
                agent=arc4.Address(Txn.sender),
                amount=amount,
                tier=arc4.UInt64(tier),
            )
        )
        return arc4.UInt64(tier)

    # ──────────────────────────────────────────────────────────────────────────
    # ABI Method 7 — get_position (readonly)
    # ──────────────────────────────────────────────────────────────────────────

    @arc4.abimethod(readonly=True)
    def get_position(
        self, agent: arc4.Address
    ) -> tuple[
        arc4.UInt64,  # usdc_outstanding
        arc4.UInt64,  # usdc_treasury_balance
        arc4.UInt64,  # payment_count
        arc4.UInt64,  # stake_amount
        arc4.UInt64,  # tier (0-3)
    ]:
        """
        Read an agent's full USDC position.

        Returns (all arc4.UInt64):
          0: usdc_outstanding      — micro-USDC owed
          1: usdc_treasury_balance — total micro-USDC in treasury
          2: payment_count         — total completed repayments
          3: stake_amount          — ALGO staked (microALGO)
          4: tier                  — current tier (0–3)
        """
        addr = agent.native
        tier = self._get_tier(self.payment_count[addr])
        return (
            arc4.UInt64(self.usdc_outstanding[addr]),
            arc4.UInt64(self.usdc_treasury_balance.value),
            arc4.UInt64(self.payment_count[addr]),
            arc4.UInt64(self.stake_amount[addr]),
            arc4.UInt64(tier),
        )

    # ──────────────────────────────────────────────────────────────────────────
    # ABI Method 8 — enable_attestation  (creator-only)
    # ──────────────────────────────────────────────────────────────────────────

    @arc4.abimethod
    def enable_attestation(self) -> None:
        """Switch from demo-bypass to production attestation mode."""
        assert (
            Txn.sender == Global.creator_address
        ), "Only creator"
        self.skip_attestation.value = UInt64(0)

    # ──────────────────────────────────────────────────────────────────────────
    # Private subroutine — _get_tier
    # ──────────────────────────────────────────────────────────────────────────

    @algopy.subroutine
    def _get_tier(self, payment_count: UInt64) -> UInt64:
        """Derive tier (0–3) from payment_count."""
        if payment_count >= TIER_3_THRESHOLD:
            return UInt64(3)
        elif payment_count >= TIER_2_THRESHOLD:
            return UInt64(2)
        elif payment_count >= TIER_1_THRESHOLD:
            return UInt64(1)
        else:
            return UInt64(0)


## ─────────────────────────────────────────────────────────────────────────────
## DEPLOYMENT CHECKLIST
## ─────────────────────────────────────────────────────────────────────────────
# TrestleUSDC local state:  5 × uint64, 0 × bytes
# TrestleUSDC global state: 4 × uint64, 0 × bytes
#
# 1. puyapy contracts/trestle_usdc.py --out-dir contracts/
#    → TrestleUSDC.approval.teal, TrestleUSDC.clear.teal, TrestleUSDC.arc56.json
#
# 2. python contracts/deploy_usdc.py
#    → Creates app, funds with 10 ALGO (for MBR and agent stakes)
#    → Opts contract into USDC ASA 10458941
#    → Seeds USDC treasury with whatever is in the deployer wallet
#
# 3. Update frontend/src/utils/contract.js with the new USDC_APP_ID
