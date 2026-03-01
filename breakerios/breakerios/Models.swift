//
//  Models.swift
//  breakerios
//
//  Created by Tong tong Wang on 28/2/2026.
//

import Foundation

// MARK: - Grid Status

enum GridStatus: String, Codable {
    case green, yellow, red
}

enum TOUPeriod: String, Codable {
    case peak, offPeak = "off_peak", superOffPeak = "super_off_peak"
}

struct GridSnapshot: Codable {
    let renewablePct: Float
    let carbonIntensityGco2Kwh: Float
    let touPriceCentsKwh: Float
    let touPeriod: TOUPeriod
    let status: GridStatus
}

struct GridHour: Codable {
    let hour: Int
    let renewablePct: Float
    let carbonIntensityGco2Kwh: Float
    let touPriceCentsKwh: Float
    let touPeriod: TOUPeriod
    let status: GridStatus
}

// MARK: - Channel & Sensor

struct ChannelReading: Codable, Identifiable {
    var id: Int { channelId }
    let channelId: Int
    let assignedZone: String
    let assignedAppliance: String
    let currentAmps: Float
    
    var currentWatts: Float {
        currentAmps * 120
    }
}

struct LiveChannel: Codable, Identifiable {
    var id: Int { channelId }
    let channelId: Int
    let assignedZone: String
    let assignedAppliance: String
    let currentWatts: Float
    let isActive: Bool
    var isOn: Bool = true

    private enum CodingKeys: String, CodingKey {
        case channelId, assignedZone, assignedAppliance, currentWatts, isActive
    }
}

struct CurrentPower: Codable {
    let ch0Watts: Float
    let ch1Watts: Float
    let ch2Watts: Float
    let ch3Watts: Float
    let totalWatts: Float
}

// MARK: - Optimization

struct OptimizedEvent: Codable, Identifiable {
    let eventId: String
    let title: String
    let originalStart: String
    let originalEnd: String
    let optimizedStart: String
    let optimizedEnd: String
    let channelId: Int?
    let estimatedWatts: Float
    let savingsCents: Float
    let carbonAvoidedG: Float
    let reason: String
    let gridStatusAtTime: GridStatus
    let isDeferrable: Bool
    let wasMoved: Bool
    
    var id: String { eventId }
}

struct OptimizationResult: Codable {
    let optimizedEvents: [OptimizedEvent]
    let totalSavingsCents: Float
    let totalCarbonAvoidedG: Float
    let optimizationConfidence: Float
}

// MARK: - Dashboard

struct DashboardResponse: Codable {
    let currentPower: CurrentPower
    let grid: GridSnapshot
    let hardwareConnected: Bool
    let optimization: OptimizationResult?
}

// MARK: - Insights

enum InsightCategory: String, Codable {
    case scheduleOptimization = "schedule_optimization"
    case anomaly
    case gridStatus = "grid_status"
}

enum InsightSeverity: String, Codable {
    case info, warning, critical
}

struct Insight: Codable, Identifiable {
    let message: String
    let category: InsightCategory
    let severity: InsightSeverity
    let insightId: String?

    let stableId = UUID().uuidString

    var id: String { insightId ?? stableId }

    private enum CodingKeys: String, CodingKey {
        case message, category, severity, insightId
    }
}

// MARK: - Demo Data

extension DashboardResponse {
    static var demo: DashboardResponse {
        DashboardResponse(
            currentPower: CurrentPower(
                ch0Watts: 850,
                ch1Watts: 1200,
                ch2Watts: 450,
                ch3Watts: 0,
                totalWatts: 2500
            ),
            grid: GridSnapshot(
                renewablePct: 67.5,
                carbonIntensityGco2Kwh: 120,
                touPriceCentsKwh: 12.5,
                touPeriod: .offPeak,
                status: .green
            ),
            hardwareConnected: true,
            optimization: OptimizationResult(
                optimizedEvents: [
                    OptimizedEvent(
                        eventId: UUID().uuidString,
                        title: "Water Heater - Morning Shower",
                        originalStart: "2026-02-28T07:00:00Z",
                        originalEnd: "2026-02-28T07:30:00Z",
                        optimizedStart: "2026-02-28T06:30:00Z",
                        optimizedEnd: "2026-02-28T07:00:00Z",
                        channelId: 0,
                        estimatedWatts: 4500,
                        savingsCents: 15.5,
                        carbonAvoidedG: 235,
                        reason: "Moved to super off-peak period with 85% renewable energy",
                        gridStatusAtTime: .green,
                        isDeferrable: true,
                        wasMoved: true
                    ),
                    OptimizedEvent(
                        eventId: UUID().uuidString,
                        title: "Dryer - Laundry",
                        originalStart: "2026-02-28T18:00:00Z",
                        originalEnd: "2026-02-28T19:30:00Z",
                        optimizedStart: "2026-02-28T21:30:00Z",
                        optimizedEnd: "2026-02-28T23:00:00Z",
                        channelId: 1,
                        estimatedWatts: 3000,
                        savingsCents: 42.0,
                        carbonAvoidedG: 520,
                        reason: "Shifted to off-peak period, avoiding peak pricing",
                        gridStatusAtTime: .yellow,
                        isDeferrable: true,
                        wasMoved: true
                    ),
                    OptimizedEvent(
                        eventId: UUID().uuidString,
                        title: "EV Charging",
                        originalStart: "2026-02-28T19:00:00Z",
                        originalEnd: "2026-02-28T23:00:00Z",
                        optimizedStart: "2026-02-28T01:00:00Z",
                        optimizedEnd: "2026-02-28T05:00:00Z",
                        channelId: 3,
                        estimatedWatts: 7200,
                        savingsCents: 128.0,
                        carbonAvoidedG: 1450,
                        reason: "Scheduled during super off-peak with maximum renewable availability",
                        gridStatusAtTime: .green,
                        isDeferrable: true,
                        wasMoved: true
                    )
                ],
                totalSavingsCents: 185.5,
                totalCarbonAvoidedG: 2205,
                optimizationConfidence: 0.92
            )
        )
    }
}

