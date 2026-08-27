# TRESTLE — USDC SUPPORT IMPLEMENTATION
# Add USDC draws and repayments alongside existing ALGO flow.
# ALGO behaviour is unchanged. USDC is a parallel denomination.
# ═══════════════════════════════════════════════════════════════════
# Paste this entire file as the first message to Antigravity.
# Read every section before writing a single line of code.
# ═══════════════════════════════════════════════════════════════════


## OBJECTIVE

Add USDC (Algorand Standard Asset) as a second loan denomination to Trestle.
Every existing ALGO method stays exactly as-is. Every ALGO test still passes.
USDC is a parallel path: agents can draw ALGO credit OR USDC credit, not both
simultaneously (no cross-denomination debt stacking).

The shared credit identity (payment_count, tier, is_defaulted) applies to both
currencies. One reputation score, two denominations.


## WHAT YOU MUST NOT TOUCH

- `METHOD_REGISTER`, `do_register()`, `register()` — unchanged
- `METHOD_REPAY`, `do_repay()`, `repay()` — unchanged
- `METHOD_RECORD_PAYMENT`, `do_record_payment()`, `record_payment()` — unchanged
- `METHOD_GET_POSITION`, `get_position()` — unchanged (returns 9 values, stays as 9)
- `seed_treasury()`, `set_signer()`, `enable_attestation()` — unchanged
- `slash()` — unchanged
- All existing tests — must still pass after this change
- TIER_MAX_DRAW, TIER_APR_BPS, TIER_DAILY_CAP, TIER_THRESHOLDS, TIER_NAMES — unchanged
- `TrestleCreditAgent.draw()`, `.repay()`, `.record_payment()`, `.get_position()` — unchanged


## USDC ASA CONSTANTS

```python
# Algorand Standard Asset IDs for USDC
USDC_ASA_ID_TESTNET = 10_458_941    # Circle's USDC on Algorand testnet
USDC_ASA_ID_MAINNET = 31_566_704    # Circle's USDC on Algorand mainnet

# USDC has 6 decimal places (same as microALGO).
# $1.00 USDC = 1,000,000 micro-USDC.
# All amounts below are in micro-USDC.

# Per-draw hard caps (same USD value as ALGO caps)
TIER_0_MAX_DRAW_USDC = 100_000    # $0.10
TIER_1_MAX_DRAW_USDC = 500_000    # $0.50
TIER_2_MAX_DRAW_USDC = 2_000_000  # $2.00
TIER_3_MAX_DRAW_USDC = 5_000_000  # $5.00

# Daily draw caps (same USD value as ALGO daily caps)
TIER_0_DAILY_CAP_USDC = 500_000     # $0.50
TIER_1_DAILY_CAP_USDC = 2_000_000   # $2.00
TIER_2_DAILY_CAP_USDC = 10_000_000  # $10.00
TIER_3_DAILY_CAP_USDC = 25_000_000  # $25.00

# APR basis points: SAME as ALGO (shared tier system)
# TIER_0_APR_BPS = 2400, TIER_1 = 1600, TIER_2 = 900, TIER_3 = 400
```


## STATE SCHEMA CHANGES

The contract must be redeployed with an expanded schema.
This is a NEW contract — do not update-application the existing one.

```
CURRENT (App ID <YOUR_APP_ID>):
  Global: 3 × uint64, 1 × bytes
  Local:  9 × uint64, 0 × bytes

NEW (after USDC support):
  Global: 5 × uint64, 1 × bytes    ← adds usdc_asa_id, usdc_treasury_balance
  Local:  10 × uint64, 0 × bytes   ← adds usdc_outstanding
```

New global state fields:
  `usdc_asa_id`           — uint64: the USDC ASA ID (set by configure_usdc)
  `usdc_treasury_balance` — uint64: micro-USDC balance managed by the contract

New local state field:
  `usdc_outstanding`      — uint64: micro-USDC owed by this agent


## ═══════════════════════════════════════════════════════════════
## FILE 1 — contracts/contract.py
## ═══════════════════════════════════════════════════════════════

### 1.1 — New imports (add to existing import block at top)

```python
from algopy import Asset   # needed for configure_usdc asset parameter
```

Existing imports (gtxn, itxn, arc4, UInt64, etc.) are unchanged.

### 1.2 — New USDC constants (add after existing tier constants)

Add ALL constants listed in the USDC ASA CONSTANTS section above.
Place them after `DAY_IN_ROUNDS` and `ROUNDS_PER_YEAR`.

### 1.3 — New ARC-4 Event Structs (add after existing event structs)

```python
class UsdcDrawn(arc4.Struct):
    agent:       arc4.Address
    amount:      arc4.UInt64
    interest:    arc4.UInt64
    outstanding: arc4.UInt64


class UsdcRepaid(arc4.Struct):
    agent:       arc4.Address
    amount:      arc4.UInt64
    outstanding: arc4.UInt64
```

### 1.4 — Updated class docstring

Change:
  Local state schema:  9 × uint64, 0 × bytes
  Global state schema: 3 × uint64, 1 × bytes

To:
  Local state schema:  10 × uint64, 0 × bytes
  Global state schema: 5 × uint64, 1 × bytes

### 1.5 — New global state declarations (add in class body, after existing)

```python
usdc_asa_id:           GlobalState[UInt64]
usdc_treasury_balance: GlobalState[UInt64]
```

New local state declaration (add after existing 9 local state declarations):
```python
usdc_outstanding: LocalState[UInt64]
```

### 1.6 — Updated __init__ (add initialisations for new state fields)

In `__init__`, add:
```python
self.usdc_asa_id           = GlobalState(UInt64(0))
self.usdc_treasury_balance = GlobalState(UInt64(0))
self.usdc_outstanding      = LocalState(UInt64)
```

### 1.7 — Updated opt_in baremethod

Add `usdc_outstanding` initialisation:
```python
self.usdc_outstanding[Txn.sender] = UInt64(0)
```
The existing 9 initialisations stay unchanged. This becomes the 10th.

### 1.8 — Updated draw() method (ALGO)

Add ONE new assertion at the top of draw(), immediately after the
`stake_amount > 0` check. This prevents cross-denomination debt stacking:

```python
assert (
    self.usdc_outstanding[Txn.sender] == UInt64(0)
), "Repay USDC balance before drawing ALGO"
```

No other change to draw(). All existing logic is unchanged.

### 1.9 — NEW ABI Method: configure_usdc

