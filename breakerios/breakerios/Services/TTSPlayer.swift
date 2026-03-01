//
//  TTSPlayer.swift
//  breakerios
//
//  Created by Tong tong Wang on 28/2/2026.
//

import Foundation
import AVFoundation
import Combine

class TTSPlayer: NSObject, ObservableObject, AVAudioPlayerDelegate {
    static let shared = TTSPlayer()

    @Published var isPlaying = false
    @Published var currentInsightId: String?

    private var audioData = Data()
    private var audioPlayer: AVAudioPlayer?
    private var cancellables = Set<AnyCancellable>()

    private override init() {
        super.init()
    }

    func startListening() {
        setupAudioSession()

        WebSocketManager.shared.ttsChunkReceived
            .receive(on: DispatchQueue.main)
            .sink { [weak self] chunk in
                self?.handleChunk(chunk)
            }
            .store(in: &cancellables)
    }

    private func setupAudioSession() {
        let session = AVAudioSession.sharedInstance()
        try? session.setCategory(.playback, mode: .spokenAudio)
        try? session.setActive(true)
    }

    private func handleChunk(_ chunk: TTSAudioChunk) {
        if chunk.isFinal {
            playAccumulatedAudio(insightId: chunk.insightId)
        } else {
            currentInsightId = chunk.insightId
            if let decoded = Data(base64Encoded: chunk.audio) {
                audioData.append(decoded)
            }
        }
    }

    private func playAccumulatedAudio(insightId: String) {
        guard !audioData.isEmpty else {
            audioData = Data()
            currentInsightId = nil
            return
        }

        do {
            audioPlayer = try AVAudioPlayer(data: audioData)
            audioPlayer?.delegate = self
            audioPlayer?.play()
            isPlaying = true
        } catch {
            isPlaying = false
            currentInsightId = nil
        }

        audioData = Data()
    }

    // AVAudioPlayerDelegate
    nonisolated func audioPlayerDidFinishPlaying(_ player: AVAudioPlayer, successfully flag: Bool) {
        Task { @MainActor in
            self.isPlaying = false
            self.currentInsightId = nil
        }
    }
}
