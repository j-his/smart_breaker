//
//  SettingsView.swift
//  breakerios
//
//  Created by Tong tong Wang on 28/2/2026.
//

import SwiftUI
import Combine

struct SettingsView: View {
    @StateObject private var viewModel = SettingsViewModel()
    @ObservedObject private var ble = BLEManager.shared
    @State private var showUnpairConfirmation = false
    @State private var wifiSSID = ""
    @State private var wifiPassword = ""
    @State private var showWiFiSentAlert = false

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    NavigationLink {
                        AboutView()
                    } label: {
                        Label("About SaveBox", systemImage: "info.circle")
                    }
                }
                
                Section("Hardware Connection") {
                    HStack {
                        Text("BLE Status")
                        Spacer()
                        HStack(spacing: 6) {
                            Circle()
                                .fill(ble.isConnected ? Color.green : Color.orange)
                                .frame(width: 8, height: 8)
                            Text(ble.isConnected ? "Connected" : "Disconnected")
                                .font(.subheadline)
                                .foregroundStyle(.secondary)
                        }
                    }

                    if let name = ble.connectedDeviceName {
                        HStack {
                            Text("Device")
                            Spacer()
                            Text(name)
                                .font(.subheadline)
                                .foregroundStyle(.secondary)
                        }
                    }

                    HStack {
                        Text("WiFi")
                        Spacer()
                        Text(wifiStatusText)
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                    }

                    Button("Unpair Device", role: .destructive) {
                        showUnpairConfirmation = true
                    }
                    .confirmationDialog("Unpair Device?", isPresented: $showUnpairConfirmation) {
                        Button("Unpair", role: .destructive) {
                            ble.disconnect()
                            UserDefaults.standard.removeObject(forKey: "pairedDeviceUUID")
                        }
                    } message: {
                        Text("This will disconnect and forget the Smart Breaker. You'll need to pair again.")
                    }
                }
                
                Section("WiFi Configuration") {
                    TextField("WiFi Network Name (SSID)", text: $wifiSSID)
                        .autocorrectionDisabled()
                        .textInputAutocapitalization(.never)
                    
                    SecureField("WiFi Password", text: $wifiPassword)
                        .autocorrectionDisabled()
                        .textInputAutocapitalization(.never)
                    
                    Button("Send to Device") {
                        ble.sendWiFiCredentials(ssid: wifiSSID, password: wifiPassword)
                        showWiFiSentAlert = true
                    }
                    .disabled(!ble.isConnected || wifiSSID.isEmpty || wifiPassword.isEmpty)
                }
                .alert("WiFi Credentials Sent", isPresented: $showWiFiSentAlert) {
                    Button("OK") { }
                } message: {
                    Text("The WiFi network name and password have been sent to the device. Check the WiFi status above to see if the connection is successful.")
                }

                Section("Device Configuration") {
                    ForEach(0..<4) { channelId in
                        NavigationLink {
                            ChannelConfigView(channelId: channelId, config: viewModel.channelConfigs[channelId]) { updated in
                                viewModel.channelConfigs[channelId] = updated
                                viewModel.saveChannelConfigs()
                            }
                        } label: {
                            HStack {
                                Text("Channel \(channelId)")
                                    .fontWeight(.medium)
                                Spacer()
                                VStack(alignment: .trailing, spacing: 2) {
                                    Text(viewModel.channelConfigs[channelId].zone)
                                        .font(.subheadline)
                                        .foregroundStyle(.primary)
                                    Text(viewModel.channelConfigs[channelId].appliance)
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                }
                            }
                        }
                    }
                }

                Section("Optimization Weights") {
                    VStack(alignment: .leading, spacing: 8) {
                        HStack {
                            Text("Cost Priority (α)")
                                .font(.subheadline)
                            Spacer()
                            Text(String(format: "%.2f", viewModel.alpha))
                                .font(.subheadline)
                                .foregroundStyle(.secondary)
                        }

                        Slider(value: $viewModel.alpha, in: 0...1, step: 0.1)

                        Text("Higher values prioritize cost savings over carbon reduction")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                    .padding(.vertical, 4)

                    VStack(alignment: .leading, spacing: 8) {
                        HStack {
                            Text("Carbon Priority (β)")
                                .font(.subheadline)
                            Spacer()
                            Text(String(format: "%.2f", viewModel.beta))
                                .font(.subheadline)
                                .foregroundStyle(.secondary)
                        }

                        Slider(value: $viewModel.beta, in: 0...1, step: 0.1)

                        Text("Higher values prioritize carbon reduction over cost savings")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                    .padding(.vertical, 4)

                    Button("Save Weights") {
                        Task { await viewModel.saveSettings() }
                    }
                    .disabled(viewModel.isSaving)
                }

                Section("Server Configuration") {
                    TextField("Server URL", text: $viewModel.serverURL)
                        .autocorrectionDisabled()
                        .textInputAutocapitalization(.never)
                        .keyboardType(.URL)

                    HStack {
                        Text("Connection")
                        Spacer()
                        HStack(spacing: 6) {
                            Circle()
                                .fill(viewModel.isConnected ? Color.green : Color.red)
                                .frame(width: 8, height: 8)
                            Text(viewModel.isConnected ? "Connected" : "Offline")
                                .font(.subheadline)
                                .foregroundStyle(.secondary)
                        }
                    }

                    Button("Test Connection") {
                        Task {
                            await viewModel.testConnection()
                        }
                    }

                    if let result = viewModel.connectionTestResult {
                        Text(result)
                            .font(.caption)
                            .foregroundStyle(viewModel.isConnected ? .green : .red)
                    }
                }

                Section("Calendar Sync") {
                    Button {
                        viewModel.subscribeToCalendar()
                    } label: {
                        Label("Add to iPhone Calendar", systemImage: "calendar.badge.plus")
                    }

                    Text("Adds your optimized energy schedule as a subscribed calendar that updates automatically.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }

                Section("Notifications") {
                    Toggle("Anomaly Alerts", isOn: $viewModel.anomalyAlertsEnabled)
                    Toggle("Grid Status Changes", isOn: $viewModel.gridStatusAlertsEnabled)
                    Toggle("Optimization Complete", isOn: $viewModel.optimizationAlertsEnabled)
                }

                Section {
                    Button("Reset to Defaults") {
                        viewModel.resetToDefaults()
                    }
                    .foregroundStyle(.red)
                }
            }
            .navigationTitle("Settings")
            .onDisappear {
                viewModel.persistToUserDefaults()
            }
        }
    }

    private var wifiStatusText: String {
        switch ble.wifiStatus {
        case 0x00: return "Disconnected"
        case 0x01: return "Connecting..."
        case 0x02: return "Connected"
        case 0x03: return "Failed"
        default: return "Unknown"
        }
    }
}

