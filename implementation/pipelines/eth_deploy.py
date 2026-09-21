
import json
import subprocess
import time
from pathlib import Path

import solcx
from web3 import Web3

BASE_DIR = Path(__file__).resolve().parent.parent
CONTRACT_PATH = BASE_DIR / "contracts" / "PharmaSupplyChain.sol"
OUTPUT_DIR = BASE_DIR / "output"
DEPLOYMENT_PATH = OUTPUT_DIR / "eth_deployment_real.json"
GANACHE_PORT = 8545
GANACHE_LOG = OUTPUT_DIR / "ganache_real.log"

SOLC_VERSION = "0.8.24"

def start_ganache():
    w3 = Web3(Web3.HTTPProvider(f"http://127.0.0.1:{GANACHE_PORT}"))
    if w3.is_connected():
        return None

    OUTPUT_DIR.mkdir(exist_ok=True)
    log_file = open(GANACHE_LOG, "w")
    proc = subprocess.Popen(
        [
            "ganache",
            "--port", str(GANACHE_PORT),
            "--wallet.deterministic",
            "--chain.chainId", "1337",
        ],
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )

    for _ in range(60):
        if w3.is_connected():
            break
        time.sleep(0.5)
    else:
        raise RuntimeError("Ganache did not become reachable in time; see " + str(GANACHE_LOG))

    return proc

def compile_contract():
    solcx.set_solc_version(SOLC_VERSION)
    source = CONTRACT_PATH.read_text()
    compiled = solcx.compile_source(
        source,
        output_values=["abi", "bin"],
        solc_version=SOLC_VERSION,
    )
    contract_id, contract_interface = next(iter(compiled.items()))
    return contract_interface["abi"], contract_interface["bin"]

def deploy(w3, abi, bytecode):
    account = w3.eth.accounts[0]
    contract = w3.eth.contract(abi=abi, bytecode=bytecode)
    tx_hash = contract.constructor().transact({"from": account})
    tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    return tx_receipt.contractAddress

def main():
    ganache_proc = start_ganache()
    w3 = Web3(Web3.HTTPProvider(f"http://127.0.0.1:{GANACHE_PORT}"))
    assert w3.is_connected(), "Ganache not reachable after startup"

    abi, bytecode = compile_contract()
    address = deploy(w3, abi, bytecode)

    OUTPUT_DIR.mkdir(exist_ok=True)
    DEPLOYMENT_PATH.write_text(json.dumps({"address": address, "abi": abi}, indent=2))

    print(f"Deployed PharmaSupplyChain at {address} (Ganache pid: "
          f"{ganache_proc.pid if ganache_proc else 'already running'})")

if __name__ == "__main__":
    main()
