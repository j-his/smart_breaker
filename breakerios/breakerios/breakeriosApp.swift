//
//  breakeriosApp.swift
//  breakerios
//
//  Created by Tong tong Wang on 28/2/2026.
//

import SwiftUI

@main
struct breakeriosApp: App {
    @AppStorage("pairedDeviceUUID") private var pairedDeviceUUID: String?
    @State private var isPaired = false

    var body: some Scene {
        WindowGroup {
            if pairedDeviceUUID != nil || isPaired {
                ContentView()
            } else {
                PairingView(isPaired: $isPaired)
            }
        }
    }
}
