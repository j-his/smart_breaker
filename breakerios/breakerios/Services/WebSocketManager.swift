//
//  WebSocketManager.swift
//  breakerios
//
//  Created by Tong tong Wang on 28/2/2026.
//

import Foundation
import Combine

class WebSocketManager: ObservableObject {
    static let shared = WebSocketManager()

    @Published var isConnected = false

    let sensorUpdate = PassthroughSubject<SensorUpdateData, Never>()
    let gridStatusUpdate = PassthroughSubject<GridStatusUpdate, Never>()
    let calendarUpdate = PassthroughSubject<OptimizationResult, Never>()
    let insightReceived = PassthroughSubject<Insight, Never>()
    let anomalyReceived = PassthroughSubject<AnomalyAlert, Never>()
    let ttsChunkReceived = PassthroughSubject<TTSAudioChunk, Never>()

    private var webSocketTask: URLSessionWebSocketTask?
    private var reconnectAttempts = 0
    private let maxReconnectDelay: TimeInterval = 30

    private let decoder: JSONDecoder = {
        let d = JSONDecoder()
        d.keyDecodingStrategy = .convertFromSnakeCase
        return d
    }()

    private init() {}

    // MARK: - Connection

    func connect() {
        let base = APIClient.shared.baseURL
            .replacingOccurrences(of: "http://", with: "ws://")
            .replacingOccurrences(of: "https://", with: "wss://")

        guard let url = URL(string: base + "/ws/live") else { return }

        let session = URLSession(configuration: .default)
        webSocketTask = session.webSocketTask(with: url)
        webSocketTask?.resume()
        isConnected = true
        reconnectAttempts = 0
        receiveMessage()
    }

    func disconnect() {
        webSocketTask?.cancel(with: .goingAway, reason: nil)
        webSocketTask = nil
        isConnected = false
    }

    // MARK: - Receive Loop

    private func receiveMessage() {
        webSocketTask?.receive { [weak self] result in
            guard let self else { return }

            switch result {
            case .success(let message):
                switch message {
                case .data(let data):
                    Task { @MainActor in self.handleMessage(data) }
                case .string(let text):
                    if let data = text.data(using: .utf8) {
                        Task { @MainActor in self.handleMessage(data) }
                    }
                @unknown default:
                    break
                }
                self.receiveMessage()

            case .failure:
                Task { @MainActor in
                    self.isConnected = false
                    self.reconnect()
                }
            }
        }
    }

    // MARK: - Message Routing

    private func handleMessage(_ data: Data) {
        guard let envelope = try? decoder.decode(WSTypeOnly.self, from: data) else { return }

        switch envelope.type {
        case "sensor_update":
            if let msg = try? decoder.decode(WSTypedEnvelope<SensorUpdateData>.self, from: data) {
                sensorUpdate.send(msg.data)
            }
        case "grid_status":
            if let msg = try? decoder.decode(WSTypedEnvelope<GridStatusUpdate>.self, from: data) {
                gridStatusUpdate.send(msg.data)
            }
        case "calendar_update":
            if let msg = try? decoder.decode(WSTypedEnvelope<OptimizationResult>.self, from: data) {
                calendarUpdate.send(msg.data)
            }
        case "insight":
            if let msg = try? decoder.decode(WSTypedEnvelope<Insight>.self, from: data) {
                insightReceived.send(msg.data)
            }
        case "anomaly_alert":
            if let msg = try? decoder.decode(WSTypedEnvelope<AnomalyAlert>.self, from: data) {
                anomalyReceived.send(msg.data)
            }
        case "tts_audio":
            if let msg = try? decoder.decode(WSTypedEnvelope<TTSAudioChunk>.self, from: data) {
                ttsChunkReceived.send(msg.data)
            }
        default:
            break
        }
    }

    // MARK: - Reconnection

    private func reconnect() {
        let delay = min(pow(2, Double(reconnectAttempts)), maxReconnectDelay)
        reconnectAttempts += 1

        Task {
            try? await Task.sleep(for: .seconds(delay))
            await MainActor.run { self.connect() }
        }
    }
}
