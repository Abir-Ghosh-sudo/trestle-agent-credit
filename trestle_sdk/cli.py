"""
cli.py — Trestle CLI: `trestle init` command.

Generates an agent wallet, funds it from the testnet faucet,
opts in to the Trestle contract, registers (stakes ALGO), and
writes credentials to .trestle.env — in under 30 seconds.

Usage:
    trestle init --network testnet
    trestle init --network testnet --stake 2000000
"""

import base64
import json
import os
import sys
import time
from pathlib import Path

# Ensure UTF-8 output on Windows (click Choice help uses → which breaks cp1252)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import click
import requests
from algosdk import account, mnemonic, transaction
from algosdk.atomic_transaction_composer import (
    AccountTransactionSigner,
    AtomicTransactionComposer,
    TransactionWithSigner,
)
from algosdk.transaction import ApplicationOptInTxn
from algosdk.v2client import algod

from trestle_sdk.chain import do_register, make_algod_client

# ── Constants ──────────────────────────────────────────────────────────────────

ALGOD_URLS: dict[str, str] = {
    "testnet": "https://testnet-api.algonode.cloud",
    "mainnet": "https://mainnet-api.algonode.cloud",
}

# Default App IDs point at nothing by default — set TRESTLE_APP_ID to your
# own deployed contract's App ID (see contracts/deploy.py). Falling back to
# a hardcoded App ID here would silently register against someone else's
# deployment instead of your own.
_env_app_id = os.environ.get("TRESTLE_APP_ID", "")
TRESTLE_APP_IDS: dict[str, int | None] = {
    "testnet": int(_env_app_id) if _env_app_id else None,
    "mainnet": None,  # mainnet TBD
}

FAUCET_URL = "https://bank.testnet.algorand.network/"

STAKE_DEFAULT = 1_000_000  # 1 ALGO in microALGO


# ── CLI entry point ────────────────────────────────────────────────────────────