```python
@arc4.abimethod
def configure_usdc(self, usdc_asset: Asset) -> None:
    """
    Opt the contract into the USDC ASA and store the ASA ID.
    Must be called once before any USDC draws are possible.
    Creator-only.

    Preconditions:
      - Txn.sender == Global.creator_address
      - usdc_asa_id == 0 (not yet configured)

    Mutates:
      - usdc_asa_id = usdc_asset.id
      - Submits inner opt-in AssetTransfer (amount=0) to self

    Emits: nothing.

    Note: The contract address must hold ≥ 200,000 μA extra MBR
    before this call (100,000 μA MBR for the ASA holding, plus
    fees). Fund the contract address with an additional 0.2 ALGO
    before calling configure_usdc.
    """
    assert (
        Txn.sender == Global.creator_address
    ), "Only creator can configure USDC"
    assert (
        self.usdc_asa_id.value == UInt64(0)
    ), "USDC already configured"

    # Opt the contract into the USDC ASA via inner transaction
    # asset_receiver must be the contract itself for opt-in
    itxn.AssetTransfer(
        xfer_asset=usdc_asset.id,
        asset_receiver=Global.current_application_address,
        asset_amount=UInt64(0),
        fee=Global.min_txn_fee,
    ).submit()

    self.usdc_asa_id.value = usdc_asset.id
```

### 1.10 — NEW ABI Method: seed_usdc_treasury

```python
@arc4.abimethod
def seed_usdc_treasury(self, axfer: gtxn.AssetTransferTransaction) -> None:
    """
    Fund the USDC treasury. Creator-only.

    Preconditions:
      - Txn.sender == Global.creator_address
      - axfer.xfer_asset == usdc_asa_id (must be configured first)
      - axfer.asset_receiver == application address
      - axfer.asset_amount > 0

    Mutates:
      - usdc_treasury_balance += axfer.asset_amount

    Emits: nothing.
    """
    assert (
        Txn.sender == Global.creator_address
    ), "Only creator can seed USDC treasury"
    assert (
        self.usdc_asa_id.value > UInt64(0)
    ), "Call configure_usdc first"
    assert (
        axfer.xfer_asset == self.usdc_asa_id.value
    ), "Wrong ASA — must be USDC"
    assert (
        axfer.asset_receiver == Global.current_application_address
    ), "Transfer must be to application address"
    assert axfer.asset_amount > UInt64(0), "Amount must be > 0"

    self.usdc_treasury_balance.value += axfer.asset_amount
```

### 1.11 — NEW ABI Method: draw_usdc

```python
@arc4.abimethod
def draw_usdc(
    self,
    amount: arc4.UInt64,
    attestation_hash: arc4.StaticArray[arc4.Byte, typing.Literal[32]],
) -> None:
    """
    Draw undercollateralised USDC credit from the protocol treasury.
    Sends USDC from the contract to Txn.sender via inner AssetTransfer.

    Follows the same tier caps, daily caps, and attestation logic as
    draw() but in USDC denomination. APR basis points are identical
    (shared tier system). Interest is denominated in micro-USDC.

    Preconditions:
      - usdc_asa_id > 0 (USDC must be configured)
      - Agent not defaulted (is_defaulted == 0)
      - Agent registered (stake_amount > 0)
      - No outstanding ALGO debt (outstanding == 0)
      - No outstanding USDC debt (usdc_outstanding == 0)
      - draw amount <= USDC tier per-draw hard cap
      - USDC daily drawn + amount <= USDC tier daily cap
      - contract USDC treasury has sufficient balance

    Mutates:
      - usdc_outstanding[sender] += amount + interest
      - usdc_treasury_balance -= amount
      - repay_by_round[sender] = current_round + DAY_IN_ROUNDS
        (shared repayment deadline field with ALGO draws)
      - daily_drawn[sender] += amount
        (shared daily accumulator — resets on new window)
      - day_start_round[sender] updated if new window

    Emits: UsdcDrawn
    """
    assert (
        self.usdc_asa_id.value > UInt64(0)
    ), "USDC not configured — call configure_usdc first"
    assert (
        self.is_defaulted[Txn.sender] == UInt64(0)
    ), "Agent is defaulted"
    assert (
        self.stake_amount[Txn.sender] > UInt64(0)
    ), "Agent not registered"
    assert (
        self.outstanding[Txn.sender] == UInt64(0)
    ), "Repay ALGO balance before drawing USDC"
    assert (
        self.usdc_outstanding[Txn.sender] == UInt64(0)
    ), "Agent already has outstanding USDC debt"

    draw_amt = amount.native
    current_round = op.Global.round

    # ── Attestation (same logic as ALGO draw) ──
    if self.skip_attestation.value == UInt64(0):
        expected = op.sha256(
            Txn.sender.bytes
            + amount.bytes
            + op.itob(current_round)
        )
        assert attestation_hash.bytes == expected, "Invalid attestation hash"

    # ── Daily window reset (shared with ALGO daily_drawn) ──
    rounds_in_window = current_round - self.day_start_round[Txn.sender]
    if rounds_in_window >= UInt64(DAY_IN_ROUNDS):
        self.daily_drawn[Txn.sender]     = UInt64(0)
        self.day_start_round[Txn.sender] = current_round

    # ── Tier lookup (shared payment_count) ──
    tier = self._get_tier(self.payment_count[Txn.sender])

    # ── Per-draw hard cap (USDC) ──
    if tier == UInt64(3):
        assert draw_amt <= UInt64(TIER_3_MAX_DRAW_USDC), "Exceeds USDC tier max draw"
    elif tier == UInt64(2):
        assert draw_amt <= UInt64(TIER_2_MAX_DRAW_USDC), "Exceeds USDC tier max draw"
    elif tier == UInt64(1):
        assert draw_amt <= UInt64(TIER_1_MAX_DRAW_USDC), "Exceeds USDC tier max draw"
    else:
        assert draw_amt <= UInt64(TIER_0_MAX_DRAW_USDC), "Exceeds USDC tier max draw"

    # ── Daily cap (USDC) — uses shared daily_drawn accumulator ──
    new_daily = self.daily_drawn[Txn.sender] + draw_amt
    if tier == UInt64(3):
        assert new_daily <= UInt64(TIER_3_DAILY_CAP_USDC), "Exceeds USDC daily cap"
    elif tier == UInt64(2):
        assert new_daily <= UInt64(TIER_2_DAILY_CAP_USDC), "Exceeds USDC daily cap"
    elif tier == UInt64(1):
        assert new_daily <= UInt64(TIER_1_DAILY_CAP_USDC), "Exceeds USDC daily cap"
    else:
        assert new_daily <= UInt64(TIER_0_DAILY_CAP_USDC), "Exceeds USDC daily cap"

    assert (
        self.usdc_treasury_balance.value >= draw_amt
    ), "Insufficient USDC treasury balance"

    # ── Interest (same APR formula, USDC denomination) ──
    if tier == UInt64(3):
        apr_bps = UInt64(TIER_3_APR_BPS)
    elif tier == UInt64(2):
        apr_bps = UInt64(TIER_2_APR_BPS)
    elif tier == UInt64(1):
        apr_bps = UInt64(TIER_1_APR_BPS)
    else:
        apr_bps = UInt64(TIER_0_APR_BPS)

    interest = (draw_amt * apr_bps * UInt64(DAY_IN_ROUNDS)) // (
        UInt64(10_000) * UInt64(ROUNDS_PER_YEAR)
    )

    # ── Send USDC via inner AssetTransfer ──
    itxn.AssetTransfer(
        xfer_asset=self.usdc_asa_id.value,
        asset_receiver=Txn.sender,
        asset_amount=draw_amt,
        fee=Global.min_txn_fee,
    ).submit()

    # ── Update state ──
    self.daily_drawn[Txn.sender]       = new_daily
    self.usdc_outstanding[Txn.sender] += draw_amt + interest
    self.repay_by_round[Txn.sender]    = current_round + UInt64(DAY_IN_ROUNDS)
    self.usdc_treasury_balance.value  -= draw_amt

    arc4.emit(
        UsdcDrawn(
            agent=arc4.Address(Txn.sender),
            amount=arc4.UInt64(draw_amt),
            interest=arc4.UInt64(interest),
            outstanding=arc4.UInt64(self.usdc_outstanding[Txn.sender]),
        )
    )
```

