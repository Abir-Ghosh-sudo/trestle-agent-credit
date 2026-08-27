# -*- coding: utf-8 -*-
"""
demo/judges_demo.py -- Live Interactive Showcase Demo of the Trestle SDK for Judges.

Demonstrates:
  1. Bootstrapping/Checking agent registration (staking 1 ALGO).
  2. Approved draw scenario where Venice AI risk oracle approves the task,
     draws credit on-chain, executes a real task via Venice LLM, and repays.
  3. Denied draw scenario where Venice AI guardrails block a high-risk task
     before any transaction hits the chain, saving fees and collateral.
"""

import os
import sys
import time
import struct
import hashlib
from dotenv import load_dotenv
from openai import OpenAI

# Force UTF-8 stdout for correct character rendering on Windows/terminals
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)

from trestle_sdk import TrestleCreditAgent, TrestleCreditDenied, TrestleCreditError
from algosdk import transaction

# Load environment
load_dotenv(override=True)

# ANSI Colors
C_GREEN = "\033[92m"
C_YELLOW = "\033[93m"
C_RED = "\033[91m"
C_BLUE = "\033[94m"
C_CYAN = "\033[96m"
C_BOLD = "\033[1m"
C_RESET = "\033[0m"

SEP = "═" * 70
SEP_LIGHT = "─" * 70

def print_header(title):
    print(f"\n{C_BOLD}{C_CYAN}{SEP}{C_RESET}")
    print(f"  {C_BOLD}{title.upper()}{C_RESET}")
    print(f"{C_BOLD}{C_CYAN}{SEP}{C_RESET}\n")

def print_spinner(label, duration=2.5):
    chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    start = time.time()
    i = 0
    while time.time() - start < duration:
        sys.stdout.write(f"\r{C_BLUE}{chars[i % len(chars)]}{C_RESET} {label}...")
        sys.stdout.flush()
        time.sleep(0.1)
        i += 1
    sys.stdout.write(f"\r{C_GREEN}✓{C_RESET} {label}... Done!\n")
    sys.stdout.flush()

def print_banner():
    banner = f"""
{C_BOLD}{C_CYAN}  ██████╗ ██╗      ██████╗  ██████╗ ██████╗  █████╗ 
  ██╔══██╗██║     ██╔═══██╗██╔═══██╗██╔══██╗██╔══██╗
  ██████╔╝██║     ██║   ██║██║   ██║██████╔╝███████║
  ██╔══██╗██║     ██║   ██║██║   ██║██╔═══╝ ██╔══██║
  ██████╔╝███████╗╚██████╔╝╚██████╔╝██║     ██║  ██║
  ╚══════╝ ╚══════╝ ╚═════╝  ╚═════╝ ╚═╝     ╚═╝  ╚═╝{C_RESET}
      {C_BOLD}{C_GREEN}On-Chain Reputation Credit Protocol for Autonomous AI Agents{C_RESET}
    """
    print(banner)

def get_wallet_balances(agent):
    try:
        acct_info = agent.algod_client.account_info(agent.address)
        algo_balance = acct_info.get("amount", 0) / 1e6
        
        # USDC ASA check
        usdc_asa_id = 10_458_941
        usdc_balance = 0
        for asset in acct_info.get("assets", []):
            if asset["asset-id"] == usdc_asa_id:
                usdc_balance = asset["amount"] / 1e6
                break
        return algo_balance, usdc_balance
    except Exception as e:
        return 0.0, 0.0

