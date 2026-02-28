//
//  DeviceView.swift
//  breakerios
//
//  Created by Tong tong Wang on 28/2/2026.
//

import SwiftUI
import Combine

struct DeviceView: View {
    @StateObject private var viewModel = DeviceViewModel()
    
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 20) {
                    // Connection Status
                    HStack {
                        Circle()
                            .fill(viewModel.isConnected ? Color.green : Color.red)
                            .frame(width: 12, height: 12)
                        Text(viewModel.isConnected ? "Device Connected" : "Device Offline")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                        Spacer()
                    }
                    .padding(.horizontal)
                    
                    // Total Power Usage
                    VStack(spacing: 8) {
                        Text("Total Power")
                            .font(.headline)
                            .foregroundStyle(.secondary)
                        
                        HStack(alignment: .firstTextBaseline, spacing: 4) {
                            Text(String(format: "%.0f", viewModel.totalWatts))
                                .font(.system(size: 56, weight: .bold, design: .rounded))
                            Text("W")
                                .font(.title2)
                                .foregroundStyle(.secondary)
                        }
                        
                        // Power gauge
                        GeometryReader { geometry in
                            ZStack(alignment: .leading) {
                                RoundedRectangle(cornerRadius: 8)
                                    .fill(Color.gray.opacity(0.2))
                                
                                RoundedRectangle(cornerRadius: 8)
                                    .fill(LinearGradient(
                                        colors: powerGradientColors,
                                        startPoint: .leading,
                                        endPoint: .trailing
                                    ))
                                    .frame(width: geometry.size.width * min(CGFloat(viewModel.totalWatts / 7200), 1.0))
                            }
                        }
                        .frame(height: 12)
                        
                        HStack {
                            Text("0 W")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                            Spacer()
                            Text("7,200 W Max")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                    }
                    .padding()
                    .background(
                        RoundedRectangle(cornerRadius: 16)
                            .fill(Color(.secondarySystemBackground))
                    )
                    .padding(.horizontal)
                    
                    // Grid Status
                    GridStatusCard(grid: viewModel.gridSnapshot)
                        .padding(.horizontal)
                    
                    // Channel Readings
                    VStack(alignment: .leading, spacing: 12) {
                        Text("Breaker Channels")
                            .font(.title2)
                            .fontWeight(.bold)
                            .padding(.horizontal)
                        
                        ForEach(viewModel.channels) { channel in
                            ChannelCard(channel: channel)
                                .padding(.horizontal)
                        }
                    }
                    .padding(.top)
                }
                .padding(.vertical)
            }
            .navigationTitle("Smart Breaker")
            .refreshable {
                await viewModel.refresh()
            }
        }
        .task {
            await viewModel.startMonitoring()
        }
    }
    
    private var powerGradientColors: [Color] {
        let usage = viewModel.totalWatts / 7200
        if usage < 0.5 {
            return [.green, .green]
        } else if usage < 0.75 {
            return [.green, .yellow]
        } else {
            return [.yellow, .red]
        }
    }
}

struct ChannelCard: View {
    let channel: LiveChannel
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text("CH\(channel.channelId)")
                        .font(.caption)
                        .fontWeight(.semibold)
                        .foregroundStyle(.secondary)
                    
                    Text(channel.assignedZone)
                        .font(.headline)
                    
                    Text(channel.assignedAppliance)
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }
                
                Spacer()
                
                VStack(alignment: .trailing, spacing: 4) {
                    HStack(alignment: .firstTextBaseline, spacing: 2) {
                        Text(String(format: "%.0f", channel.currentWatts))
                            .font(.system(size: 28, weight: .bold, design: .rounded))
                        Text("W")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                    }
                    
                    HStack(spacing: 4) {
                        Circle()
                            .fill(channel.isActive ? Color.green : Color.gray)
                            .frame(width: 8, height: 8)
                        Text(channel.isActive ? "Active" : "Idle")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
            }
        }
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 12)
                .fill(Color(.secondarySystemBackground))
                .overlay(
                    RoundedRectangle(cornerRadius: 12)
                        .strokeBorder(channel.isActive ? Color.green.opacity(0.3) : Color.clear, lineWidth: 2)
                )
        )
    }
}