### 1.12 — NEW ABI Method: repay_usdc

```python
@arc4.abimethod
def repay_usdc(self, axfer: gtxn.AssetTransferTransaction) -> None:
    """
    Repay outstanding USDC credit by sending USDC back to the contract.

    Preconditions:
      - axfer.xfer_asset == usdc_asa_id
      - axfer.asset_receiver == application address
      - axfer.asset_amount > 0

    Mutates:
      - usdc_outstanding[sender] reduced by repay_amt (floored at 0)
      - usdc_treasury_balance += repay_amt
      - total_repaid[sender] += repay_amt
        (shared total_repaid accumulator — tracks all repayments)
      - last_payment_round[sender] = current round

    Emits: UsdcRepaid
    """
    assert (
        axfer.xfer_asset == self.usdc_asa_id.value
    ), "Wrong ASA — must be USDC"
    assert (
        axfer.asset_receiver == Global.current_application_address
    ), "Transfer must be to application address"
    assert axfer.asset_amount > UInt64(0), "Repayment must be > 0"

    repay_amt = axfer.asset_amount
    current_outstanding = self.usdc_outstanding[Txn.sender]

    if repay_amt >= current_outstanding:
        self.usdc_outstanding[Txn.sender] = UInt64(0)
    else:
        self.usdc_outstanding[Txn.sender] = current_outstanding - repay_amt

    self.total_repaid[Txn.sender]       += repay_amt
    self.usdc_treasury_balance.value    += repay_amt
    self.last_payment_round[Txn.sender]  = op.Global.round

    arc4.emit(
        UsdcRepaid(
            agent=arc4.Address(Txn.sender),
            amount=arc4.UInt64(repay_amt),
            outstanding=arc4.UInt64(self.usdc_outstanding[Txn.sender]),
        )
    )
```

### 1.13 — NEW ABI Method: get_usdc_position (readonly)

```python
@arc4.abimethod(readonly=True)
def get_usdc_position(
    self, agent: arc4.Address
) -> tuple[
    arc4.UInt64, arc4.UInt64, arc4.UInt64, arc4.UInt64,
]:
    """
    Read an agent's USDC position. Does not modify state.

    Returns (all arc4.UInt64):
      0: usdc_outstanding      — micro-USDC owed
      1: usdc_treasury_balance — total micro-USDC in treasury
      2: usdc_asa_id           — the USDC ASA ID (0 if not configured)
      3: usdc_tier_max_draw    — agent's per-draw USDC cap for their tier
    """
    addr = agent.native
    tier = self._get_tier(self.payment_count[addr])

    if tier == UInt64(3):
        usdc_tier_max_draw = UInt64(TIER_3_MAX_DRAW_USDC)
    elif tier == UInt64(2):
        usdc_tier_max_draw = UInt64(TIER_2_MAX_DRAW_USDC)
    elif tier == UInt64(1):
        usdc_tier_max_draw = UInt64(TIER_1_MAX_DRAW_USDC)
    else:
        usdc_tier_max_draw = UInt64(TIER_0_MAX_DRAW_USDC)

    return (
        arc4.UInt64(self.usdc_outstanding[addr]),
        arc4.UInt64(self.usdc_treasury_balance.value),
        arc4.UInt64(self.usdc_asa_id.value),
        arc4.UInt64(usdc_tier_max_draw),
    )
```

### 1.14 — Update DEPLOYMENT CHECKLIST comment at bottom of contract.py

Replace:
```
# Trestle local state:  9 × uint64, 0 × bytes
# Trestle global state: 3 × uint64, 1 × bytes
```

With:
```
# Trestle local state:  10 × uint64, 0 × bytes
# Trestle global state: 5 × uint64, 1 × bytes (usdc_asa_id and usdc_treasury_balance added)
```

Also add after Step 3 (seed_treasury):
```
# 3b. For USDC support:
#     a. Fund contract with extra 0.2 ALGO for ASA MBR
#     b. call configure_usdc(usdc_asset_id)
#        atc.add_method_call(app_id, "configure_usdc(uint64)void", ...)
#     c. Transfer USDC to contract via seed_usdc_treasury
#        atc.add_method_call(app_id, "seed_usdc_treasury(axfer)void", ...)
```


## ═══════════════════════════════════════════════════════════════
## FILE 2 — contracts/deploy.py
## ═══════════════════════════════════════════════════════════════

Make TWO changes only:

### 2.1 — Update schema declarations (STEP 5)

Change:
```python
global_schema = transaction.StateSchema(num_uints=3, num_byte_slices=1)
local_schema  = transaction.StateSchema(num_uints=9, num_byte_slices=0)
```

To:
```python
global_schema = transaction.StateSchema(num_uints=5, num_byte_slices=1)
local_schema  = transaction.StateSchema(num_uints=10, num_byte_slices=0)
```

### 2.2 — Add STEP 8b: configure_usdc (add after the seed_treasury step)

