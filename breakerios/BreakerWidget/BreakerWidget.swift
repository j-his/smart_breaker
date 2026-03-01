//
//  BreakerWidget.swift
//  BreakerWidget
//
//  Created by Tong tong Wang on 28/2/2026.
//

import WidgetKit
import SwiftUI

// MARK: - Data Model

struct WidgetPowerData {
    let totalWatts: Float
    let gridStatus: String
    let renewablePct: Float
    let touPrice: Float
    let channels: [(zone: String, watts: Float)]
    let isStale: Bool

    static var placeholder: WidgetPowerData {
        WidgetPowerData(
            totalWatts: 2500,
            gridStatus: "green",
            renewablePct: 67.5,
            touPrice: 12.5,
            channels: [
                ("Kitchen", 850),
                ("Laundry", 1200),
                ("Garage", 450),
                ("Bedroom", 0),
            ],
            isStale: false
        )
    }
}

// MARK: - API Fetch

struct WidgetDashboardResponse: Codable {
    let currentPower: WidgetCurrentPower
    let grid: WidgetGridSnapshot
    let hardwareConnected: Bool

    struct WidgetCurrentPower: Codable {
        let ch0Watts: Float
        let ch1Watts: Float
        let ch2Watts: Float
        let ch3Watts: Float
        let totalWatts: Float
    }

    struct WidgetGridSnapshot: Codable {
        let renewablePct: Float
        let touPriceCentsKwh: Float
        let status: String
    }
}

func fetchDashboard() async -> WidgetPowerData? {
    let defaults = UserDefaults(suiteName: "group.com.tongtonginc.breakerios")
    let baseURL = defaults?.string(forKey: "serverURL")
        ?? UserDefaults.standard.string(forKey: "serverURL")
        ?? "http://localhost:8000"

    guard let url = URL(string: baseURL + "/api/dashboard") else { return nil }

    do {
        let (data, _) = try await URLSession.shared.data(from: url)
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        let response = try decoder.decode(WidgetDashboardResponse.self, from: data)

        let channels: [(String, Float)] = [
            ("CH0", response.currentPower.ch0Watts),
            ("CH1", response.currentPower.ch1Watts),
            ("CH2", response.currentPower.ch2Watts),
            ("CH3", response.currentPower.ch3Watts),
        ]

        return WidgetPowerData(
            totalWatts: response.currentPower.totalWatts,
            gridStatus: response.grid.status,
            renewablePct: response.grid.renewablePct,
            touPrice: response.grid.touPriceCentsKwh,
            channels: channels,
            isStale: false
        )
    } catch {
        return nil
    }
}

// MARK: - Timeline Provider

struct PowerTimelineProvider: TimelineProvider {
    func placeholder(in context: Context) -> PowerEntry {
        PowerEntry(date: .now, data: .placeholder)
    }

    func getSnapshot(in context: Context, completion: @escaping (PowerEntry) -> Void) {
        if context.isPreview {
            completion(PowerEntry(date: .now, data: .placeholder))
            return
        }

        Task {
            let data = await fetchDashboard() ?? .placeholder
            completion(PowerEntry(date: .now, data: data))
        }
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<PowerEntry>) -> Void) {
        Task {
            let data = await fetchDashboard()
                ?? WidgetPowerData(
                    totalWatts: 0,
                    gridStatus: "unknown",
                    renewablePct: 0,
                    touPrice: 0,
                    channels: [],
                    isStale: true
                )

            let entry = PowerEntry(date: .now, data: data)
            let nextUpdate = Calendar.current.date(byAdding: .minute, value: 5, to: .now)!
            let timeline = Timeline(entries: [entry], policy: .after(nextUpdate))
            completion(timeline)
        }
    }
}

struct PowerEntry: TimelineEntry {
    let date: Date
    let data: WidgetPowerData
}

// MARK: - Widget Views

