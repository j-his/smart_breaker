//
//  ContentView.swift
//  breakerios
//
//  Created by Tong tong Wang on 28/2/2026.
//

import SwiftUI

struct ContentView: View {
    @State private var selectedTab = 0
    @State private var showingChat = false

    var body: some View {
        TabView(selection: $selectedTab) {
            DeviceView()
                .tabItem {
                    Label("Device", systemImage: "bolt.circle.fill")
                }
                .tag(0)

            CalendarView()
                .tabItem {
                    Label("Calendar", systemImage: "calendar")
                }
                .tag(1)

            InsightsView()
                .tabItem {
                    Label("Insights", systemImage: "sparkles")
                }
                .tag(2)

            SettingsView()
                .tabItem {
                    Label("Settings", systemImage: "gear")
                }
                .tag(3)

            AboutView()
                .tabItem {
                    Label("About", systemImage: "info.circle")
                }
                .tag(4)
        }
        .overlay(alignment: .bottomTrailing) {
            Button { showingChat = true } label: {
                Image(systemName: "bubble.left.and.bubble.right.fill")
                    .font(.title2)
                    .foregroundStyle(.white)
                    .frame(width: 56, height: 56)
                    .background(Circle().fill(Color.blue))
                    .shadow(radius: 4)
            }
            .padding(.trailing, 20)
            .padding(.bottom, 80)
        }
        .sheet(isPresented: $showingChat) {
            ChatView()
        }
        .task {
            WebSocketManager.shared.connect()
            TTSPlayer.shared.startListening()
        }
    }
}

#Preview {
    ContentView()
}
