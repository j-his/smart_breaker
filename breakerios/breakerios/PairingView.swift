//
//  PairingView.swift
//  breakerios
//
//  Created by Tong tong Wang on 28/2/2026.
//

import SwiftUI
import CoreBluetooth

struct PairingView: View {
    @StateObject private var ble = BLEManager.shared
    @State private var step: PairingStep = .scanning
    @State private var ssid = ""
    @State private var password = ""
    @Binding var isPaired: Bool

    enum PairingStep {
        case scanning, wifiSetup
    }

    var body: some View {
        NavigationStack {
            Group {
                switch step {
                case .scanning:
                    scanningView
                case .wifiSetup:
                    wifiSetupView
                }
            }
            .navigationTitle("Set Up Device")
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    NavigationLink {
                        AboutView()
                    } label: {
                        Image(systemName: "info.circle")
                    }
                }
            }
        }
    }

    // MARK: - Scanning View

    private var scanningView: some View {
        VStack(spacing: 24) {
            Spacer()

            Image(systemName: "antenna.radiowaves.left.and.right")
                .font(.system(size: 64))
                .foregroundStyle(.blue)
                .symbolEffect(.variableColor.iterative, isActive: ble.isScanning)

            HStack(alignment: .firstTextBaseline, spacing: 0) {
                Text("Looking for Save Box")
                    .font(.title2)
                    .fontWeight(.semibold)
                Text("™")
                    .font(.caption)
                    .fontWeight(.semibold)
                    .baselineOffset(6)
                Text(" Devices")
                    .font(.title2)
                    .fontWeight(.semibold)
            }

            Text("Make sure your SaveBox is powered on and nearby.")
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 40)

            if ble.discoveredPeripherals.isEmpty && ble.isScanning {
                ProgressView()
                    .padding(.top)
            }

            List(ble.discoveredPeripherals, id: \.identifier) { peripheral in
                Button {
                    ble.connect(to: peripheral)
                    step = .wifiSetup
                } label: {
                    HStack {
                        Image(systemName: "bolt.circle.fill")
                            .foregroundStyle(.blue)
                            .font(.title3)
                        VStack(alignment: .leading, spacing: 2) {
                            Text(peripheral.name ?? "Unknown Device")
                                .font(.headline)
                            Text(peripheral.identifier.uuidString.prefix(8) + "...")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                        Spacer()
                        Image(systemName: "chevron.right")
                            .foregroundStyle(.secondary)
                    }
                    .padding(.vertical, 4)
                }
            }
            .listStyle(.insetGrouped)
            .frame(maxHeight: 300)
            .opacity(ble.discoveredPeripherals.isEmpty ? 0 : 1)

            Spacer()

            Button(ble.isScanning ? "Scanning..." : "Start Scanning") {
                ble.startScanning()
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.large)
            .disabled(ble.isScanning)

            Spacer()
        }
    }

    // MARK: - WiFi Setup View

    private var wifiSetupView: some View {
        VStack(spacing: 24) {
            Spacer()

            Image(systemName: "wifi")
                .font(.system(size: 56))
                .foregroundStyle(.blue)

            Text("Connect to WiFi")
                .font(.title2)
                .fontWeight(.semibold)

            Text("Your SaveBox needs WiFi to send data to the server.")
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 40)

            VStack(spacing: 16) {
                TextField("WiFi Network Name (SSID)", text: $ssid)
                    .textFieldStyle(.roundedBorder)
                    .autocorrectionDisabled()
                    .textInputAutocapitalization(.never)

                SecureField("Password", text: $password)
                    .textFieldStyle(.roundedBorder)
            }
            .padding(.horizontal, 32)

            if ble.isConnected {
                Label("Device Connected", systemImage: "checkmark.circle.fill")
                    .foregroundStyle(.green)
                    .font(.subheadline)
            } else {
                Label("Connecting...", systemImage: "ellipsis.circle")
                    .foregroundStyle(.orange)
                    .font(.subheadline)
            }

            Spacer()

            VStack(spacing: 12) {
                Button("Complete Setup") {
                    if ble.isConnected && !ssid.isEmpty {
                        ble.sendWiFiCredentials(ssid: ssid, password: password)
                    }
                    if ble.isConnected {
                        isPaired = true
                    }
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.large)
                .disabled(!ble.isConnected || ssid.isEmpty)
                
                Text("Bluetooth connection required to complete setup")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 32)
            }

            Spacer()
        }
    }
}
