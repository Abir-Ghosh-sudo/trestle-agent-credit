"""
TrestleUSDC -- Testnet Deployment Script

Deploys the TrestleUSDC ARC-4 contract to Algorand testnet.
Idempotent -- reuses existing app if app_usdc_id.txt is present.

Full deployment flow:
  1. Deploy TrestleUSDC (global 4 x uint64, local 5 x uint64)
  2. Fund contract with 10 ALGO (covers MBR + ASA opt-in + agent stakes)
  3. Opt contract into USDC ASA 10458941 (configure_usdc)
  4. If deployer wallet has USDC, seed the treasury

Usage:
  1. puyapy contracts/trestle_usdc.py --out-dir contracts/
  2. python contracts/deploy_usdc.py
  3. Note the USDC_APP_ID from output

Reads contracts/.env for DEPLOYER_MNEMONIC (same file as main deploy.py).
"""

import base64
import os
from pathlib import Path

import algosdk
from algosdk import account, mnemonic, transaction
from algosdk.atomic_transaction_composer import (
    AccountTransactionSigner,
    AtomicTransactionComposer,
    TransactionWithSigner,
)
from algosdk import abi
from algosdk.v2client import algod
from dotenv import load_dotenv

# ??????????????????????????????????????????????
# STEP 1 -- Load environment
# ??????????????????????????????????????????????

load_dotenv(Path(__file__).parent / ".env")

DEPLOYER_MNEMONIC = os.environ.get("DEPLOYER_MNEMONIC", "")
if not DEPLOYER_MNEMONIC:
    raise SystemExit(
        "ERROR: DEPLOYER_MNEMONIC is not set.\n"
        "  1. cp contracts/.env.example contracts/.env\n"
        "  2. Put YOUR OWN 25-word testnet mnemonic in contracts/.env\n"
        "  Get a free testnet account + funds at:\n"
        "     https://bank.testnet.algorand.network/"
    )
deployer_private_key = mnemonic.to_private_key(DEPLOYER_MNEMONIC)
deployer_address = account.address_from_private_key(deployer_private_key)

print(f"Deployer: {deployer_address}")

# ??????????????????????????????????????????????
# STEP 2 -- Algod client
# ??????????????????????????????????????????????

ALGOD_TOKEN  = ""
ALGOD_SERVER = "https://testnet-api.algonode.cloud"

algod_client = algod.AlgodClient(
    ALGOD_TOKEN, ALGOD_SERVER, headers={"X-API-Key": ALGOD_TOKEN}
)

status = algod_client.status()
print(f"Connected to testnet. Round: {status['last-round']}")

# ??????????????????????????????????????????????
# STEP 3 -- Load compiled TEAL
# ??????????????????????????????????????????????

ARTIFACTS_DIR = Path(__file__).parent

approval_path = ARTIFACTS_DIR / "TrestleUSDC.approval.teal"
clear_path    = ARTIFACTS_DIR / "TrestleUSDC.clear.teal"

for p in [approval_path, clear_path]:
    if not p.exists():
        raise FileNotFoundError(
            f"Missing artifact: {p}\n"
            "Run:  puyapy contracts/trestle_usdc.py --out-dir contracts/"
        )

approval_source = approval_path.read_text()
clear_source    = clear_path.read_text()

# ??????????????????????????????????????????????
# STEP 4 -- Compile TEAL to bytecode
# ??????????????????????????????????????????????


def compile_teal(client: algod.AlgodClient, teal: str) -> bytes:
    """Compile TEAL source to AVM bytecode via algod."""
    result = client.compile(teal)
    return base64.b64decode(result["result"])


approval_bytes = compile_teal(algod_client, approval_source)
clear_bytes    = compile_teal(algod_client, clear_source)

print(f"Approval program: {len(approval_bytes)} bytes")
print(f"Clear program:    {len(clear_bytes)} bytes")

if len(approval_bytes) > 2048:
    raise RuntimeError(
        f"Approval program too large: {len(approval_bytes)} bytes. "
        "Max is 2048 bytes (1 page). Use extra_program_pages for larger contracts."
    )

# ??????????????????????????????????????????????
# STEP 5 -- State schema (must match trestle_usdc.py)
# ??????????????????????????????????????????????

# TrestleUSDC local state:  5 x uint64, 0 x bytes
# TrestleUSDC global state: 4 x uint64, 0 x bytes
global_schema = transaction.StateSchema(num_uints=4, num_byte_slices=0)
local_schema  = transaction.StateSchema(num_uints=5, num_byte_slices=0)

# ??????????????????????????????????????????????
# STEP 6 -- Wait for confirmation helper
# ??????????????????????????????????????????????