struct ChannelConfigView: View {
    let channelId: Int
    @State var config: ChannelConfig
    @Environment(\.dismiss) var dismiss
    let onSave: (ChannelConfig) -> Void

    var body: some View {
        Form {
            Section("Channel \(channelId)") {
                TextField("Zone Name", text: $config.zone)
                    .autocorrectionDisabled()

                TextField("Appliance", text: $config.appliance)
                    .autocorrectionDisabled()
            }

            Section("Quick Presets") {
                Button("Bathroom - Water Heater") {
                    config.zone = "Bathroom"
                    config.appliance = "Water Heater"
                }

                Button("Kitchen - Induction Stove") {
                    config.zone = "Kitchen"
                    config.appliance = "Induction Stove"
                }

                Button("Laundry - Dryer") {
                    config.zone = "Laundry Room"
                    config.appliance = "Dryer"
                }

                Button("Garage - EV Charger") {
                    config.zone = "Garage"
                    config.appliance = "EV Charger"
                }

                Button("Living Room - Air Conditioning") {
                    config.zone = "Living Room"
                    config.appliance = "Air Conditioning"
                }

                Button("Bedroom - Air Conditioning") {
                    config.zone = "Bedroom"
                    config.appliance = "Air Conditioning"
                }
            }
        }
        .navigationTitle("Configure Channel \(channelId)")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .confirmationAction) {
                Button("Save") {
                    onSave(config)
                    dismiss()
                }
            }
        }
    }
}

struct ChannelConfig: Codable {
    var zone: String
    var appliance: String
}

