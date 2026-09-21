
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from acel_generator import generate_acel
from acel_merge import merge_acel_logs
from acel_to_ocel import acel_to_ocel
from cross_chain_proof import CROSS_CHAIN_ACTIVITY, build_transitions, transitions_to_comm_acel
from discover import discover_and_save_ocdfg
from scenario import generate_trace, split_trace_by_chain

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"
OUTPUT_DIR = BASE_DIR / "output"

def _decode(events, chain_tag):
    decoded = []
    for i, e in enumerate(events):
        tx_seed = f"{chain_tag}-{e['activity']}-{e['timestamp']}-{i}".encode()
        digest = hashlib.sha256(tx_seed).hexdigest()
        resource = f"0x{digest}" if chain_tag == "ethereum" else digest
        fields = {k: v for k, v in e.items() if k not in ("activity", "timestamp")}
        decoded.append({
            "activity": e["activity"],
            "timestamp": e["timestamp"],
            "blockNumber": 1 + i,
            "resource": resource,
            "fields": fields,
        })
    return decoded

def run(num_lots, seed):
    OUTPUT_DIR.mkdir(exist_ok=True)

    trace = generate_trace(num_lots, seed=seed)
    fabric_events, eth_events = split_trace_by_chain(trace)

    eth_config = json.loads((CONFIG_DIR / "pharma_ethereum.json").read_text())
    fabric_config = json.loads((CONFIG_DIR / "pharma_fabric.json").read_text())

    decoded_eth = _decode(eth_events, "ethereum")
    decoded_fabric = _decode(fabric_events, "fabric")

    acel_eth = generate_acel(decoded_eth, eth_config)
    acel_fabric = generate_acel(decoded_fabric, fabric_config)

    (OUTPUT_DIR / "acel_pharma_split_ethereum.jsonacel").write_text(json.dumps(acel_eth, indent=2))
    (OUTPUT_DIR / "acel_pharma_split_fabric.jsonacel").write_text(json.dumps(acel_fabric, indent=2))

    for name, acel_log in (("ethereum", acel_eth), ("fabric", acel_fabric)):
        ocel_single_path = OUTPUT_DIR / f"ocel_pharma_split_{name}.jsonocel"
        ocel_single_path.write_text(json.dumps(acel_to_ocel(acel_log), indent=2))
        png_single_path = OUTPUT_DIR / f"ocdfg_pharma_split_{name}.png"
        discover_and_save_ocdfg(str(ocel_single_path), str(png_single_path))

    transitions, chain_local = build_transitions(
        [("fabric", decoded_fabric), ("ethereum", decoded_eth)], fabric_config
    )
    comm_log = transitions_to_comm_acel(transitions, fabric_config)

    proof_path = OUTPUT_DIR / "cross_chain_transitions_split.json"
    proof_path.write_text(json.dumps({"transitions": transitions, "chainLocal": chain_local}, indent=2))

    merged = merge_acel_logs([
        ("fabric", acel_fabric), ("ethereum", acel_eth), ("cross-chain-proof", comm_log),
    ])
    merged_path = OUTPUT_DIR / "acel_pharma_split_merged.jsonacel"
    merged_path.write_text(json.dumps(merged, indent=2))

    ocel_path = OUTPUT_DIR / "ocel_pharma_split_merged.jsonocel"
    ocel_path.write_text(json.dumps(acel_to_ocel(merged), indent=2))

    png_path = OUTPUT_DIR / "ocdfg_pharma_split_merged.png"
    discover_and_save_ocdfg(str(ocel_path), str(png_path), exclude_activities={CROSS_CHAIN_ACTIVITY})

    write_report(fabric_events, eth_events, acel_fabric, acel_eth, merged, transitions, chain_local)
    print(
        f"Done: {len(fabric_events)} Fabric-only events, {len(eth_events)} Ethereum-only events, "
        f"{len(merged['acel:events'])} merged events, {len(merged['acel:objects'])} merged objects, "
        f"{len(transitions)} cross-chain transition proofs -> {png_path}"
    )

