
import hashlib

from scenario import generate_trace

BLOCKS_PER_EVENT = 1

def _fetch_raw_logs(num_lots, seed):
    trace = generate_trace(num_lots, seed=seed)
    raw_logs = []
    for i, e in enumerate(trace):
        block_number = 1 + i * BLOCKS_PER_EVENT
        tx_seed = f"{e['activity']}-{e['timestamp']}-{i}".encode()
        tx_hash = "0x" + hashlib.sha256(tx_seed).hexdigest()
        return_values = {k: v for k, v in e.items() if k not in ("activity", "timestamp")}
        raw_logs.append({
            "event": e["activity"],
            "blockNumber": block_number,
            "transactionHash": tx_hash,
            "timestamp": e["timestamp"],
            "returnValues": return_values,
        })
    return raw_logs

def _decode(raw_logs):
    decoded = []
    for log in raw_logs:
        decoded.append({
            "activity": log["event"],
            "timestamp": log["timestamp"],
            "blockNumber": log["blockNumber"],
            "resource": log["transactionHash"],
            "fields": dict(log["returnValues"]),
        })
    return decoded

def simulate_collect(num_lots, seed=42):
    raw_logs = _fetch_raw_logs(num_lots, seed=seed)
    return _decode(raw_logs)
