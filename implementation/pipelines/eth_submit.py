
import json
from pathlib import Path

from web3 import Web3

from scenario import generate_trace

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "output"
DEPLOYMENT_PATH = OUTPUT_DIR / "eth_deployment_real.json"
GANACHE_PORT = 8545

ACTIVITY_TO_FUNCTION = {
    "LotCreated": lambda c, e: c.functions.createLot(e["lotId"], e["product"], e["quantity"], e["manufacturer"]),
    "RawMaterialReceived": lambda c, e: c.functions.receiveRawMaterial(e["lotId"], e["batchId"], e["materialName"], e["supplier"], e["quantity"]),
    "QualityControlApproved": lambda c, e: c.functions.approveQualityControl(e["lotId"]),
    "QualityControlRejected": lambda c, e: c.functions.rejectQualityControl(e["lotId"]),
    "LotShipped": lambda c, e: c.functions.shipLot(e["lotId"], e["shipmentId"], e["carrier"], e["destination"]),
    "LotDelivered": lambda c, e: c.functions.deliverLot(e["lotId"], e["shipmentId"]),
}

def main(num_lots=50, seed=42, start_index=0):
    deployment = json.loads(DEPLOYMENT_PATH.read_text())
    w3 = Web3(Web3.HTTPProvider(f"http://127.0.0.1:{GANACHE_PORT}"))
    assert w3.is_connected(), "Ganache not reachable - run eth_deploy.py first"

    contract = w3.eth.contract(address=deployment["address"], abi=deployment["abi"])
    account = w3.eth.accounts[0]

    trace = generate_trace(num_lots, seed=seed, start_index=start_index)
    submitted = 0
    for e in trace:
        fn = ACTIVITY_TO_FUNCTION[e["activity"]](contract, e)
        tx_hash = fn.transact({"from": account})
        w3.eth.wait_for_transaction_receipt(tx_hash)
        submitted += 1

    print(f"Submitted {submitted} real transactions to {deployment['address']}")
    return submitted

if __name__ == "__main__":
    main()
