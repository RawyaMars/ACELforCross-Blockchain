import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

CROSSZID_DIR = Path.home() / "Documents" / "crosszid_poc"
CPR_PORT = 7546
CPR_GANACHE_URL = f"http://127.0.0.1:{CPR_PORT}"
CPR_CHAIN_ID = 1338
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"
CPR_GANACHE_LOG = OUTPUT_DIR / "ganache_cpr_real.log"

sys.path.insert(0, str(CROSSZID_DIR))
import pharma_supply_chain as czid

ORG_SEED = "ACEL_PHARMA_MANUFACTURER_SEED"
RECEIVER_SEED = b"ACEL_PHARMA_ETHEREUM_RECEIVER_SEED"

def _receiver_sk_hex():
    return format(int.from_bytes(hashlib.sha256(RECEIVER_SEED).digest(), "big") % (2**253), "064x")

def start_cpr_chain():

    from web3 import Web3
    w3 = Web3(Web3.HTTPProvider(CPR_GANACHE_URL))
    if w3.is_connected():
        return None

    OUTPUT_DIR.mkdir(exist_ok=True)
    log_file = open(CPR_GANACHE_LOG, "w")
    proc = subprocess.Popen(
        ["ganache", "--port", str(CPR_PORT), "--wallet.deterministic",
         "--chain.chainId", str(CPR_CHAIN_ID)],
        stdout=log_file, stderr=subprocess.STDOUT,
    )
    for _ in range(60):
        if w3.is_connected():
            break
        time.sleep(0.5)
    else:
        raise RuntimeError(f"CPR chain did not become reachable in time; see {CPR_GANACHE_LOG}")
    return proc

def ensure_zkp_server(timeout=310):
    if czid._zkp_ready.is_set():
        return True
    print("[crosszid_bridge] starting gnark ZKP-2C server (loads pk.bin)...")
    czid.start_zkp_server_bg()
    if not czid._zkp_ready.wait(timeout=timeout):
        raise RuntimeError("gnark_zkp2c server did not become ready")
    print("[crosszid_bridge] ZKP-2C server ready.")
    return True

def _representative_fabric_tx(transition):

    fabric_txs = [t for t in transition["transactions"] if t["chainSource"] == "fabric"]
    return (fabric_txs or transition["transactions"])[0]["resource"]

def register_transition_on_chain(transition, epoch, ganache_url=CPR_GANACHE_URL):

    fabric_tx_id = _representative_fabric_tx(transition)
    lot_id = transition["caseKey"]
    activities = "->".join(t["activity"] for t in transition["transactions"])

    c1_merkle = czid.get_c1_merkle(fabric_tx_id)
    zid = czid.PharmaZIDKey(ORG_SEED, lot_id, epoch)
    zkp = czid.prove_zkp2c(zid, c1_merkle=c1_merkle)

    sender_sk_hex = format(zid.sk_int % (2**256), "064x")
    pre = czid.pre_pipeline(sender_sk_hex, _receiver_sk_hex())

    ccm = czid.build_pharma_ccm(
        {
            "drug_name": activities,
            "manufacturer_id": "acel-pharma",
            "lot_number": lot_id,
            "batch_quantity": len(transition["transactions"]),
            "unit": "event",
            "expiry_date": "",
            "compliance_cert": f"handoff:{'+'.join(transition['chains'])}",
            "fabric_tx_id": fabric_tx_id,
        },
        zid, zkp, pre, "ETHEREUM_SIDE",
    )

    cpr = czid.submit_cpr(ccm, ganache_url, proof_bytes_hex=zkp.get("proof_bytes", ""))

    return {
        "epoch": epoch,
        "nullifier": zid.nullifier,
        "zkp2c": {
            "mode": zkp.get("mode"),
            "proveMs": zkp.get("prove_ms"),
            "verified": zkp.get("verified"),
            "c1Root": c1_merkle.get("root"),
        },
        "pre": {"mode": pre.get("mode"), "pipelineMs": pre.get("pre_pipeline_ms")},
        "cpr": cpr,
    }

def register_all(transitions, ganache_url=CPR_GANACHE_URL, progress_every=10):
    start_cpr_chain()
    ensure_zkp_server()
    epoch_base = int(time.time())
    results = []
    for i, transition in enumerate(transitions):
        cz = register_transition_on_chain(transition, epoch_base + i, ganache_url=ganache_url)
        results.append({**transition, "crossZid": cz})
        if (i + 1) % progress_every == 0 or (i + 1) == len(transitions):
            ok = sum(1 for r in results if r["crossZid"]["cpr"].get("mode") == "ganache-cpr-verified")
            print(f"[crosszid_bridge] {i + 1}/{len(transitions)} on-chain CPR registrations ({ok} verified)")
    return results

def summarize(results):
    verified = [r for r in results if r["crossZid"]["cpr"].get("mode") == "ganache-cpr-verified"]
    total_gas = sum(r["crossZid"]["cpr"].get("gas", 0) for r in verified)
    avg_prove_ms = (
        sum(r["crossZid"]["zkp2c"]["proveMs"] for r in results) / len(results) if results else 0.0
    )
    return {
        "totalProofs": len(results),
        "onChainVerified": len(verified),
        "onChainFailed": len(results) - len(verified),
        "totalCprGas": total_gas,
        "avgZkp2cProveMs": avg_prove_ms,
        "cprContract": verified[0]["crossZid"]["cpr"].get("contract") if verified else None,
    }

if __name__ == "__main__":
    proof_path = Path(sys.argv[1]) if len(sys.argv) > 1 else (
        Path(__file__).resolve().parent.parent / "output" / "cross_chain_transitions_real.json"
    )
    data = json.loads(proof_path.read_text())
    results = register_all(data["transitions"])
    out_path = proof_path.parent / "cross_chain_transitions_real_crosszid.json"
    out_path.write_text(json.dumps({"transitions": results}, indent=2))
    verified = sum(1 for r in results if r["crossZid"]["cpr"].get("mode") == "ganache-cpr-verified")
    print(f"Done: {verified}/{len(results)} real on-chain CPR registrations. -> {out_path}")
