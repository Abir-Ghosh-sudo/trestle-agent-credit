"""
Trestle — On-chain reputation credit protocol for AI agents.

Agents stake ALGO, build repayment history, and unlock undercollateralised
credit lines governed by four hardcoded tiers. Defaulters get slashed.
No human in the loop.

ARC-4 compliant. Algorand Python (Puya compiler).

Local state schema:  9 × uint64, 0 × bytes
Global state schema: 3 × uint64, 1 × bytes
"""

import typing

import algopy
from algopy import (
    Account,
    Bytes,
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
# Tier threshold constants (based on payment_count)
# ──────────────────────────────────────────────────────────────────────────────

TIER_0_THRESHOLD = 0
TIER_1_THRESHOLD = 10
TIER_2_THRESHOLD = 50
TIER_3_THRESHOLD = 100

# ──────────────────────────────────────────────────────────────────────────────
# Per-draw hard cap constants (microALGO)
# ──────────────────────────────────────────────────────────────────────────────

TIER_0_MAX_DRAW = 100_000    # $0.10
TIER_1_MAX_DRAW = 500_000    # $0.50
TIER_2_MAX_DRAW = 2_000_000  # $2.00
TIER_3_MAX_DRAW = 5_000_000  # $5.00

# ──────────────────────────────────────────────────────────────────────────────
# Daily cap constants (microALGO)
# ──────────────────────────────────────────────────────────────────────────────

TIER_0_DAILY_CAP = 500_000    # $0.50
TIER_1_DAILY_CAP = 2_000_000  # $2.00
TIER_2_DAILY_CAP = 10_000_000 # $10.00
TIER_3_DAILY_CAP = 25_000_000 # $25.00

# ──────────────────────────────────────────────────────────────────────────────
# APR basis points (interest = draw * bps * DAY_IN_ROUNDS / (10000 * ROUNDS_PER_YEAR))
# ──────────────────────────────────────────────────────────────────────────────

TIER_0_APR_BPS = 2400  # 24%
TIER_1_APR_BPS = 1600  # 16%
TIER_2_APR_BPS = 900   # 9%
TIER_3_APR_BPS = 400   # 4%

# ──────────────────────────────────────────────────────────────────────────────
# Time constants
# ──────────────────────────────────────────────────────────────────────────────

ROUNDS_PER_YEAR = 31_536_000  # ~1 round per second
DAY_IN_ROUNDS   = 86_400      # ~24 hours


# ──────────────────────────────────────────────────────────────────────────────
# ARC-4 Event Structs
# ──────────────────────────────────────────────────────────────────────────────


class AgentRegistered(arc4.Struct):
    agent: arc4.Address
    stake: arc4.UInt64


class PaymentRecorded(arc4.Struct):
    agent: arc4.Address
    amount: arc4.UInt64
    tier: arc4.UInt64


class CreditDrawn(arc4.Struct):
    agent: arc4.Address
    amount: arc4.UInt64
    interest: arc4.UInt64
    outstanding: arc4.UInt64


class Repaid(arc4.Struct):
    agent: arc4.Address
    amount: arc4.UInt64
    outstanding: arc4.UInt64


class AgentSlashed(arc4.Struct):
    agent: arc4.Address
    stake_burned: arc4.UInt64
    caller_reward: arc4.UInt64


# ──────────────────────────────────────────────────────────────────────────────
# Contract
# ──────────────────────────────────────────────────────────────────────────────


class Trestle(arc4.ARC4Contract):
    """
    On-chain reputation credit protocol for AI agents.

    Local state schema:  9 × uint64, 0 × bytes
      stake_amount, payment_count, total_repaid, outstanding,
      is_defaulted, last_payment_round, daily_drawn,
      day_start_round, repay_by_round

    Global state schema: 3 × uint64, 1 × bytes
      treasury_balance, total_agents, skip_attestation,
      protocol_signer (bytes)
    """

    # ── Global State ──
    treasury_balance:  GlobalState[UInt64]
    total_agents:      GlobalState[UInt64]
    skip_attestation:  GlobalState[UInt64]   # 1 = skip (demo mode)
    protocol_signer:   GlobalState[Account]  # stored as bytes slot

    # ── Local State (per opted-in agent) ──
    stake_amount:       LocalState[UInt64]
    payment_count:      LocalState[UInt64]
    total_repaid:       LocalState[UInt64]
    outstanding:        LocalState[UInt64]
    is_defaulted:       LocalState[UInt64]  # 1 = defaulted
    last_payment_round: LocalState[UInt64]
    daily_drawn:        LocalState[UInt64]  # total drawn in current day window
    day_start_round:    LocalState[UInt64]  # round when current day window started
    repay_by_round:     LocalState[UInt64]  # deadline: day_start_round + DAY_IN_ROUNDS

    def __init__(self) -> None:
        self.treasury_balance = GlobalState(UInt64(0))
        self.total_agents     = GlobalState(UInt64(0))
        self.skip_attestation = GlobalState(UInt64(1))  # default: bypass for demo
        self.protocol_signer  = GlobalState(Account)

        self.stake_amount       = LocalState(UInt64)
        self.payment_count      = LocalState(UInt64)
        self.total_repaid       = LocalState(UInt64)
        self.outstanding        = LocalState(UInt64)
        self.is_defaulted       = LocalState(UInt64)
        self.last_payment_round = LocalState(UInt64)
        self.daily_drawn        = LocalState(UInt64)
        self.day_start_round    = LocalState(UInt64)
        self.repay_by_round     = LocalState(UInt64)

    # ──────────────────────────────────────────────────────────────────────────
    # Bare method — Opt-In
    # ──────────────────────────────────────────────────────────────────────────

    @arc4.baremethod(allow_actions=["OptIn"])
    def opt_in(self) -> None:
        """
        Allow agents to opt in and initialise all local state slots to zero.

        Preconditions: none (any account may opt in).
        Mutates: all 9 local state slots set to 0 for Txn.sender.
        Emits: nothing.

        Puya compiles local-state reads as app_local_get_ex + assert, so
        every slot must be written before register() can safely read it.
        """
        self.stake_amount[Txn.sender]       = UInt64(0)
        self.payment_count[Txn.sender]      = UInt64(0)
        self.total_repaid[Txn.sender]       = UInt64(0)
        self.outstanding[Txn.sender]        = UInt64(0)
        self.is_defaulted[Txn.sender]       = UInt64(0)
        self.last_payment_round[Txn.sender] = UInt64(0)
        self.daily_drawn[Txn.sender]        = UInt64(0)
        self.day_start_round[Txn.sender]    = UInt64(0)
        self.repay_by_round[Txn.sender]     = UInt64(0)

    # ──────────────────────────────────────────────────────────────────────────
    # ABI Method 1 — register
    # ──────────────────────────────────────────────────────────────────────────

    @arc4.abimethod
    def register(self, pay: gtxn.PaymentTransaction) -> None:
        """
        Register a new agent by staking ALGO.

        Preconditions:
          - pay.receiver == application address
          - pay.amount >= 1_000_000 microALGO (1 ALGO)
          - Agent must not already be registered (stake_amount == 0)

        Mutates:
          - All 9 local state slots initialised for Txn.sender.
          - treasury_balance += pay.amount
          - total_agents += 1

        Emits: AgentRegistered
        """
        assert (
            pay.receiver == Global.current_application_address
        ), "Payment must be to application address"
        assert pay.amount >= UInt64(1_000_000), "Minimum stake is 1 ALGO"
        assert (
            self.stake_amount[Txn.sender] == UInt64(0)
        ), "Agent already registered"

        self.stake_amount[Txn.sender]       = pay.amount
        self.payment_count[Txn.sender]      = UInt64(0)
        self.total_repaid[Txn.sender]       = UInt64(0)
        self.outstanding[Txn.sender]        = UInt64(0)
        self.is_defaulted[Txn.sender]       = UInt64(0)
        self.last_payment_round[Txn.sender] = op.Global.round
        self.daily_drawn[Txn.sender]        = UInt64(0)
        self.day_start_round[Txn.sender]    = op.Global.round
        self.repay_by_round[Txn.sender]     = UInt64(0)

        self.treasury_balance.value += pay.amount
        self.total_agents.value     += UInt64(1)

        arc4.emit(
            AgentRegistered(
                agent=arc4.Address(Txn.sender),
                stake=arc4.UInt64(pay.amount),
            )
        )

    # ──────────────────────────────────────────────────────────────────────────
    # ABI Method 2 — record_payment
    # ──────────────────────────────────────────────────────────────────────────

    @arc4.abimethod
    def record_payment(self, amount: arc4.UInt64) -> arc4.UInt64:
        """
        Record an off-chain machine-to-machine payment. No ALGO transfer occurs.
        Increments payment_count, which gates tier advancement.

        Preconditions:
          - Agent is not defaulted (is_defaulted == 0)
          - Agent is registered (stake_amount > 0)

        Mutates:
          - payment_count[sender] += 1
          - last_payment_round[sender] = current round

        Emits: PaymentRecorded
        Returns: current tier number (0-3) as arc4.UInt64
        """
        assert (
            self.is_defaulted[Txn.sender] == UInt64(0)
        ), "Agent is defaulted"
        assert (
            self.stake_amount[Txn.sender] > UInt64(0)
        ), "Agent not registered"

        self.payment_count[Txn.sender]      += UInt64(1)
        self.last_payment_round[Txn.sender]  = op.Global.round

        tier = self._get_tier(self.payment_count[Txn.sender])

        arc4.emit(
            PaymentRecorded(
                agent=arc4.Address(Txn.sender),
                amount=amount,
                tier=arc4.UInt64(tier),
            )
        )

        return arc4.UInt64(tier)

    # ──────────────────────────────────────────────────────────────────────────
    # ABI Method 3 — draw
    # ──────────────────────────────────────────────────────────────────────────

    @arc4.abimethod
    def draw(
        self,
        amount: arc4.UInt64,
        attestation_hash: arc4.StaticArray[arc4.Byte, typing.Literal[32]],
    ) -> None:
        """
        Draw undercollateralised credit from the protocol treasury.
        Sends ALGO from the contract to Txn.sender via inner transaction.

        Preconditions:
          - Agent not defaulted (is_defaulted == 0)
          - Agent registered (stake_amount > 0)
          - draw amount <= tier per-draw hard cap
          - daily_drawn + amount <= tier daily cap
          - contract has sufficient balance
          - attestation_hash valid (if skip_attestation == 0)

        Mutates:
          - daily_drawn[sender] += amount  (resets if new day window)
          - day_start_round[sender] updated if new window
          - outstanding[sender] += amount + interest
          - repay_by_round[sender] = current_round + DAY_IN_ROUNDS
          - treasury_balance.value -= amount  (funds leave contract)

        Emits: CreditDrawn
        """
        assert (
            self.is_defaulted[Txn.sender] == UInt64(0)
        ), "Agent is defaulted"
        assert (
            self.stake_amount[Txn.sender] > UInt64(0)
        ), "Agent not registered"

        draw_amt = amount.native
        current_round = op.Global.round

        # ── Attestation verification (production path) ──
        if self.skip_attestation.value == UInt64(0):
            expected = op.sha256(
                Txn.sender.bytes
                + amount.bytes
                + op.itob(current_round)
            )
            assert attestation_hash.bytes == expected, "Invalid attestation hash"

        # ── Daily window reset ──
        rounds_in_window = current_round - self.day_start_round[Txn.sender]
        if rounds_in_window >= UInt64(DAY_IN_ROUNDS):
            self.daily_drawn[Txn.sender]     = UInt64(0)
            self.day_start_round[Txn.sender] = current_round

        # ── Tier lookup ──
        tier = self._get_tier(self.payment_count[Txn.sender])

        # ── Per-draw hard cap check ──
        if tier == UInt64(3):
            assert draw_amt <= UInt64(TIER_3_MAX_DRAW), "Exceeds tier max draw"
        elif tier == UInt64(2):
            assert draw_amt <= UInt64(TIER_2_MAX_DRAW), "Exceeds tier max draw"
        elif tier == UInt64(1):
            assert draw_amt <= UInt64(TIER_1_MAX_DRAW), "Exceeds tier max draw"
        else:
            assert draw_amt <= UInt64(TIER_0_MAX_DRAW), "Exceeds tier max draw"

        # ── Daily cap check ──
        new_daily = self.daily_drawn[Txn.sender] + draw_amt
        if tier == UInt64(3):
            assert new_daily <= UInt64(TIER_3_DAILY_CAP), "Exceeds daily cap"
        elif tier == UInt64(2):
            assert new_daily <= UInt64(TIER_2_DAILY_CAP), "Exceeds daily cap"
        elif tier == UInt64(1):
            assert new_daily <= UInt64(TIER_1_DAILY_CAP), "Exceeds daily cap"
        else:
            assert new_daily <= UInt64(TIER_0_DAILY_CAP), "Exceeds daily cap"

        assert (
            Global.current_application_address.balance >= draw_amt
        ), "Insufficient contract balance"

        # ── Interest calculation ──
        # interest = (draw_amt * APR_BPS * DAY_IN_ROUNDS) / (10000 * ROUNDS_PER_YEAR)
        if tier == UInt64(3):
            apr_bps = UInt64(TIER_3_APR_BPS)
        elif tier == UInt64(2):
            apr_bps = UInt64(TIER_2_APR_BPS)
        elif tier == UInt64(1):
            apr_bps = UInt64(TIER_1_APR_BPS)
        else:
            apr_bps = UInt64(TIER_0_APR_BPS)

        interest = (draw_amt * apr_bps * UInt64(DAY_IN_ROUNDS)) // (UInt64(10_000) * UInt64(ROUNDS_PER_YEAR))

        # ── Send ALGO via inner transaction ──
        itxn.Payment(
            receiver=Txn.sender,
            amount=draw_amt,
            fee=Global.min_txn_fee,
        ).submit()

        # ── Update state ──
        self.daily_drawn[Txn.sender]    = new_daily
        self.outstanding[Txn.sender]   += draw_amt + interest
        self.repay_by_round[Txn.sender] = current_round + UInt64(DAY_IN_ROUNDS)
        self.treasury_balance.value    -= draw_amt

        arc4.emit(
            CreditDrawn(
                agent=arc4.Address(Txn.sender),
                amount=arc4.UInt64(draw_amt),
                interest=arc4.UInt64(interest),
                outstanding=arc4.UInt64(self.outstanding[Txn.sender]),
            )
        )

    # ──────────────────────────────────────────────────────────────────────────
    # ABI Method 4 — repay
    # ──────────────────────────────────────────────────────────────────────────

    @arc4.abimethod
    def repay(self, pay: gtxn.PaymentTransaction) -> None:
        """
        Repay outstanding credit (principal + interest) by sending ALGO
        back to the contract address.

        Preconditions:
          - pay.receiver == application address
          - pay.amount > 0

        Mutates:
          - outstanding[sender] reduced by repay_amt (floored at 0)
          - total_repaid[sender] += repay_amt
          - treasury_balance += repay_amt
          - last_payment_round[sender] = current round

        Emits: Repaid
        """
        assert (
            pay.receiver == Global.current_application_address
        ), "Payment must be to application address"
        assert pay.amount > UInt64(0), "Repayment must be > 0"

        repay_amt = pay.amount
        current_outstanding = self.outstanding[Txn.sender]

        if repay_amt >= current_outstanding:
            self.outstanding[Txn.sender] = UInt64(0)
        else:
            self.outstanding[Txn.sender] = current_outstanding - repay_amt

        self.total_repaid[Txn.sender]       += repay_amt
        self.treasury_balance.value         += repay_amt
        self.last_payment_round[Txn.sender]  = op.Global.round

        arc4.emit(
            Repaid(
                agent=arc4.Address(Txn.sender),
                amount=arc4.UInt64(repay_amt),
                outstanding=arc4.UInt64(self.outstanding[Txn.sender]),
            )
        )

    # ──────────────────────────────────────────────────────────────────────────
    # ABI Method 5 — slash
    # ──────────────────────────────────────────────────────────────────────────

    @arc4.abimethod
    def slash(self, agent: arc4.Address) -> None:
        """
        Slash a delinquent agent. Anyone may call this; caller earns 10% reward.

        Preconditions:
          - Agent has outstanding > 0
          - Agent has never repaid (payment_count == 0)
            OR last payment was > 30 rounds ago

        Mutates:
          - is_defaulted[agent] = 1
          - stake_amount[agent] = 0
          - treasury_balance += 90% of stake
          - Sends 10% of stake to Txn.sender via inner transaction

        Emits: AgentSlashed
        """
        agent_addr = agent.native

        assert (
            self.outstanding[agent_addr] > UInt64(0)
        ), "Agent has no outstanding debt"

        payment_count = self.payment_count[agent_addr]
        rounds_since  = op.Global.round - self.last_payment_round[agent_addr]

        assert (
            payment_count == UInt64(0) or rounds_since > UInt64(30)
        ), "Agent is not delinquent"

        stake = self.stake_amount[agent_addr]

        caller_reward    = stake // UInt64(10)
        treasury_portion = stake - caller_reward

        # Slash the agent
        self.is_defaulted[agent_addr]  = UInt64(1)
        self.stake_amount[agent_addr]  = UInt64(0)
        self.treasury_balance.value   += treasury_portion

        # Reward the caller
        itxn.Payment(
            receiver=Txn.sender,
            amount=caller_reward,
            fee=Global.min_txn_fee,
        ).submit()

        arc4.emit(
            AgentSlashed(
                agent=arc4.Address(agent_addr),
                stake_burned=arc4.UInt64(stake),
                caller_reward=arc4.UInt64(caller_reward),
            )
        )

    # ──────────────────────────────────────────────────────────────────────────
    # ABI Method 6 — get_position (readonly)
    # ──────────────────────────────────────────────────────────────────────────

    @arc4.abimethod(readonly=True)
    def get_position(
        self, agent: arc4.Address
    ) -> tuple[
        arc4.UInt64, arc4.UInt64, arc4.UInt64, arc4.UInt64,
        arc4.UInt64, arc4.UInt64, arc4.UInt64, arc4.UInt64, arc4.UInt64,
    ]:
        """
        Read an agent's full position. Does not modify state.

        Returns (all arc4.UInt64):
          0: stake_amount
          1: payment_count
          2: tier_max_draw      (derived from tier, replaces credit_limit formula)
          3: outstanding
          4: is_defaulted
          5: tier               (0-3)
          6: apr_bps            (tier APR in basis points)
          7: daily_drawn
          8: repay_by_round
        """
        addr = agent.native
        tier = self._get_tier(self.payment_count[addr])

        # Derive tier_max_draw on the fly
        if tier == UInt64(3):
            tier_max_draw = UInt64(TIER_3_MAX_DRAW)
            apr_bps       = UInt64(TIER_3_APR_BPS)
        elif tier == UInt64(2):
            tier_max_draw = UInt64(TIER_2_MAX_DRAW)
            apr_bps       = UInt64(TIER_2_APR_BPS)
        elif tier == UInt64(1):
            tier_max_draw = UInt64(TIER_1_MAX_DRAW)
            apr_bps       = UInt64(TIER_1_APR_BPS)
        else:
            tier_max_draw = UInt64(TIER_0_MAX_DRAW)
            apr_bps       = UInt64(TIER_0_APR_BPS)

        return (
            arc4.UInt64(self.stake_amount[addr]),
            arc4.UInt64(self.payment_count[addr]),
            arc4.UInt64(tier_max_draw),
            arc4.UInt64(self.outstanding[addr]),
            arc4.UInt64(self.is_defaulted[addr]),
            arc4.UInt64(tier),
            arc4.UInt64(apr_bps),
            arc4.UInt64(self.daily_drawn[addr]),
            arc4.UInt64(self.repay_by_round[addr]),
        )

    # ──────────────────────────────────────────────────────────────────────────
    # ABI Method 7 — seed_treasury
    # ──────────────────────────────────────────────────────────────────────────

    @arc4.abimethod
    def seed_treasury(self, pay: gtxn.PaymentTransaction) -> None:
        """
        Seed the protocol treasury with ALGO. Creator-only.

        Preconditions:
          - Txn.sender == Global.creator_address
          - pay.receiver == application address
          - pay.amount > 0

        Mutates:
          - treasury_balance += pay.amount

        Emits: nothing.
        """
        assert (
            Txn.sender == Global.creator_address
        ), "Only creator can seed treasury"
        assert (
            pay.receiver == Global.current_application_address
        ), "Payment must be to application address"
        assert pay.amount > UInt64(0), "Amount must be > 0"

        self.treasury_balance.value += pay.amount

    # ──────────────────────────────────────────────────────────────────────────
    # ABI Method 8 — set_signer
    # ──────────────────────────────────────────────────────────────────────────

    @arc4.abimethod
    def set_signer(self, signer: arc4.Address) -> None:
        """
        Set the protocol attestation signer address. Creator-only.

        Preconditions:
          - Txn.sender == Global.creator_address

        Mutates:
          - protocol_signer = signer.native

        Emits: nothing.
        """
        assert (
            Txn.sender == Global.creator_address
        ), "Only creator can set signer"
        self.protocol_signer.value = signer.native

    # ──────────────────────────────────────────────────────────────────────────
    # ABI Method 9 — enable_attestation
    # ──────────────────────────────────────────────────────────────────────────

    @arc4.abimethod
    def enable_attestation(self) -> None:
        """
        Switch draw() from demo-bypass mode into full attestation-hash
        verification mode. Creator-only.

        Preconditions:
          - Txn.sender == Global.creator_address

        Mutates:
          - skip_attestation = 0

        Emits: nothing.
        Note: Call set_signer() before enabling attestation in production.
        """
        assert (
            Txn.sender == Global.creator_address
        ), "Only creator can enable attestation"
        self.skip_attestation.value = UInt64(0)

    # ──────────────────────────────────────────────────────────────────────────
    # Private subroutine — _get_tier
    # ──────────────────────────────────────────────────────────────────────────

    @algopy.subroutine
    def _get_tier(self, payment_count: UInt64) -> UInt64:
        """
        Derive the agent's tier from payment_count.

        Tier thresholds:
          Tier 0 (Fresh):   0   <= payment_count < 10
          Tier 1 (Trusted): 10  <= payment_count < 50
          Tier 2 (Veteran): 50  <= payment_count < 100
          Tier 3 (Elite):   payment_count >= 100

        Returns: tier as UInt64 (0, 1, 2, or 3).
        Mutates: nothing.
        """
        if payment_count >= UInt64(TIER_3_THRESHOLD):
            return UInt64(3)
        elif payment_count >= UInt64(TIER_2_THRESHOLD):
            return UInt64(2)
        elif payment_count >= UInt64(TIER_1_THRESHOLD):
            return UInt64(1)
        else:
            return UInt64(0)


## ─────────────────────────────────────────────────────────────────────────────
## DEPLOYMENT CHECKLIST
## ─────────────────────────────────────────────────────────────────────────────
# 1. algokit compile py contracts/contract.py
#    → produces Trestle.approval.teal, Trestle.clear.teal, Trestle.arc56.json
#
# 2. algokit deploy (or use deploy.py):
#    a. Create application (stores app_id)
#    b. Fund minimum balance: send ~0.5 ALGO to app address for MBR
#       (9 local uint × 50_000 + 4 global × 50_000 + base 100_000 = 750_000 μA)
#
# 3. Call seed_treasury with X ALGO to fund draws:
#    e.g., seed 5 ALGO so agents can draw from the pool
#    atc.add_method_call(app_id, "seed_treasury", pay_txn, ...)
#
# 4. For demo: skip_attestation defaults to 1 — no action needed.
#    draw() will skip attestation_hash verification automatically.
#
# 5. For production:
#    a. call enable_attestation()   → sets skip_attestation = 0
#    b. call set_signer(signer_addr) → registers the Claude Skill signer
#    The Claude Skill must then sign: sha256(sender_bytes + amount_bytes + round_bytes)
#    and pass the 32-byte result as attestation_hash to draw().