extension Array where Element == LiveChannel {
    static var demo: [LiveChannel] {
        [
            LiveChannel(
                channelId: 0,
                assignedZone: "Bathroom",
                assignedAppliance: "Water Heater",
                currentWatts: 850,
                isActive: true
            ),
            LiveChannel(
                channelId: 1,
                assignedZone: "Kitchen",
                assignedAppliance: "Induction Stove",
                currentWatts: 1200,
                isActive: true
            ),
            LiveChannel(
                channelId: 2,
                assignedZone: "Living Room",
                assignedAppliance: "Air Conditioning",
                currentWatts: 450,
                isActive: true
            ),
            LiveChannel(
                channelId: 3,
                assignedZone: "Garage",
                assignedAppliance: "EV Charger",
                currentWatts: 0,
                isActive: false
            )
        ]
    }
}

extension Array where Element == GridHour {
    static var demo24h: [GridHour] {
        (0..<24).map { hour in
            let isOffPeak = hour < 7 || hour >= 21
            let isSuperOffPeak = hour < 7
            let isPeak = hour >= 16 && hour < 21

            return GridHour(
                hour: hour,
                renewablePct: isSuperOffPeak ? Float.random(in: 75...95) : (isOffPeak ? Float.random(in: 60...80) : Float.random(in: 30...50)),
                carbonIntensityGco2Kwh: isPeak ? Float.random(in: 300...450) : Float.random(in: 90...200),
                touPriceCentsKwh: isSuperOffPeak ? Float.random(in: 8...12) : (isOffPeak ? Float.random(in: 14...18) : Float.random(in: 28...45)),
                touPeriod: isSuperOffPeak ? .superOffPeak : (isPeak ? .peak : .offPeak),
                status: isPeak ? .red : (isSuperOffPeak ? .green : .yellow)
            )
        }
    }
}

// MARK: - WebSocket Envelope Decoding

struct WSTypeOnly: Decodable {
    let type: String
}

struct WSTypedEnvelope<T: Decodable>: Decodable {
    let type: String
    let timestamp: String
    let data: T
}

// MARK: - WebSocket Data Types

struct SensorUpdateData: Codable {
    let deviceId: String
    let timestamp: String
    let simulated: Bool
    let totalWatts: Float
    let channels: [LiveChannel]
}

struct GridStatusUpdate: Codable {
    let current: GridSnapshot
    let forecastNext3h: [GridHour]
}

struct AnomalyAlert: Codable, Identifiable {
    let channelId: Int
    let assignedZone: String
    let assignedAppliance: String
    let currentWatts: Float
    let expectedWatts: Float
    let deviationPct: Float?
    let message: String

    var id: String { "\(channelId)-\(currentWatts)" }
}

struct TTSAudioChunk: Codable {
    let audio: String
    let format: String
    let insightId: String
    let isFinal: Bool
}

// MARK: - Chat Types

struct ChatMessage: Identifiable {
    let id = UUID()
    let role: ChatRole
    var text: String
    let timestamp: Date
}

enum ChatRole {
    case user, assistant
}

struct ChatResponseData: Codable {
    let chunk: String?
    let message: String?
    let done: Bool
}

// MARK: - REST Request/Response Types

struct HealthResponse: Codable {
    let status: String
    let hardwareConnected: Bool
    let bufferFill: String
    let wsClients: Int
    let timestamp: String
}

struct ForecastResponse: Codable {
    let gridForecast24h: [GridHour]
}

struct TaskRequest: Codable {
    let title: String
    let channelId: Int?
    let estimatedWatts: Int?
    let estimatedDurationMin: Int?
    let deadline: String?
    let isDeferrable: Bool?
    let priority: String?
}

struct TaskResponse: Codable {
    let eventId: String
    let message: String
}

struct SettingsRequest: Codable {
    let alpha: Double?
    let beta: Double?
    let narrationEnabled: Bool?

    enum CodingKeys: String, CodingKey {
        case alpha, beta
        case narrationEnabled = "narration_enabled"
    }
}

struct SettingsResponse: Codable {
    let alpha: Double
    let beta: Double
    let narrationEnabled: Bool?

    enum CodingKeys: String, CodingKey {
        case alpha, beta
        case narrationEnabled = "narration_enabled"
    }
}

struct InsightsResponse: Codable {
    let insights: [Insight]
}

struct CalendarImportRequest: Codable {
    let icalData: String?
    let jsonEvents: [[String: String]]?
}

struct CalendarImportResponse: Codable {
    let eventsImported: Int
    let deferrableEvents: Int
    let nonDeferrableEvents: Int
    let message: String
}

// MARK: - Loading State

enum LoadingState: Equatable {
    case idle, loading, loaded, error(String)
}

// MARK: - API Error

enum APIError: LocalizedError {
    case invalidURL
    case networkError(Error)
    case decodingError(Error)
    case serverError(Int, String?)

    var errorDescription: String? {
        switch self {
        case .invalidURL: return "Invalid server URL"
        case .networkError(let e): return "Network error: \(e.localizedDescription)"
        case .decodingError(let e): return "Data error: \(e.localizedDescription)"
        case .serverError(let code, let msg): return "Server error \(code): \(msg ?? "Unknown")"
        }
    }

    static func == (lhs: APIError, rhs: APIError) -> Bool {
        lhs.localizedDescription == rhs.localizedDescription
    }
}
