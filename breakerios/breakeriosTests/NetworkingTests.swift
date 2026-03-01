//
//  NetworkingTests.swift
//  breakeriosTests
//
//  Created by Tong tong Wang on 28/2/2026.
//

import Testing
import Foundation
@testable import breakerios

// Shared decoder matching APIClient configuration
private let decoder: JSONDecoder = {
    let d = JSONDecoder()
    d.keyDecodingStrategy = .convertFromSnakeCase
    return d
}()

// MARK: - REST Response Decoding

struct HealthResponseTests {
    @Test func decodesHealthResponse() throws {
        let json = """
        {
            "status": "ok",
            "hardware_connected": true,
            "buffer_fill": "10/100",
            "ws_clients": 2,
            "timestamp": "2026-02-28T12:00:00Z"
        }
        """.data(using: .utf8)!

        let health = try decoder.decode(HealthResponse.self, from: json)
        #expect(health.status == "ok")
        #expect(health.hardwareConnected == true)
        #expect(health.bufferFill == "10/100")
        #expect(health.wsClients == 2)
    }
}

struct DashboardResponseTests {
    @Test func decodesDashboardResponse() throws {
        let json = """
        {
            "current_power": {
                "ch0_watts": 850.0,
                "ch1_watts": 1200.0,
                "ch2_watts": 450.0,
                "ch3_watts": 0.0,
                "total_watts": 2500.0
            },
            "grid": {
                "renewable_pct": 67.5,
                "carbon_intensity_gco2_kwh": 120.0,
                "tou_price_cents_kwh": 12.5,
                "tou_period": "off_peak",
                "status": "green"
            },
            "hardware_connected": true,
            "optimization": {
                "optimized_events": [],
                "total_savings_cents": 0,
                "total_carbon_avoided_g": 0,
                "optimization_confidence": 0.0
            }
        }
        """.data(using: .utf8)!

        let dashboard = try decoder.decode(DashboardResponse.self, from: json)
        #expect(dashboard.currentPower.totalWatts == 2500.0)
        #expect(dashboard.currentPower.ch0Watts == 850.0)
        #expect(dashboard.grid.status == .green)
        #expect(dashboard.grid.touPeriod == .offPeak)
        #expect(dashboard.grid.renewablePct == 67.5)
        #expect(dashboard.hardwareConnected == true)
        #expect(dashboard.optimization?.optimizedEvents.isEmpty == true)
    }

    @Test func decodesNullOptimization() throws {
        let json = """
        {
            "current_power": {
                "ch0_watts": 0, "ch1_watts": 0, "ch2_watts": 0, "ch3_watts": 0, "total_watts": 0
            },
            "grid": {
                "renewable_pct": 50, "carbon_intensity_gco2_kwh": 200,
                "tou_price_cents_kwh": 15, "tou_period": "peak", "status": "red"
            },
            "hardware_connected": false,
            "optimization": null
        }
        """.data(using: .utf8)!

        let dashboard = try decoder.decode(DashboardResponse.self, from: json)
        #expect(dashboard.optimization == nil)
        #expect(dashboard.grid.touPeriod == .peak)
        #expect(dashboard.grid.status == .red)
    }
}

struct ForecastResponseTests {
    @Test func decodesForecast24h() throws {
        let hours = (0..<24).map { hour in
            """
            {"hour": \(hour), "renewable_pct": 50.0, "carbon_intensity_gco2_kwh": 150.0,
             "tou_price_cents_kwh": 15.0, "tou_period": "off_peak", "status": "yellow"}
            """
        }.joined(separator: ",")

        let json = """
        {"grid_forecast_24h": [\(hours)]}
        """.data(using: .utf8)!

        let forecast = try decoder.decode(ForecastResponse.self, from: json)
        #expect(forecast.gridForecast24h.count == 24)
        #expect(forecast.gridForecast24h[0].hour == 0)
        #expect(forecast.gridForecast24h[23].hour == 23)
    }
}

