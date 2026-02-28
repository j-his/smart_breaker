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
    
    var body: some View {
        NavigationStack {
            Form {
                Section("Device Configuration") {
                    ForEach(0..<4) { channelId in
                        NavigationLink {
                            ChannelConfigView(channelId: channelId, config: viewModel.channelConfigs[channelId])
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
                }
                
                Section("Server Configuration") {
                    HStack {
                        Text("Server URL")
                        Spacer()
                        Text(viewModel.serverURL)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                    
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
        }
    }
}

struct ChannelConfigView: View {
    let channelId: Int
    @State var config: ChannelConfig
    @Environment(\.dismiss) var dismiss
    
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
                    // TODO: Save to UserDefaults or API
                    dismiss()
                }
            }
        }
    }
}

struct ChannelConfig {
    var zone: String
    var appliance: String
}

@MainActor
class SettingsViewModel: ObservableObject {
    @Published var channelConfigs: [ChannelConfig] = [
        ChannelConfig(zone: "Bathroom", appliance: "Water Heater"),
        ChannelConfig(zone: "Kitchen", appliance: "Induction Stove"),
        ChannelConfig(zone: "Living Room", appliance: "Air Conditioning"),
        ChannelConfig(zone: "Garage", appliance: "EV Charger")
    ]
    
    @Published var alpha: Double = 0.5
    @Published var beta: Double = 0.5
    
    @Published var serverURL: String = "http://localhost:8000"
    @Published var isConnected: Bool = false
    
    @Published var anomalyAlertsEnabled: Bool = true
    @Published var gridStatusAlertsEnabled: Bool = true
    @Published var optimizationAlertsEnabled: Bool = true
    
    func testConnection() async {
        // TODO: Implement actual connection test
        isConnected = true
    }
    
    func resetToDefaults() {
        alpha = 0.5
        beta = 0.5
        anomalyAlertsEnabled = true
        gridStatusAlertsEnabled = true
        optimizationAlertsEnabled = true
        
        channelConfigs = [
            ChannelConfig(zone: "Bathroom", appliance: "Water Heater"),
            ChannelConfig(zone: "Kitchen", appliance: "Induction Stove"),
            ChannelConfig(zone: "Living Room", appliance: "Air Conditioning"),
            ChannelConfig(zone: "Garage", appliance: "EV Charger")
        ]
    }
}

#Preview {
    SettingsView()
}
