
from collections import defaultdict

CROSS_CHAIN_ACTIVITY = "CrossChainHandoffVerified"

def _case_key_field(config):
    return config["Correlation"]["caseKeyField"]

def _artifact_type_for(config):

    return config["Correlation"]["artifactTypes"][0]

def build_transitions(platform_events, config):
    key_field = _case_key_field(config)
    cases = defaultdict(list)
    for chain_source, events in platform_events:
        for ev in events:
            case_id = ev["fields"].get(key_field)
            if case_id is None:
                continue
            cases[case_id].append({
                "chainSource": chain_source,
                "activity": ev["activity"],
                "timestamp": ev["timestamp"],
                "blockNumber": ev.get("blockNumber"),
                "resource": ev["resource"],
            })

    transitions = []
    chain_local = []
    for case_id in sorted(cases):
        entries = sorted(cases[case_id], key=lambda e: e["timestamp"])
        chains_involved = sorted({e["chainSource"] for e in entries})
        if len(chains_involved) > 1:
            transitions.append({
                "proofId": f"transition_{len(transitions)}",
                "caseKey": case_id,
                "chains": chains_involved,
                "transactions": entries,
            })
        else:
            chain_local.append(case_id)

    transitions.sort(key=lambda t: t["transactions"][0]["timestamp"])
    return transitions, chain_local

def transitions_to_comm_acel(transitions, config):
    artifact_type = _artifact_type_for(config)
    objects = {}
    events = {}

    for i, transition in enumerate(transitions):
        obj_id = f"{artifact_type}:{transition['caseKey']}"
        if obj_id not in objects:
            objects[obj_id] = {"acel:type": artifact_type, "acel:ovmap": {}}
        objects[obj_id]["acel:ovmap"]["crossChainStatus"] = "linked"

        events[f"c{i}"] = {
            "acel:activity": CROSS_CHAIN_ACTIVITY,
            "acel:timestamp": transition["transactions"][-1]["timestamp"],
            "vmap": {
                "source": "cross-chain-proof",
                "resource": "cross-chain-proof",
                "chains": transition["chains"],

                "transactions": transition["transactions"],
                "proofId": transition["proofId"],
            },
            "omap": [obj_id],
            "rmap": [],
            "ocmap": {
                obj_id: {"acel:lifecycle": "verified",
                         "acel:changed": {"crossChainStatus": "linked"}}
            },
            "rcmap": {},
        }

    return {
        "acel:global-log": {
            "acel:version": "1.0",
            "acel:ordering": "timestamp",
            "acel:attribute-names": ["crossChainStatus"],
            "acel:object-types": sorted({o["acel:type"] for o in objects.values()}),
            "acel:relation-types": [],
            "acel:bc-reference": {"NAME": "Cross-Chain Correlation Layer", "BLOCKCHAINID": "multi-chain"},
            "acel:sc-reference": {"CONTRACTID": "cross-chain-transition"},
        },
        "acel:objects": objects,
        "acel:relations": {},
        "acel:events": events,
    }