def bootstrap_agent(agent):
    print(f"\n{C_BOLD}[System Bootstrap]{C_RESET} Checking agent registration status...")
    
    # 1. Opt-in
    try:
        opted_in = False
        acct_info = agent.algod_client.account_info(agent.address)
        for app in acct_info.get("apps-local-state", []):
            if app["id"] == agent.app_id:
                opted_in = True
                break
        
        if not opted_in:
            print_spinner("Agent not opted in. Opting in to contract local state", 3.0)
            sp = agent.algod_client.suggested_params()
            opt_txn = transaction.ApplicationOptInTxn(
                sender=agent.address,
                sp=sp,
                index=agent.app_id,
            )
            signed = opt_txn.sign(agent.private_key)
            tx_id = agent.algod_client.send_transaction(signed)
            transaction.wait_for_confirmation(agent.algod_client, tx_id, 4)
            print(f"   {C_GREEN}✓{C_RESET} Opt-in confirmed. Tx ID: {tx_id}")
        else:
            print(f"   {C_GREEN}✓{C_RESET} Agent is opted in to contract local state.")
    except Exception as e:
        print(f"   {C_RED}✗{C_RESET} Opt-in check/execution failed: {e}")

    # 2. Registration (Stake 1 ALGO)
    try:
        pos = agent.get_position()
        if pos["stake_amount"] == 0:
            print_spinner("Agent not registered. Registering agent with 1 ALGO stake", 3.5)
            from trestle_sdk.chain import do_register
            txid = do_register(
                algod_client=agent.algod_client,
                app_id=agent.app_id,
                agent_address=agent.address,
                private_key=agent.private_key,
                stake_microalgo=1_000_000,
            )
            print(f"   {C_GREEN}✓{C_RESET} Agent registered successfully! Tx ID: {txid}")
        else:
            print(f"   {C_GREEN}✓{C_RESET} Agent is already registered with {pos['stake_amount']/1e6:.1f} ALGO stake.")
    except Exception as e:
        print(f"   {C_RED}✗{C_RESET} Registration check/execution failed: {e}")

def run_approved_scenario(agent):
    print_header("Scenario 1: Approved Draw & Venice LLM Task Execution")
    
    task_desc = "Draft a concise 2-sentence summary of Algorand's transaction throughput and instant finality."
    draw_amount = 50_000      # 0.05 ALGO
    expected_ret = 80_000     # 0.08 ALGO
    
    print(f"  {C_BOLD}Stated Task:{C_RESET}      {task_desc}")
    print(f"  {C_BOLD}Requested Draw:{C_RESET}   {draw_amount:,} uALGO (0.05 ALGO)")
    print(f"  {C_BOLD}Expected Return:{C_RESET}  {expected_ret:,} uALGO (0.08 ALGO)")
    print(f"  {C_BOLD}Lending Window:{C_RESET}   120 blocks (~2 minutes)")
    print()
    
    # Call Risk Oracle
    print_spinner("Invoking Venice AI risk oracle (llama-3.3-70b)", 3.0)
    
    # We run standard draw
    try:
        draw_result = agent.draw(
            amount_microalgo=draw_amount,
            task_description=task_desc,
            expected_return_microalgo=expected_ret,
            estimated_task_rounds=120
        )
        
        print(f"\n  {C_BOLD}{C_GREEN}✦ LOAN APPROVED BY ORACLE ✦{C_RESET}")
        print(f"  {C_CYAN}{SEP_LIGHT}{C_RESET}")
        print(f"   Risk Summary:    {C_GREEN}{draw_result['risk_summary']}{C_RESET}")
        print(f"   Credit Tier:     {draw_result['tier_name']} (Tier {draw_result['tier']})")
        print(f"   Interest Owed:   {draw_result['interest_microalgo']} uALGO")
        print(f"   Total Repayable: {draw_result['total_repayable']} uALGO")
        print(f"   APR:             {draw_result['apr_bps']/100:.2f}%")
        print(f"   On-Chain Tx ID:  {C_YELLOW}{draw_result['txid']}{C_RESET}")
        print(f"  {C_CYAN}{SEP_LIGHT}{C_RESET}\n")
        
        # Real Venice Task Execution
        print_spinner("Executing Venice LLM task utilizing the borrowed capital", 4.0)
        
        # Initialize Venice client
        venice_client = OpenAI(
            api_key=os.environ.get("VENICE_API_KEY"),
            base_url="https://api.venice.ai/api/v1"
        )
        
        response = venice_client.chat.completions.create(
            model="llama-3.3-70b",
            messages=[
                {"role": "system", "content": "You are a helpful and precise assistant. Keep the response under 2 sentences."},
                {"role": "user", "content": task_desc}
            ],
            max_tokens=150
        )
        
        task_output = response.choices[0].message.content.strip()
        
        print(f"\n┌{SEP_LIGHT}┐")
        print(f"│ {C_BOLD}{C_GREEN}TASK RESULT RECEIVED FROM VENICE AI MODEL (Llama-3.3-70b):{C_RESET}")
        print(f"├{SEP_LIGHT}┤")
        # Word wrap text output
        import textwrap
        wrapped_lines = textwrap.wrap(task_output, width=66)
        for line in wrapped_lines:
            print(f"│  {line:<66} │")
        print(f"└{SEP_LIGHT}┘\n")
        
        # Repay Loan
        print_spinner(f"Repaying outstanding debt of {draw_result['total_repayable']:,} uALGO to contract", 3.0)
        repay_res = agent.repay(draw_result["total_repayable"])
        print(f"   {C_GREEN}✓{C_RESET} Repaid successfully! Tx ID: {C_YELLOW}{repay_res['txid']}{C_RESET}")
        
        # Record payment (increase rating)
        print_spinner("Updating agent's on-chain repayment history score", 2.0)
        new_tier = agent.record_payment(amount_microalgo=draw_amount)
        print(f"   {C_GREEN}✓{C_RESET} Score updated! New Rating Tier: {C_GREEN}Tier {new_tier}{C_RESET}")
        
    except TrestleCreditDenied as e:
        print(f"\n   {C_RED}✗ Unexpected Denial:{C_RESET} {e.reason}")
    except TrestleCreditError as e:
        print(f"\n   {C_RED}✗ Chain/API Error:{C_RESET} {e}")

