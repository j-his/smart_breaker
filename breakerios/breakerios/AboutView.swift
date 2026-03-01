//
//  AboutView.swift
//  breakerios
//
//  Created by Tong tong Wang on 28/2/2026.
//

import SwiftUI

struct AboutView: View {
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 30) {
                    // App Icon and Title
                    VStack(spacing: 16) {
                        Image(systemName: "bolt.shield.fill")
                            .font(.system(size: 80))
                            .foregroundStyle(
                                LinearGradient(
                                    colors: [.blue, .green],
                                    startPoint: .topLeading,
                                    endPoint: .bottomTrailing
                                )
                            )
                        
                        Text("Smart Breaker")
                            .font(.title)
                            .fontWeight(.bold)
                        
                        Text("Version 1.0.0")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                    }
                    .padding(.top, 40)
                    
                    // Description
                    VStack(alignment: .leading, spacing: 16) {
                        Text("About This App")
                            .font(.title2)
                            .fontWeight(.bold)
                        
                        Text("Smart Breaker is an intelligent energy management system that monitors your home's electricity usage in real-time and optimizes your schedule to reduce costs and carbon emissions.")
                            .font(.body)
                            .foregroundStyle(.secondary)
                        
                        Text("Using advanced AI and real-time grid data, the app automatically schedules high-power tasks during periods of low cost and high renewable energy availability.")
                            .font(.body)
                            .foregroundStyle(.secondary)
                    }
                    .padding(.horizontal)
                    
                    // Features
                    VStack(alignment: .leading, spacing: 20) {
                        Text("Key Features")
                            .font(.title2)
                            .fontWeight(.bold)
                            .padding(.horizontal)
                        
                        FeatureRow(
                            icon: "chart.line.uptrend.xyaxis",
                            title: "Real-Time Monitoring",
                            description: "Track power usage across 4 breaker channels with live current readings"
                        )
                        
                        FeatureRow(
                            icon: "calendar.badge.clock",
                            title: "Smart Scheduling",
                            description: "AI-powered optimization to schedule tasks during off-peak hours"
                        )
                        
                        FeatureRow(
                            icon: "leaf.fill",
                            title: "Carbon Reduction",
                            description: "Automatically prioritize renewable energy periods to reduce your carbon footprint"
                        )
                        
                        FeatureRow(
                            icon: "dollarsign.circle.fill",
                            title: "Cost Savings",
                            description: "Save money by shifting energy-intensive tasks to cheaper rate periods"
                        )
                        
                        FeatureRow(
                            icon: "brain.head.profile",
                            title: "Predictive AI",
                            description: "Machine learning categorizes your appliances and predicts usage patterns"
                        )
                        
                        FeatureRow(
                            icon: "bolt.trianglebadge.exclamationmark",
                            title: "Anomaly Detection",
                            description: "Get alerts when unusual power consumption is detected"
                        )
                    }
                    
                    // System Info
                    VStack(spacing: 12) {
                        InfoCard(
                            title: "Hardware",
                            items: [
                                "4-channel smart breaker",
                                "7,200W maximum capacity",
                                "120V AC monitoring",
                                "Real-time CT sensor readings"
                            ]
                        )
                        
                        InfoCard(
                            title: "AI Capabilities",
                            items: [
                                "Transformer-based schedule optimization",
                                "Automatic appliance categorization",
                                "24-hour grid forecast integration",
                                "Multi-objective optimization (cost + carbon)"
                            ]
                        )
                    }
                    .padding(.horizontal)
                    
                    // Credits
                    VStack(spacing: 8) {
                        Text("Developed by Tong tong Wang")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                        
                        Text("© 2026 All Rights Reserved")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                    .padding(.bottom, 40)
                }
            }
            .navigationTitle("About")
        }
    }
}

struct FeatureRow: View {
    let icon: String
    let title: String
    let description: String
    
    var body: some View {
        HStack(alignment: .top, spacing: 16) {
            Image(systemName: icon)
                .font(.title2)
                .foregroundStyle(.blue)
                .frame(width: 32)
            
            VStack(alignment: .leading, spacing: 4) {
                Text(title)
                    .font(.headline)
                
                Text(description)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }
        }
        .padding(.horizontal)
    }
}

struct InfoCard: View {
    let title: String
    let items: [String]
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(title)
                .font(.headline)
                .padding(.bottom, 4)
            
            ForEach(items, id: \.self) { item in
                HStack(alignment: .top, spacing: 8) {
                    Image(systemName: "checkmark.circle.fill")
                        .font(.caption)
                        .foregroundStyle(.green)
                    
                    Text(item)
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 12)
                .fill(Color(.secondarySystemBackground))
        )
    }
}

#Preview {
    AboutView()
}
