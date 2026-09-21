
import hashlib
import json

from scenario import generate_trace

BLOCKS_PER_EVENT = 1

def _fetch_raw_transactions(num_lots, seed):
    trace = generate_trace(num_lots, seed=seed)
    raw_txs = []
    for i, e in enumerate(trace):
        block_number = 1 + i * BLOCKS_PER_EVENT
        tx_seed = f"fabric-{e['activity']}-{e['timestamp']}-{i}".encode()
        tx_id = hashlib.sha256(tx_seed).hexdigest()
        payload = {k: v for k, v in e.items() if k not in ("activity", "timestamp")}
        raw_txs.append({
            "event": e["activity"],
            "blockNumber": block_number,
            "txId": tx_id,
            "timestamp": e["timestamp"],
            "chaincodeEventPayload": json.dumps(payload),
        })
    return raw_txs

def _decode(raw_txs):
    decoded = []
    for tx in raw_txs:
        decoded.append({
            "activity": tx["event"],
            "timestamp": tx["timestamp"],
            "blockNumber": tx["blockNumber"],
            "resource": tx["txId"],
            "fields": json.loads(tx["chaincodeEventPayload"]),
        })
    return decoded

def simulate_collect(num_lots, seed=42):
    raw_txs = _fetch_raw_transactions(num_lots, seed=seed)
    return _decode(raw_txs)
