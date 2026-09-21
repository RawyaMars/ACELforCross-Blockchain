

def merge_acel_logs(tagged_logs):
    objects = {}
    relations = {}
    raw_events = []

    for tag, log in tagged_logs:
        for oid, odata in log["acel:objects"].items():
            if oid not in objects:
                objects[oid] = {"acel:type": odata["acel:type"], "acel:ovmap": {}}
            objects[oid]["acel:ovmap"].update(odata["acel:ovmap"])

        for rid, rdata in log["acel:relations"].items():
            relations.setdefault(rid, rdata)

        for edata in log["acel:events"].values():
            raw_events.append((edata["acel:timestamp"], tag, edata))

    raw_events.sort(key=lambda t: (t[0], t[1]))

    events = {}
    for i, (_, tag, edata) in enumerate(raw_events):
        merged = dict(edata)
        merged["vmap"] = {**edata.get("vmap", {}), "chainSource": tag}
        events[f"e{i}"] = merged

    attribute_names = sorted({a for _, log in tagged_logs for a in log["acel:global-log"]["acel:attribute-names"]})
    object_types = sorted({t for _, log in tagged_logs for t in log["acel:global-log"]["acel:object-types"]})
    relation_types = sorted({t for _, log in tagged_logs for t in log["acel:global-log"]["acel:relation-types"]})

    return {
        "acel:global-log": {
            "acel:version": "1.0",
            "acel:ordering": "timestamp",
            "acel:attribute-names": attribute_names,
            "acel:object-types": object_types,
            "acel:relation-types": relation_types,
            "acel:bc-reference": [log["acel:global-log"]["acel:bc-reference"] for _, log in tagged_logs],
            "acel:sc-reference": [log["acel:global-log"]["acel:sc-reference"] for _, log in tagged_logs],
        },
        "acel:objects": objects,
        "acel:relations": relations,
        "acel:events": events,
    }