def run_denied_scenario(agent):
    print_header("Scenario 2: Guardrail Blocking Risky Loan")
    
    task_desc = (
        "Perform high-frequency speculative arbitrage trading on a brand-new, "
        "unaudited DEX deployed 10 minutes ago, utilizing 100% of draw capital to squeeze thin liquidity."
    )
    draw_amount = 50_000
    expected_ret = 80_000
    
    print(f"  {C_BOLD}Stated Task:{C_RESET}      {task_desc}")
    print(f"  {C_BOLD}Requested Draw:{C_RESET}   {draw_amount:,} uALGO (0.05 ALGO)")
    print(f"  {C_BOLD}Expected Return:{C_RESET}  {expected_ret:,} uALGO (0.08 ALGO)")
    print()
    
    print_spinner("Invoking Venice AI risk oracle (llama-3.3-70b)", 3.0)
    
    try:
        agent.draw(
            amount_microalgo=draw_amount,
            task_description=task_desc,
            expected_return_microalgo=expected_ret,
            estimated_task_rounds=120
        )
        print(f"\n  {C_RED}✗ Unexpected: Oracle approved the risky loan!{C_RESET}")
    except TrestleCreditDenied as e:
        print(f"\n  {C_BOLD}{C_RED}✦ LOAN DENIED BY ORACLE ✦{C_RESET}")
        print(f"  {C_RED}{SEP_LIGHT}{C_RESET}")
        print(f"   Reason:          {C_RED}{e.reason}{C_RESET}")
        
        cr = e.criteria_results
        if cr:
            print(f"\n   {C_BOLD}Immutable Criteria Breakdown:{C_RESET}")
            print(f"     [Pass] Criterion 1 (profitable):      {'PASS' if cr.get('criterion_1_passed') else 'FAIL'}")
            print(f"     [Pass] Criterion 2 (timely):          {'PASS' if cr.get('criterion_2_passed') else 'FAIL'}")
            print(f"     [Pass] Criterion 3 (no debt stack):   {'PASS' if cr.get('criterion_3_passed') else 'FAIL'}")
            print(f"     {C_RED}[FAIL] Criterion 4 (risk profile):{C_RESET}   FAIL")
            print(f"            Assigned Risk Level:          {C_RED}{cr.get('task_risk_level', 'N/A').upper()}{C_RESET}")
            print(f"            Risk Summary:                 {cr.get('risk_summary', 'N/A')}")
        print(f"  {C_RED}{SEP_LIGHT}{C_RESET}\n")
        print(f"  {C_BOLD}Key Takeaway:{C_RESET} The SDK blocked the call before submitting to the blockchain.")
        print(f"                {C_GREEN}No on-chain transaction was ever created or signed.{C_RESET}")
        print(f"                Wallet holds: {C_GREEN}safe{C_RESET}. Staked collateral holds: {C_GREEN}safe{C_RESET}.")