struct OptimizationResultTests {
    @Test func decodesWithEvents() throws {
        let json = """
        {
            "optimized_events": [{
                "event_id": "abc-123",
                "title": "EV Charging",
                "original_start": "2026-02-28T19:00:00Z",
                "original_end": "2026-02-28T23:00:00Z",
                "optimized_start": "2026-02-28T01:00:00Z",
                "optimized_end": "2026-02-28T05:00:00Z",
                "channel_id": 3,
                "estimated_watts": 7200.0,
                "savings_cents": 128.0,
                "carbon_avoided_g": 1450.0,
                "reason": "Shifted to super off-peak",
                "grid_status_at_time": "green",
                "is_deferrable": true,
                "was_moved": true
            }],
            "total_savings_cents": 128.0,
            "total_carbon_avoided_g": 1450.0,
            "optimization_confidence": 0.92
        }
        """.data(using: .utf8)!

        let result = try decoder.decode(OptimizationResult.self, from: json)
        #expect(result.optimizedEvents.count == 1)
        #expect(result.optimizedEvents[0].title == "EV Charging")
        #expect(result.optimizedEvents[0].channelId == 3)
        #expect(result.optimizedEvents[0].wasMoved == true)
        #expect(result.optimizedEvents[0].gridStatusAtTime == .green)
        #expect(result.totalSavingsCents == 128.0)
        #expect(result.optimizationConfidence == 0.92)
    }

    @Test func decodesEmptyEvents() throws {
        let json = """
        {
            "optimized_events": [],
            "total_savings_cents": 0,
            "total_carbon_avoided_g": 0,
            "optimization_confidence": 0.0
        }
        """.data(using: .utf8)!

        let result = try decoder.decode(OptimizationResult.self, from: json)
        #expect(result.optimizedEvents.isEmpty)
    }
}

struct InsightDecodingTests {
    @Test func decodesInsight() throws {
        let json = """
        {
            "message": "Your dryer was shifted to off-peak hours",
            "category": "schedule_optimization",
            "severity": "info",
            "insight_id": "ins-001"
        }
        """.data(using: .utf8)!

        let insight = try decoder.decode(Insight.self, from: json)
        #expect(insight.message == "Your dryer was shifted to off-peak hours")
        #expect(insight.category == .scheduleOptimization)
        #expect(insight.severity == .info)
        #expect(insight.insightId == "ins-001")
    }

    @Test func decodesInsightsResponse() throws {
        let json = """
        {
            "insights": [
                {"message": "Grid is green", "category": "grid_status", "severity": "info", "insight_id": "g1"},
                {"message": "Anomaly detected", "category": "anomaly", "severity": "critical", "insight_id": "a1"}
            ]
        }
        """.data(using: .utf8)!

        let response = try decoder.decode(InsightsResponse.self, from: json)
        #expect(response.insights.count == 2)
        #expect(response.insights[1].severity == .critical)
        #expect(response.insights[1].category == .anomaly)
    }
}

struct SettingsResponseTests {
    @Test func decodesSettingsResponse() throws {
        let json = """
        {"alpha": 0.7, "beta": 0.3}
        """.data(using: .utf8)!

        let response = try decoder.decode(SettingsResponse.self, from: json)
        #expect(response.alpha == 0.7)
        #expect(response.beta == 0.3)
    }
}

struct CalendarImportResponseTests {
    @Test func decodesImportResponse() throws {
        let json = """
        {
            "events_imported": 5,
            "deferrable_events": 3,
            "non_deferrable_events": 2,
            "message": "Imported 5 events (3 deferrable, 2 fixed). Schedule re-optimized."
        }
        """.data(using: .utf8)!

        let response = try decoder.decode(CalendarImportResponse.self, from: json)
        #expect(response.eventsImported == 5)
        #expect(response.deferrableEvents == 3)
        #expect(response.nonDeferrableEvents == 2)
    }
}

struct TaskResponseTests {
    @Test func decodesTaskResponse() throws {
        let json = """
        {"event_id": "uuid-123", "message": "Task added and schedule re-optimized"}
        """.data(using: .utf8)!

        let response = try decoder.decode(TaskResponse.self, from: json)
        #expect(response.eventId == "uuid-123")
    }
}