@click.command()
@click.option(
    "--network",
    default="testnet",
    type=click.Choice(["testnet", "mainnet"]),
    help="Algorand network to use",
)
@click.option(
    "--stake",
    default=STAKE_DEFAULT,
    help="Stake amount in microALGO (default 1 ALGO = 1000000)",
)
def init(network: str, stake: int) -> None:
    """Bootstrap a Trestle agent wallet: generate, fund, opt-in, register, save."""

    # ── STEP 1 — Generate keypair ──────────────────────────────────────────────
    click.echo("[1/6] Generating agent keypair...")
    private_key, address = account.generate_account()
    mnemonic_phrase = mnemonic.from_private_key(private_key)
    click.echo(f"      Address: {address}")

    if TRESTLE_APP_IDS[network] is None:
        click.echo(
            f"ERROR: TRESTLE_APP_ID is not set.\n"
            f"       Deploy your own Trestle contract first (contracts/deploy.py),\n"
            f"       then run:  TRESTLE_APP_ID=<your_app_id> trestle init --network {network}"
        )
        sys.exit(1)

    # ── STEP 2 — Fund wallet ───────────────────────────────────────────────────
    click.echo("[2/6] Funding wallet...")

    if network == "testnet":
        click.echo("      Requesting from Algonode testnet faucet...")
        try:
            resp = requests.post(
                FAUCET_URL,
                json={"receiver": address, "amount": 3_000_000},
                timeout=10,
            )
            if resp.status_code == 200:
                click.echo("      Faucet request sent. Waiting...")
            else:
                raise requests.exceptions.RequestException(
                    f"Faucet returned HTTP {resp.status_code}"
                )
        except requests.exceptions.RequestException as exc:
            click.echo(f"      Faucet unavailable ({exc}). Fund manually:")
            click.echo("      https://bank.testnet.algorand.network/")
            click.echo(f"      Address: {address}")
            click.pause("      Press Enter once funded...")

    else:  # mainnet
        click.echo(f"      Fund {address} with ≥2 ALGO, then press Enter...")
        click.pause()

    # ── STEP 3 — Wait for funding to confirm ──────────────────────────────────
    click.echo("[3/6] Waiting 6 rounds for funding to confirm (~6 seconds)...")
    time.sleep(6)

    # Attempt verification; skip silently on algod errors
    try:
        _verify_client = make_algod_client(ALGOD_URLS[network])
        acct_check = _verify_client.account_info(address)
        balance = acct_check.get("amount", 0)
        if balance == 0:
            click.echo(
                "      Balance shows 0. If you just funded, wait a few more seconds "
                "and run trestle init again."
            )
    except Exception:
        pass  # algod unreachable — continue regardless

    # ── STEP 4 — Connect to algod ──────────────────────────────────────────────
    click.echo(f"[4/6] Connecting to Algorand {network}...")
    try:
        algod_client = make_algod_client(ALGOD_URLS[network])
        algod_client.suggested_params()  # sanity-check the connection
    except Exception as exc:
        click.echo(f"      Cannot connect to {network} algod. Check internet connection.")
        click.echo(f"      Error: {exc}")
        sys.exit(1)

    app_id: int = TRESTLE_APP_IDS[network]  # guaranteed non-None by the guard above
    private_key_algosdk = mnemonic.to_private_key(mnemonic_phrase)
    signer = AccountTransactionSigner(private_key_algosdk)

    # ── STEP 5 — Opt in to contract ───────────────────────────────────────────
    click.echo("[5/6] Opting in to Trestle contract...")

    acct_info = algod_client.account_info(address)
    already_opted_in = any(
        ls["id"] == app_id for ls in acct_info.get("apps-local-state", [])
    )

    if already_opted_in:
        click.echo("      Already opted in — skipping.")
    else:
        try:
            sp = algod_client.suggested_params()
            opt_in_txn = ApplicationOptInTxn(
                sender=address,
                sp=sp,
                index=app_id,
            )
            atc = AtomicTransactionComposer()
            atc.add_transaction(TransactionWithSigner(opt_in_txn, signer))
            result = atc.execute(algod_client, wait_rounds=4)
            click.echo(f"      Opted in. Txn: {result.tx_ids[0]}")
        except Exception as exc:
            click.echo(f"      Opt-in failed: {exc}")
            click.echo(
                "      Manual: run contracts/demo_agent.py for step-by-step setup"
            )
            # continue — do not abort

    # ── STEP 6 — Register with Trestle ─────────────────────────────────────────
    click.echo(f"[6/6] Registering with Trestle (staking {stake} \u03bcA)...")

    # Check if already registered by reading local state
    acct_info = algod_client.account_info(address)
    local_state: dict[str, int] = {}
    for ls in acct_info.get("apps-local-state", []):
        if ls["id"] == app_id:
            for kv in ls.get("key-value", []):
                k = base64.b64decode(kv["key"]).decode("utf-8", errors="replace")
                local_state[k] = kv["value"].get("uint", 0)
    existing_stake = local_state.get("stake_amount", 0)

    if existing_stake > 0:
        click.echo(f"      Already registered (stake={existing_stake} \u03bcA) — skipping.")
    else:
        try:
            txid = do_register(
                algod_client=algod_client,
                app_id=app_id,
                agent_address=address,
                private_key=private_key_algosdk,
                stake_microalgo=stake,
            )
            click.echo(f"      Registered! Txn: {txid}")
            click.echo(
                f"      Explorer: https://testnet.explorer.perawallet.app/tx/{txid}"
            )
        except Exception as exc:
            click.echo(f"      Registration failed: {exc}")
            click.echo(
                f"      Manual: export AGENT_MNEMONIC='...' APP_ID={app_id}"
            )
            click.echo("              python contracts/demo_agent.py")
            # continue — still write .trestle.env

    # ── Write .trestle.env ──────────────────────────────────────────────────────
    env_content = (
        f"TRESTLE_ADDRESS={address}\n"
        f"TRESTLE_MNEMONIC={mnemonic_phrase}\n"
        f"TRESTLE_NETWORK={network}\n"
        f"TRESTLE_APP_ID={app_id}\n"
        f"ALGOD_URL={ALGOD_URLS[network]}\n"
    )

    try:
        Path(".trestle.env").write_text(env_content, encoding="utf-8")
        click.echo("      Credentials saved to .trestle.env")
        click.echo("      \u26a0  Keep .trestle.env secret. Add it to .gitignore.")
    except Exception as exc:
        click.echo(f"      WARNING: Could not write .trestle.env: {exc}")

    # Append .trestle.env to .gitignore
    gitignore_path = Path(".gitignore")
    try:
        if gitignore_path.exists():
            existing = gitignore_path.read_text(encoding="utf-8")
            if ".trestle.env" not in existing:
                gitignore_path.write_text(
                    existing.rstrip("\n") + "\n.trestle.env\n",
                    encoding="utf-8",
                )
        else:
            gitignore_path.write_text(".trestle.env\n", encoding="utf-8")
    except Exception as exc:
        click.echo(f"      WARNING: Could not update .gitignore: {exc}")

    # ── Final summary ──────────────────────────────────────────────────────────
    click.echo("")
    click.echo("\u2500" * 50)
    click.echo("Done. Trestle agent ready.")
    click.echo("Tier:     0 (Fresh)")
    click.echo("Max draw: 100,000 \u03bcA (0.10 ALGO) per transaction")
    click.echo("APR:      24%")
    click.echo("Interest: ~1 \u03bcA per 50,000 \u03bcA draw per day")
    click.echo("")
    click.echo("Next steps:")
    click.echo("  1. Set VENICE_API_KEY in your shell or .env")
    click.echo("     export VENICE_API_KEY=your-venice-api-key")
    click.echo("  2. Run the demo:")
    click.echo("     VENICE_API_KEY=your-key python demo/demo_with_skill.py")
    click.echo("  3. Build tier by running record_payment():")
    click.echo(
        "     agent.record_payment() \u2014 10 times \u2192 Tier 1 (0.50 ALGO draws)"
    )

    # ── Oracle API key warning ─────────────────────────────────────────────────
    if (
        os.environ.get("VENICE_API_KEY") is None
        and os.environ.get("ANTHROPIC_API_KEY") is None
    ):
        click.echo("")
        click.echo("\u26a0  No oracle API key detected.")
        click.echo("   Set VENICE_API_KEY to use the risk oracle:")
        click.echo("   Get one free at: https://api.venice.ai")
        click.echo(
            "   Without it, agent.draw() will fail with TrestleCreditError"
        )
