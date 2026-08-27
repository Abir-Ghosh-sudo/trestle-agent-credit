import os
import logging
from dotenv import load_dotenv
from trestle_sdk import TrestleCreditAgent, TrestleX402Client

logging.basicConfig(level=logging.INFO)
load_dotenv()

agent = TrestleCreditAgent(
    mnemonic_phrase=os.environ["AGENT_MNEMONIC"],
    app_id=int(os.environ["TRESTLE_APP_ID"]),
    usdc_app_id=int(os.environ["USDC_APP_ID"]),
    demo_mode=True
)

client = TrestleX402Client(agent)
print("Sending request to x402 endpoint...")
try:
    resp = client.get("https://x402.goplausible.xyz/examples/weather")
    print("STATUS:", resp.status_code)
    print("TEXT:", resp.text)
except Exception as e:
    print("ERROR:", e)
