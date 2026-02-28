//
//  CalendarView.swift
//  breakerios
//
//  Created by Tong tong Wang on 28/2/2026.
//

import SwiftUI
import Combine

struct CalendarView: View {
    @StateObject private var viewModel = CalendarViewModel()
    
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 20) {
                    // Optimization Summary
                    if let optimization = viewModel.optimization {
                        OptimizationSummaryCard(result: optimization)
                            .padding(.horizontal)
                    }
                    
                    // 24-hour forecast
                    VStack(alignment: .leading, spacing: 12) {
                        Text("24-Hour Grid Forecast")
                            .font(.title3)
                            .fontWeight(.semibold)
                            .padding(.horizontal)
                        
                        ScrollView(.horizontal, showsIndicators: false) {
                            HStack(spacing: 12) {
                                ForEach(viewModel.forecast24h, id: \.hour) { forecast in
                                    ForecastHourCard(forecast: forecast)
                                }
                            }
                            .padding(.horizontal)
                        }
                    }
                    
                    // Optimized Events
                    VStack(alignment: .leading, spacing: 12) {
                        HStack {
                            Text("Optimized Schedule")
                                .font(.title2)
                                .fontWeight(.bold)
                            Spacer()
                            
                            Button(action: {
                                viewModel.showingAddTask = true
                            }) {
                                Image(systemName: "plus.circle.fill")
                                    .font(.title2)
                            }
                        }
                        .padding(.horizontal)
                        
                        if let events = viewModel.optimization?.optimizedEvents, !events.isEmpty {
                            ForEach(events) { event in
                                OptimizedEventCard(event: event)
                                    .padding(.horizontal)
                            }
                        } else {
                            ContentUnavailableView(
                                "No Scheduled Tasks",
                                systemImage: "calendar.badge.plus",
                                description: Text("Add tasks to optimize your energy usage")
                            )
                            .frame(height: 200)
                        }
                    }
                    .padding(.top)
                }
                .padding(.vertical)
            }
            .navigationTitle("Energy Schedule")
            .sheet(isPresented: $viewModel.showingAddTask) {
                AddTaskView()
            }
        }
        .task {
            await viewModel.loadData()
        }
    }
}

struct OptimizationSummaryCard: View {
    let result: OptimizationResult
    
    var body: some View {
        VStack(spacing: 16) {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Total Savings")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    HStack(alignment: .firstTextBaseline, spacing: 2) {
                        Text(String(format: "%.1f", result.totalSavingsCents))
                            .font(.title)
                            .fontWeight(.bold)
                            .foregroundStyle(.green)
                        Text("¢")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                    }
                }
                
                Spacer()
                
                VStack(alignment: .trailing, spacing: 4) {
                    Text("Carbon Avoided")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    HStack(alignment: .firstTextBaseline, spacing: 2) {
                        Text(String(format: "%.0f", result.totalCarbonAvoidedG))
                            .font(.title)
                            .fontWeight(.bold)
                            .foregroundStyle(.green)
                        Text("g")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                    }
                }
            }
            
            Divider()
            
            HStack {
                Image(systemName: "sparkles")
                    .foregroundStyle(.purple)
                Text("Optimization Confidence")
                    .font(.subheadline)
                Spacer()
                Text(String(format: "%.0f%%", result.optimizationConfidence * 100))
                    .font(.subheadline)
                    .fontWeight(.semibold)
            }
        }
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 16)
                .fill(Color(.secondarySystemBackground))
        )
    }
}

struct ForecastHourCard: View {
    let forecast: GridHour
    
    var body: some View {
        VStack(spacing: 8) {
            Text(hourText)
                .font(.caption)
                .fontWeight(.semibold)
                .foregroundStyle(.secondary)
            
            Circle()
                .fill(statusColor)
                .frame(width: 32, height: 32)
                .overlay(
                    Text(String(format: "%.0f", forecast.touPriceCentsKwh))
                        .font(.caption2)
                        .fontWeight(.bold)
                        .foregroundStyle(.white)
                )
            
            Text(String(format: "%.0f%%", forecast.renewablePct))
                .font(.caption2)
                .foregroundStyle(.secondary)
            
            Image(systemName: "leaf.fill")
                .font(.caption2)
                .foregroundStyle(.green.opacity(Double(forecast.renewablePct / 100)))
        }
        .frame(width: 60)
        .padding(.vertical, 12)
        .background(
            RoundedRectangle(cornerRadius: 12)
                .fill(statusColor.opacity(0.1))
                .overlay(
                    RoundedRectangle(cornerRadius: 12)
                        .strokeBorder(statusColor.opacity(0.3), lineWidth: 1.5)
                )
        )
    }
    