struct BreakerWidgetSmallView: View {
    let entry: PowerEntry

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: "bolt.circle.fill")
                    .foregroundStyle(gridColor)
                Text("EnergyAI")
                    .font(.caption)
                    .fontWeight(.semibold)
                    .foregroundStyle(.secondary)
            }

            Spacer()

            HStack(alignment: .firstTextBaseline, spacing: 2) {
                Text(String(format: "%.0f", entry.data.totalWatts))
                    .font(.system(size: 36, weight: .bold, design: .rounded))
                Text("W")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }

            HStack(spacing: 4) {
                Circle()
                    .fill(gridColor)
                    .frame(width: 8, height: 8)
                Text(String(format: "%.0f%%", entry.data.renewablePct) + " renewable")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }

            if entry.data.isStale {
                Text("No connection")
                    .font(.caption2)
                    .foregroundStyle(.red)
            }
        }
        .containerBackground(.fill.tertiary, for: .widget)
    }

    private var gridColor: Color {
        switch entry.data.gridStatus {
        case "green": return .green
        case "yellow": return .yellow
        case "red": return .red
        default: return .gray
        }
    }
}

struct BreakerWidgetMediumView: View {
    let entry: PowerEntry

    var body: some View {
        HStack(spacing: 16) {
            // Left: Total power
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Image(systemName: "bolt.circle.fill")
                        .foregroundStyle(gridColor)
                    Text("EnergyAI")
                        .font(.caption)
                        .fontWeight(.semibold)
                        .foregroundStyle(.secondary)
                }

                Spacer()

                HStack(alignment: .firstTextBaseline, spacing: 2) {
                    Text(String(format: "%.0f", entry.data.totalWatts))
                        .font(.system(size: 36, weight: .bold, design: .rounded))
                    Text("W")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }

                HStack(spacing: 8) {
                    Label(String(format: "%.0f%%", entry.data.renewablePct), systemImage: "leaf.fill")
                        .font(.caption2)
                        .foregroundStyle(.green)

                    Label(String(format: "%.1f¢", entry.data.touPrice), systemImage: "dollarsign.circle")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
            }

            Divider()

            // Right: Channel breakdown
            VStack(alignment: .leading, spacing: 6) {
                Text("Channels")
                    .font(.caption)
                    .fontWeight(.semibold)
                    .foregroundStyle(.secondary)

                ForEach(Array(entry.data.channels.enumerated()), id: \.offset) { _, ch in
                    HStack {
                        Text(ch.zone)
                            .font(.caption2)
                            .lineLimit(1)
                        Spacer()
                        Text(String(format: "%.0fW", ch.watts))
                            .font(.caption2)
                            .fontWeight(.medium)
                            .monospacedDigit()
                    }
                }

                if entry.data.isStale {
                    Text("No connection")
                        .font(.caption2)
                        .foregroundStyle(.red)
                }
            }
        }
        .containerBackground(.fill.tertiary, for: .widget)
    }

    private var gridColor: Color {
        switch entry.data.gridStatus {
        case "green": return .green
        case "yellow": return .yellow
        case "red": return .red
        default: return .gray
        }
    }
}

// MARK: - Widget Definition

struct BreakerWidget: Widget {
    let kind: String = "BreakerWidget"

    var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: PowerTimelineProvider()) { entry in
            if #available(iOS 17.0, *) {
                BreakerWidgetEntryView(entry: entry)
            } else {
                BreakerWidgetEntryView(entry: entry)
            }
        }
        .configurationDisplayName("EnergyAI Power")
        .description("Real-time power usage and grid status at a glance.")
        .supportedFamilies([.systemSmall, .systemMedium])
    }
}

struct BreakerWidgetEntryView: View {
    @Environment(\.widgetFamily) var family
    let entry: PowerEntry

    var body: some View {
        switch family {
        case .systemMedium:
            BreakerWidgetMediumView(entry: entry)
        default:
            BreakerWidgetSmallView(entry: entry)
        }
    }
}

// MARK: - Widget Bundle

@main
struct BreakerWidgetBundle: WidgetBundle {
    var body: some Widget {
        BreakerWidget()
    }
}

// MARK: - Preview

#Preview("Small", as: .systemSmall) {
    BreakerWidget()
} timeline: {
    PowerEntry(date: .now, data: .placeholder)
}

#Preview("Medium", as: .systemMedium) {
    BreakerWidget()
} timeline: {
    PowerEntry(date: .now, data: .placeholder)
}