```python
# ──────────────────────────────────────────────
# STEP 8b — Configure USDC (optional but needed for USDC draws)
# ──────────────────────────────────────────────

CONFIGURE_USDC = os.environ.get("CONFIGURE_USDC", "true").lower() == "true"
USDC_ASA_ID = int(os.environ.get("USDC_ASA_ID", "10458941"))  # testnet default

if CONFIGURE_USDC:
    print(f"\nConfiguring USDC ASA ID: {USDC_ASA_ID}...")

    # The contract needs extra MBR for holding the ASA: 100,000 μA
    # We send it as a plain payment BEFORE calling configure_usdc
    sp_mbr = algod_client.suggested_params()
    mbr_txn = transaction.PaymentTxn(
        sender=deployer_address,
        sp=sp_mbr,
        receiver=APP_ADDRESS,
        amt=200_000,  # 0.2 ALGO covers MBR + buffer
    )
    signed_mbr = mbr_txn.sign(deployer_private_key)
    mbr_txid = algod_client.send_transaction(signed_mbr)
    wait_for_confirmation(algod_client, mbr_txid)
    print(f"  MBR funded. txn: {mbr_txid}")

    # Call configure_usdc
    from algosdk.atomic_transaction_composer import (
        AtomicTransactionComposer,
        AccountTransactionSigner,
    )
    from algosdk import abi

    signer = AccountTransactionSigner(deployer_private_key)
    sp = algod_client.suggested_params()

    atc_usdc = AtomicTransactionComposer()
    atc_usdc.add_method_call(
        app_id=APP_ID,
        method=abi.Method.from_signature("configure_usdc(uint64)void"),
        sender=deployer_address,
        sp=sp,
        signer=signer,
        method_args=[USDC_ASA_ID],
        foreign_assets=[USDC_ASA_ID],  # must include in foreign assets
    )
    result_usdc = atc_usdc.execute(algod_client, wait_rounds=4)
    print(f"  USDC configured. txn: {result_usdc.tx_ids[0]}")
    print(f"  USDC ASA ID: {USDC_ASA_ID}")
else:
    print("\nSkipping USDC configuration (CONFIGURE_USDC=false).")
    print("  Run manually: configure_usdc(usdc_asset_id) after deploy.")
```


## ═══════════════════════════════════════════════════════════════
## FILE 3 — trestle_sdk/criteria.py
## ═══════════════════════════════════════════════════════════════

### 3.1 — Add USDC constants (after existing TIER_DAILY_CAP list)

```python
# ── USDC denomination constants (micro-USDC, 6 decimals) ──────────────────────
# USDC has 6 decimal places. $1.00 = 1,000,000 micro-USDC.
# Caps are equivalent USD values to ALGO caps.

USDC_ASA_ID_TESTNET: int = 10_458_941
USDC_ASA_ID_MAINNET: int = 31_566_704

TIER_MAX_DRAW_USDC:  list[int] = [100_000, 500_000, 2_000_000, 5_000_000]
TIER_DAILY_CAP_USDC: list[int] = [500_000, 2_000_000, 10_000_000, 25_000_000]
# APR basis points are SHARED with ALGO (same TIER_APR_BPS list)
```

### 3.2 — Add two new functions (after existing calculate_interest function)

```python
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
```

### 3.3 — Update __all__ export list if one exists, or leave as-is.


## ═══════════════════════════════════════════════════════════════
## FILE 4 — trestle_sdk/chain.py
## ═══════════════════════════════════════════════════════════════

### 4.1 — Add new ABI Method objects (after existing METHOD_ constants)

```python
METHOD_DRAW_USDC = Method.from_signature("draw_usdc(uint64,byte[32])void")

METHOD_REPAY_USDC = Method.from_signature("repay_usdc(axfer)void")

METHOD_GET_USDC_POSITION = Method.from_signature(
    "get_usdc_position(address)(uint64,uint64,uint64,uint64)"
)

METHOD_CONFIGURE_USDC = Method.from_signature("configure_usdc(uint64)void")

METHOD_SEED_USDC_TREASURY = Method.from_signature("seed_usdc_treasury(axfer)void")
```

### 4.2 — Add get_usdc_position function (after get_position function)

```python
def get_usdc_position(
    algod_client: algod.AlgodClient,
    app_id: int,
    agent_address: str,
    signer: AccountTransactionSigner,
) -> dict:
    """Read an agent's USDC credit position via get_usdc_position(address).

    Uses atc.simulate() — no transaction submitted, no fees paid.

    Args:
        algod_client: Connected AlgodClient.
        app_id: Trestle contract application ID.
        agent_address: Algorand address to query.
        signer: AccountTransactionSigner for the agent wallet.

    Returns:
        Dict with keys:
            ``usdc_outstanding``      — micro-USDC owed by this agent
            ``usdc_treasury_balance`` — total micro-USDC in treasury
            ``usdc_asa_id``           — USDC ASA ID (0 if not configured)
            ``usdc_tier_max_draw``    — per-draw cap for agent's tier (micro-USDC)
    """
    sp = algod_client.suggested_params()
    atc = AtomicTransactionComposer()
    atc.add_method_call(
        app_id=app_id,
        method=METHOD_GET_USDC_POSITION,
        sender=agent_address,
        sp=sp,
        signer=signer,
        method_args=[agent_address],
    )
    sim_result = atc.simulate(algod_client)
    values = sim_result.abi_results[0].return_value  # list of 4 ints

    return {
        "usdc_outstanding":      int(values[0]),
        "usdc_treasury_balance": int(values[1]),
        "usdc_asa_id":           int(values[2]),
        "usdc_tier_max_draw":    int(values[3]),
    }
```

### 4.3 — Add do_draw_usdc function (after do_draw function)

```python
def do_draw_usdc(
    algod_client: algod.AlgodClient,
    app_id: int,
    agent_address: str,
    private_key: str,
    amount_microusdc: int,
    attestation_hash: bytes,
    usdc_asa_id: int,
) -> str:
    """Call draw_usdc(uint64, byte[32]) on the Trestle contract.

    The contract sends USDC ASA to Txn.sender via inner AssetTransfer.
    The agent must already hold the USDC ASA (opted into the ASA) to
    receive it. If the agent hasn't opted into USDC, this call will fail.

    Args:
        algod_client: Connected AlgodClient.
        app_id: Trestle contract application ID.
        agent_address: Sending agent's Algorand address.
        private_key: Agent's private key.
        amount_microusdc: Draw amount in micro-USDC.
        attestation_hash: Exactly 32 bytes (bytes(32) in demo mode).
        usdc_asa_id: USDC ASA ID (10_458_941 on testnet).

    Returns:
        Confirmed transaction ID string.

    Raises:
        AssertionError: If attestation_hash is not 32 bytes.
    """
    assert len(attestation_hash) == 32, (
        f"attestation_hash must be exactly 32 bytes, got {len(attestation_hash)}"
    )

    sp = algod_client.suggested_params()
    signer = AccountTransactionSigner(private_key)
    atc = AtomicTransactionComposer()
    atc.add_method_call(
        app_id=app_id,
        method=METHOD_DRAW_USDC,
        sender=agent_address,
        sp=sp,
        signer=signer,
        method_args=[amount_microusdc, attestation_hash],
        foreign_assets=[usdc_asa_id],   # must include USDC ASA in foreign assets
    )
    result = atc.execute(algod_client, 4)
    return result.tx_ids[0]
```