// MARK: - WebSocket Envelope Decoding

struct WebSocketEnvelopeTests {
    @Test func decodesEnvelopeType() throws {
        let json = """
        {"type": "sensor_update", "timestamp": "2026-02-28T12:00:00Z", "data": {}}
        """.data(using: .utf8)!

        let envelope = try decoder.decode(WSTypeOnly.self, from: json)
        #expect(envelope.type == "sensor_update")
    }

    @Test func decodesSensorUpdateEnvelope() throws {
        let json = """
        {
            "type": "sensor_update",
            "timestamp": "2026-02-28T12:00:00Z",
            "data": {
                "device_id": "esp32-001",
                "timestamp": "2026-02-28T12:00:00Z",
                "simulated": true,
                "total_watts": 2500.0,
                "channels": [
                    {"channel_id": 0, "assigned_zone": "Kitchen", "assigned_appliance": "Stove",
                     "current_watts": 1200.0, "is_active": true},
                    {"channel_id": 1, "assigned_zone": "Garage", "assigned_appliance": "EV Charger",
                     "current_watts": 0.0, "is_active": false},
                    {"channel_id": 2, "assigned_zone": "Laundry", "assigned_appliance": "Dryer",
                     "current_watts": 800.0, "is_active": true},
                    {"channel_id": 3, "assigned_zone": "Bedroom", "assigned_appliance": "AC",
                     "current_watts": 500.0, "is_active": true}
                ]
            }
        }
        """.data(using: .utf8)!

        let envelope = try decoder.decode(WSTypedEnvelope<SensorUpdateData>.self, from: json)
        #expect(envelope.data.deviceId == "esp32-001")
        #expect(envelope.data.simulated == true)
        #expect(envelope.data.totalWatts == 2500.0)
        #expect(envelope.data.channels.count == 4)
        #expect(envelope.data.channels[0].isActive == true)
        #expect(envelope.data.channels[1].isActive == false)
    }

    @Test func decodesGridStatusEnvelope() throws {
        let json = """
        {
            "type": "grid_status",
            "timestamp": "2026-02-28T12:00:00Z",
            "data": {
                "current": {
                    "renewable_pct": 72.0,
                    "carbon_intensity_gco2_kwh": 95.0,
                    "tou_price_cents_kwh": 10.5,
                    "tou_period": "super_off_peak",
                    "status": "green"
                },
                "forecast_next_3h": [
                    {"hour": 1, "renewable_pct": 70.0, "carbon_intensity_gco2_kwh": 100.0,
                     "tou_price_cents_kwh": 11.0, "tou_period": "super_off_peak", "status": "green"},
                    {"hour": 2, "renewable_pct": 68.0, "carbon_intensity_gco2_kwh": 110.0,
                     "tou_price_cents_kwh": 11.5, "tou_period": "super_off_peak", "status": "green"},
                    {"hour": 3, "renewable_pct": 65.0, "carbon_intensity_gco2_kwh": 115.0,
                     "tou_price_cents_kwh": 12.0, "tou_period": "super_off_peak", "status": "green"}
                ]
            }
        }
        """.data(using: .utf8)!

        let envelope = try decoder.decode(WSTypedEnvelope<GridStatusUpdate>.self, from: json)
        #expect(envelope.data.current.status == .green)
        #expect(envelope.data.current.touPeriod == .superOffPeak)
        #expect(envelope.data.forecastNext3h.count == 3)
    }

    @Test func decodesAnomalyAlertEnvelope() throws {
        let json = """
        {
            "type": "anomaly_alert",
            "timestamp": "2026-02-28T12:00:00Z",
            "data": {
                "channel_id": 2,
                "assigned_zone": "Kitchen",
                "assigned_appliance": "Induction Stove",
                "current_watts": 3500.0,
                "expected_watts": 1200.0,
                "deviation_pct": 191.7,
                "message": "Unusual power on Induction Stove (3500W vs expected 1200W)"
            }
        }
        """.data(using: .utf8)!

        let envelope = try decoder.decode(WSTypedEnvelope<AnomalyAlert>.self, from: json)
        #expect(envelope.data.channelId == 2)
        #expect(envelope.data.currentWatts == 3500.0)
        #expect(envelope.data.expectedWatts == 1200.0)
        #expect(envelope.data.deviationPct == 191.7)
    }

