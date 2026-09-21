
def generate_acel(decoded_events, config):
    bc_ref = config["BC reference"]
    sc_ref = config["SC reference"]
    artifacts = config["Artifacts"]
    relations_conf = config["Relations"]
    event_defs = config["Events"]

    objects = {}
    relations = {}
    events = {}
    relation_seen = set()

    ordered = sorted(decoded_events, key=lambda ev: ev["timestamp"])

    for i, de in enumerate(ordered):
        activity = de["activity"]
        edef = event_defs.get(activity)
        if edef is None:
            continue

        fields = de["fields"]

        omap = []
        ocmap = {}
        for odef in edef["objects"]:
            id_field = odef["idField"]
            if id_field not in fields:
                continue
            obj_id = f"{odef['type']}:{fields[id_field]}"
            omap.append(obj_id)

            changed_attrs = {a: fields[a] for a in odef["attributes"] if a in fields}
            if obj_id not in objects:
                objects[obj_id] = {"acel:type": odef["type"], "acel:ovmap": {}}
            objects[obj_id]["acel:ovmap"].update(changed_attrs)

            ocmap[obj_id] = {"acel:lifecycle": odef["lifecycle"], "acel:changed": changed_attrs}

        rmap = []
        rcmap = {}
        for rdef in edef.get("relations", []):
            src_val = fields.get(rdef["sourceField"])
            tgt_val = fields.get(rdef["targetField"])
            if src_val is None or tgt_val is None:
                continue

            rel_type = rdef["type"]
            rel_conf = relations_conf[rel_type]
            src_id = f"{rel_conf['source']}:{src_val}"
            tgt_id = f"{rel_conf['target']}:{tgt_val}"
            rel_id = f"{rel_type}:{src_id}->{tgt_id}"

            if rel_id not in relations:
                relations[rel_id] = {
                    "acel:type": rel_type,
                    "acel:rvmap": {
                        "source": src_id,
                        "target": tgt_id,
                        "cardinality": rel_conf["cardinality"],
                    },
                }

            rmap.append(rel_id)
            rcmap[rel_id] = "created" if rel_id not in relation_seen else "unchanged"
            relation_seen.add(rel_id)

        event_id = f"e{i}"
        events[event_id] = {
            "acel:activity": activity,
            "acel:timestamp": de["timestamp"],
            "vmap": {"blocknum": de["blockNumber"], "resource": de["resource"]},
            "omap": omap,
            "rmap": rmap,
            "ocmap": ocmap,
            "rcmap": rcmap,
        }

    all_attribute_names = sorted({a for art in artifacts.values() for a in art["attributes"]})

    acel_log = {
        "acel:global-log": {
            "acel:version": "1.0",
            "acel:ordering": "timestamp",
            "acel:attribute-names": all_attribute_names,
            "acel:object-types": list(artifacts.keys()),
            "acel:relation-types": list(relations_conf.keys()),
            "acel:bc-reference": bc_ref,
            "acel:sc-reference": sc_ref,
        },
        "acel:objects": objects,
        "acel:relations": relations,
        "acel:events": events,
    }
    return acel_log
