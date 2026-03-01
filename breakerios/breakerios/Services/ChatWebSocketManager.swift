//
//  ChatWebSocketManager.swift
//  breakerios
//
//  Created by Tong tong Wang on 28/2/2026.
//

import Foundation
import Combine

class ChatWebSocketManager: ObservableObject {
    static let shared = ChatWebSocketManager()

    @Published var isConnected = false

    /// Emits (chunk, done, fullMessage). When done=true, fullMessage contains the complete response.
    let responseChunk = PassthroughSubject<(chunk: String, done: Bool, fullMessage: String?), Never>()

    private var webSocketTask: URLSessionWebSocketTask?
    private var reconnectAttempts = 0

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

        guard let url = URL(string: base + "/ws/chat") else { return }

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

    // MARK: - Send

    func sendMessage(_ text: String) {
        let payload = "{\"message\": \"\(text.replacingOccurrences(of: "\"", with: "\\\""))\"}"
        webSocketTask?.send(.string(payload)) { error in
            if error != nil {
                Task { @MainActor in
                    self.isConnected = false
                }
            }
        }
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

    // MARK: - Message Handling

    private func handleMessage(_ data: Data) {
        guard let envelope = try? decoder.decode(WSTypeOnly.self, from: data) else { return }

        guard envelope.type == "chat_response" else { return }

        guard let msg = try? decoder.decode(WSTypedEnvelope<ChatResponseData>.self, from: data) else { return }

        let chatData = msg.data
        if chatData.done {
            responseChunk.send((chunk: "", done: true, fullMessage: chatData.message))
        } else {
            responseChunk.send((chunk: chatData.chunk ?? "", done: false, fullMessage: nil))
        }
    }

    // MARK: - Reconnection

    private func reconnect() {
        let delay = min(pow(2, Double(reconnectAttempts)), 30.0)
        reconnectAttempts += 1

        Task {
            try? await Task.sleep(for: .seconds(delay))
            await MainActor.run { self.connect() }
        }
    }
}
