import base64
from algosdk.v2client import algod

algod_client = algod.AlgodClient("", "https://testnet-api.algonode.cloud")
app_id = 764373926

try:
    info = algod_client.application_info(app_id)
    global_state = info.get("params", {}).get("global-state", [])
    print("Global State:")
    for kv in global_state:
        key = base64.b64decode(kv["key"])
        val_info = kv["value"]
        if val_info["type"] == 2:  # uint
            print(f"  {key}: {val_info['uint']}")
        else:
            print(f"  {key}: {val_info['bytes']}")
except Exception as e:
    print(f"Error: {e}")
