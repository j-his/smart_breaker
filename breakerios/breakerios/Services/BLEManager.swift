//
//  BLEManager.swift
//  breakerios
//
//  Created by Tong tong Wang on 28/2/2026.
//

import Foundation
import CoreBluetooth
import Combine

class BLEManager: NSObject, ObservableObject {
    static let shared = BLEManager()

    // MARK: - BLE UUIDs

    static let serviceUUID = CBUUID(string: "12340001-1234-5678-9ABC-FEDCBA987654")
    static let wifiSSIDCharUUID = CBUUID(string: "12340002-1234-5678-9ABC-FEDCBA987654")
    static let wifiPasswordCharUUID = CBUUID(string: "12340003-1234-5678-9ABC-FEDCBA987654")
    static let wifiStatusCharUUID = CBUUID(string: "12340004-1234-5678-9ABC-FEDCBA987654")
    static let breakerStateCharUUID = CBUUID(string: "12340005-1234-5678-9ABC-FEDCBA987654")
    static let breakerCommandCharUUID = CBUUID(string: "12340006-1234-5678-9ABC-FEDCBA987654")

    // MARK: - Published State

    @Published var isConnected = false
    @Published var isScanning = false
    @Published var discoveredPeripherals: [CBPeripheral] = []
    @Published var breakerStates: [Bool] = [true, true, true, true]
    @Published var wifiStatus: UInt8 = 0x00
    @Published var connectedDeviceName: String?

    // MARK: - Private

    private var centralManager: CBCentralManager!
    private var connectedPeripheral: CBPeripheral?
    private var characteristics: [CBUUID: CBCharacteristic] = [:]

    private override init() {
        super.init()
        centralManager = CBCentralManager(delegate: self, queue: nil)
    }

    // MARK: - Public API

    func startScanning() {
        guard centralManager.state == .poweredOn else { return }
        discoveredPeripherals.removeAll()
        isScanning = true
        centralManager.scanForPeripherals(
            withServices: nil,
            options: [CBCentralManagerScanOptionAllowDuplicatesKey: false]
        )
    }

    func stopScanning() {
        centralManager.stopScan()
        isScanning = false
    }

    func connect(to peripheral: CBPeripheral) {
        stopScanning()
        connectedPeripheral = peripheral
        peripheral.delegate = self
        centralManager.connect(peripheral, options: nil)
    }

    func disconnect() {
        if let peripheral = connectedPeripheral {
            centralManager.cancelPeripheralConnection(peripheral)
        }
        cleanupConnection()
    }

    func sendWiFiCredentials(ssid: String, password: String) {
        guard let peripheral = connectedPeripheral else { return }

        if let ssidChar = characteristics[Self.wifiSSIDCharUUID],
           let ssidData = ssid.data(using: .utf8) {
            peripheral.writeValue(ssidData, for: ssidChar, type: .withResponse)
        }

        if let passChar = characteristics[Self.wifiPasswordCharUUID],
           let passData = password.data(using: .utf8) {
            peripheral.writeValue(passData, for: passChar, type: .withResponse)
        }
    }

    func toggleBreaker(channel: Int, on: Bool) {
        guard channel >= 0 && channel < 4,
              let peripheral = connectedPeripheral,
              let cmdChar = characteristics[Self.breakerCommandCharUUID] else { return }

        let command = Data([UInt8(channel), on ? 0x01 : 0x00])
        peripheral.writeValue(command, for: cmdChar, type: .withResponse)
    }

    func reconnectSavedDevice() {
        guard let uuidString = UserDefaults.standard.string(forKey: "pairedDeviceUUID"),
              let uuid = UUID(uuidString: uuidString) else { return }

        let peripherals = centralManager.retrievePeripherals(withIdentifiers: [uuid])
        if let peripheral = peripherals.first {
            connect(to: peripheral)
        }
    }

    // MARK: - Private Helpers

    private func cleanupConnection() {
        connectedPeripheral = nil
        characteristics.removeAll()
        isConnected = false
        connectedDeviceName = nil
    }
}

// MARK: - CBCentralManagerDelegate

extension BLEManager: CBCentralManagerDelegate {
    func centralManagerDidUpdateState(_ central: CBCentralManager) {
        if central.state != .poweredOn {
            isScanning = false
        }
    }

    func centralManager(_ central: CBCentralManager,
                        didDiscover peripheral: CBPeripheral,
                        advertisementData: [String: Any],
                        rssi RSSI: NSNumber) {
        let name = peripheral.name ?? ""
        guard name.hasPrefix("getmogged") else { return }

        if !discoveredPeripherals.contains(where: { $0.identifier == peripheral.identifier }) {
            discoveredPeripherals.append(peripheral)
        }
    }

    func centralManager(_ central: CBCentralManager, didConnect peripheral: CBPeripheral) {
        isConnected = true
        connectedDeviceName = peripheral.name
        peripheral.discoverServices([Self.serviceUUID])

        // Save for auto-reconnect
        UserDefaults.standard.set(peripheral.identifier.uuidString, forKey: "pairedDeviceUUID")
    }

    func centralManager(_ central: CBCentralManager,
                        didDisconnectPeripheral peripheral: CBPeripheral,
                        error: Error?) {
        cleanupConnection()

        // Auto-reconnect after brief delay
        DispatchQueue.main.asyncAfter(deadline: .now() + 2) { [weak self] in
            self?.reconnectSavedDevice()
        }
    }

    func centralManager(_ central: CBCentralManager,
                        didFailToConnect peripheral: CBPeripheral,
                        error: Error?) {
        cleanupConnection()
    }
}

// MARK: - CBPeripheralDelegate

extension BLEManager: CBPeripheralDelegate {
    func peripheral(_ peripheral: CBPeripheral, didDiscoverServices error: Error?) {
        guard let services = peripheral.services else { return }
        for service in services where service.uuid == Self.serviceUUID {
            peripheral.discoverCharacteristics([
                Self.wifiSSIDCharUUID,
                Self.wifiPasswordCharUUID,
                Self.wifiStatusCharUUID,
                Self.breakerStateCharUUID,
                Self.breakerCommandCharUUID,
            ], for: service)
        }
    }

    func peripheral(_ peripheral: CBPeripheral,
                    didDiscoverCharacteristicsFor service: CBService,
                    error: Error?) {
        guard let chars = service.characteristics else { return }
        for char in chars {
            characteristics[char.uuid] = char

            // Subscribe to notify characteristics
            if char.uuid == Self.breakerStateCharUUID || char.uuid == Self.wifiStatusCharUUID {
                peripheral.setNotifyValue(true, for: char)
            }

            // Read initial values
            if char.properties.contains(.read) {
                peripheral.readValue(for: char)
            }
        }
    }

    func peripheral(_ peripheral: CBPeripheral,
                    didUpdateValueFor characteristic: CBCharacteristic,
                    error: Error?) {
        guard let data = characteristic.value else { return }

        switch characteristic.uuid {
        case Self.breakerStateCharUUID:
            guard let byte = data.first else { return }
            breakerStates = (0..<4).map { bit in (byte >> bit) & 1 == 1 }

        case Self.wifiStatusCharUUID:
            if let byte = data.first {
                wifiStatus = byte
            }

        default:
            break
        }
    }
}