def wait_for_confirmation(client: algod.AlgodClient, tx_id: str, max_rounds: int = 10) -> dict:
    """Poll until confirmed or timeout."""
    last_round = client.status()["last-round"]
    start = last_round
    while True:
        try:
            info = client.pending_transaction_info(tx_id)
            if info.get("confirmed-round", 0) > 0:
                print(f"  Confirmed in round {info['confirmed-round']}")
                return info
            if info.get("pool-error"):
                raise RuntimeError(f"Transaction failed: {info['pool-error']}")
        except Exception as e:
            if "not found" not in str(e).lower():
                raise
        client.status_after_block(last_round + 1)
        last_round += 1
        if last_round > start + max_rounds:
            raise TimeoutError(f"Confirmation timeout after {max_rounds} rounds")


# ??????????????????????????????????????????????
# STEP 7 -- Deploy (idempotent)
# ??????????????????????????????????????????????

APP_ID_FILE = Path(__file__).parent / "usdc_app_id.txt"


def get_existing_app_id() -> int | None:
    """Return existing USDC app ID if still live on-chain."""
    if APP_ID_FILE.exists():
        raw = APP_ID_FILE.read_text().strip()
        if not raw:
            return None
        app_id = int(raw)
        try:
            info = algod_client.application_info(app_id)
            if not info.get("deleted", False):
                print(f"Existing TrestleUSDC app found: {app_id}")
                return app_id
            else:
                print(f"App {app_id} was deleted. Redeploying.")
        except Exception:
            print(f"App {app_id} not found on-chain. Redeploying.")
    return None


APP_ID = get_existing_app_id()

if APP_ID is None:
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

    signed = create_txn.sign(deployer_private_key)
    tx_id  = algod_client.send_transaction(signed)
    print(f"Deploy txn sent: {tx_id}")

    result = wait_for_confirmation(algod_client, tx_id)
    APP_ID = result["application-index"]
    print(f"TrestleUSDC deployed. App ID: {APP_ID}")

    APP_ID_FILE.write_text(str(APP_ID))
    print(f"App ID written to {APP_ID_FILE}")
else:
    print(f"Reusing existing TrestleUSDC App ID: {APP_ID}")

APP_ADDRESS = algosdk.logic.get_application_address(APP_ID)
print(f"Contract address: {APP_ADDRESS}")

# ??????????????????????????????????????????????
# STEP 8 -- Fund contract (ALGO for MBR + ASA opt-in)
# ??????????????????????????????????????????????


def get_balance(address: str) -> int:
    return algod_client.account_info(address).get("amount", 0)


current_algo = get_balance(APP_ADDRESS)
# MBR for app (100k) + ASA opt-in (100k) + buffer for agent stakes
FUND_TARGET = 5_000_000  # 5 ALGO

if current_algo < FUND_TARGET:
    fund_amount = FUND_TARGET - current_algo
    sp = algod_client.suggested_params()
    fund_txn = transaction.PaymentTxn(
        sender=deployer_address,
        sp=sp,
        receiver=APP_ADDRESS,
        amt=fund_amount,
    )
    signed = fund_txn.sign(deployer_private_key)
    tx_id  = algod_client.send_transaction(signed)
    print(f"Funding {fund_amount} uALGO to contract...")
    wait_for_confirmation(algod_client, tx_id)
    print(f"  Funded. txn: {tx_id}")
else:
    print(f"Contract already has {current_algo} uALGO -- skipping fund.")

# ??????????????????????????????????????????????
# STEP 9 -- configure_usdc (opt contract into ASA)
# ??????????????????????????????????????????????

USDC_ASA_ID = int(os.environ.get("USDC_ASA_ID", "10458941"))

# Check if already configured
app_info    = algod_client.application_info(APP_ID)
global_state = {}
for kv in app_info.get("params", {}).get("global-state", []):
    key   = base64.b64decode(kv["key"]).decode("utf-8", errors="replace")
    value = kv["value"]
    if value["type"] == 2:
        global_state[key] = value["uint"]
    else:
        global_state[key] = base64.b64decode(value.get("bytes", ""))

usdc_configured = global_state.get("usdc_asa_id", 0)

