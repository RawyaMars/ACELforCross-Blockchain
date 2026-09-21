
import json
import subprocess

from fabric_env import CHAINCODE, CHANNEL, peer_cli_env

def collect():
    env = peer_cli_env()
    cmd = ["peer", "chaincode", "query", "-C", CHANNEL, "-n", CHAINCODE, "-c", '{"Args":["GetAllEvents"]}']
    result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"GetAllEvents query failed: {result.stderr}")

    records = json.loads(result.stdout)

    decoded = []
    for r in records:
        decoded.append({
            "activity": r["activity"],
            "timestamp": r["timestamp"],
            "blockNumber": None,
            "resource": r["txId"],
            "fields": r["fields"],
        })

    decoded.sort(key=lambda ev: ev["timestamp"])
    return decoded

if __name__ == "__main__":
    events = collect()
    print(f"Collected {len(events)} real events from pharmatrace")
