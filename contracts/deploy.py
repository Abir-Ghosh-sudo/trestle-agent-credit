"""
Trestle — Testnet Deployment Script

Deploys the compiled Trestle ARC-4 contract to Algorand testnet
using raw algosdk transactions. Idempotent — reuses existing app
if already deployed. Funds the contract treasury with 10 ALGO.

Usage:
    1. pip install -r contracts/requirements.txt
    2. cp contracts/.env.example contracts/.env
    3. Fill DEPLOYER_MNEMONIC in contracts/.env
       (testnet account with at least 15 ALGO)
    4. Compile: puyapy contracts/contract.py
    5. python contracts/deploy.py
    6. Note the APP_ID from output
"""

import base64
import os
from pathlib import Path

import algosdk
from algosdk import account, mnemonic, transaction
from algosdk.v2client import algod
from dotenv import load_dotenv

# ──────────────────────────────────────────────
# STEP 1 — Load environment
# ──────────────────────────────────────────────

load_dotenv(Path(__file__).parent / ".env")

DEPLOYER_MNEMONIC = os.environ.get("DEPLOYER_MNEMONIC", "")
if not DEPLOYER_MNEMONIC:
    raise SystemExit(
        "ERROR: DEPLOYER_MNEMONIC is not set.\n"
        "  1. cp contracts/.env.example contracts/.env\n"
        "  2. Put YOUR OWN 25-word testnet mnemonic in contracts/.env\n"
        "     (never commit this file — it's already in .gitignore)\n"
        "  Get a free testnet account + funds at:\n"
        "     https://bank.testnet.algorand.network/"
    )
deployer_private_key = mnemonic.to_private_key(DEPLOYER_MNEMONIC)
deployer_address = account.address_from_private_key(deployer_private_key)

print(f"Deployer: {deployer_address}")

# ──────────────────────────────────────────────
# STEP 2 — Algod client (testnet via Algonode)
# ──────────────────────────────────────────────

ALGOD_TOKEN = ""  # public node, no token required
ALGOD_SERVER = "https://testnet-api.algonode.cloud"

algod_client = algod.AlgodClient(
    ALGOD_TOKEN,
    ALGOD_SERVER,
    headers={"X-API-Key": ALGOD_TOKEN},
)

status = algod_client.status()
print(f"Connected to testnet. Round: {status['last-round']}")

# ──────────────────────────────────────────────
# STEP 3 — Load compiled TEAL artifacts
# ──────────────────────────────────────────────

ARTIFACTS_DIR = Path(__file__).parent

approval_path = ARTIFACTS_DIR / "Trestle.approval.teal"
clear_path = ARTIFACTS_DIR / "Trestle.clear.teal"

# Verify artifacts exist
for p in [approval_path, clear_path]:
    if not p.exists():
        raise FileNotFoundError(
            f"Missing artifact: {p}\n"
            f"Run:  puyapy contracts/contract.py\n"
            f"or:   algokit compile python contracts/contract.py"
        )

approval_program = approval_path.read_text()
clear_program = clear_path.read_text()

# Check for ARC spec (informational only — not used for raw deploy)
spec_path = ARTIFACTS_DIR / "Trestle.arc56.json"
if not spec_path.exists():
    spec_path = ARTIFACTS_DIR / "Trestle.arc32.json"
if spec_path.exists():
    print(f"ARC spec found: {spec_path.name}")
else:
    print("Warning: No ARC spec JSON found (non-blocking)")

# ──────────────────────────────────────────────
# STEP 4 — Compile TEAL to bytecode
# ──────────────────────────────────────────────


def compile_teal(client: algod.AlgodClient, teal_source: str) -> bytes:
    """Compile TEAL source to AVM bytecode via algod."""
    result = client.compile(teal_source)
    return base64.b64decode(result["result"])


approval_bytes = compile_teal(algod_client, approval_program)
clear_bytes = compile_teal(algod_client, clear_program)

print(f"Approval program: {len(approval_bytes)} bytes")
print(f"Clear program:    {len(clear_bytes)} bytes")

# ──────────────────────────────────────────────
# STEP 5 — State schema (must match contract.py)
# ──────────────────────────────────────────────

# Trestle local state:  9 × uint64, 0 × bytes
# Trestle global state: 3 × uint64, 1 × bytes
global_schema = transaction.StateSchema(num_uints=3, num_byte_slices=1)
local_schema  = transaction.StateSchema(num_uints=9, num_byte_slices=0)

# ──────────────────────────────────────────────
# STEP 6 — Deploy with idempotency check
# ──────────────────────────────────────────────