if usdc_configured == 0:
    print(f"\nConfiguring USDC ASA {USDC_ASA_ID}...")

    # Extra payment for ASA MBR (0.2 ALGO) -- plain payment to contract first
    sp_mbr  = algod_client.suggested_params()
    mbr_txn = transaction.PaymentTxn(
        sender=deployer_address,
        sp=sp_mbr,
        receiver=APP_ADDRESS,
        amt=200_000,
    )
    signed_mbr = mbr_txn.sign(deployer_private_key)
    mbr_txid   = algod_client.send_transaction(signed_mbr)
    wait_for_confirmation(algod_client, mbr_txid)
    print(f"  MBR funded (0.2 ALGO). txn: {mbr_txid}")

    # ABI call: configure_usdc(uint64)void  (Puya compiles Asset as uint64)

    signer = AccountTransactionSigner(deployer_private_key)
    atc    = AtomicTransactionComposer()
    sp     = algod_client.suggested_params()

    atc.add_method_call(
        app_id=APP_ID,
        method=abi.Method.from_signature("configure_usdc(uint64)void"),

        sender=deployer_address,
        sp=sp,
        signer=signer,
        method_args=[USDC_ASA_ID],
        foreign_assets=[USDC_ASA_ID],
    )
    result = atc.execute(algod_client, wait_rounds=4)
    print(f"  USDC configured! txn: {result.tx_ids[0]}")
else:
    print(f"\nUSDC already configured (ASA ID: {usdc_configured}) -- skipping.")

# ??????????????????????????????????????????????
# STEP 10 -- Seed USDC treasury (if wallet has USDC)
# ??????????????????????????????????????????????

def get_usdc_balance(address: str) -> int:
    """Return micro-USDC balance, 0 if not opted-in."""
    try:
        info   = algod_client.account_info(address)
        assets = info.get("assets", [])
        for a in assets:
            if a.get("asset-id") == USDC_ASA_ID:
                return int(a.get("amount", 0))
        return 0
    except Exception:
        return 0


deployer_usdc = get_usdc_balance(deployer_address)
contract_usdc = get_usdc_balance(APP_ADDRESS)

SEED_AMOUNT = int(os.environ.get("USDC_SEED_AMOUNT", "0"))  # micro-USDC

if SEED_AMOUNT == 0:
    # Auto-detect: try to seed up to 10 USDC ($10) if deployer has balance
    SEED_AMOUNT = min(deployer_usdc, 10_000_000)  # max $10

if SEED_AMOUNT > 0 and deployer_usdc >= SEED_AMOUNT:
    print(f"\nSeeding USDC treasury with {SEED_AMOUNT} uUSDC...")

    signer  = AccountTransactionSigner(deployer_private_key)
    sp_seed = algod_client.suggested_params()

    # Build axfer: deployer -> contract
    axfer_txn = transaction.AssetTransferTxn(
        sender=deployer_address,
        sp=sp_seed,
        receiver=APP_ADDRESS,
        amt=SEED_AMOUNT,
        index=USDC_ASA_ID,
    )

    atc_seed = AtomicTransactionComposer()
    atc_seed.add_method_call(
        app_id=APP_ID,
        method=abi.Method.from_signature("seed_treasury(axfer)void"),
        sender=deployer_address,
        sp=sp_seed,
        signer=signer,
        method_args=[TransactionWithSigner(axfer_txn, signer)],
        foreign_assets=[USDC_ASA_ID],
    )
    result_seed = atc_seed.execute(algod_client, wait_rounds=4)
    print(f"  USDC treasury seeded! txn: {result_seed.tx_ids[0]}")
elif deployer_usdc == 0:
    print(
        "\nDeployer has no USDC -- skipping treasury seed.\n"
        "  Get testnet USDC from: https://faucet.circle.com/\n"
        "  Then re-run this script or call seed_treasury() manually."
    )
else:
    print(f"\nSeed amount ({SEED_AMOUNT}) > deployer USDC ({deployer_usdc}) -- skipping seed.")

# ??????????????????????????????????????????????
# STEP 11 -- Summary
# ??????????????????????????????????????????????

final_algo = get_balance(APP_ADDRESS)
final_usdc = get_usdc_balance(APP_ADDRESS)

print("\n" + "=" * 55)
print("TRESTLEUSDC DEPLOYMENT SUMMARY")
print("=" * 55)
print(f"Network:              TESTNET")
print(f"App ID:               {APP_ID}")
print(f"App Address:          {APP_ADDRESS}")
print(f"Deployer:             {deployer_address}")
print(f"USDC ASA ID:          {USDC_ASA_ID}")
print(f"ALGO balance:         {final_algo} uALGO ({final_algo / 1e6:.4f} ALGO)")
print(f"USDC treasury:        {final_usdc} uUSDC (${final_usdc / 1e6:.4f})")
print(f"Explorer:             https://testnet.explorer.perawallet.app/application/{APP_ID}/")
print("=" * 55)
print()
print("Next steps:")
print(f"  1. Update frontend: export const USDC_APP_ID = {APP_ID};")
print(f"  2. Get testnet USDC: https://faucet.circle.com/")
print(f"  3. Seed treasury: python contracts/deploy_usdc.py")
print(f"  4. Run demo: python demo/x402_usdc_demo.py")