### 4.4 — Add do_repay_usdc function (after do_repay function)

```python
def do_repay_usdc(
    algod_client: algod.AlgodClient,
    app_id: int,
    agent_address: str,
    private_key: str,
    amount_microusdc: int,
    usdc_asa_id: int,
) -> str:
    """Call repay_usdc(axfer) on the Trestle contract.

    The repay_usdc method takes an asset transfer transaction as its ABI
    argument. The AssetTransferTxn sends micro-USDC directly to the
    contract's escrow address.

    Args:
        algod_client: Connected AlgodClient.
        app_id: Trestle contract application ID.
        agent_address: Repaying agent's Algorand address.
        private_key: Agent's private key.
        amount_microusdc: Amount to repay in micro-USDC.
        usdc_asa_id: USDC ASA ID (10_458_941 on testnet).

    Returns:
        Confirmed transaction ID string.
    """
    sp = algod_client.suggested_params()
    signer = AccountTransactionSigner(private_key)
    app_address = logic.get_application_address(app_id)

    # Build the AssetTransferTxn that sends USDC to the contract
    axfer_txn = transaction.AssetTransferTxn(
        sender=agent_address,
        sp=sp,
        receiver=app_address,
        amt=amount_microusdc,
        index=usdc_asa_id,
    )
    axfer_tws = TransactionWithSigner(axfer_txn, signer)

    atc = AtomicTransactionComposer()
    atc.add_method_call(
        app_id=app_id,
        method=METHOD_REPAY_USDC,
        sender=agent_address,
        sp=sp,
        signer=signer,
        method_args=[axfer_tws],
        foreign_assets=[usdc_asa_id],
    )
    result = atc.execute(algod_client, 4)
    return result.tx_ids[0]
```

### 4.5 — Add ensure_usdc_opted_in helper (after do_repay_usdc)

```python
def ensure_usdc_opted_in(
    algod_client: algod.AlgodClient,
    agent_address: str,
    private_key: str,
    usdc_asa_id: int,
) -> bool:
    """Opt an agent wallet into the USDC ASA if not already opted in.

    An agent must hold the USDC ASA to receive draws. This function checks
    their current holdings and submits an opt-in (zero-amount self-transfer)
    if needed.

    Args:
        algod_client: Connected AlgodClient.
        agent_address: Agent's Algorand address.
        private_key: Agent's private key.
        usdc_asa_id: USDC ASA ID (10_458_941 on testnet).

    Returns:
        True if already opted in (no action taken).
        False if opt-in was submitted and confirmed.
    """
    acct_info = algod_client.account_info(agent_address)
    for asset in acct_info.get("assets", []):
        if asset["asset-id"] == usdc_asa_id:
            return True  # already opted in

    # Submit opt-in: zero-amount self-transfer
    sp = algod_client.suggested_params()
    signer = AccountTransactionSigner(private_key)
    opt_in_txn = transaction.AssetTransferTxn(
        sender=agent_address,
        sp=sp,
        receiver=agent_address,
        amt=0,
        index=usdc_asa_id,
    )
    opt_in_tws = TransactionWithSigner(opt_in_txn, signer)

    atc = AtomicTransactionComposer()
    atc.add_transaction(opt_in_tws)
    atc.execute(algod_client, 4)
    return False
```


## ═══════════════════════════════════════════════════════════════
## FILE 5 — trestle_sdk/agent.py
## ═══════════════════════════════════════════════════════════════

### 5.1 — Update imports from chain.py (add to existing import block)

Add to the existing chain.py import:
```python
    get_usdc_position,
    do_draw_usdc,
    do_repay_usdc,
    ensure_usdc_opted_in,
```

### 5.2 — Add USDC ASA ID constants (after ProtocolConfig class, before TrestleCreditAgent)

```python
# USDC ASA IDs for reference. Pass the correct one to draw_usdc().
USDC_ASA_ID_TESTNET: int = 10_458_941
USDC_ASA_ID_MAINNET: int = 31_566_704
```

### 5.3 — Add three new methods to TrestleCreditAgent (after record_payment method)

```python
# ── USDC methods ──────────────────────────────────────────────────────────────

def get_usdc_position(self) -> dict:
    """Read the agent's current USDC credit position.

    Returns:
        Dict with keys: ``usdc_outstanding``, ``usdc_treasury_balance``,
        ``usdc_asa_id``, ``usdc_tier_max_draw`` — all ``int``.
    """
    return get_usdc_position(
        self.algod_client, self.app_id, self.address, self.signer
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
        app_id=self.app_id,
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
        app_id=self.app_id,
        agent_address=self.address,
        private_key=self.private_key,
        amount_microusdc=amount_microusdc,
        usdc_asa_id=usdc_asa_id,
    )
    return {"txid": txid, "repaid_microusdc": amount_microusdc}
```

### 5.4 — Update class docstring to mention USDC

In the TrestleCreditAgent class docstring, add after the repay() example:
```
    # Draw USDC credit (same oracle, same tier, different denomination)
    result_usdc = agent.draw_usdc(
        amount_microusdc=100_000,  # $0.10 USDC
        task_description="Fetch ETH/USD price from CoinGecko",
        expected_return_microusdc=150_000,
    )
    agent.repay_usdc(result_usdc["total_repayable_usdc"])
```


## ═══════════════════════════════════════════════════════════════
## FILE 6 — trestle_sdk/__init__.py
## ═══════════════════════════════════════════════════════════════

### 6.1 — Add new exports

Add to the `from .criteria import` line:
```python
from .criteria import (
    get_tier, calculate_interest, tier_name,
    calculate_interest_usdc, max_draw_usdc, daily_cap_usdc,
    USDC_ASA_ID_TESTNET, USDC_ASA_ID_MAINNET,
)
```

Add to `__all__`:
```python
    "calculate_interest_usdc",
    "max_draw_usdc",
    "daily_cap_usdc",
    "USDC_ASA_ID_TESTNET",
    "USDC_ASA_ID_MAINNET",
```


## ═══════════════════════════════════════════════════════════════
## FILE 7 — frontend/src/utils/contract.js
## ═══════════════════════════════════════════════════════════════

### 7.1 — Add USDC constants (after existing APP_ID, APP_ADDRESS)