    private var hourText: String {
        if forecast.hour == 0 {
            return "12 AM"
        } else if forecast.hour < 12 {
            return "\(forecast.hour) AM"
        } else if forecast.hour == 12 {
            return "12 PM"
        } else {
            return "\(forecast.hour - 12) PM"
        }
    }
    
    private var statusColor: Color {
        switch forecast.status {
        case .green: return .green
        case .yellow: return .yellow
        case .red: return .red
        }
    }
}

struct OptimizedEventCard: View {
    let event: OptimizedEvent
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text(event.title)
                        .font(.headline)
                    
                    if let channelId = event.channelId {
                        Text("Channel \(channelId)")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
                
                Spacer()
                
                if event.wasMoved {
                    Label("Rescheduled", systemImage: "calendar.badge.clock")
                        .font(.caption)
                        .foregroundStyle(.blue)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(
                            Capsule()
                                .fill(Color.blue.opacity(0.1))
                        )
                }
            }
            
            // Time display
            HStack(spacing: 12) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Original")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                    Text(formatTime(event.originalStart))
                        .font(.caption)
                        .fontWeight(.medium)
                }
                
                Image(systemName: "arrow.right")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                
                VStack(alignment: .leading, spacing: 2) {
                    Text("Optimized")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                    Text(formatTime(event.optimizedStart))
                        .font(.caption)
                        .fontWeight(.medium)
                        .foregroundStyle(event.wasMoved ? .blue : .primary)
                }
                
                Spacer()
                
                Circle()
                    .fill(statusColor)
                    .frame(width: 8, height: 8)
            }
            
            Divider()
            
            // Savings
            HStack(spacing: 20) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Savings")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                    Text(String(format: "%.1f¢", event.savingsCents))
                        .font(.subheadline)
                        .fontWeight(.semibold)
                        .foregroundStyle(.green)
                }
                
                VStack(alignment: .leading, spacing: 2) {
                    Text("Carbon Avoided")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                    Text(String(format: "%.0fg", event.carbonAvoidedG))
                        .font(.subheadline)
                        .fontWeight(.semibold)
                        .foregroundStyle(.green)
                }
                
                Spacer()
                
                Text(String(format: "%.0fW", event.estimatedWatts))
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }
            
            // Reason
            Text(event.reason)
                .font(.caption)
                .foregroundStyle(.secondary)
                .padding(.top, 4)
        }
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 12)
                .fill(Color(.secondarySystemBackground))
        )
    }
    
    private var statusColor: Color {
        switch event.gridStatusAtTime {
        case .green: return .green
        case .yellow: return .yellow
        case .red: return .red
        }
    }
    
    private func formatTime(_ isoString: String) -> String {
        let formatter = ISO8601DateFormatter()
        guard let date = formatter.date(from: isoString) else {
            return isoString
        }
        
        let timeFormatter = DateFormatter()
        timeFormatter.timeStyle = .short
        return timeFormatter.string(from: date)
    }
}

struct AddTaskView: View {
    @Environment(\.dismiss) var dismiss
    @State private var title = ""
    @State private var selectedChannel: Int? = nil
    @State private var estimatedWatts: Double = 1000
    @State private var durationMinutes: Double = 60
    
    var body: some View {
        NavigationStack {
            Form {
                Section("Task Details") {
                    TextField("Title", text: $title)
                    
                    Picker("Channel", selection: $selectedChannel) {
                        Text("None").tag(nil as Int?)
                        Text("Channel 0").tag(0 as Int?)
                        Text("Channel 1").tag(1 as Int?)
                        Text("Channel 2").tag(2 as Int?)
                        Text("Channel 3").tag(3 as Int?)
                    }
                }
                
                Section("Power Usage") {
                    VStack(alignment: .leading) {
                        Text("Estimated Watts: \(Int(estimatedWatts))W")
                            .font(.subheadline)
                        Slider(value: $estimatedWatts, in: 100...7200, step: 100)
                    }
                    
                    VStack(alignment: .leading) {
                        Text("Duration: \(Int(durationMinutes)) minutes")
                            .font(.subheadline)
                        Slider(value: $durationMinutes, in: 15...240, step: 15)
                    }
                }
            }
            .navigationTitle("Add Task")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") {
                        dismiss()
                    }
                }
                
                ToolbarItem(placement: .confirmationAction) {
                    Button("Add") {
                        // TODO: Send to API
                        dismiss()
                    }
                    .disabled(title.isEmpty)
                }
            }
        }
    }
}

@MainActor
class CalendarViewModel: ObservableObject {
    @Published var optimization: OptimizationResult?
    @Published var forecast24h: [GridHour] = []
    @Published var showingAddTask = false
    
    func loadData() async {
        let dashboard = DashboardResponse.demo
        optimization = dashboard.optimization
        forecast24h = .demo24h
    }
}

#Preview {
    CalendarView()
}
