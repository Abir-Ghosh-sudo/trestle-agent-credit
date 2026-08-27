"""
trestle_router.py — TrestleIntentRouter ARC-4 contract.

Intent-based swap fulfillment with Trestle credit on Algorand.

Separate App ID from TrestleCreditContract (<YOUR_APP_ID>).
DO NOT modify contracts/contract.py.

Architecture (Option B — solver draws credit directly):
  1. user1 calls lock_intent()  — locks ALGO in Router escrow, creates Intent
  2. user2 calls borrow_to_execute()  — claims the intent (private order enforcement)
  3. user2 calls Trestle.draw() directly (via TrestleCreditAgent.draw())
  4. user2 executes the task
  5. user2 calls settle()  — Router sends repayment to Trestle + profit to solver

Global state schema: 4 × uint64, 1 × bytes (admin)
No local state (no OptIn required from users).
Box storage: BoxMap(arc4.UInt64, Intent) with key_prefix=b"I"
"""

import typing

from algopy import (
    ARC4Contract,
    Account,
    BoxMap,
    Bytes,
    Global,
    GlobalState,
    String,
    Txn,
    UInt64,
    arc4,
    gtxn,
    itxn,
    log,
    op,
    subroutine,
)

# ── Interest constants (must match criteria.py and contract.py exactly) ────────
# Use plain int literals for module-level constants (puyapy 5.x doesn't support UInt64 at module scope)
_TIER_0_APR_BPS   = 2400
_DAY_IN_ROUNDS    = 86_400
_ROUNDS_PER_YEAR  = 31_536_000


# ── Intent struct ──────────────────────────────────────────────────────────────

class Intent(arc4.Struct):
    """Full on-chain state of a swap intent."""
    locker:          arc4.Address                                      # user1
    payment_amount:  arc4.UInt64                                       # microALGO locked by user1
    api_cost:        arc4.UInt64                                       # amount solver borrows from Trestle
    expiry_round:    arc4.UInt64                                       # Global.round + expiry_rounds_from_now
    task_hash:       arc4.StaticArray[arc4.Byte, typing.Literal[32]]  # sha256 of task params
    solver_address:  arc4.Address                                      # ONLY this solver can fulfill
    assigned_agent:  arc4.Address                                      # set when solver claims
    result_hash:     arc4.StaticArray[arc4.Byte, typing.Literal[32]]  # set on settle
    state:           arc4.UInt64                                       # 0=open 1=assigned 2=settled 3=expired


# ── Contract ───────────────────────────────────────────────────────────────────