```javascript
// USDC ASA IDs
export const USDC_ASA_ID_TESTNET = 10_458_941;
export const USDC_ASA_ID_MAINNET = 31_566_704;
export const USDC_ASA_ID = USDC_ASA_ID_TESTNET;  // switch for mainnet

// USDC has 6 decimal places — same as microALGO
export const toMicroUsdc = (usdc) => Math.round(usdc * 1_000_000);
export const fromMicroUsdc = (micro) => micro / 1_000_000;
```

### 7.2 — Add new ABI method strings to ABI_METHODS object

```javascript
export const ABI_METHODS = {
  // ... existing methods unchanged ...

  // USDC methods
  DRAW_USDC:           "draw_usdc(uint64,byte[32])void",
  REPAY_USDC:          "repay_usdc(axfer)void",
  GET_USDC_POSITION:   "get_usdc_position(address)(uint64,uint64,uint64,uint64)",
  CONFIGURE_USDC:      "configure_usdc(uint64)void",
  SEED_USDC_TREASURY:  "seed_usdc_treasury(axfer)void",
};
```


## ═══════════════════════════════════════════════════════════════
## FILE 8 — frontend/src/context/ContractContext.jsx
## ═══════════════════════════════════════════════════════════════

### 8.1 — Extend DEFAULT_POSITION with USDC fields

Add to DEFAULT_POSITION:
```javascript
const DEFAULT_POSITION = {
  // ... existing fields unchanged ...
  // USDC fields
  usdcOutstanding:     0n,
  usdcTreasuryBalance: 0n,
  usdcAsaId:           0n,
  usdcTierMaxDraw:     0n,
};
```

### 8.2 — Add fetchUsdcPosition function (after fetchPosition)

```javascript
const fetchUsdcPosition = useCallback(async () => {
  if (!address) return;
  try {
    const sp = await algodClient.getTransactionParams().do();
    const atc = new algosdk.AtomicTransactionComposer();
    const signer = makeSigner();
    atc.addMethodCall({
      appID:      APP_ID,
      method:     algosdk.ABIMethod.fromSignature(ABI_METHODS.GET_USDC_POSITION),
      sender:     address,
      suggestedParams: sp,
      signer,
      methodArgs: [address],
    });
    const simResult = await atc.simulate(algodClient);
    const vals = simResult.methodResults[0].returnValue;
    setPosition(prev => ({
      ...prev,
      usdcOutstanding:     BigInt(vals[0]),
      usdcTreasuryBalance: BigInt(vals[1]),
      usdcAsaId:           BigInt(vals[2]),
      usdcTierMaxDraw:     BigInt(vals[3]),
    }));
  } catch (err) {
    console.warn("fetchUsdcPosition failed:", err.message);
  }
}, [address, makeSigner]);
```

### 8.3 — Add callDrawUsdc function (after callDraw)

```javascript
const callDrawUsdc = useCallback(async (amountMicroUsdc, taskDescription, expectedReturn) => {
  setLoading(true);
  setError(null);
  try {
    const sp = await algodClient.getTransactionParams().do();
    const signer = makeSigner();
    const atc = new algosdk.AtomicTransactionComposer();

    atc.addMethodCall({
      appID:      APP_ID,
      method:     algosdk.ABIMethod.fromSignature(ABI_METHODS.DRAW_USDC),
      sender:     address,
      suggestedParams: sp,
      signer,
      methodArgs: [amountMicroUsdc, new Uint8Array(32)],  // demo mode: 32 zero bytes
      foreignAssets: [USDC_ASA_ID],
    });

    const result = await atc.execute(algodClient, 4);
    addActivity(`USDC draw: ${amountMicroUsdc} micro-USDC. txn: ${result.txIDs[0]}`);
    await fetchPosition();
    await fetchUsdcPosition();
    return result.txIDs[0];
  } catch (err) {
    const msg = parseError(err);
    setError(msg);
    throw new Error(msg);
  } finally {
    setLoading(false);
  }
}, [address, makeSigner, fetchPosition, fetchUsdcPosition, addActivity]);
```

### 8.4 — Add callRepayUsdc function (after callRepay)

```javascript
const callRepayUsdc = useCallback(async (amountMicroUsdc) => {
  setLoading(true);
  setError(null);
  try {
    const sp = await algodClient.getTransactionParams().do();
    const signer = makeSigner();
    const appAddress = algosdk.getApplicationAddress(APP_ID);

    // Build the AssetTransferTxn that sends USDC to the contract
    const axferTxn = algosdk.makeAssetTransferTxnWithSuggestedParamsFromObject({
      sender:    address,
      receiver:  appAddress,
      amount:    amountMicroUsdc,
      assetIndex: USDC_ASA_ID,
      suggestedParams: sp,
    });

    const atc = new algosdk.AtomicTransactionComposer();
    atc.addMethodCall({
      appID:      APP_ID,
      method:     algosdk.ABIMethod.fromSignature(ABI_METHODS.REPAY_USDC),
      sender:     address,
      suggestedParams: sp,
      signer,
      methodArgs: [{ txn: axferTxn, signer }],
      foreignAssets: [USDC_ASA_ID],
    });

    const result = await atc.execute(algodClient, 4);
    addActivity(`USDC repay: ${amountMicroUsdc} micro-USDC. txn: ${result.txIDs[0]}`);
    await fetchPosition();
    await fetchUsdcPosition();
    return result.txIDs[0];
  } catch (err) {
    const msg = parseError(err);
    setError(msg);
    throw new Error(msg);
  } finally {
    setLoading(false);
  }
}, [address, makeSigner, fetchPosition, fetchUsdcPosition, addActivity]);
```

### 8.5 — Add fetchUsdcPosition to the useEffect auto-refresh

In the existing useEffect that calls fetchPosition every 15 seconds, also call:
```javascript
await fetchUsdcPosition();
```

### 8.6 — Add new methods to the context value object

```javascript
return {
  // ... existing values unchanged ...
  fetchUsdcPosition,
  callDrawUsdc,
  callRepayUsdc,
};
```

### 8.7 — Add parseError entries for USDC errors

Add to the parseError function:
```javascript
if (msg.includes("USDC not configured"))
  return "USDC not set up on this contract — call configure_usdc first";
if (msg.includes("Repay USDC balance before drawing ALGO"))
  return "Repay your outstanding USDC loan before drawing ALGO";
if (msg.includes("Repay ALGO balance before drawing USDC"))
  return "Repay your outstanding ALGO loan before drawing USDC";
if (msg.includes("Insufficient USDC treasury"))
  return "Protocol USDC treasury is empty — contact admin";
if (msg.includes("Exceeds USDC tier max draw"))
  return "Amount exceeds your USDC draw limit for this tier";
if (msg.includes("Wrong ASA"))
  return "Wrong asset sent — must be USDC";
```


