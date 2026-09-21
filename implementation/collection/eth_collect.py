
import json
from pathlib import Path

from web3 import Web3

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "output"
DEPLOYMENT_PATH = OUTPUT_DIR / "eth_deployment_real.json"
GANACHE_PORT = 8545

ACTIVITY_NAMES = [
    "LotCreated",
    "RawMaterialReceived",
    "QualityControlApproved",
    "QualityControlRejected",
    "LotShipped",
    "LotDelivered",
]

def collect():
    deployment = json.loads(DEPLOYMENT_PATH.read_text())
    w3 = Web3(Web3.HTTPProvider(f"http://127.0.0.1:{GANACHE_PORT}"))
    assert w3.is_connected(), "Ganache not reachable - run eth_deploy.py/eth_submit.py first"

    contract = w3.eth.contract(address=deployment["address"], abi=deployment["abi"])

    decoded = []
    block_timestamps = {}
    for activity in ACTIVITY_NAMES:
        event_cls = getattr(contract.events, activity)
        for log in event_cls().get_logs(fromBlock=0, toBlock="latest"):
            block_number = log["blockNumber"]
            if block_number not in block_timestamps:
                block_timestamps[block_number] = w3.eth.get_block(block_number)["timestamp"]

            fields = {k: v for k, v in log["args"].items()}
            decoded.append({
                "activity": activity,
                "timestamp": block_timestamps[block_number],
                "blockNumber": block_number,
                "resource": log["transactionHash"].hex(),
                "fields": fields,
            })

    decoded.sort(key=lambda ev: (ev["timestamp"], ev["blockNumber"]))
    return decoded

if __name__ == "__main__":
    events = collect()
    print(f"Collected {len(events)} real events from chain")
