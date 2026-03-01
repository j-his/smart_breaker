//
//  APIClient.swift
//  breakerios
//
//  Created by Tong tong Wang on 28/2/2026.
//

import Foundation

class APIClient {
    static let shared = APIClient()

    var baseURL: String {
        UserDefaults.standard.string(forKey: "serverURL") ?? "http://localhost:8000"
    }

    let decoder: JSONDecoder = {
        let d = JSONDecoder()
        d.keyDecodingStrategy = .convertFromSnakeCase
        return d
    }()

    let encoder: JSONEncoder = {
        let e = JSONEncoder()
        e.keyEncodingStrategy = .convertToSnakeCase
        return e
    }()

    private init() {}

    // MARK: - Generic Request Methods

    func get<T: Decodable>(_ path: String) async throws -> T {
        guard let url = URL(string: baseURL + path) else {
            throw APIError.invalidURL
        }

        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await URLSession.shared.data(from: url)
        } catch {
            throw APIError.networkError(error)
        }

        if let http = response as? HTTPURLResponse, !(200...299).contains(http.statusCode) {
            let body = String(data: data, encoding: .utf8)
            throw APIError.serverError(http.statusCode, body)
        }

        do {
            return try decoder.decode(T.self, from: data)
        } catch {
            throw APIError.decodingError(error)
        }
    }

    func post<B: Encodable, R: Decodable>(_ path: String, body: B) async throws -> R {
        guard let url = URL(string: baseURL + path) else {
            throw APIError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        do {
            request.httpBody = try encoder.encode(body)
        } catch {
            throw APIError.decodingError(error)
        }

        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await URLSession.shared.data(for: request)
        } catch {
            throw APIError.networkError(error)
        }

        if let http = response as? HTTPURLResponse, !(200...299).contains(http.statusCode) {
            let body = String(data: data, encoding: .utf8)
            throw APIError.serverError(http.statusCode, body)
        }

        do {
            return try decoder.decode(R.self, from: data)
        } catch {
            throw APIError.decodingError(error)
        }
    }

    // MARK: - Convenience Methods

    func getHealth() async throws -> HealthResponse {
        try await get("/api/health")
    }

    func getDashboard() async throws -> DashboardResponse {
        try await get("/api/dashboard")
    }

    func getForecast() async throws -> ForecastResponse {
        try await get("/api/forecast")
    }

    func getSchedule() async throws -> OptimizationResult {
        try await get("/api/schedule")
    }

    func getInsights() async throws -> InsightsResponse {
        try await get("/api/insights")
    }

    func addTask(_ task: TaskRequest) async throws -> TaskResponse {
        try await post("/api/tasks", body: task)
    }

    func updateSettings(_ settings: SettingsRequest) async throws -> SettingsResponse {
        try await post("/api/settings", body: settings)
    }

    func importCalendar(_ req: CalendarImportRequest) async throws -> CalendarImportResponse {
        try await post("/api/calendar/import", body: req)
    }
}
