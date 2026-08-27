import os
from algosdk import account, mnemonic, transaction
from algosdk.v2client import algod
from dotenv import load_dotenv

load_dotenv()

AGENT_MNEMONIC = os.environ.get("AGENT_MNEMONIC", "")
algod_client = algod.AlgodClient("", "https://testnet-api.algonode.cloud")

private_key = mnemonic.to_private_key(AGENT_MNEMONIC)
address = account.address_from_private_key(private_key)

sp = algod_client.suggested_params()
current_round = algod_client.status()["last-round"]
target_round = current_round + 3

try:
    txn = transaction.PaymentTxn(
        sender=address,
        sp=sp,
        receiver=address,
        amt=0,
        first_valid_round=target_round,
        last_valid_round=target_round
    )
    print("Txn fv:", txn.first_valid_round)
    print("Txn lv:", txn.last_valid_round)
except Exception as e:
    print(f"Constructor error: {e}")