    @Test func decodesTTSAudioChunkEnvelope() throws {
        let json = """
        {
            "type": "tts_audio",
            "timestamp": "2026-02-28T12:00:00Z",
            "data": {
                "audio": "SGVsbG8gV29ybGQ=",
                "format": "mp3",
                "insight_id": "ins-001",
                "is_final": false
            }
        }
        """.data(using: .utf8)!

        let envelope = try decoder.decode(WSTypedEnvelope<TTSAudioChunk>.self, from: json)
        #expect(envelope.data.audio == "SGVsbG8gV29ybGQ=")
        #expect(envelope.data.format == "mp3")
        #expect(envelope.data.insightId == "ins-001")
        #expect(envelope.data.isFinal == false)
    }

    @Test func decodesChatResponseChunk() throws {
        let json = """
        {
            "type": "chat_response",
            "timestamp": "2026-02-28T12:00:00Z",
            "data": {"chunk": "Hello", "done": false}
        }
        """.data(using: .utf8)!

        let envelope = try decoder.decode(WSTypedEnvelope<ChatResponseData>.self, from: json)
        #expect(envelope.data.chunk == "Hello")
        #expect(envelope.data.done == false)
        #expect(envelope.data.message == nil)
    }

    @Test func decodesChatResponseFinal() throws {
        let json = """
        {
            "type": "chat_response",
            "timestamp": "2026-02-28T12:00:00Z",
            "data": {"message": "Hello, your energy usage is optimal!", "done": true}
        }
        """.data(using: .utf8)!

        let envelope = try decoder.decode(WSTypedEnvelope<ChatResponseData>.self, from: json)
        #expect(envelope.data.done == true)
        #expect(envelope.data.message == "Hello, your energy usage is optimal!")
    }

    @Test func malformedJsonDoesNotCrash() {
        let garbage = "not valid json".data(using: .utf8)!
        let result = try? decoder.decode(WSTypeOnly.self, from: garbage)
        #expect(result == nil)
    }

    @Test func unknownTypeDecodesTypeOnly() throws {
        let json = """
        {"type": "future_unknown_type", "timestamp": "2026-02-28T12:00:00Z", "data": {"foo": "bar"}}
        """.data(using: .utf8)!

        let envelope = try decoder.decode(WSTypeOnly.self, from: json)
        #expect(envelope.type == "future_unknown_type")
    }
}

// MARK: - Request Encoding

struct RequestEncodingTests {
    private let encoder: JSONEncoder = {
        let e = JSONEncoder()
        e.keyEncodingStrategy = .convertToSnakeCase
        return e
    }()

    @Test func encodesTaskRequest() throws {
        let task = TaskRequest(
            title: "EV Charging",
            channelId: 3,
            estimatedWatts: 7200,
            estimatedDurationMin: 240,
            deadline: nil,
            isDeferrable: true,
            priority: "medium"
        )

        let data = try encoder.encode(task)
        let dict = try JSONSerialization.jsonObject(with: data) as! [String: Any]
        #expect(dict["title"] as? String == "EV Charging")
        #expect(dict["channel_id"] as? Int == 3)
        #expect(dict["estimated_watts"] as? Int == 7200)
        #expect(dict["is_deferrable"] as? Bool == true)
    }

    @Test func encodesSettingsRequest() throws {
        let settings = SettingsRequest(alpha: 0.7, beta: 0.3)
        let data = try encoder.encode(settings)
        let dict = try JSONSerialization.jsonObject(with: data) as! [String: Any]
        #expect(dict["alpha"] as? Double == 0.7)
        #expect(dict["beta"] as? Double == 0.3)
    }
}