## ═══════════════════════════════════════════════════════════════
## FILE 9 — frontend/src/components/Dashboard.jsx
## ═══════════════════════════════════════════════════════════════

### 9.1 — Import USDC utilities

Add to existing imports:
```javascript
import { USDC_ASA_ID, fromMicroUsdc } from "../utils/contract.js";
```

### 9.2 — Destructure new context values

Add to existing useContract() destructuring:
```javascript
const {
  // ... existing ...
  callDrawUsdc,
  callRepayUsdc,
} = useContract();
```

### 9.3 — Add USDC state (after existing state declarations)

```javascript
const [usdcDrawAmount, setUsdcDrawAmount] = useState("");
const [usdcRepayAmount, setUsdcRepayAmount] = useState("");
const [usdcLoading, setUsdcLoading] = useState(false);
```

### 9.4 — Add USDC section to dashboard JSX

Add a new card section after the existing ALGO Draw/Repay section.
Style it to match the existing design system.

```jsx
{/* ── USDC Section ─────────────────────────────────────────── */}
<div className="card">
  <h3 className="card-title">USDC Credit</h3>

  {/* USDC Position Stats */}
  <div className="stat-row">
    <StatCard
      label="USDC Outstanding"
      value={`$${fromMicroUsdc(Number(position.usdcOutstanding)).toFixed(4)}`}
      sub="micro-USDC owed"
    />
    <StatCard
      label="USDC Draw Limit"
      value={`$${fromMicroUsdc(Number(position.usdcTierMaxDraw)).toFixed(2)}`}
      sub="per transaction"
    />
    <StatCard
      label="USDC Treasury"
      value={`$${fromMicroUsdc(Number(position.usdcTreasuryBalance)).toFixed(2)}`}
      sub="available to draw"
    />
  </div>

  {/* USDC Draw */}
  <div className="action-row">
    <Input
      type="number"
      placeholder="micro-USDC (e.g. 100000 = $0.10)"
      value={usdcDrawAmount}
      onChange={e => setUsdcDrawAmount(e.target.value)}
    />
    <Button
      onClick={async () => {
        setUsdcLoading(true);
        try {
          await callDrawUsdc(
            parseInt(usdcDrawAmount),
            "USDC credit draw from Trestle dashboard",
            parseInt(usdcDrawAmount) * 2,
          );
          setUsdcDrawAmount("");
        } finally {
          setUsdcLoading(false);
        }
      }}
      disabled={usdcLoading || !usdcDrawAmount}
    >
      Draw USDC
    </Button>
  </div>

  {/* USDC Repay */}
  <div className="action-row">
    <Input
      type="number"
      placeholder="micro-USDC to repay"
      value={usdcRepayAmount}
      onChange={e => setUsdcRepayAmount(e.target.value)}
    />
    <Button
      variant="secondary"
      onClick={async () => {
        setUsdcLoading(true);
        try {
          await callRepayUsdc(parseInt(usdcRepayAmount));
          setUsdcRepayAmount("");
        } finally {
          setUsdcLoading(false);
        }
      }}
      disabled={usdcLoading || !usdcRepayAmount}
    >
      Repay USDC
    </Button>
    <Button
      variant="ghost"
      onClick={() => setUsdcRepayAmount(String(position.usdcOutstanding))}
      disabled={position.usdcOutstanding === 0n}
    >
      Fill Outstanding
    </Button>
  </div>

  {position.usdcAsaId === 0n && (
    <p className="warning-text">
      USDC not configured on this contract. Contact the protocol admin.
    </p>
  )}
</div>
```


## ═══════════════════════════════════════════════════════════════
## FILE 10 — tests/test_criteria.py  (ADD, do not replace)
## ═══════════════════════════════════════════════════════════════

Add these test classes at the END of the existing test file:

```python
# ══════════════════════════════════════════════════════════════════
# USDC criteria tests
# ══════════════════════════════════════════════════════════════════

from trestle_sdk.criteria import (
    max_draw_usdc, daily_cap_usdc, calculate_interest_usdc,
    TIER_MAX_DRAW_USDC, TIER_DAILY_CAP_USDC,
    USDC_ASA_ID_TESTNET, USDC_ASA_ID_MAINNET,
)


class TestUsdcConstants:

    def test_usdc_testnet_asa_id(self):
        assert USDC_ASA_ID_TESTNET == 10_458_941

    def test_usdc_mainnet_asa_id(self):
        assert USDC_ASA_ID_MAINNET == 31_566_704

    def test_usdc_max_draw_same_usd_as_algo(self):
        """USDC and ALGO caps have the same USD value (both use 6 decimals)."""
        from trestle_sdk.criteria import TIER_MAX_DRAW
        assert TIER_MAX_DRAW_USDC == TIER_MAX_DRAW

    def test_usdc_daily_cap_same_usd_as_algo(self):
        from trestle_sdk.criteria import TIER_DAILY_CAP
        assert TIER_DAILY_CAP_USDC == TIER_DAILY_CAP

    def test_all_tier_lists_same_length(self):
        assert len(TIER_MAX_DRAW_USDC)  == 4
        assert len(TIER_DAILY_CAP_USDC) == 4


class TestMaxDrawUsdc:

    def test_tier_0_usdc_max_draw(self):
        assert max_draw_usdc(0) == 100_000

    def test_tier_1_usdc_max_draw(self):
        assert max_draw_usdc(1) == 500_000

    def test_tier_2_usdc_max_draw(self):
        assert max_draw_usdc(2) == 2_000_000

    def test_tier_3_usdc_max_draw(self):
        assert max_draw_usdc(3) == 5_000_000

    def test_increases_with_tier(self):
        for t in range(3):
            assert max_draw_usdc(t) < max_draw_usdc(t + 1)


class TestCalculateInterestUsdc:

    def test_zero_amount_zero_interest(self):
        for tier in range(4):
            assert calculate_interest_usdc(0, tier) == 0

    def test_formula_matches_algo_formula_for_same_amount(self):
        """Same formula, same amount → same interest regardless of denomination."""
        from trestle_sdk.criteria import calculate_interest
        for tier in range(4):
            assert calculate_interest_usdc(50_000, tier) == calculate_interest(50_000, tier)

    def test_higher_tier_lower_interest(self):
        amount = 100_000
        interests = [calculate_interest_usdc(amount, t) for t in range(4)]
        for i in range(3):
            assert interests[i] >= interests[i + 1]

    def test_non_negative(self):
        for tier in range(4):
            assert calculate_interest_usdc(500_000, tier) >= 0
```


## ═══════════════════════════════════════════════════════════════
## CRITICAL IMPLEMENTATION NOTES
## ═══════════════════════════════════════════════════════════════

