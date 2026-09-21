
import argparse
import json
from collections import Counter
from pathlib import Path

import crosszid_bridge
import eth_collect
import eth_deploy
import eth_submit
import fabric_collect
import fabric_submit
from acel_generator import generate_acel
from acel_merge import merge_acel_logs
from acel_to_ocel import acel_to_ocel
from cross_chain_proof import CROSS_CHAIN_ACTIVITY, build_transitions, transitions_to_comm_acel
from discover import discover_and_save_ocdfg

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"
OUTPUT_DIR = BASE_DIR / "output"

def run_ethereum(num_lots, seed, start_index):
    eth_deploy.main()
    eth_submit.main(num_lots=num_lots, seed=seed, start_index=start_index)
    return eth_collect.collect()

def run_fabric(num_lots, seed, start_index):
    fabric_submit.main(num_lots=num_lots, seed=seed, start_index=start_index)
    all_events = fabric_collect.collect()

    return [e for e in all_events if _lot_in_range(e["fields"].get("lotId"), start_index, num_lots)]

def _lot_in_range(lot_id, start_index, num_lots):
    if not lot_id or not lot_id.startswith("LOT-"):
        return False
    idx = int(lot_id.split("-")[1])
    return start_index <= idx < start_index + num_lots

def next_free_lot_index():
    try:
        existing = fabric_collect.collect()
    except RuntimeError:
        return 0
    lot_indices = [
        int(e["fields"]["lotId"].split("-")[1])
        for e in existing
        if e["fields"].get("lotId", "").startswith("LOT-")
    ]
    return (max(lot_indices) + 1) if lot_indices else 0

def build_outputs(name, decoded_events, config_path):
    config = json.loads(config_path.read_text())
    acel_log = generate_acel(decoded_events, config)

    acel_path = OUTPUT_DIR / f"acel_pharma_real_{name}.jsonacel"
    acel_path.write_text(json.dumps(acel_log, indent=2))

    ocel_log = acel_to_ocel(acel_log)
    ocel_path = OUTPUT_DIR / f"ocel_pharma_real_{name}.jsonocel"
    ocel_path.write_text(json.dumps(ocel_log, indent=2))

    png_path = OUTPUT_DIR / f"ocdfg_pharma_real_{name}.png"
    discover_and_save_ocdfg(str(ocel_path), str(png_path))

    return acel_log

def build_cross_chain_outputs(eth_events, fabric_events, acel_eth, acel_fabric, correlation_config):
    transitions, chain_local = build_transitions(
        [("ethereum", eth_events), ("fabric", fabric_events)], correlation_config
    )
    comm_log = transitions_to_comm_acel(transitions, correlation_config)

    proof_path = OUTPUT_DIR / "cross_chain_transitions_real.json"
    proof_path.write_text(json.dumps({"transitions": transitions, "chainLocal": chain_local}, indent=2))

    print(f"[crosszid] registering {len(transitions)} transition proofs on-chain (real ZKP-2C + PRE + CPR)...")
    crosszid_results = crosszid_bridge.register_all(transitions)
    crosszid_summary = crosszid_bridge.summarize(crosszid_results)
    crosszid_path = OUTPUT_DIR / "cross_chain_transitions_real_crosszid.json"
    crosszid_path.write_text(json.dumps({"transitions": crosszid_results}, indent=2))
    print(
        f"[crosszid] {crosszid_summary['onChainVerified']}/{crosszid_summary['totalProofs']} "
        f"verified on-chain, {crosszid_summary['totalCprGas']:,} total gas"
    )

    merged_acel = merge_acel_logs([
        ("ethereum", acel_eth),
        ("fabric", acel_fabric),
        ("cross-chain-proof", comm_log),
    ])
    acel_path = OUTPUT_DIR / "acel_pharma_real_merged.jsonacel"
    acel_path.write_text(json.dumps(merged_acel, indent=2))

    ocel_log = acel_to_ocel(merged_acel)
    ocel_path = OUTPUT_DIR / "ocel_pharma_real_merged.jsonocel"
    ocel_path.write_text(json.dumps(ocel_log, indent=2))

    png_path = OUTPUT_DIR / "ocdfg_pharma_real_merged.png"
    discover_and_save_ocdfg(str(ocel_path), str(png_path), exclude_activities={CROSS_CHAIN_ACTIVITY})

    return transitions, chain_local, merged_acel, crosszid_summary

