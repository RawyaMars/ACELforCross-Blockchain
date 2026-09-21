
import argparse
import json
from collections import Counter
from pathlib import Path

import eth_adapter
import fabric_adapter
from acel_generator import generate_acel
from acel_to_ocel import acel_to_ocel
from discover import discover_and_save_ocdfg

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"
OUTPUT_DIR = BASE_DIR / "output"

PLATFORMS = {
    "ethereum": {
        "config": CONFIG_DIR / "pharma_ethereum.json",
        "collect": eth_adapter.simulate_collect,
    },
    "fabric": {
        "config": CONFIG_DIR / "pharma_fabric.json",
        "collect": fabric_adapter.simulate_collect,
    },
}

def run_platform(name, spec, num_lots, seed):
    config = json.loads(spec["config"].read_text())
    decoded_events = spec["collect"](num_lots, seed=seed)

    acel_log = generate_acel(decoded_events, config)
    acel_path = OUTPUT_DIR / f"acel_pharma_{name}.jsonacel"
    acel_path.write_text(json.dumps(acel_log, indent=2))

    ocel_log = acel_to_ocel(acel_log)
    ocel_path = OUTPUT_DIR / f"ocel_pharma_{name}.jsonocel"
    ocel_path.write_text(json.dumps(ocel_log, indent=2))

    png_path = OUTPUT_DIR / f"ocdfg_pharma_{name}.png"
    discover_and_save_ocdfg(str(ocel_path), str(png_path))

    return acel_log, decoded_events

def summarize(name, acel_log, decoded_events):
    activity_counts = Counter(ev["acel:activity"] for ev in acel_log["acel:events"].values())
    object_counts = Counter(o["acel:type"] for o in acel_log["acel:objects"].values())
    relation_counts = Counter(r["acel:type"] for r in acel_log["acel:relations"].values())
    return {
        "platform": name,
        "raw_events_collected": len(decoded_events),
        "acel_events": len(acel_log["acel:events"]),
        "activities": dict(activity_counts),
        "objects": dict(object_counts),
        "relations": dict(relation_counts),
    }

def write_validation_report(summaries):
    by_name = {s["platform"]: s for s in summaries}
    eth, fab = by_name["ethereum"], by_name["fabric"]

    lines = [
        "# Pharma ACEL pipeline - validation report",
        "",
        "Simulated dataset, replay design: both platforms collect the SAME canonical",
        "business trace (see src/scenario.py), so event-count parity across platforms",
        "is expected by construction, mirroring the Kitty validation methodology in",
        "chapter 6 (event-count parity verifies replay fidelity + adapter integrity,",
        "not an independent empirical coincidence).",
        "",
        "## Event / object / relation counts",
        "",
        "| Metric | Ethereum | Fabric |",
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

    (OUTPUT_DIR / "validation_report.md").write_text("\n".join(lines))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--num-lots", type=int, default=600)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(exist_ok=True)

    summaries = []
    for name, spec in PLATFORMS.items():
        acel_log, decoded_events = run_platform(name, spec, args.num_lots, args.seed)
        s = summarize(name, acel_log, decoded_events)
        summaries.append(s)
        print(f"{name}: {s}")

    write_validation_report(summaries)
    print(f"Done. Outputs in {OUTPUT_DIR}")

if __name__ == "__main__":
    main()
