from datetime import datetime, timezone

def _to_iso(epoch_seconds):
    return datetime.fromtimestamp(epoch_seconds, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def acel_to_ocel(acel_log):
    global_log = acel_log["acel:global-log"]

    ocel_objects = {
        oid: {
            "ocel:type": odata["acel:type"],
            "ocel:ovmap": dict(odata["acel:ovmap"]),
        }
        for oid, odata in acel_log["acel:objects"].items()
    }

    ocel_events = {}
    for eid, edata in acel_log["acel:events"].items():
        ocel_events[eid] = {
            "ocel:activity": edata["acel:activity"],
            "ocel:timestamp": _to_iso(edata["acel:timestamp"]),
            "ocel:omap": list(edata.get("omap", [])),
            "ocel:vmap": dict(edata.get("vmap", {})),
        }

    attribute_names = sorted(
        {attr for ev in ocel_events.values() for attr in ev["ocel:vmap"]}
        | {attr for obj in ocel_objects.values() for attr in obj["ocel:ovmap"]}
    )

    return {
        "ocel:global-log": {
            "ocel:version": "1.0",
            "ocel:ordering": "timestamp",
            "ocel:attribute-names": attribute_names,
            "ocel:object-types": global_log["acel:object-types"],
        },



        "ocel:global-event": {"ocel:activity": "__INVALID__"},
        "ocel:global-object": {"ocel:type": "__INVALID__"},
        "ocel:events": ocel_events,
        "ocel:objects": ocel_objects,
    }