def summarize(name, acel_log, raw_count):
    activity_counts = Counter(ev["acel:activity"] for ev in acel_log["acel:events"].values())
    object_counts = Counter(o["acel:type"] for o in acel_log["acel:objects"].values())
    relation_counts = Counter(r["acel:type"] for r in acel_log["acel:relations"].values())
    return {
        "platform": name,
        "raw_events_collected": raw_count,
        "acel_events": len(acel_log["acel:events"]),
        "activities": dict(activity_counts),
        "objects": dict(object_counts),
        "relations": dict(relation_counts),
    }

def write_validation_report(summaries, transitions=None, chain_local=None, merged_acel=None, crosszid_summary=None):
    by_name = {s["platform"]: s for s in summaries}
    eth, fab = by_name["ethereum"], by_name["fabric"]

    lines = [
        "# Pharma ACEL pipeline - REAL on-chain execution validation report",
        "",
        "Both platforms submitted the SAME canonical business trace (src/scenario.py)",
        "as REAL transactions: real Ganache-mined Ethereum transactions to a real",
        "deployed Solidity contract, and real peer chaincode invokes to a real",
        "isolated Hyperledger Fabric network (chaincode pharmatrace). Events below",
        "were collected back from the live chains (eth_getLogs / chaincode",
        "GetAllEvents query), not simulated.",
        "",
        "## Event / object / relation counts",
        "",
        "| Metric | Ethereum (real) | Fabric (real) |",
        "|---|---|---|",
        f"| Raw events collected | {eth['raw_events_collected']} | {fab['raw_events_collected']} |",
        f"| ACEL events | {eth['acel_events']} | {fab['acel_events']} |",
    ]

    for a in sorted(set(eth["activities"]) | set(fab["activities"])):
        lines.append(f"| Activity: {a} | {eth['activities'].get(a, 0)} | {fab['activities'].get(a, 0)} |")
    for o in sorted(set(eth["objects"]) | set(fab["objects"])):
        lines.append(f"| Object: {o} | {eth['objects'].get(o, 0)} | {fab['objects'].get(o, 0)} |")
    for r in sorted(set(eth["relations"]) | set(fab["relations"])):
        lines.append(f"| Relation: {r} | {eth['relations'].get(r, 0)} | {fab['relations'].get(r, 0)} |")

    lines += ["", "## Symmetry checks", ""]
    for s in summaries:
        lots_created = s["activities"].get("LotCreated", 0)
        lot_objects = s["objects"].get("Lot", 0)
        raw_received = s["activities"].get("RawMaterialReceived", 0)
        raw_objects = s["objects"].get("RawMaterialBatch", 0)
        uses_raw = s["relations"].get("usesRawMaterial", 0)
        shipped = s["activities"].get("LotShipped", 0)
        shipment_objects = s["objects"].get("Shipment", 0)
        has_shipment = s["relations"].get("hasShipment", 0)

        lines.append(f"### {s['platform']}")
        lines.append(
            f"- LotCreated events == Lot objects: {lots_created} == {lot_objects} -> "
            f"{'OK' if lots_created == lot_objects else 'MISMATCH'}"
        )
        lines.append(
            f"- RawMaterialReceived events == RawMaterialBatch objects == usesRawMaterial relations: "
            f"{raw_received} == {raw_objects} == {uses_raw} -> "
            f"{'OK' if raw_received == raw_objects == uses_raw else 'MISMATCH'}"
        )
        lines.append(
            f"- LotShipped events == Shipment objects == hasShipment relations: "
            f"{shipped} == {shipment_objects} == {has_shipment} -> "
            f"{'OK' if shipped == shipment_objects == has_shipment else 'MISMATCH'}"
        )
        lines.append("")

    if transitions is not None:
        merged_activity_counts = Counter(
            ev["acel:activity"] for ev in merged_acel["acel:events"].values()
        )
        lines += [
            "## Cross-blockchain Correlation / Artifact Lifecycle discovery (convergence)",
            "",
            "cross_chain_proof.py groups every decoded event (any platform, any activity)",
            "by the shared caseKeyField (lotId); every lot here has activity on BOTH chains",
            "(replay-for-comparability design), so every lot yields one cross-chain",
            "transition proof listing the real transaction references (both chains, all",
            "activities) making up its journey. Each proof emits one",
            "CrossChainHandoffVerified 'Artifact related Communication Event', and",
            "acel_merge.py folds the ethereum + fabric + cross-chain-proof ACEL logs into",
            "ONE merged ACEL feeding ONE OC-DFG discovery (acel_pharma_real_merged.jsonacel /",
            "ocdfg_pharma_real_merged.png) -- the diagram's 'Artifact Lifecycle discovery'.",
            "CrossChainHandoffVerified is excluded from the OC-DFG itself (provenance, not",
            "a business activity).",
            "",
            f"- Cross-chain transition proofs built: {len(transitions)}",
            f"- Chain-local cases (no transition proof): {len(chain_local)}",
            f"- Merged ACEL events (ethereum + fabric + cross-chain-proof): "
            f"{len(merged_acel['acel:events'])}",
            f"- Merged ACEL objects (union by shared artifact id): {len(merged_acel['acel:objects'])}",
        ]
        for a, c in sorted(merged_activity_counts.items()):
            lines.append(f"  - {a}: {c}")
        lines.append("")

    if crosszid_summary is not None:
        lines += [
            "## Real on-chain Cross-ZID proof registration",
            "",
            "Each cross-chain transition proof above additionally gets a REAL on-chain",
            "record via the Cross-ZID protocol (crosszid_bridge.py, reusing",
            "~/Documents/crosszid_poc): a real Gnark PLONK/BLS12-381 ZKP-2C proof bound to",
            "the transition's representative real Fabric tx ID, a real (t,n)-threshold PRE",
            "re-encryption, and a real submitProof+verifyProof pair on",
            "CrossChainProofRegistry.sol deployed on a THIRD local chain -- distinct from",
            "this run's Ethereum (8545) and Fabric chains. This is verification/provenance",
            "evidence, not artifact lifecycle data, so it is NOT folded into the ACEL log",
            "itself -- each CrossChainHandoffVerified ACEL event carries only a `proofId`",
            "foreign key (vmap.proofId) pointing into",
            "cross_chain_transitions_real_crosszid.json and the on-chain CPR contract.",
            "",
            f"- Proofs registered on-chain: {crosszid_summary['totalProofs']}",
            f"- Verified (submitProof + verifyProof both succeeded, status=1): "
            f"{crosszid_summary['onChainVerified']}",
            f"- Failed on-chain: {crosszid_summary['onChainFailed']}",
            f"- Total CPR gas (submit+verify, all proofs): {crosszid_summary['totalCprGas']:,}",
            f"- Avg real ZKP-2C prove time: {crosszid_summary['avgZkp2cProveMs']:.0f} ms",
            f"- CPR contract: {crosszid_summary['cprContract']}",
            "",
        ]

    (OUTPUT_DIR / "validation_report_real.md").write_text("\n".join(lines))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--num-lots", type=int, default=50)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(exist_ok=True)

    start_index = next_free_lot_index()
    print(f"=== lotId start_index = {start_index} (avoids colliding with prior Fabric ledger state) ===")

    print("=== Ethereum: deploy + submit + collect (real) ===")
    eth_events = run_ethereum(args.num_lots, args.seed, start_index)
    eth_acel = build_outputs("ethereum", eth_events, CONFIG_DIR / "pharma_ethereum.json")

    print("=== Fabric: submit + collect (assumes network already up + chaincode deployed) ===")
    fab_events = run_fabric(args.num_lots, args.seed, start_index)
    fab_acel = build_outputs("fabric", fab_events, CONFIG_DIR / "pharma_fabric.json")

    print("=== Cross-chain: transition proofs (Correlation) + merged ACEL/OCEL/OC-DFG ===")
    correlation_config = json.loads((CONFIG_DIR / "pharma_ethereum.json").read_text())
    transitions, chain_local, merged_acel, crosszid_summary = build_cross_chain_outputs(
        eth_events, fab_events, eth_acel, fab_acel, correlation_config
    )
    print(f"  {len(transitions)} cross-chain transition proofs, {len(chain_local)} chain-local")

    summaries = [
        summarize("ethereum", eth_acel, len(eth_events)),
        summarize("fabric", fab_acel, len(fab_events)),
    ]
    for s in summaries:
        print(f"{s['platform']}: {s}")

    write_validation_report(
        summaries, transitions=transitions, chain_local=chain_local, merged_acel=merged_acel,
        crosszid_summary=crosszid_summary,
    )
    print(f"Done. Outputs in {OUTPUT_DIR}")

if __name__ == "__main__":
    main()
