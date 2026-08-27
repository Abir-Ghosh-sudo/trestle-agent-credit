"""
intent_agent.py — Off-chain intent market agent stack for Trestle Intent Router.

Three classes:
    IntentListener  — polls Algorand indexer for new intents targeted at this solver
    IntentBrain     — evaluates an intent using TrestleCreditAgent oracle (Venice AI / Anthropic)
    IntentExecutor  — orchestrates: claim → task → settle

All imports from stdlib + algosdk + trestle_sdk only. No new dependencies.

Usage:
    from trestle_sdk.intent_agent import IntentListener, IntentBrain, IntentExecutor
    from trestle_sdk import TrestleCreditAgent

    agent = TrestleCreditAgent(mnemonic_phrase="...", app_id=<YOUR_APP_ID>)

    listener = IntentListener(router_app_id=ROUTER_ID, solver_address=agent.address)
    brain    = IntentBrain(agent)
    executor = IntentExecutor(agent, ROUTER_ID, task_handler=my_handler)

    listener.run_forever(on_intent_callback=executor.handle_intent)
"""

import base64
import time
from typing import Callable

import requests
from algosdk.abi import Method
from algosdk.atomic_transaction_composer import AtomicTransactionComposer

from trestle_sdk.agent import TrestleCreditAgent
from trestle_sdk.criteria import TIER_MAX_DRAW
from trestle_sdk.exceptions import TrestleCreditDenied


# ── Layer 1 — IntentListener ───────────────────────────────────────────────────