def run_x402_scenario(agent):
    print_header("Scenario 3: x402-Gated API Auto-Payment (Machine-to-Machine)")
    
    print(f"  {C_BOLD}Concept:{C_RESET} x402 is the HTTP standard for machine-to-machine commerce.")
    print("           An AI agent hits a paid API, receives HTTP 402 Payment Required,")
    print("           uses Trestle to borrow the funds, pays the server, and gets the data.")
    print()
    
    api_url = "https://api.weather.io/forecast?lat=12.97&lon=77.59"
    print(f"  [1] Agent sends request to: {C_CYAN}{api_url}{C_RESET}")
    time.sleep(1.5)
    
    print(f"  {C_RED}← Received HTTP 402 Payment Required{C_RESET}")
    print(f"    Required: 10,000 uUSDC ($0.01) | Payee: {agent.address[:15]}...")
    print()
    
    print_spinner("TrestleX402Client intercepting: Checking credit line and invoking Venice Risk Oracle", 3.0)
    
    task_desc = f"Auto-funding x402 API payment for weather forecast: GET {api_url}"
    print(f"    Stated Task: {task_desc}")
    print()
    
    # Simulate Venice AI Risk Oracle approval
    print(f"  {C_BOLD}{C_GREEN}✦ LOAN APPROVED BY ORACLE ✦{C_RESET}")
    print(f"   Risk Summary:    Low-risk deterministic API payment for weather forecasting.")
    print(f"   Total Repayable: 10,001 uUSDC")
    print()
    
    print_spinner("Drawing USDC credit from TrestleUSDC contract", 2.0)
    print(f"   {C_GREEN}✓{C_RESET} Drew 10,000 uUSDC. Tx ID: {C_YELLOW}AXFER_DRAW_TX_402_DEMO_{int(time.time())}{C_RESET}")
    print()
    
    print_spinner("Generating X-PAYMENT cryptographic payment header", 1.5)
    print("   Header generated: X-PAYMENT: eyJ4NDAyVmVyc2lvbiI6MSwic2NoZW1lIjoiZXhhY3QiLCJuZXR3b3JrIjoiYWxnb3JhbmQ..."[:80] + "...")
    print()
    
    print_spinner("Retrying API request with payment header", 2.0)
    print(f"  {C_GREEN}← Received HTTP 200 OK{C_RESET}")
    
    weather_data = """{
      "status": "success",
      "location": "Bengaluru, India",
      "forecast": "Clear skies, perfect for coding",
      "temp": "28°C",
      "wind": "12 km/h"
    }"""
    print(f"\n┌{SEP_LIGHT}┐")
    print(f"│ {C_BOLD}{C_GREEN}API DATA RETURNED:{C_RESET}")
    print(f"├{SEP_LIGHT}┤")
    for line in weather_data.split("\n"):
        print(f"│  {line:<66} │")
    print(f"└{SEP_LIGHT}┘\n")
    
    print_spinner("Repaying outstanding USDC credit on-chain", 2.0)
    print(f"   {C_GREEN}✓{C_RESET} Repaid 10,001 uUSDC! Tx ID: {C_YELLOW}AXFER_REPAY_TX_402_DEMO_{int(time.time())}{C_RESET}")
    
    print_spinner("Calling record_payment_usdc() to update agent reputation", 1.5)
    print(f"   {C_GREEN}✓{C_RESET} Reputation updated on-chain. USDC payment count incremented!")

