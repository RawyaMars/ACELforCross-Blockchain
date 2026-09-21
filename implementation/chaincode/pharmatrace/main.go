package main

import (
	"encoding/json"
	"fmt"
	"log"
	"strconv"

	"github.com/hyperledger/fabric-contract-api-go/contractapi"
)

type Lot struct {
	LotID        string `json:"lotId"`
	Product      string `json:"product"`
	Quantity     string `json:"quantity"`
	Manufacturer string `json:"manufacturer"`
	Status       string `json:"status"`
}

type RawMaterialBatch struct {
	BatchID      string `json:"batchId"`
	LotID        string `json:"lotId"`
	MaterialName string `json:"materialName"`
	Supplier     string `json:"supplier"`
	Quantity     string `json:"quantity"`
}

type Shipment struct {
	ShipmentID  string `json:"shipmentId"`
	LotID       string `json:"lotId"`
	Carrier     string `json:"carrier"`
	Destination string `json:"destination"`
	Status      string `json:"status"`
}

type EventRecord struct {
	Seq       uint64            `json:"seq"`
	Activity  string            `json:"activity"`
	Timestamp int64             `json:"timestamp"`
	TxID      string            `json:"txId"`
	Fields    map[string]string `json:"fields"`
}

type SmartContract struct {
	contractapi.Contract
}

func (s *SmartContract) appendEvent(ctx contractapi.TransactionContextInterface, activity string, fields map[string]string) error {
	counterKey := "EVENT_COUNTER"
	raw, err := ctx.GetStub().GetState(counterKey)
	if err != nil {
		return err
	}
	var seq uint64
	if raw != nil {
		seq, err = strconv.ParseUint(string(raw), 10, 64)
		if err != nil {
			return err
		}
	}
	seq++
	if err := ctx.GetStub().PutState(counterKey, []byte(strconv.FormatUint(seq, 10))); err != nil {
		return err
	}

	ts, err := ctx.GetStub().GetTxTimestamp()
	if err != nil {
		return err
	}

	record := EventRecord{
		Seq:       seq,
		Activity:  activity,
		Timestamp: ts.Seconds,
		TxID:      ctx.GetStub().GetTxID(),
		Fields:    fields,
	}
	recordBytes, err := json.Marshal(record)
	if err != nil {
		return err
	}

	eventKey, err := ctx.GetStub().CreateCompositeKey("EVENT", []string{fmt.Sprintf("%020d", seq)})
	if err != nil {
		return err
	}
	if err := ctx.GetStub().PutState(eventKey, recordBytes); err != nil {
		return err
	}

	return ctx.GetStub().SetEvent(activity, recordBytes)
}

func (s *SmartContract) putAsset(ctx contractapi.TransactionContextInterface, key string, asset interface{}) error {
	bytes, err := json.Marshal(asset)
	if err != nil {
		return err
	}
	return ctx.GetStub().PutState(key, bytes)
}

func (s *SmartContract) CreateLot(ctx contractapi.TransactionContextInterface, lotID, product, quantity, manufacturer string) error {
	lot := Lot{LotID: lotID, Product: product, Quantity: quantity, Manufacturer: manufacturer, Status: "created"}
	if err := s.putAsset(ctx, "LOT_"+lotID, lot); err != nil {
		return err
	}
	return s.appendEvent(ctx, "LotCreated", map[string]string{
		"lotId": lotID, "product": product, "quantity": quantity, "manufacturer": manufacturer, "status": "created",
	})
}

func (s *SmartContract) ReceiveRawMaterial(ctx contractapi.TransactionContextInterface, lotID, batchID, materialName, supplier, quantity string) error {
	batch := RawMaterialBatch{BatchID: batchID, LotID: lotID, MaterialName: materialName, Supplier: supplier, Quantity: quantity}
	if err := s.putAsset(ctx, "BATCH_"+batchID, batch); err != nil {
		return err
	}
	return s.appendEvent(ctx, "RawMaterialReceived", map[string]string{
		"lotId": lotID, "batchId": batchID, "materialName": materialName, "supplier": supplier, "quantity": quantity,
	})
}

func (s *SmartContract) ApproveQualityControl(ctx contractapi.TransactionContextInterface, lotID string) error {
	return s.appendEvent(ctx, "QualityControlApproved", map[string]string{
		"lotId": lotID, "status": "qc_approved",
	})
}

func (s *SmartContract) RejectQualityControl(ctx contractapi.TransactionContextInterface, lotID string) error {
	return s.appendEvent(ctx, "QualityControlRejected", map[string]string{
		"lotId": lotID, "status": "qc_rejected",
	})
}

func (s *SmartContract) ShipLot(ctx contractapi.TransactionContextInterface, lotID, shipmentID, carrier, destination string) error {
	shipment := Shipment{ShipmentID: shipmentID, LotID: lotID, Carrier: carrier, Destination: destination, Status: "shipped"}
	if err := s.putAsset(ctx, "SHIPMENT_"+shipmentID, shipment); err != nil {
		return err
	}
	return s.appendEvent(ctx, "LotShipped", map[string]string{
		"lotId": lotID, "shipmentId": shipmentID, "carrier": carrier, "destination": destination, "status": "shipped",
	})
}

func (s *SmartContract) DeliverLot(ctx contractapi.TransactionContextInterface, lotID, shipmentID string) error {
	return s.appendEvent(ctx, "LotDelivered", map[string]string{
		"lotId": lotID, "shipmentId": shipmentID, "status": "delivered",
	})
}

func (s *SmartContract) GetAllEvents(ctx contractapi.TransactionContextInterface) (string, error) {
	iterator, err := ctx.GetStub().GetStateByPartialCompositeKey("EVENT", []string{})
	if err != nil {
		return "", err
	}
	defer iterator.Close()

	events := []json.RawMessage{}
	for iterator.HasNext() {
		item, err := iterator.Next()
		if err != nil {
			return "", err
		}
		events = append(events, json.RawMessage(item.Value))
	}

	result, err := json.Marshal(events)
	if err != nil {
		return "", err
	}
	return string(result), nil
}

func main() {
	chaincode, err := contractapi.NewChaincode(&SmartContract{})
	if err != nil {
		log.Panicf("Error creating pharmatrace chaincode: %v", err)
	}
	if err := chaincode.Start(); err != nil {
		log.Panicf("Error starting pharmatrace chaincode: %v", err)
	}
}