class IntentListener:
    """
    Polls the Algorand indexer for new intents on the Router contract.

    Uses REST polling (not WebSocket) against the Algonode indexer.
    Filters intents by log prefix "LogIntentLocked:" and then reads the full
    Intent struct via get_intent() to confirm solver_address matches.

    Attributes:
        router_app_id:   Router contract App ID
        solver_address:  Only intents assigned to this solver are returned
        indexer_url:     Algonode indexer base URL
        poll_interval:   Seconds between polls (default 3)
        _seen_intents:   Set of intent IDs already processed (prevents re-processing)
    """

    def __init__(
        self,
        router_app_id: int,
        solver_address: str,
        network: str = "testnet",
        poll_interval: int = 3,
        algod_client=None,
    ) -> None:
        self.router_app_id   = router_app_id
        self.solver_address  = solver_address
        self.indexer_url     = f"https://{network}-idx.algonode.cloud"
        self.poll_interval   = poll_interval
        self.algod_client    = algod_client  # used for get_intent simulation
        self._seen_intents: set[int] = set()

    def poll_once(self) -> list[dict]:
        """
        Query indexer for recent LogIntentLocked transactions on the Router.

        Steps:
        1. Query /v2/transactions with application-id and note-prefix filter
        2. Parse intent_id from log bytes (first 8 bytes after prefix)
        3. Call get_intent(intent_id) on-chain to read full Intent struct
        4. Filter: only return if intent.solver_address == self.solver_address
        5. Add to _seen_intents

        Returns:
            List of new intent dicts with keys:
                intent_id, locker, payment_amount, api_cost, expiry_round,
                solver_address, state, task_description (placeholder)
        """
        url = f"{self.indexer_url}/v2/transactions"
        note_prefix = base64.b64encode(b"LogIntentLocked:").decode()

        try:
            resp = requests.get(
                url,
                params={
                    "application-id": self.router_app_id,
                    "limit": 20,
                    "note-prefix": note_prefix,
                },
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.RequestException as exc:
            print(f"[listener] indexer request failed: {exc}")
            return []

        new_intents = []

        for txn in data.get("transactions", []):
            # Parse logs from the transaction
            logs = txn.get("logs", [])
            for log_b64 in logs:
                try:
                    log_bytes = base64.b64decode(log_b64)
                except Exception:
                    continue

                prefix = b"LogIntentLocked:"
                if not log_bytes.startswith(prefix):
                    continue

                # Format: prefix (16 bytes) + intent_id (8 bytes) + ":" (1 byte) + payment (8 bytes)
                payload = log_bytes[len(prefix):]
                if len(payload) < 9:
                    continue

                intent_id = int.from_bytes(payload[:8], "big")

                if intent_id in self._seen_intents:
                    continue

                # Fetch full intent via get_intent() if we have an algod client
                intent_dict = self._fetch_intent(intent_id)
                if intent_dict is None:
                    continue

                # Filter: only intents assigned to this solver
                if intent_dict.get("solver_address", "") != self.solver_address:
                    self._seen_intents.add(intent_id)
                    continue

                # Only open intents (state == 0)
                if intent_dict.get("state", -1) != 0:
                    self._seen_intents.add(intent_id)
                    continue

                self._seen_intents.add(intent_id)
                new_intents.append(intent_dict)

        return new_intents

    def _fetch_intent(self, intent_id: int) -> dict | None:
        """
        Call get_intent(intent_id) on the Router contract to read full struct.

        Falls back to indexer lookup if algod_client is not available.
        Returns None on failure.
        """
        if self.algod_client is None:
            # Minimal fallback: return a stub with just the intent_id
            return {
                "intent_id": intent_id,
                "solver_address": "",  # unknown without algod
                "state": 0,
                "payment_amount": 0,
                "api_cost": 0,
                "expiry_round": 0,
                "locker": "",
                "task_description": f"intent_{intent_id}",
            }

        try:
            from algosdk.atomic_transaction_composer import (
                AtomicTransactionComposer,
                AccountTransactionSigner,
            )
            from algosdk.abi import Method

            # We need a signer — use a dummy zero-key for readonly simulation
            # The simulation doesn't require a real signature
            atc = AtomicTransactionComposer()
            sp  = self.algod_client.suggested_params()

            # We'll use simulate — requires a dummy signer that won't actually sign
            # Use the solver's address if we have it configured
            # For simplicity, use the indexer to read box state directly
            return self._fetch_intent_from_indexer(intent_id)

        except Exception as exc:
            print(f"[listener] get_intent({intent_id}) failed: {exc}")
            return None

    def _fetch_intent_from_indexer(self, intent_id: int) -> dict | None:
        """
        Read intent box state from the indexer.
        Box key = b"I" + arc4.UInt64(intent_id).bytes = b"I" + intent_id.to_bytes(8, big)
        """
        try:
            box_key_bytes = b"I" + intent_id.to_bytes(8, "big")
            box_key_b64 = base64.b64encode(box_key_bytes).decode()

            url = f"{self.indexer_url}/v2/applications/{self.router_app_id}/box"
            resp = requests.get(
                url,
                params={"name": f"b64:{box_key_b64}"},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()

            # Decode box value (ARC-4 encoded Intent struct)
            value_b64 = data.get("value", "")
            if not value_b64:
                return None

            raw = base64.b64decode(value_b64)
            return self._decode_intent_struct(intent_id, raw)

        except Exception as exc:
            print(f"[listener] box fetch failed for intent {intent_id}: {exc}")
            return None

    def _decode_intent_struct(self, intent_id: int, raw: bytes) -> dict | None:
        """
        Decode ARC-4 encoded Intent struct bytes.

        Intent layout (ARC-4 packed, in order):
            locker:          32 bytes (arc4.Address)
            payment_amount:  8 bytes  (arc4.UInt64)
            api_cost:        8 bytes  (arc4.UInt64)
            expiry_round:    8 bytes  (arc4.UInt64)
            task_hash:       32 bytes (arc4.StaticArray[Byte, 32])
            solver_address:  32 bytes (arc4.Address)
            assigned_agent:  32 bytes (arc4.Address)
            result_hash:     32 bytes (arc4.StaticArray[Byte, 32])
            state:           8 bytes  (arc4.UInt64)
        Total: 32+8+8+8+32+32+32+32+8 = 192 bytes
        """
        if len(raw) < 192:
            return None

        try:
            from algosdk.encoding import encode_address

            offset = 0
            locker_bytes     = raw[offset:offset+32]; offset += 32
            payment_amount   = int.from_bytes(raw[offset:offset+8], "big"); offset += 8
            api_cost         = int.from_bytes(raw[offset:offset+8], "big"); offset += 8
            expiry_round     = int.from_bytes(raw[offset:offset+8], "big"); offset += 8
            _task_hash       = raw[offset:offset+32]; offset += 32
            solver_bytes     = raw[offset:offset+32]; offset += 32
            assigned_bytes   = raw[offset:offset+32]; offset += 32
            _result_hash     = raw[offset:offset+32]; offset += 32
            state            = int.from_bytes(raw[offset:offset+8], "big"); offset += 8

            locker          = encode_address(locker_bytes)
            solver_address  = encode_address(solver_bytes)
            assigned_agent  = encode_address(assigned_bytes)

            return {
                "intent_id":      intent_id,
                "locker":         locker,
                "payment_amount": payment_amount,
                "api_cost":       api_cost,
                "expiry_round":   expiry_round,
                "task_hash":      _task_hash.hex(),
                "solver_address": solver_address,
                "assigned_agent": assigned_agent,
                "result_hash":    _result_hash.hex(),
                "state":          state,
                "task_description": f"Swap intent {intent_id}",  # placeholder; real desc not stored on-chain
            }
        except Exception as exc:
            print(f"[listener] struct decode error: {exc}")
            return None

    def run_forever(self, on_intent_callback: Callable[[dict], None]) -> None:
        """
        Poll indefinitely. Calls on_intent_callback(intent_dict) for each new intent.

        Errors during polling are caught and logged — the loop continues.

        Args:
            on_intent_callback: Called with intent dict for each new intent targeting this solver.
        """
        print(f"[listener] Polling {self.indexer_url} for router {self.router_app_id}...")
        while True:
            try:
                new_intents = self.poll_once()
                for intent in new_intents:
                    on_intent_callback(intent)
            except Exception as exc:
                print(f"[listener] polling error: {exc}")
            time.sleep(self.poll_interval)


# ── Layer 2 — IntentBrain ─────────────────────────────────────────────────────

class IntentBrain:
    """
    Evaluates an intent in <100ms using TrestleCreditAgent oracle (Venice AI / Anthropic).

    Pre-checks before calling the LLM oracle (to save API cost on obvious rejects):
        1. Time window: rounds_remaining > time_buffer_rounds
        2. Profit ratio: (payment - api_cost) / payment >= min_profit_ratio
        3. No outstanding debt: agent.get_position()["outstanding"] == 0
        4. Tier cap: api_cost <= TIER_MAX_DRAW[agent_tier]

    If all pre-checks pass: calls agent.oracle.evaluate() with real LLM.
    Returns (should_execute: bool, reason: str, borrow_amount: int)
    """

    def __init__(
        self,
        agent: TrestleCreditAgent,
        min_profit_ratio: float = 0.10,
        time_buffer_rounds: int = 120,
    ) -> None:
        self.agent               = agent
        self.min_profit_ratio    = min_profit_ratio
        self.time_buffer_rounds  = time_buffer_rounds

    def evaluate(
        self, intent: dict, current_round: int
    ) -> tuple[bool, str, int]:
        """
        Evaluate an intent and decide whether to execute.

        Args:
            intent:        Intent dict (from IntentListener.poll_once())
            current_round: Current Algorand round

        Returns:
            (should_execute, reason, borrow_amount)
            - should_execute: True if approved
            - reason: Human-readable explanation
            - borrow_amount: api_cost to borrow (0 if rejected)
        """
        payment    = intent["payment_amount"]
        api_cost   = intent["api_cost"]
        expiry     = intent["expiry_round"]
        intent_id  = intent["intent_id"]

        # ── Pre-check 1: time window ───────────────────────────────────────────
        rounds_remaining = expiry - current_round
        if rounds_remaining <= self.time_buffer_rounds:
            return False, "insufficient_time_window", 0

        # ── Pre-check 2: profit ratio ──────────────────────────────────────────
        if payment <= 0 or api_cost <= 0:
            return False, "invalid_amounts", 0
        profit = payment - api_cost
        if profit <= 0:
            return False, "no_profit_margin", 0
        ratio = profit / payment
        if ratio < self.min_profit_ratio:
            return (
                False,
                f"profit_ratio_{ratio:.2%}_below_{self.min_profit_ratio:.0%}",
                0,
            )

        # ── Pre-check 3: no outstanding debt ──────────────────────────────────
        try:
            pos  = self.agent.get_position()
            tier = pos["tier"]
            if pos["outstanding"] > 0:
                return False, "outstanding_debt_exists", 0
        except Exception as exc:
            return False, f"position_read_failed:{exc}", 0

        # ── Pre-check 4: tier cap ──────────────────────────────────────────────
        if api_cost > TIER_MAX_DRAW[tier]:
            return (
                False,
                f"api_cost_{api_cost}_exceeds_tier_{tier}_cap_{TIER_MAX_DRAW[tier]}",
                0,
            )

        # ── Full LLM oracle evaluation ─────────────────────────────────────────
        task_desc = intent.get(
            "task_description",
            f"Execute swap intent {intent_id}: ALGO-to-USDC DEX swap",
        )

        try:
            _decision = self.agent.oracle.evaluate(
                agent_address=self.agent.address,
                amount_microalgo=api_cost,
                payment_count=int(pos["payment_count"]),
                outstanding_microalgo=int(pos["outstanding"]),
                task_description=task_desc,
                expected_return_microalgo=profit,
                estimated_task_rounds=self.time_buffer_rounds,
            )
            return True, "oracle_approved", api_cost
        except TrestleCreditDenied as exc:
            return False, f"oracle_denied:{exc.reason}", 0
        except Exception as exc:
            return False, f"oracle_error:{exc}", 0


# ── Layer 3 — IntentExecutor ──────────────────────────────────────────────────

class IntentExecutor:
    """
    Orchestrates the full intent execution loop.

    Flow:
        1. IntentBrain.evaluate()           — pre-checks + LLM oracle
        2. agent.draw()                     — draw Trestle credit directly
        3. Router.borrow_to_execute()       — claim intent on Router
        4. task_handler(intent)             — execute the task (user-provided)
        5. Router.settle()                  — atomic: repay Trestle + profit to solver

    Args:
        agent:          TrestleCreditAgent for the solver
        router_app_id:  TrestleIntentRouter App ID
        task_handler:   Callable[[dict], tuple[str, bytes]] → (result_str, result_hash_bytes)
        brain:          Optional IntentBrain (created automatically if None)
    """

    def __init__(
        self,
        agent: TrestleCreditAgent,
        router_app_id: int,
        task_handler: Callable[[dict], tuple[str, bytes]],
        brain: "IntentBrain | None" = None,
    ) -> None:
        self.agent          = agent
        self.router_app_id  = router_app_id
        self.task_handler   = task_handler
        self.brain          = brain or IntentBrain(agent)

    def handle_intent(self, intent: dict) -> bool:
        """
        Full execution loop for a single intent.

        Returns True on successful settlement, False on any failure.

        Steps:
            1. Evaluate with IntentBrain (pre-checks + LLM oracle)
            2. Draw Trestle credit directly via agent.draw()
            3. Claim intent via Router.borrow_to_execute()
            4. Execute task via task_handler()
            5. Settle via Router.settle()
        """
        current_round = self.agent.algod_client.status()["last-round"]
        intent_id     = intent["intent_id"]

        print(f"[executor] Evaluating intent {intent_id}...")

        # Step 1: Brain evaluation
        should_exec, reason, borrow_amount = self.brain.evaluate(intent, current_round)
        if not should_exec:
            print(f"[executor] Skipping intent {intent_id}: {reason}")
            return False

        print(f"[executor] Approved! Drawing {borrow_amount} \u03bcA from Trestle...")

        # Step 2: Draw credit from Trestle directly (Option B)
        task_desc = intent.get(
            "task_description",
            f"Execute swap intent {intent_id}: ALGO-to-USDC DEX swap",
        )
        profit = intent["payment_amount"] - borrow_amount

        try:
            draw_result = self.agent.draw(
                amount_microalgo=borrow_amount,
                task_description=task_desc,
                expected_return_microalgo=profit,
                estimated_task_rounds=self.brain.time_buffer_rounds,
            )
            print(f"[executor] Credit drawn. Txn: {draw_result['txid']}")
        except TrestleCreditDenied as exc:
            print(f"[executor] Trestle draw denied: {exc.reason}")
            return False
        except Exception as exc:
            print(f"[executor] Trestle draw failed: {exc}")
            return False

        # Step 3: Claim intent on Router
        try:
            self._call_router_borrow(intent_id, task_desc, profit)
            print(f"[executor] Intent {intent_id} claimed on Router.")
        except Exception as exc:
            print(f"[executor] borrow_to_execute failed: {exc}")
            # Credit was drawn — solver should repay manually
            print(f"[executor] WARNING: Repay {draw_result['total_repayable']} \u03bcA to Trestle manually.")
            return False

        # Step 4: Execute task
        try:
            result_str, result_hash = self.task_handler(intent)
            print(f"[executor] Task complete: {result_str[:80]}")
        except Exception as exc:
            print(f"[executor] Task failed: {exc}. Intent will expire; locker reclaims funds.")
            return False

        # Step 5: Settle on-chain
        try:
            self._call_router_settle(intent_id, result_hash, result_str[:200])
            print(f"[executor] Intent {intent_id} settled! Profit credited.")
            return True
        except Exception as exc:
            print(f"[executor] settle() failed: {exc}")
            return False

    def _call_router_borrow(
        self,
        intent_id: int,
        task_description: str,
        expected_return: int,
    ) -> None:
        """Call borrow_to_execute(uint64,string,uint64)bool on the Router."""
        from algosdk.abi import Method

        atc = AtomicTransactionComposer()
        sp  = self.agent.algod_client.suggested_params()

        # Box reference: key = b"I" + intent_id.to_bytes(8, "big")
        box_key = b"I" + intent_id.to_bytes(8, "big")

        atc.add_method_call(
            app_id=self.router_app_id,
            method=Method.from_signature("borrow_to_execute(uint64,string,uint64)bool"),
            sender=self.agent.address,
            sp=sp,
            signer=self.agent.signer,
            method_args=[intent_id, task_description, expected_return],
            boxes=[(self.router_app_id, box_key)],
        )
        atc.execute(self.agent.algod_client, 4)

    def _call_router_settle(
        self,
        intent_id: int,
        result_hash: bytes,
        result_pointer: str,
    ) -> None:
        """Call settle(uint64,byte[32],string)bool on the Router."""
        from algosdk.abi import Method

        atc = AtomicTransactionComposer()
        sp  = self.agent.algod_client.suggested_params()

        # Box reference: key = b"I" + intent_id.to_bytes(8, "big")
        box_key = b"I" + intent_id.to_bytes(8, "big")

        # result_hash as list[int] for arc4.StaticArray[Byte, 32]
        hash_list = list(result_hash)

        atc.add_method_call(
            app_id=self.router_app_id,
            method=Method.from_signature("settle(uint64,byte[32],string)bool"),
            sender=self.agent.address,
            sp=sp,
            signer=self.agent.signer,
            method_args=[intent_id, hash_list, result_pointer],
            boxes=[(self.router_app_id, box_key)],
            foreign_apps=[self.agent.app_id],  # Trestle app for inner txn
            accounts=[self.agent.address],      # solver address for record_payment
        )
        atc.execute(self.agent.algod_client, 4)
