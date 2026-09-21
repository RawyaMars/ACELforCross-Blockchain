
import random

MANUFACTURERS = ["Sanofi-TN", "Biolab-TN", "PharmaGen"]
MATERIALS = ["Paracetamol API", "Excipient-X", "Amoxicillin API", "Lactose Base"]
SUPPLIERS = ["ChemSource Ltd", "APIWorks", "RawChem Co"]
CARRIERS = ["DHL Pharma", "FedEx CoolChain", "LocalFreight"]
DESTINATIONS = ["Tunis Depot", "Sfax Depot", "Export - EU"]
QC_APPROVAL_RATE = 0.85

START_TS = 1_700_000_000

def generate_trace(num_lots, seed=42, start_index=0):
    rng = random.Random(seed)
    events = []
    ts = START_TS

    for i in range(start_index, start_index + num_lots):
        lot_id = f"LOT-{i:05d}"
        manufacturer = rng.choice(MANUFACTURERS)
        product = rng.choice(MATERIALS)
        quantity = rng.randint(500, 5000)

        ts += rng.randint(60, 600)
        events.append({
            "activity": "LotCreated",
            "timestamp": ts,
            "lotId": lot_id,
            "product": product,
            "quantity": quantity,
            "manufacturer": manufacturer,
            "status": "created",
        })

        num_batches = rng.randint(1, 3)
        for b in range(num_batches):
            batch_id = f"{lot_id}-RM{b}"
            ts += rng.randint(60, 1800)
            events.append({
                "activity": "RawMaterialReceived",
                "timestamp": ts,
                "lotId": lot_id,
                "batchId": batch_id,
                "materialName": rng.choice(MATERIALS),
                "supplier": rng.choice(SUPPLIERS),
                "quantity": rng.randint(100, 1000),
            })

        ts += rng.randint(3600, 7200)
        approved = rng.random() < QC_APPROVAL_RATE
        if approved:
            events.append({
                "activity": "QualityControlApproved",
                "timestamp": ts,
                "lotId": lot_id,
                "status": "qc_approved",
            })
        else:
            events.append({
                "activity": "QualityControlRejected",
                "timestamp": ts,
                "lotId": lot_id,
                "status": "qc_rejected",
            })
            continue

        shipment_id = f"{lot_id}-SHIP"
        ts += rng.randint(1800, 3600)
        events.append({
            "activity": "LotShipped",
            "timestamp": ts,
            "lotId": lot_id,
            "shipmentId": shipment_id,
            "carrier": rng.choice(CARRIERS),
            "destination": rng.choice(DESTINATIONS),
            "status": "shipped",
        })

        ts += rng.randint(3600, 86400)
        events.append({
            "activity": "LotDelivered",
            "timestamp": ts,
            "lotId": lot_id,
            "shipmentId": shipment_id,
            "status": "delivered",
        })

    events.sort(key=lambda e: e["timestamp"])
    return events

FABRIC_ACTIVITIES = {"LotCreated", "RawMaterialReceived", "QualityControlApproved", "QualityControlRejected"}
ETHEREUM_ACTIVITIES = {"LotShipped", "LotDelivered"}

def split_trace_by_chain(trace):
    fabric_events = [e for e in trace if e["activity"] in FABRIC_ACTIVITIES]
    ethereum_events = [e for e in trace if e["activity"] in ETHEREUM_ACTIVITIES]
    return fabric_events, ethereum_events
