
import json
import subprocess

from fabric_env import CHAINCODE, CHANNEL, ORDERER_ADDRESS, ORDERER_CA, peer_cli_env
from scenario import generate_trace

def _args_for(event):
    activity = event["activity"]
    if activity == "LotCreated":
        return ["CreateLot", event["lotId"], event["product"], str(event["quantity"]), event["manufacturer"]]
    if activity == "RawMaterialReceived":
        return ["ReceiveRawMaterial", event["lotId"], event["batchId"], event["materialName"], event["supplier"], str(event["quantity"])]
    if activity == "QualityControlApproved":
        return ["ApproveQualityControl", event["lotId"]]
    if activity == "QualityControlRejected":
        return ["RejectQualityControl", event["lotId"]]
    if activity == "LotShipped":
        return ["ShipLot", event["lotId"], event["shipmentId"], event["carrier"], event["destination"]]
    if activity == "LotDelivered":
        return ["DeliverLot", event["lotId"], event["shipmentId"]]
    raise ValueError(f"unknown activity: {activity}")

def invoke(args, env):
    cc_args = json.dumps({"Args": args})
    cmd = [
        "peer", "chaincode", "invoke",
        "-o", ORDERER_ADDRESS,
        "-C", CHANNEL,
        "-n", CHAINCODE,
        "-c", cc_args,
        "--tls", "--cafile", ORDERER_CA,
        "--waitForEvent",
    ]
    result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"invoke failed for {args}: {result.stderr}")

def main(num_lots=50, seed=42, start_index=0):
    env = peer_cli_env()
    trace = generate_trace(num_lots, seed=seed, start_index=start_index)

    submitted = 0
    for e in trace:
        invoke(_args_for(e), env)
        submitted += 1
        if submitted % 25 == 0:
            print(f"  {submitted}/{len(trace)} submitted...")

    print(f"Submitted {submitted} real transactions to pharmatrace on {CHANNEL}")
    return submitted

if __name__ == "__main__":
    main()