class SettingsViewModel: ObservableObject {
    @Published var channelConfigs: [ChannelConfig] = []
    @Published var alpha: Double = 0.5
    @Published var beta: Double = 0.5
    @Published var serverURL: String = "http://localhost:8000"
    @Published var isConnected: Bool = false
    @Published var connectionTestResult: String?
    @Published var isSaving = false
    @Published var anomalyAlertsEnabled: Bool = true
    @Published var gridStatusAlertsEnabled: Bool = true
    @Published var optimizationAlertsEnabled: Bool = true

    init() {
        loadFromUserDefaults()
    }

    func testConnection() async {
        do {
            persistToUserDefaults()
            let health = try await APIClient.shared.getHealth()
            isConnected = true
            connectionTestResult = "Connected! Buffer: \(health.bufferFill), \(health.wsClients) client(s)"
        } catch {
            isConnected = false
            connectionTestResult = error.localizedDescription
        }
    }

    func subscribeToCalendar() {
        // Convert http(s):// to webcal:// and append the .ics path
        var base = serverURL
            .replacingOccurrences(of: "https://", with: "webcal://")
            .replacingOccurrences(of: "http://", with: "webcal://")
        if base.hasSuffix("/") { base.removeLast() }
        let webcalURL = base + "/api/calendar.ics"
        if let url = URL(string: webcalURL) {
            UIApplication.shared.open(url)
        }
    }

    func saveSettings() async {
        isSaving = true
        persistToUserDefaults()

        let request = SettingsRequest(alpha: alpha, beta: beta)
        _ = try? await APIClient.shared.updateSettings(request)
        isSaving = false
    }

    func saveChannelConfigs() {
        if let data = try? JSONEncoder().encode(channelConfigs) {
            UserDefaults.standard.set(data, forKey: "channelConfigs")
        }
    }

    func persistToUserDefaults() {
        UserDefaults.standard.set(serverURL, forKey: "serverURL")
        UserDefaults.standard.set(alpha, forKey: "alpha")
        UserDefaults.standard.set(beta, forKey: "beta")
        UserDefaults.standard.set(anomalyAlertsEnabled, forKey: "anomalyAlerts")
        UserDefaults.standard.set(gridStatusAlertsEnabled, forKey: "gridStatusAlerts")
        UserDefaults.standard.set(optimizationAlertsEnabled, forKey: "optimizationAlerts")
        saveChannelConfigs()
    }

    func resetToDefaults() {
        alpha = 0.5
        beta = 0.5
        anomalyAlertsEnabled = true
        gridStatusAlertsEnabled = true
        optimizationAlertsEnabled = true

        channelConfigs = Self.defaultConfigs
        persistToUserDefaults()
    }

    private func loadFromUserDefaults() {
        serverURL = UserDefaults.standard.string(forKey: "serverURL") ?? "http://localhost:8000"

        if UserDefaults.standard.object(forKey: "alpha") != nil {
            alpha = UserDefaults.standard.double(forKey: "alpha")
        }
        if UserDefaults.standard.object(forKey: "beta") != nil {
            beta = UserDefaults.standard.double(forKey: "beta")
        }

        anomalyAlertsEnabled = UserDefaults.standard.object(forKey: "anomalyAlerts") as? Bool ?? true
        gridStatusAlertsEnabled = UserDefaults.standard.object(forKey: "gridStatusAlerts") as? Bool ?? true
        optimizationAlertsEnabled = UserDefaults.standard.object(forKey: "optimizationAlerts") as? Bool ?? true

        if let data = UserDefaults.standard.data(forKey: "channelConfigs"),
           let configs = try? JSONDecoder().decode([ChannelConfig].self, from: data) {
            channelConfigs = configs
        } else {
            channelConfigs = Self.defaultConfigs
        }
    }

    private static let defaultConfigs = [
        ChannelConfig(zone: "Kitchen", appliance: "Induction Stove"),
        ChannelConfig(zone: "Laundry Room", appliance: "Dryer"),
        ChannelConfig(zone: "Garage", appliance: "EV Charger"),
        ChannelConfig(zone: "Bedroom", appliance: "Air Conditioning"),
    ]
}

#Preview {
    SettingsView()
}