def wait_for_confirmation(
    client: algod.AlgodClient, tx_id: str, max_rounds: int = 10
) -> dict:
    """Wait until a transaction is confirmed or rejected."""
    last_round = client.status()["last-round"]
    txn_start_round = last_round
    while True:
        try:
            result = client.pending_transaction_info(tx_id)
            if result.get("confirmed-round", 0) > 0:
                print(
                    f"  Confirmed in round {result['confirmed-round']}"
                )
                return result
            if result.get("pool-error"):
                raise Exception(
                    f"Transaction failed: {result['pool-error']}"
                )
        except Exception as e:
            if "not found" not in str(e).lower():
                raise
        client.status_after_block(last_round + 1)
        last_round += 1
        if last_round > txn_start_round + max_rounds:
            raise TimeoutError(
                f"Confirmation timeout after {max_rounds} rounds"
            )


def get_existing_app_id() -> int | None:
    """Check if a previously deployed app is still live."""
    app_id_file = Path(__file__).parent / "app_id.txt"
    if app_id_file.exists():
        raw = app_id_file.read_text().strip()
        if not raw:
            return None
        app_id = int(raw)
        try:
            info = algod_client.application_info(app_id)
            if not info.get("deleted", False):
                print(f"Existing app found: {app_id}")
                return app_id
            else:
                print(f"App {app_id} was deleted. Redeploying.")
        except Exception:
            print(f"App {app_id} not found on-chain. Redeploying.")
    return None


APP_ID = get_existing_app_id()

if APP_ID is None:
    # ── Create new application ──
    sp = algod_client.suggested_params()

    create_txn = transaction.ApplicationCreateTxn(
        sender=deployer_address,
        sp=sp,
        on_complete=transaction.OnComplete.NoOpOC,
        approval_program=approval_bytes,
        clear_program=clear_bytes,
        global_schema=global_schema,
        local_schema=local_schema,
    )

    signed_txn = create_txn.sign(deployer_private_key)
    tx_id = algod_client.send_transaction(signed_txn)
    print(f"Deploy txn sent: {tx_id}")

    result = wait_for_confirmation(algod_client, tx_id)
    APP_ID = result["application-index"]
    print(f"Deployed. App ID: {APP_ID}")

    # ── Save APP_ID ──
    app_id_file = Path(__file__).parent / "app_id.txt"
    app_id_file.write_text(str(APP_ID))
    print(f"App ID written to {app_id_file}")
else:
    print(f"Reusing existing App ID: {APP_ID}")

# ──────────────────────────────────────────────
# STEP 8 — Fund contract treasury (10 ALGO)
# ──────────────────────────────────────────────

APP_ADDRESS = algosdk.logic.get_application_address(APP_ID)
print(f"Contract address: {APP_ADDRESS}")


def get_balance(address: str) -> int:
    """Get the microALGO balance of an address."""
    info = algod_client.account_info(address)
    return info.get("amount", 0)


current_balance = get_balance(APP_ADDRESS)
MIN_BALANCE = 100_000  # MBR for the contract account
TARGET_TREASURY = 1_000_000  # 1 ALGO in microALGO

if current_balance < TARGET_TREASURY:
    fund_amount = TARGET_TREASURY - current_balance

    sp = algod_client.suggested_params()
    fund_txn = transaction.PaymentTxn(
        sender=deployer_address,
        sp=sp,
        receiver=APP_ADDRESS,
        amt=fund_amount,
    )
    
    # We must use seed_treasury method to update the global state tracking
    from algosdk.atomic_transaction_composer import (
        AtomicTransactionComposer,
        TransactionWithSigner,
        AccountTransactionSigner,
    )
    from algosdk import abi
    
    signer = AccountTransactionSigner(deployer_private_key)
    atc = AtomicTransactionComposer()
    
    atc.add_method_call(
        app_id=APP_ID,
        method=abi.Method.from_signature("seed_treasury(pay)void"),
        sender=deployer_address,
        sp=sp,
        signer=signer,
        method_args=[TransactionWithSigner(fund_txn, signer)],
    )
    
    result = atc.execute(algod_client, wait_rounds=4)
    print(f"Funded contract with {fund_amount} microALGO via seed_treasury")
    print(f"   Treasury txn: {result.tx_ids[0]}")
else:
    print(
        f"Contract already funded: "
        f"{current_balance} microALGO "
        f"({current_balance / 1_000_000:.6f} ALGO)"
    )

# ──────────────────────────────────────────────
# STEP 9 — Deployment summary
# ──────────────────────────────────────────────

final_balance = get_balance(APP_ADDRESS)

print("\n" + "=" * 50)
print("TRESTLE DEPLOYMENT SUMMARY")
print("=" * 50)
print(f"Network:          TESTNET")
print(f"App ID:           {APP_ID}")
print(f"App Address:      {APP_ADDRESS}")
print(f"Deployer:         {deployer_address}")
print(f"Treasury balance: {final_balance} microALGO ({final_balance / 1_000_000:.6f} ALGO)")
print(f"Explorer:         https://testnet.explorer.perawallet.app/application/{APP_ID}/")
print("=" * 50)

print(f"\nNext step: copy APP_ID into frontend/src/lib/contract.js")
print(f"  export const APP_ID = {APP_ID};")
print(f"\nOr better — set it via environment variable and skip editing code:")
print(f"  echo 'VITE_APP_ID={APP_ID}' >> frontend/.env")
