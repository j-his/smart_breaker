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
                            ChannelCard(channel: channel) { channelId, on in
                                viewModel.toggleBreaker(channel: channelId, on: on)
                            }
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
            .overlay {
                if viewModel.loadingState == .loading {
                    ProgressView()
                }
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
    var onToggle: ((Int, Bool) -> Void)?

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

            // Breaker Toggle
            Toggle(isOn: Binding(
                get: { channel.isOn },
                set: { newValue in onToggle?(channel.channelId, newValue) }
            )) {
                Label("Breaker", systemImage: channel.isOn ? "power.circle.fill" : "power.circle")
                    .font(.subheadline)
                    .foregroundStyle(channel.isOn ? .primary : .secondary)
            }
            .tint(.green)
        }
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 12)
                .fill(Color(.secondarySystemBackground))
                .overlay(
                    RoundedRectangle(cornerRadius: 12)
                        .strokeBorder(channel.isOn ? (channel.isActive ? Color.green.opacity(0.3) : Color.clear) : Color.red.opacity(0.3), lineWidth: 2)
                )
        )
        .opacity(channel.isOn ? 1.0 : 0.6)
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
    @Published var loadingState: LoadingState = .idle

    private var cancellables = Set<AnyCancellable>()

    func startMonitoring() async {
        loadingState = .loading

        do {
            let dashboard = try await APIClient.shared.getDashboard()
            channels = channelsFromDashboard(dashboard)
            totalWatts = dashboard.currentPower.totalWatts
            gridSnapshot = dashboard.grid
            isConnected = dashboard.hardwareConnected
            loadingState = .loaded
        } catch {
            loadDemoData()
            loadingState = .loaded
        }

        subscribeToWebSocket()
    }

    func refresh() async {
        do {
            let dashboard = try await APIClient.shared.getDashboard()
            channels = channelsFromDashboard(dashboard)
            totalWatts = dashboard.currentPower.totalWatts
            gridSnapshot = dashboard.grid
            isConnected = dashboard.hardwareConnected
        } catch {
            loadDemoData()
        }
    }

    func toggleBreaker(channel: Int, on: Bool) {
        BLEManager.shared.toggleBreaker(channel: channel, on: on)
    }

    private func subscribeToWebSocket() {
        WebSocketManager.shared.sensorUpdate
            .receive(on: DispatchQueue.main)
            .sink { [weak self] update in
                self?.channels = update.channels
                self?.totalWatts = update.totalWatts
                self?.mergeBreakerStates()
            }
            .store(in: &cancellables)

        WebSocketManager.shared.gridStatusUpdate
            .receive(on: DispatchQueue.main)
            .sink { [weak self] update in
                self?.gridSnapshot = update.current
            }
            .store(in: &cancellables)

        WebSocketManager.shared.$isConnected
            .receive(on: DispatchQueue.main)
            .assign(to: &$isConnected)

        // Subscribe to BLE breaker state changes
        BLEManager.shared.$breakerStates
            .receive(on: DispatchQueue.main)
            .sink { [weak self] _ in
                self?.mergeBreakerStates()
            }
            .store(in: &cancellables)
    }

    private func mergeBreakerStates() {
        let states = BLEManager.shared.breakerStates
        for i in channels.indices where i < states.count {
            channels[i].isOn = states[i]
        }
    }

    private func loadDemoData() {
        let dashboard = DashboardResponse.demo
        channels = .demo
        totalWatts = dashboard.currentPower.totalWatts
        gridSnapshot = dashboard.grid
        isConnected = dashboard.hardwareConnected
    }

    private func channelsFromDashboard(_ d: DashboardResponse) -> [LiveChannel] {
        let configs: [(zone: String, appliance: String)] = [
            ("Kitchen", "Induction Stove"),
            ("Laundry Room", "Dryer"),
            ("Garage", "EV Charger"),
            ("Bedroom", "Air Conditioning"),
        ]
        let watts = [d.currentPower.ch0Watts, d.currentPower.ch1Watts,
                     d.currentPower.ch2Watts, d.currentPower.ch3Watts]

        return (0..<4).map { i in
            LiveChannel(
                channelId: i,
                assignedZone: configs[i].zone,
                assignedAppliance: configs[i].appliance,
                currentWatts: watts[i],
                isActive: watts[i] > 10
            )
        }
    }
}

#Preview {
    DeviceView()
}
