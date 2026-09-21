
pragma solidity ^0.8.24;

contract PharmaSupplyChain {
    enum LotStatus { Created, QcApproved, QcRejected, Shipped, Delivered }

    struct Lot {
        string product;
        uint256 quantity;
        string manufacturer;
        LotStatus status;
        bool exists;
    }

    struct Shipment {
        string carrier;
        string destination;
        bool delivered;
        bool exists;
    }

    mapping(string => Lot) public lots;
    mapping(string => Shipment) public shipments;

    event LotCreated(string lotId, string product, uint256 quantity, string manufacturer, string status);
    event RawMaterialReceived(string lotId, string batchId, string materialName, string supplier, uint256 quantity);
    event QualityControlApproved(string lotId, string status);
    event QualityControlRejected(string lotId, string status);
    event LotShipped(string lotId, string shipmentId, string carrier, string destination, string status);
    event LotDelivered(string lotId, string shipmentId, string status);

    function createLot(string calldata lotId, string calldata product, uint256 quantity, string calldata manufacturer) external {
        require(!lots[lotId].exists, "lot exists");
        lots[lotId] = Lot(product, quantity, manufacturer, LotStatus.Created, true);
        emit LotCreated(lotId, product, quantity, manufacturer, "created");
    }

    function receiveRawMaterial(string calldata lotId, string calldata batchId, string calldata materialName, string calldata supplier, uint256 quantity) external {
        require(lots[lotId].exists, "unknown lot");
        emit RawMaterialReceived(lotId, batchId, materialName, supplier, quantity);
    }

    function approveQualityControl(string calldata lotId) external {
        require(lots[lotId].exists, "unknown lot");
        lots[lotId].status = LotStatus.QcApproved;
        emit QualityControlApproved(lotId, "qc_approved");
    }

    function rejectQualityControl(string calldata lotId) external {
        require(lots[lotId].exists, "unknown lot");
        lots[lotId].status = LotStatus.QcRejected;
        emit QualityControlRejected(lotId, "qc_rejected");
    }

    function shipLot(string calldata lotId, string calldata shipmentId, string calldata carrier, string calldata destination) external {
        require(lots[lotId].exists, "unknown lot");
        require(!shipments[shipmentId].exists, "shipment exists");
        shipments[shipmentId] = Shipment(carrier, destination, false, true);
        lots[lotId].status = LotStatus.Shipped;
        emit LotShipped(lotId, shipmentId, carrier, destination, "shipped");
    }

    function deliverLot(string calldata lotId, string calldata shipmentId) external {
        require(lots[lotId].exists, "unknown lot");
        require(shipments[shipmentId].exists, "unknown shipment");
        shipments[shipmentId].delivered = true;
        lots[lotId].status = LotStatus.Delivered;
        emit LotDelivered(lotId, shipmentId, "delivered");
    }
}
