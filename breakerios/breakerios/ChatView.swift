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
            .navigationTitle("Natalia")
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
        HStack(alignment: .top) {
            if message.role == .user { Spacer(minLength: 40) }

            VStack(alignment: message.role == .user ? .trailing : .leading, spacing: 0) {
                if message.text.isEmpty {
                    Text("...")
                        .font(.body)
                        .foregroundStyle(message.role == .user ? .white : .primary)
                } else if message.role == .assistant {
                    // Use Markdown formatting for assistant messages
                    FormattedMessageView(text: message.text)
                } else {
                    // Plain text for user messages
                    Text(message.text)
                        .font(.body)
                        .foregroundStyle(.white)
                }
            }
            .padding(.horizontal, 14)
            .padding(.vertical, 10)
            .background(
                RoundedRectangle(cornerRadius: 12)
                    .fill(message.role == .user ? Color.blue : Color(.secondarySystemBackground))
            )
            .frame(maxWidth: .infinity, alignment: message.role == .user ? .trailing : .leading)

            if message.role == .assistant { Spacer(minLength: 40) }
        }
    }
}

struct FormattedMessageView: View {
    let text: String
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            // Parse and render the message with better formatting
            let components = parseMessageComponents(text)
            
            ForEach(Array(components.enumerated()), id: \.offset) { _, component in
                switch component {
                case .text(let content):
                    // Use AttributedString for proper Markdown rendering
                    if let attributed = try? AttributedString(markdown: content) {
                        Text(attributed)
                            .font(.body)
                            .foregroundStyle(.primary)
                            .textSelection(.enabled)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    } else {
                        // Fallback to plain text if Markdown parsing fails
                        Text(content)
                            .font(.body)
                            .foregroundStyle(.primary)
                            .textSelection(.enabled)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }
                    
                case .codeBlock(let code, let language):
                    VStack(alignment: .leading, spacing: 4) {
                        if let lang = language, !lang.isEmpty {
                            Text(lang.uppercased())
                                .font(.caption2)
                                .fontWeight(.semibold)
                                .foregroundStyle(.white)
                                .padding(.horizontal, 8)
                                .padding(.vertical, 4)
                                .background(
                                    Capsule()
                                        .fill(Color.blue.opacity(0.8))
                                )
                        }
                        
                        ScrollView(.horizontal, showsIndicators: false) {
                            Text(code)
                                .font(.system(.callout, design: .monospaced))
                                .foregroundStyle(.primary)
                                .textSelection(.enabled)
                                .padding(12)
                        }
                        .background(
                            RoundedRectangle(cornerRadius: 8)
                                .fill(Color(.tertiarySystemBackground))
                        )
                        .overlay(
                            RoundedRectangle(cornerRadius: 8)
                                .strokeBorder(Color.gray.opacity(0.2), lineWidth: 1)
                        )
                    }
                    
                case .list(let items):
                    VStack(alignment: .leading, spacing: 6) {
                        ForEach(Array(items.enumerated()), id: \.offset) { index, item in
                            HStack(alignment: .top, spacing: 8) {
                                Text("•")
                                    .font(.body)
                                    .foregroundStyle(.blue)
                                    .fontWeight(.bold)
                                if let attributed = try? AttributedString(markdown: item) {
                                    Text(attributed)
                                        .font(.body)
                                        .foregroundStyle(.primary)
                                        .textSelection(.enabled)
                                } else {
                                    Text(item)
                                        .font(.body)
                                        .foregroundStyle(.primary)
                                        .textSelection(.enabled)
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    
    private func parseMessageComponents(_ text: String) -> [MessageComponent] {
        var components: [MessageComponent] = []
        var currentText = ""
        var remainingText = text
        
        // Pattern for code blocks with optional language - more flexible
        let codeBlockPattern = /```([a-zA-Z0-9_+-]*)\n?([\s\S]*?)```/
        
        while !remainingText.isEmpty {
            // Check for code blocks
            if let match = remainingText.firstMatch(of: codeBlockPattern) {
                let matchRange = remainingText.range(of: match.0)!
                
                // Add any text before the code block
                let beforeText = String(remainingText[..<matchRange.lowerBound])
                if !beforeText.isEmpty {
                    currentText += beforeText
                }
                
                // Flush current text
                if !currentText.isEmpty {
                    components.append(.text(currentText.trimmingCharacters(in: .whitespacesAndNewlines)))
                    currentText = ""
                }
                
                // Add code block
                let languageSubstring = match.1
                let languageString = String(languageSubstring).trimmingCharacters(in: .whitespacesAndNewlines)
                let language: String? = languageString.isEmpty ? nil : languageString
                let code = String(match.2).trimmingCharacters(in: .newlines)
                components.append(.codeBlock(code, language))
                
                // Continue with remaining text
                remainingText = String(remainingText[matchRange.upperBound...])
            } else {
                // No more code blocks, add remaining text
                currentText += remainingText
                break
            }
        }
        
        // Process the final text for lists
        if !currentText.isEmpty {
            components.append(contentsOf: parseTextForLists(currentText))
        }
        
        return components.isEmpty ? [.text(text)] : components
    }
    
    private func parseTextForLists(_ text: String) -> [MessageComponent] {
        var components: [MessageComponent] = []
        let lines = text.split(separator: "\n", omittingEmptySubsequences: false)
        var currentList: [String] = []
        var currentText = ""
        var inList = false
        
        for line in lines {
            let trimmed = line.trimmingCharacters(in: .whitespaces)
            
            // Check if this is a list item (starts with -, *, or number.)
            if trimmed.hasPrefix("- ") || trimmed.hasPrefix("* ") {
                // Flush current text
                if !currentText.isEmpty && !inList {
                    let cleaned = currentText.trimmingCharacters(in: .whitespacesAndNewlines)
                    if !cleaned.isEmpty {
                        components.append(.text(cleaned))
                    }
                    currentText = ""
                }
                
                inList = true
                // Add to current list
                let item = String(trimmed.dropFirst(2))
                currentList.append(item)
            } else if let match = trimmed.firstMatch(of: /^(\d+)\.\s+(.*)/) {
                // Numbered list item
                if !currentText.isEmpty && !inList {
                    let cleaned = currentText.trimmingCharacters(in: .whitespacesAndNewlines)
                    if !cleaned.isEmpty {
                        components.append(.text(cleaned))
                    }
                    currentText = ""
                }
                
                inList = true
                let item = String(match.2)
                currentList.append(item)
            } else if trimmed.isEmpty && inList {
                // Empty line - might be end of list, but continue to see
                continue
            } else {
                // Not a list item
                // Flush current list
                if !currentList.isEmpty {
                    components.append(.list(currentList))
                    currentList = []
                    inList = false
                }
                
                // Add to current text
                if !line.isEmpty || !currentText.isEmpty {
                    currentText += (currentText.isEmpty ? "" : "\n") + line
                }
            }
        }
        
        // Flush remaining content
        if !currentList.isEmpty {
            components.append(.list(currentList))
        }
        if !currentText.isEmpty {
            let cleaned = currentText.trimmingCharacters(in: .whitespacesAndNewlines)
            if !cleaned.isEmpty {
                components.append(.text(cleaned))
            }
        }
        
        return components
    }
}

enum MessageComponent {
    case text(String)
    case codeBlock(String, String?) // code, language
    case list([String])
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
#Preview("Formatted Message") {
    VStack {
        ChatBubble(message: ChatMessage(
            role: .assistant,
            text: """
            Here's your energy analysis:
            
            **Current Status:**
            Your total power consumption is 2,500W with the following breakdown:
            
            - Kitchen Stove: 1,200W (active)
            - Water Heater: 850W (heating)
            - EV Charger: 450W (charging)
            
            **Recommendations:**
            
            1. Shift EV charging to after 9 PM for lower rates
            2. Use water heater during super off-peak hours
            3. Delay laundry until renewable energy peaks
            
            Here's a code example for optimal scheduling:
            
            ```python
            def optimize_schedule(tasks):
                for task in tasks:
                    if task.power > 1000:
                        task.schedule_at(off_peak_hours)
                return tasks
            ```
            
            You could save **$12.50** per day with these changes!
            """,
            timestamp: Date()
        ))
        .padding()
        
        ChatBubble(message: ChatMessage(
            role: .user,
            text: "What's my current energy usage?",
            timestamp: Date()
        ))
        .padding()
    }
}