struct GridStatusCard: View {
    let grid: GridSnapshot
    
    var body: some View {
        VStack(spacing: 12) {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Grid Status")
                        .font(.headline)
                    
                    HStack(spacing: 6) {
                        Circle()
                            .fill(gridColor)
                            .frame(width: 12, height: 12)
                        Text(grid.status.rawValue.capitalized)
                            .font(.subheadline)
                            .fontWeight(.semibold)
                    }
                }
                
                Spacer()
                
                VStack(alignment: .trailing, spacing: 4) {
                    HStack(alignment: .firstTextBaseline, spacing: 2) {
                        Text(String(format: "%.1f", grid.touPriceCentsKwh))
                            .font(.title2)
                            .fontWeight(.bold)
                        Text("¢/kWh")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                    
                    Text(touPeriodText)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
            
            Divider()
            
            HStack(spacing: 20) {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Renewable")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    HStack(alignment: .firstTextBaseline, spacing: 2) {
                        Text(String(format: "%.1f", grid.renewablePct))
                            .font(.headline)
                        Text("%")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
                
                Spacer()
                
                VStack(alignment: .trailing, spacing: 4) {
                    Text("Carbon Intensity")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    HStack(alignment: .firstTextBaseline, spacing: 2) {
                        Text(String(format: "%.0f", grid.carbonIntensityGco2Kwh))
                            .font(.headline)
                        Text("g/kWh")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
            }
        }
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 16)
                .fill(gridColor.opacity(0.1))
                .overlay(
                    RoundedRectangle(cornerRadius: 16)
                        .strokeBorder(gridColor.opacity(0.3), lineWidth: 2)
                )
        )
    }
    
    private var gridColor: Color {
        switch grid.status {
        case .green: return .green
        case .yellow: return .yellow
        case .red: return .red
        }
    }
    
    private var touPeriodText: String {
        switch grid.touPeriod {
        case .peak: return "Peak"
        case .offPeak: return "Off-Peak"
        case .superOffPeak: return "Super Off-Peak"
        }
    }
}

@MainActor
class DeviceViewModel: ObservableObject {
    @Published var channels: [LiveChannel] = []
    @Published var totalWatts: Float = 0
    @Published var gridSnapshot: GridSnapshot = GridSnapshot(
        renewablePct: 0,
        carbonIntensityGco2Kwh: 0,
        touPriceCentsKwh: 0,
        touPeriod: .offPeak,
        status: .yellow
    )
    @Published var isConnected: Bool = false
    
    func startMonitoring() async {
        // Load demo data
        loadDemoData()
        
        // Simulate live updates
        while true {
            try? await Task.sleep(for: .seconds(2))
            updateLiveReadings()
        }
    }
    
    func refresh() async {
        loadDemoData()
    }
    
    private func loadDemoData() {
        let dashboard = DashboardResponse.demo
        channels = .demo
        totalWatts = dashboard.currentPower.totalWatts
        gridSnapshot = dashboard.grid
        isConnected = dashboard.hardwareConnected
    }
    
    private func updateLiveReadings() {
        // Simulate fluctuating power readings
        for i in 0..<channels.count {
            let baseWatts = channels[i].currentWatts
            let variation = Float.random(in: -50...50)
            let newWatts = max(0, baseWatts + variation)
            
            channels[i] = LiveChannel(
                channelId: channels[i].channelId,
                assignedZone: channels[i].assignedZone,
                assignedAppliance: channels[i].assignedAppliance,
                currentWatts: newWatts,
                isActive: newWatts > 10
            )
        }
        
        totalWatts = channels.reduce(0) { $0 + $1.currentWatts }
    }
}

#Preview {
    DeviceView()
}
