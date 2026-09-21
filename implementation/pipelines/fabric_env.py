
import os
from pathlib import Path

FABRIC_NETWORK_DIR = Path(__file__).resolve().parent.parent / "fabric-network"
FABRIC_SAMPLES_BIN = "/home/hyperledger2026/web3-env/fabric-samples/bin"

ORDERER_ADDRESS = "127.0.0.1:17050"
CHANNEL = "pharmachannel"
CHAINCODE = "pharmatrace"

ORDERER_CA = str(
    FABRIC_NETWORK_DIR / "crypto-config/ordererOrganizations/pharmaorderer.local"
    "/orderers/orderer.pharmaorderer.local/tls/ca.crt"
)
PEER_TLS_ROOTCERT = str(
    FABRIC_NETWORK_DIR / "crypto-config/peerOrganizations/pharmaorg.local"
    "/peers/peer0.pharmaorg.local/tls/ca.crt"
)
ADMIN_MSP = str(
    FABRIC_NETWORK_DIR / "crypto-config/peerOrganizations/pharmaorg.local"
    "/users/Admin@pharmaorg.local/msp"
)

def peer_cli_env():
    env = os.environ.copy()
    env["PATH"] = f"{FABRIC_SAMPLES_BIN}:{env.get('PATH', '')}"
    env["FABRIC_CFG_PATH"] = str(FABRIC_NETWORK_DIR / "config")
    env["FABRIC_LOGGING_SPEC"] = "WARNING"
    env["CORE_PEER_TLS_ENABLED"] = "true"
    env["CORE_PEER_TLS_ROOTCERT_FILE"] = PEER_TLS_ROOTCERT
    env["CORE_PEER_ADDRESS"] = "127.0.0.1:17051"
    env["CORE_PEER_LOCALMSPID"] = "PharmaOrgMSP"
    env["CORE_PEER_MSPCONFIGPATH"] = ADMIN_MSP
    return env
