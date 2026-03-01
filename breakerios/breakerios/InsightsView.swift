//
//  InsightsView.swift
//  breakerios
//
//  Created by Tong tong Wang on 28/2/2026.
//

import SwiftUI
import Combine

struct InsightsView: View {
    @StateObject private var viewModel = InsightsViewModel()

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 20) {
                    // Anomaly Alerts
                    if !viewModel.anomalies.isEmpty {
                        VStack(alignment: .leading, spacing: 12) {
                            Text("Active Alerts")
                                .font(.title3)
                                .fontWeight(.semibold)
                                .padding(.horizontal)

                            ForEach(viewModel.anomalies) { anomaly in
                                AnomalyCard(anomaly: anomaly)
                                    .padding(.horizontal)
                            }
                        }
                    }

                    // Insights
                    if viewModel.insights.isEmpty && viewModel.anomalies.isEmpty
                        && viewModel.loadingState != .loading {
                        ContentUnavailableView(
                            "No Insights Yet",
                            systemImage: "sparkles",
                            description: Text("AI-generated energy insights will appear here as the system monitors your usage")
                        )
                    } else {
                        VStack(alignment: .leading, spacing: 12) {
                            if !viewModel.insights.isEmpty {
                                Text("Energy Insights")
                                    .font(.title3)
                                    .fontWeight(.semibold)
                                    .padding(.horizontal)
                            }

                            ForEach(viewModel.insights) { insight in
                                InsightCard(
                                    insight: insight,
                                    isPlaying: TTSPlayer.shared.currentInsightId == insight.id
                                )
                                .padding(.horizontal)
                            }
                        }
                    }
                }
                .padding(.vertical)
            }
            .navigationTitle("Insights")
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
            await viewModel.loadData()
        }
    }
}

struct InsightCard: View {
    let insight: Insight
    let isPlaying: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: categoryIcon)
                    .foregroundStyle(severityColor)

                Capsule()
                    .fill(severityColor.opacity(0.1))
                    .frame(width: 70, height: 24)
                    .overlay(
                        Text(insight.severity.rawValue.capitalized)
                            .font(.caption2)
                            .fontWeight(.semibold)
                            .foregroundStyle(severityColor)
                    )

                Spacer()

                if isPlaying {
                    Image(systemName: "speaker.wave.2.fill")
                        .foregroundStyle(.blue)
                        .font(.caption)
                }
            }

            Text(insight.message)
                .font(.body)
                .foregroundStyle(.primary)
        }
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 12)
                .fill(Color(.secondarySystemBackground))
                .overlay(
                    RoundedRectangle(cornerRadius: 12)
                        .strokeBorder(severityColor.opacity(0.3), lineWidth: 1.5)
                )
        )
    }

    private var severityColor: Color {
        switch insight.severity {
        case .info: return .blue
        case .warning: return .yellow
        case .critical: return .red
        }
    }

    private var categoryIcon: String {
        switch insight.category {
        case .scheduleOptimization: return "calendar.badge.clock"
        case .anomaly: return "exclamationmark.triangle.fill"
        case .gridStatus: return "bolt.circle.fill"
        }
    }
}

struct AnomalyCard: View {
    let anomaly: AnomalyAlert

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "exclamationmark.triangle.fill")
                    .foregroundStyle(.red)

                Text(anomaly.assignedZone)
                    .font(.headline)

                Text("·")
                    .foregroundStyle(.secondary)

                Text(anomaly.assignedAppliance)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)

                Spacer()
            }

            HStack(alignment: .firstTextBaseline) {
                Text(String(format: "%.0f", anomaly.currentWatts))
                    .font(.system(size: 28, weight: .bold, design: .rounded))
                Text("W")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)

                Spacer()

                Text("Expected: \(String(format: "%.0f", anomaly.expectedWatts))W")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            Text(anomaly.message)
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 12)
                .fill(Color.red.opacity(0.05))
                .overlay(
                    RoundedRectangle(cornerRadius: 12)
                        .strokeBorder(Color.red.opacity(0.3), lineWidth: 1.5)
                )
        )
    }
}

class InsightsViewModel: ObservableObject {
    @Published var insights: [Insight] = []
    @Published var anomalies: [AnomalyAlert] = []
    @Published var loadingState: LoadingState = .idle

    private var cancellables = Set<AnyCancellable>()

    func loadData() async {
        loadingState = .loading

        do {
            let response = try await APIClient.shared.getInsights()
            insights = response.insights
        } catch {
            insights = []
        }

        loadingState = .loaded
        subscribeToWebSocket()
    }

    func refresh() async {
        do {
            let response = try await APIClient.shared.getInsights()
            insights = response.insights
        } catch {
            // Keep existing data
        }
    }

    private func subscribeToWebSocket() {
        WebSocketManager.shared.insightReceived
            .receive(on: DispatchQueue.main)
            .sink { [weak self] insight in
                self?.insights.insert(insight, at: 0)
            }
            .store(in: &cancellables)

        WebSocketManager.shared.anomalyReceived
            .receive(on: DispatchQueue.main)
            .sink { [weak self] anomaly in
                self?.anomalies.insert(anomaly, at: 0)
                if (self?.anomalies.count ?? 0) > 10 {
                    self?.anomalies = Array(self!.anomalies.prefix(10))
                }
            }
            .store(in: &cancellables)
    }
}

#Preview {
    InsightsView()
}