def _describe(acel_log):
    activities = Counter(ev["acel:activity"] for ev in acel_log["acel:events"].values())
    objects = Counter(o["acel:type"] for o in acel_log["acel:objects"].values())
    return activities, objects

def write_report(fabric_events, eth_events, acel_fabric, acel_eth, merged, transitions, chain_local):
    fab_activities, fab_objects = _describe(acel_fabric)
    eth_activities, eth_objects = _describe(acel_eth)
    merged_activities, merged_objects = _describe(merged)

    lines = [
        "# Single-hop cross-chain pipeline - validation report",
        "",
        "Simulated dataset. Unlike run_pipeline.py / run_real_pipeline.py's replay-for-",
        "comparability design (both chains record every activity), this run splits ONE",
        "canonical trace so each activity is recorded on exactly one chain, mirroring",
        "~/Documents/temporal-constraints/bpmn/PharmaBatchIOBP_NoConstraints.bpmn:",
        "Fabricant's activities on Hyperledger Fabric, Logistics' activities on Ethereum.",
        "",
        "## Per-chain activity counts (disjoint by construction)",
        "",
        "| Activity | Fabric | Ethereum |",
        "|---|---|---|",
    ]
    for a in sorted(set(fab_activities) | set(eth_activities)):
        lines.append(f"| {a} | {fab_activities.get(a, 0)} | {eth_activities.get(a, 0)} |")

    lines += [
        "",
        "## Merged cross-chain log",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Fabric-only events | {len(fabric_events)} |",
        f"| Ethereum-only events | {len(eth_events)} |",
        f"| Merged ACEL events | {sum(merged_activities.values())} |",
        f"| Merged ACEL objects (union by shared id) | {sum(merged_objects.values())} |",
        f"| Lot objects | {merged_objects.get('Lot', 0)} |",
        f"| RawMaterialBatch objects | {merged_objects.get('RawMaterialBatch', 0)} |",
        f"| Shipment objects | {merged_objects.get('Shipment', 0)} |",
        "",
        "## Cross-blockchain Correlation (transition proofs)",
        "",
        "No activity is ever duplicated across chains here, so there is nothing to",
        "consensus-check field-by-field. Correlation instead groups every decoded event",
        "(any platform, any activity) by the shared caseKeyField (lotId); a Lot whose",
        "events span more than one platform gets one CrossChainHandoffVerified event",
        "listing the real transaction references making up its cross-chain journey. A",
        "Lot rejected at QC never reaches Ethereum and stays chain-local -- no such",
        "event is produced for it, which is the expected, correct signal, not a failure.",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Cross-chain transition proofs (CrossChainHandoffVerified) | {len(transitions)} |",
        f"| Chain-local cases (no transition proof) | {len(chain_local)} |",
        "",
    ]

    chain_scope = classify_objects_by_chain_scope(merged)

    lines += ["", "## Cross-chain vs. chain-local objects", "", "| Object type | Cross-chain | Fabric-only | Ethereum-only |", "|---|---|---|---|"]
    for otype in sorted(merged_objects):
        counts = Counter(chain_scope[oid] for oid in merged["acel:objects"] if merged["acel:objects"][oid]["acel:type"] == otype)
        lines.append(f"| {otype} | {counts.get('cross-chain', 0)} | {counts.get('fabric-only', 0)} | {counts.get('ethereum-only', 0)} |")

    (OUTPUT_DIR / "validation_report_split.md").write_text("\n".join(lines))

def classify_objects_by_chain_scope(merged_acel):
    scope = {}
    for oid in merged_acel["acel:objects"]:
        sources = {
            ev.get("vmap", {}).get("chainSource")
            for ev in merged_acel["acel:events"].values()
            if oid in ev.get("omap", [])
        }
        sources.discard(None)
        if len(sources) > 1:
            scope[oid] = "cross-chain"
        elif sources:
            scope[oid] = f"{next(iter(sources))}-only"
        else:
            scope[oid] = "unknown"
    return scope

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--num-lots", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    run(args.num_lots, args.seed)

if __name__ == "__main__":
    main()
