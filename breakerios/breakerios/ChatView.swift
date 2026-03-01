//
//  ChatView.swift
//  breakerios
//
//  Created by Tong tong Wang on 28/2/2026.
//

import SwiftUI
import Combine

struct ChatView: View {
    @StateObject private var viewModel = ChatViewModel()
    @Environment(\.dismiss) var dismiss

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                // Messages
                ScrollViewReader { proxy in
                    ScrollView {
                        LazyVStack(spacing: 12) {
                            ForEach(viewModel.messages) { message in
                                ChatBubble(message: message)
                                    .id(message.id)
                            }
                        }
                        .padding()
                    }
                    .onChange(of: viewModel.messages.count) {
                        if let last = viewModel.messages.last {
                            withAnimation {
                                proxy.scrollTo(last.id, anchor: .bottom)
                            }
                        }
                    }
                }

                Divider()

                // Input Bar
                HStack(spacing: 12) {
                    TextField("Ask about your energy...", text: $viewModel.inputText)
                        .textFieldStyle(.roundedBorder)
                        .disabled(viewModel.isStreaming)

                    Button {
                        viewModel.send()
                    } label: {
                        Image(systemName: "arrow.up.circle.fill")
                            .font(.title2)
                            .foregroundStyle(canSend ? .blue : .gray)
                    }
                    .disabled(!canSend)
                }
                .padding()
            }
            .navigationTitle("Energy Assistant")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Close") { dismiss() }
                }
            }
        }
        .task {
            viewModel.connect()
        }
    }

    private var canSend: Bool {
        !viewModel.inputText.trimmingCharacters(in: .whitespaces).isEmpty && !viewModel.isStreaming
    }
}

struct ChatBubble: View {
    let message: ChatMessage

    var body: some View {
        HStack {
            if message.role == .user { Spacer() }

            Text(message.text.isEmpty ? "..." : message.text)
                .font(.body)
                .foregroundStyle(message.role == .user ? .white : .primary)
                .padding(.horizontal, 14)
                .padding(.vertical, 10)
                .background(
                    RoundedRectangle(cornerRadius: 12)
                        .fill(message.role == .user ? Color.blue : Color(.secondarySystemBackground))
                )
                .frame(maxWidth: 280, alignment: message.role == .user ? .trailing : .leading)

            if message.role == .assistant { Spacer() }
        }
    }
}

class ChatViewModel: ObservableObject {
    @Published var messages: [ChatMessage] = []
    @Published var inputText = ""
    @Published var isStreaming = false

    private var cancellables = Set<AnyCancellable>()

    func connect() {
        ChatWebSocketManager.shared.connect()

        ChatWebSocketManager.shared.responseChunk
            .receive(on: DispatchQueue.main)
            .sink { [weak self] (chunk, done, fullMessage) in
                guard let self else { return }

                if done {
                    if let full = fullMessage, let lastIndex = self.lastAssistantIndex() {
                        self.messages[lastIndex].text = full
                    }
                    self.isStreaming = false
                } else {
                    if let lastIndex = self.lastAssistantIndex() {
                        self.messages[lastIndex].text += chunk
                    }
                }
            }
            .store(in: &cancellables)
    }

    func send() {
        let text = inputText.trimmingCharacters(in: .whitespaces)
        guard !text.isEmpty else { return }

        messages.append(ChatMessage(role: .user, text: text, timestamp: Date()))
        messages.append(ChatMessage(role: .assistant, text: "", timestamp: Date()))

        ChatWebSocketManager.shared.sendMessage(text)
        inputText = ""
        isStreaming = true
    }

    private func lastAssistantIndex() -> Int? {
        messages.indices.last { messages[$0].role == .assistant }
    }
}

#Preview {
    ChatView()
}