class TrestleIntentRouter(ARC4Contract):
    """
    Intent-based swap fulfillment router with Trestle credit integration.

    Global state:
        trestle_app_id   — Trestle core contract App ID
        total_intents   — auto-increment intent counter
        router_treasury — fee accumulation (reserved for future use)
        admin           — admin address (creator)
        is_live         — 0=paused, 1=live

    Box storage:
        intents[arc4.UInt64] = Intent  (key_prefix=b"I")
    """

    trestle_app_id:   GlobalState[UInt64]
    total_intents:   GlobalState[UInt64]
    router_treasury: GlobalState[UInt64]
    admin:           GlobalState[Account]
    is_live:         GlobalState[UInt64]

    # BoxMap: intent_id (arc4.UInt64) → Intent
    intents: BoxMap[arc4.UInt64, Intent]

    def __init__(self) -> None:
        self.trestle_app_id   = GlobalState(UInt64(0))
        self.total_intents   = GlobalState(UInt64(0))
        self.router_treasury = GlobalState(UInt64(0))
        self.admin           = GlobalState(Account)
        self.is_live         = GlobalState(UInt64(0))
        self.intents         = BoxMap(arc4.UInt64, Intent, key_prefix=b"I")

    # ── ABI Method 1 — bootstrap ───────────────────────────────────────────────

    @arc4.abimethod(create="require")
    def bootstrap(self, trestle_app_id: arc4.UInt64) -> None:
        """
        Initialise the router. Called once on contract creation by the admin.

        Preconditions:
            - Txn.sender == Global.creator_address (enforced by create="require")

        Mutates:
            - Sets all 5 global state fields.
            - is_live = 1 (router goes live immediately)
        """
        assert Txn.sender == Global.creator_address, "admin_only"
        self.trestle_app_id.value   = trestle_app_id.native
        self.total_intents.value   = UInt64(0)
        self.router_treasury.value = UInt64(0)
        self.admin.value           = Txn.sender
        self.is_live.value         = UInt64(1)

    # ── ABI Method 2 — lock_intent ─────────────────────────────────────────────

    @arc4.abimethod
    def lock_intent(
        self,
        task_hash: arc4.StaticArray[arc4.Byte, typing.Literal[32]],
        expiry_rounds_from_now: arc4.UInt64,
        api_cost_estimate: arc4.UInt64,
        solver_address: arc4.Address,
    ) -> arc4.UInt64:
        """
        Lock ALGO and create a private swap intent.

        user1 sends a payment to the Router (as the previous gtxn) and specifies
        which solver can fulfill. Only the named solver_address can call
        borrow_to_execute().

        The payment transaction must be the immediately preceding transaction
        in the group (gtxn[-1] / gtxn[Txn.group_index - 1]).

        Args:
            task_hash:             sha256(task params) — 32 bytes
            expiry_rounds_from_now: Rounds until intent expires (10–86400)
            api_cost_estimate:     Amount solver will borrow from Trestle
            solver_address:        The ONLY solver that may fulfill this intent

        Returns:
            intent_id (arc4.UInt64)

        Emits log: b"LogIntentLocked:" + intent_id (8 bytes) + ":" + payment (8 bytes)
        """
        # The payment must be the previous transaction in the group
        pay_txn = gtxn.PaymentTransaction(Txn.group_index - UInt64(1))
        payment_amount = pay_txn.amount

        assert pay_txn.receiver == Global.current_application_address, "pay_to_router"
        assert payment_amount > api_cost_estimate.native, "payment_must_exceed_api_cost"
        assert payment_amount <= UInt64(10_000_000), "payment_too_large_max_10_algo"
        assert expiry_rounds_from_now.native > UInt64(10), "expiry_too_soon"
        assert expiry_rounds_from_now.native <= UInt64(86_400), "expiry_too_far"
        assert self.is_live.value == UInt64(1), "router_paused"

        intent_id = self.total_intents.value
        self.total_intents.value += UInt64(1)
        expiry = op.Global.round + expiry_rounds_from_now.native

        # Build zero bytes32 for result_hash and assigned_agent
        zero_bytes32 = arc4.StaticArray[arc4.Byte, typing.Literal[32]].from_bytes(
            op.bzero(32)
        )
        zero_address = arc4.Address(Global.zero_address)

        intent = Intent(
            locker=arc4.Address(Txn.sender),
            payment_amount=arc4.UInt64(payment_amount),
            api_cost=arc4.UInt64(api_cost_estimate.native),
            expiry_round=arc4.UInt64(expiry),
            task_hash=task_hash.copy(),
            solver_address=solver_address.copy(),
            assigned_agent=zero_address,
            result_hash=zero_bytes32.copy(),
            state=arc4.UInt64(0),
        )

        intent_key = arc4.UInt64(intent_id)
        self.intents[intent_key] = intent.copy()

        # Emit log for indexer polling
        log(
            b"LogIntentLocked:"
            + op.itob(intent_id)
            + b":"
            + op.itob(payment_amount)
        )

        return arc4.UInt64(intent_id)

    # ── ABI Method 3 — borrow_to_execute ──────────────────────────────────────

    @arc4.abimethod
    def borrow_to_execute(
        self,
        intent_id: arc4.UInt64,
        task_description: arc4.String,
        expected_return_microalgo: arc4.UInt64,
    ) -> arc4.Bool:
        """
        Claim a private intent as the designated solver.

        The solver must have ALREADY drawn credit from Trestle externally
        (via TrestleCreditAgent.draw()) before calling this method.
        This method only enforces the private order and marks the intent assigned.

        PRIVATE ORDER ENFORCEMENT: Only intent.solver_address can call this.
        Any other caller gets assertion failure.

        Args:
            intent_id:                Intent to claim
            task_description:         Plain-English task description (for logging)
            expected_return_microalgo: Solver's expected return (for logging)

        Returns:
            True if assigned successfully

        Emits log: b"LogIntentAssigned:" + intent_id + ":" + solver_address
        """
        assert intent_id in self.intents, "intent_not_found"

        intent = self.intents[intent_id].copy()

        assert intent.state == arc4.UInt64(0), "intent_not_open"
        assert op.Global.round < intent.expiry_round.native, "intent_expired"
        assert Txn.sender == intent.solver_address.native, "not_authorized_solver"

        # Update intent: assigned_agent = solver, state = 1 (assigned)
        updated = Intent(
            locker=intent.locker.copy(),
            payment_amount=arc4.UInt64(intent.payment_amount.native),
            api_cost=arc4.UInt64(intent.api_cost.native),
            expiry_round=arc4.UInt64(intent.expiry_round.native),
            task_hash=intent.task_hash.copy(),
            solver_address=intent.solver_address.copy(),
            assigned_agent=arc4.Address(Txn.sender),
            result_hash=intent.result_hash.copy(),
            state=arc4.UInt64(1),
        )
        self.intents[intent_id] = updated.copy()

        log(
            b"LogIntentAssigned:"
            + op.itob(intent_id.native)
            + b":"
            + Txn.sender.bytes
        )

        return arc4.Bool(True)

    # ── ABI Method 4 — settle ─────────────────────────────────────────────────

    @arc4.abimethod
    def settle(
        self,
        intent_id: arc4.UInt64,
        result_hash: arc4.StaticArray[arc4.Byte, typing.Literal[32]],
        result_pointer: arc4.String,
    ) -> arc4.Bool:
        """
        Settle a completed intent atomically.

        Sends repayment to Trestle from Router escrow + profit to solver.
        Calls Trestle.record_payment() to build solver's tier history.

        Interest formula (Tier 0, matches contract.py exactly):
            interest = (api_cost * 2400 * 86400) // (10000 * 31536000)
            interest += 1  # minimum 1 μA

        Args:
            intent_id:      Intent to settle
            result_hash:    sha256 of result (32 bytes)
            result_pointer: Short result summary string (≤200 chars)

        Returns:
            True on success

        Inner transactions (atomic):
            [0] Payment to Trestle app address (repayment)
            [1] Payment to solver (profit)
            [2] ApplicationCall to Trestle.record_payment()
        Emits log: b"LogIntentSettled:" + intent_id + ":" + result_pointer
        """
        assert intent_id in self.intents, "intent_not_found"

        intent = self.intents[intent_id].copy()

        assert intent.state == arc4.UInt64(1), "intent_not_assigned"
        assert Txn.sender == intent.assigned_agent.native, "not_assigned_solver"
        assert op.Global.round < intent.expiry_round.native, "intent_expired_during_execution"

        api_cost = intent.api_cost.native
        payment_amount = intent.payment_amount.native

        # Interest: exact formula from contract.py (Tier 0 APR = 2400 bps)
        interest = (api_cost * UInt64(2400) * UInt64(86_400)) // (
            UInt64(10_000) * UInt64(31_536_000)
        )
        interest = interest + UInt64(1)  # minimum 1 μA
        repayment = api_cost + interest

        profit = payment_amount - repayment
        assert profit > UInt64(0), "insufficient_profit_after_repayment"

        # Get Trestle contract address (escrow that receives repayment)
        trestle_addr, trestle_addr_exists = op.AppParamsGet.app_address(self.trestle_app_id.value)
        assert trestle_addr_exists, "trestle_app_not_found"

        # [0] Repay Trestle: send repayment from Router escrow to Trestle app address
        itxn.Payment(
            receiver=trestle_addr,
            amount=repayment,
            fee=Global.min_txn_fee,
        ).submit()

        # [1] Pay solver profit
        itxn.Payment(
            receiver=Txn.sender,
            amount=profit,
            fee=Global.min_txn_fee,
        ).submit()

        # [2] Call Trestle.record_payment() for the solver
        # Note: accounts=[Txn.sender] passes solver address for local state update.
        # Txn.sender in this inner txn is the Router app address.
        # Trestle.record_payment uses Txn.sender — so the Router must be a Trestle agent.
        # In the demo flow, the solver calls record_payment() directly after settle().
        # This inner call is included for atomic on-chain completeness.
        itxn.ApplicationCall(
            app_id=self.trestle_app_id.value,
            app_args=(
                arc4.arc4_signature("record_payment(uint64)uint64"),
                arc4.UInt64(api_cost),
            ),
            accounts=(Txn.sender,),
            fee=Global.min_txn_fee,
        ).submit()

        # Update intent state
        settled = Intent(
            locker=intent.locker.copy(),
            payment_amount=arc4.UInt64(intent.payment_amount.native),
            api_cost=arc4.UInt64(intent.api_cost.native),
            expiry_round=arc4.UInt64(intent.expiry_round.native),
            task_hash=intent.task_hash.copy(),
            solver_address=intent.solver_address.copy(),
            assigned_agent=intent.assigned_agent.copy(),
            result_hash=result_hash.copy(),
            state=arc4.UInt64(2),
        )
        self.intents[intent_id] = settled.copy()

        # [3] Log result on-chain
        log(
            b"LogIntentSettled:"
            + op.itob(intent_id.native)
            + b":"
            + result_pointer.bytes
        )

        return arc4.Bool(True)

    # ── ABI Method 5 — reclaim_expired ────────────────────────────────────────

    @arc4.abimethod
    def reclaim_expired(self, intent_id: arc4.UInt64) -> arc4.Bool:
        """
        Reclaim locked funds for an expired intent.

        Only the original locker (user1) can reclaim.
        If the intent was assigned but never settled (solver took job, disappeared):
            → Slash the assigned agent via Trestle inner txn
        Return locked funds to locker regardless.

        Args:
            intent_id: Intent to expire and reclaim

        Returns:
            True on success
        """
        assert intent_id in self.intents, "intent_not_found"

        intent = self.intents[intent_id].copy()

        assert Txn.sender == intent.locker.native, "not_locker"
        assert op.Global.round >= intent.expiry_round.native, "not_expired_yet"
        assert intent.state != arc4.UInt64(2), "already_settled"

        # If assigned but never settled: slash the delinquent solver
        if intent.state == arc4.UInt64(1):
            itxn.ApplicationCall(
                app_id=self.trestle_app_id.value,
                app_args=(
                    arc4.arc4_signature("slash(account)void"),
                    intent.assigned_agent,
                ),
                fee=Global.min_txn_fee,
            ).submit()

        # Return locked funds to user1
        itxn.Payment(
            receiver=intent.locker.native,
            amount=intent.payment_amount.native,
            fee=Global.min_txn_fee,
        ).submit()

        # Update state to expired
        expired = Intent(
            locker=intent.locker.copy(),
            payment_amount=arc4.UInt64(intent.payment_amount.native),
            api_cost=arc4.UInt64(intent.api_cost.native),
            expiry_round=arc4.UInt64(intent.expiry_round.native),
            task_hash=intent.task_hash.copy(),
            solver_address=intent.solver_address.copy(),
            assigned_agent=intent.assigned_agent.copy(),
            result_hash=intent.result_hash.copy(),
            state=arc4.UInt64(3),
        )
        self.intents[intent_id] = expired.copy()

        return arc4.Bool(True)

    # ── ABI Method 6 — get_intent (readonly) ──────────────────────────────────

    @arc4.abimethod(readonly=True)
    def get_intent(self, intent_id: arc4.UInt64) -> Intent:
        """
        Read a full intent struct. Does not modify state.

        Args:
            intent_id: ID of the intent to read

        Returns:
            Full Intent struct copy
        """
        assert intent_id in self.intents, "intent_not_found"
        return self.intents[intent_id].copy()