### Note 1 — foreign_assets in ATC calls

Every ATC method call that touches the USDC ASA must include:
```python
foreign_assets=[usdc_asa_id]
```
Without this, the AVM rejects the transaction with "asset not in foreign assets array."
This applies to: draw_usdc, repay_usdc, configure_usdc, seed_usdc_treasury.

### Note 2 — Agent must opt into USDC ASA before receiving draws

The `ensure_usdc_opted_in()` helper handles this. The agent's wallet needs to
hold the USDC ASA before `draw_usdc()` sends them any. If they haven't opted in,
the inner AssetTransfer in `draw_usdc()` will fail with "receiver not opted in."

### Note 3 — Contract MBR for holding ASA

Every Algorand account (including contracts) must hold an extra 100,000 μA MBR
per ASA it holds. The deploy.py STEP 8b sends 200,000 μA before configure_usdc
to cover this. If the contract has insufficient balance, configure_usdc will fail.

### Note 4 — gtxn.AssetTransferTransaction in algopy

In algopy (Algorand Python), the type for accepting group asset transfers is:
```python
gtxn.AssetTransferTransaction
```
NOT `gtxn.AssetTransfer` (that doesn't exist in algopy). Use:
```python
from algopy import gtxn
def repay_usdc(self, axfer: gtxn.AssetTransferTransaction) -> None:
```

### Note 5 — Cross-denomination debt stacking prevention

Both draw() and draw_usdc() now check for the other denomination's outstanding:
- draw()      checks: usdc_outstanding[sender] == 0
- draw_usdc() checks: outstanding[sender] == 0 AND usdc_outstanding[sender] == 0

This is intentional. The oracle enforces this via criterion 3, but the contract
also enforces it on-chain as a hard assert. Belt and suspenders.

### Note 6 — Shared daily_drawn accumulator

Both draw() and draw_usdc() share the `daily_drawn` and `day_start_round` local
state fields. This means the daily cap is across both denominations combined.
If an agent draws 100,000 μA ALGO and then 100,000 micro-USDC, their daily_drawn
accumulates both — they can't double the daily cap by using two currencies.

This is the intentional design. If separate daily caps per currency are needed
in future, a new `usdc_daily_drawn` local state field can be added.

### Note 7 — recompile after contract changes

After modifying contract.py, recompile before deploying:
```bash
algokit compile python contracts/contract.py
# or
puyapy contracts/contract.py
```
This regenerates Trestle.approval.teal, Trestle.clear.teal, and Trestle.arc56.json.
The arc56.json is used by the ABI_METHODS in chain.py and the frontend.

### Note 8 — do NOT modify the existing draw() oracle call path

The oracle.evaluate() in agent.draw_usdc() passes `amount_microalgo=amount_microusdc`.
This reuses the same oracle infrastructure — the oracle evaluates generic micro-amounts,
not currency-specific amounts. The task_description prefix "[USDC draw]" tells the oracle
the denomination context. Do not add a `currency` parameter to oracle.evaluate().


## ═══════════════════════════════════════════════════════════════
## SUCCESS CRITERIA — verify all of these before finishing
## ═══════════════════════════════════════════════════════════════

CONTRACT:
[ ] contract.py compiles with: algokit compile python contracts/contract.py
[ ] arc56.json contains all 14 methods (9 existing + 5 new USDC methods)
[ ] deploy.py uses global_schema(num_uints=5) and local_schema(num_uints=10)
[ ] opt_in initialises usdc_outstanding = 0 (10th field)

SDK:
[ ] criteria.py: TIER_MAX_DRAW_USDC, TIER_DAILY_CAP_USDC, calculate_interest_usdc, max_draw_usdc
[ ] chain.py: get_usdc_position, do_draw_usdc, do_repay_usdc, ensure_usdc_opted_in all exist
[ ] agent.py: draw_usdc(), repay_usdc(), get_usdc_position() all exist on TrestleCreditAgent
[ ] python -c "from trestle_sdk import TrestleCreditAgent; a = TrestleCreditAgent.__dict__; print('draw_usdc' in str(a))"

EXISTING TESTS:
[ ] pytest tests/test_criteria.py — all original tests pass (USDC tests added, not replacing)
[ ] pytest tests/test_oracle.py   — all tests pass (oracle unchanged)

USDC TESTS:
[ ] pytest tests/test_criteria.py::TestUsdcConstants     — passes
[ ] pytest tests/test_criteria.py::TestMaxDrawUsdc       — passes
[ ] pytest tests/test_criteria.py::TestCalculateInterestUsdc — passes

FRONTEND:
[ ] Dashboard shows USDC Outstanding, USDC Draw Limit, USDC Treasury stats
[ ] callDrawUsdc and callRepayUsdc exist in ContractContext value
[ ] USDC_ASA_ID exported from contract.js


## ═══════════════════════════════════════════════════════════════
## WHAT NOT TO DO
## ═══════════════════════════════════════════════════════════════

[ ] DO NOT modify METHOD_DRAW, do_draw(), draw() in any way
[ ] DO NOT modify METHOD_REPAY, do_repay(), repay() in any way
[ ] DO NOT modify get_position() return values (still returns 9 values)
[ ] DO NOT change TIER_MAX_DRAW, TIER_APR_BPS, TIER_DAILY_CAP
[ ] DO NOT add a currency parameter to oracle.evaluate()
[ ] DO NOT change the existing tests — only ADD to test_criteria.py
[ ] DO NOT use gtxn.AssetTransfer (wrong) — use gtxn.AssetTransferTransaction
[ ] DO NOT forget foreign_assets=[usdc_asa_id] in all ATC calls touching USDC
[ ] DO NOT deploy using the existing App ID <YOUR_APP_ID> — this is a NEW deploy


## ═══════════════════════════════════════════════════════════════
## EXECUTION ORDER
## ═══════════════════════════════════════════════════════════════

1. contracts/contract.py  — add constants, fields, methods
2. algokit compile python contracts/contract.py  — verify no compile errors
3. contracts/deploy.py    — update schema, add configure_usdc step
4. trestle_sdk/criteria.py — add USDC constants and functions
5. trestle_sdk/chain.py    — add METHOD_ constants and do_ functions
6. trestle_sdk/agent.py    — add draw_usdc, repay_usdc, get_usdc_position
7. trestle_sdk/__init__.py — add new exports
8. tests/test_criteria.py — append USDC test classes
9. frontend/src/utils/contract.js  — add USDC constants
10. frontend/src/context/ContractContext.jsx — add USDC methods
11. frontend/src/components/Dashboard.jsx   — add USDC UI section

Show me the updated contract.py before creating it.
Then proceed through steps 2-11 in order without stopping.