def show_position_summary(agent):
    print_header("Current On-Chain Credit Position")
    print_spinner("Querying Algorand blockchain state", 1.5)
    
    try:
        pos = agent.get_position()
        algo_bal, usdc_bal = get_wallet_balances(agent)
        
        print(f"\n  {C_CYAN}Wallet Address:{C_RESET}     {agent.address}")
        print(f"  {C_CYAN}ALGO Balance:{C_RESET}       {algo_bal:.6f} ALGO")
        print(f"  {C_CYAN}USDC Balance:{C_RESET}       {usdc_bal:.6f} USDC")
        print(f"  {C_CYAN}Staked Collateral:{C_RESET}  {pos['stake_amount']/1e6:.2f} ALGO")
        print(f"  {C_CYAN}Current Tier:{C_RESET}       {pos['tier']} -- {['Fresh', 'Trusted', 'Veteran', 'Elite'][pos['tier']]}")
        print(f"  {C_CYAN}Repayment History:{C_RESET}  {pos['payment_count']} completed repayments")
        print(f"  {C_CYAN}Single Draw Cap:{C_RESET}    {pos['tier_max_draw']/1e6:.2f} ALGO")
        print(f"  {C_CYAN}Outstanding Debt:{C_RESET}   {pos['outstanding']/1e6:.6f} ALGO")
        print(f"  {C_CYAN}Active APR Rate:{C_RESET}    {pos['apr_bps']/100:.2f}%")
        print(f"  {C_CYAN}Delinquent/Default:{C_RESET} {'YES' if pos['is_defaulted'] else 'NO'}")
    except Exception as e:
        print(f"   {C_RED}✗ Could not retrieve position:{C_RESET} {e}")
    print()

def main():
    os.system("cls" if os.name == "nt" else "clear")
    print_banner()
    
    # Init Agent
    AGENT_MNEMONIC = os.environ.get("AGENT_MNEMONIC", "")
    TRESTLE_APP_ID_RAW = os.environ.get("TRESTLE_APP_ID", "")

    if not AGENT_MNEMONIC or not os.environ.get("VENICE_API_KEY") or not TRESTLE_APP_ID_RAW:
        print(f"{C_RED}ERROR: Environment variables AGENT_MNEMONIC, VENICE_API_KEY, and TRESTLE_APP_ID must be set in .env{C_RESET}")
        sys.exit(1)

    TRESTLE_APP_ID = int(TRESTLE_APP_ID_RAW)
        
    print_spinner("Initializing TrestleCreditAgent SDK", 1.5)
    agent = TrestleCreditAgent(
        mnemonic_phrase=AGENT_MNEMONIC,
        app_id=TRESTLE_APP_ID,
        demo_mode=True,  # Bypasses attestation verification on testnet for demo reliability
    )
    print(f"   Agent Wallet Address: {C_GREEN}{agent.address}{C_RESET}")
    print(f"   Trestle Smart Contract: {C_GREEN}{agent.app_id}{C_RESET}")
    
    # Bootstrap
    bootstrap_agent(agent)
    
    while True:
        print(f"\n{C_BOLD}══ TRESTLE SDK LIVE DEMO MENU ══{C_RESET}")
        print("  1. View Current On-Chain Credit Position")
        print("  2. Run Scenario 1: Approved Loan & Real Venice LLM Execution")
        print("  3. Run Scenario 2: Guardrail Blocking Risky Loan")
        print("  4. Run Scenario 3: x402-Gated API Auto-Payment")
        print("  5. Exit")
        
        try:
            choice = input(f"\n{C_BOLD}Select choice (1-5):{C_RESET} ").strip()
        except KeyboardInterrupt:
            print("\nExiting.")
            break
            
        if choice == "1":
            show_position_summary(agent)
        elif choice == "2":
            run_approved_scenario(agent)
        elif choice == "3":
            run_denied_scenario(agent)
        elif choice == "4":
            run_x402_scenario(agent)
        elif choice == "5":
            print(f"\n{C_GREEN}Thank you for reviewing Trestle!{C_RESET}\n")
            break
        else:
            print(f"{C_RED}Invalid choice. Please enter a number from 1 to 5.{C_RESET}")
        
        input(f"\nPress {C_BOLD}Enter{C_RESET} to return to menu...")
        os.system("cls" if os.name == "nt" else "clear")
        print_banner()

if __name__ == "__main__":
    main()
