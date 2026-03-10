import Foundation

class APIClient {

    enum APIError: LocalizedError {
        case invalidURL
        case httpError(Int, String)
        case decodingError(String)

        var errorDescription: String? {
            switch self {
            case .invalidURL: return "Invalid server URL"
            case .httpError(let code, let msg): return "HTTP \(code): \(msg)"
            case .decodingError(let msg): return "Decoding error: \(msg)"
            }
        }
    }

    private func request(baseURL: String, path: String, apiKey: String) throws -> URLRequest {
        guard let url = URL(string: "\(baseURL)\(path)") else {
            throw APIError.invalidURL
        }
        var req = URLRequest(url: url)
        req.setValue(apiKey, forHTTPHeaderField: "X-API-Key")
        req.timeoutInterval = 120
        return req
    }

    // MARK: - List Meetings

    func listMeetings(baseURL: String, apiKey: String, limit: Int = 20) async throws -> [Meeting] {
        var req = try request(baseURL: baseURL, path: "/api/v1/meetings?limit=\(limit)", apiKey: apiKey)
        req.httpMethod = "GET"

        let (data, response) = try await URLSession.shared.data(for: req)
        try checkResponse(response, data: data)

        let decoded = try JSONDecoder().decode(MeetingListResponse.self, from: data)
        return decoded.meetings
    }

    // MARK: - Get Meeting

    func getMeeting(baseURL: String, apiKey: String, id: String) async throws -> Meeting {
        var req = try request(baseURL: baseURL, path: "/api/v1/meetings/\(id)", apiKey: apiKey)
        req.httpMethod = "GET"

        let (data, response) = try await URLSession.shared.data(for: req)
        try checkResponse(response, data: data)

        return try JSONDecoder().decode(Meeting.self, from: data)
    }

    // MARK: - Upload Meeting

    func uploadMeeting(baseURL: String, apiKey: String, fileURL: URL, title: String, language: String = "ru") async throws -> Meeting {
        guard let url = URL(string: "\(baseURL)/api/v1/meetings/upload") else {
            throw APIError.invalidURL
        }

        let boundary = UUID().uuidString
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue(apiKey, forHTTPHeaderField: "X-API-Key")
        req.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        req.timeoutInterval = 300

        let fileData = try Data(contentsOf: fileURL)
        let filename = fileURL.lastPathComponent

        var body = Data()

        // File field
        body.appendString("--\(boundary)\r\n")
        body.appendString("Content-Disposition: form-data; name=\"file\"; filename=\"\(filename)\"\r\n")
        body.appendString("Content-Type: application/octet-stream\r\n\r\n")
        body.append(fileData)
        body.appendString("\r\n")

        // Title field
        body.appendString("--\(boundary)\r\n")
        body.appendString("Content-Disposition: form-data; name=\"title\"\r\n\r\n")
        body.appendString("\(title)\r\n")

        // Language field
        body.appendString("--\(boundary)\r\n")
        body.appendString("Content-Disposition: form-data; name=\"language\"\r\n\r\n")
        body.appendString("\(language)\r\n")

        body.appendString("--\(boundary)--\r\n")
        req.httpBody = body

        let (data, response) = try await URLSession.shared.data(for: req)
        try checkResponse(response, data: data)

        let uploadResp = try JSONDecoder().decode(UploadResponse.self, from: data)

        // Return a Meeting object with initial status
        return Meeting(
            id: uploadResp.meetingId,
            title: title,
            status: uploadResp.status,
            errorMessage: nil,
            audioDurationSec: nil,
            language: language,
            source: "mac",
            createdAt: ISO8601DateFormatter().string(from: Date()),
            updatedAt: nil,
            transcript: nil,
            summary: nil
        )
    }

    // MARK: - Delete Meeting

    func deleteMeeting(baseURL: String, apiKey: String, id: String) async throws {
        var req = try request(baseURL: baseURL, path: "/api/v1/meetings/\(id)", apiKey: apiKey)
        req.httpMethod = "DELETE"

        let (data, response) = try await URLSession.shared.data(for: req)
        if let http = response as? HTTPURLResponse, http.statusCode != 204 {
            try checkResponse(response, data: data)
        }
    }

    // MARK: - Helpers

    private func checkResponse(_ response: URLResponse, data: Data) throws {
        guard let http = response as? HTTPURLResponse else { return }
        guard (200...299).contains(http.statusCode) else {
            let body = String(data: data, encoding: .utf8) ?? "Unknown error"
            throw APIError.httpError(http.statusCode, body)
        }
    }
}

extension Data {
    mutating func appendString(_ string: String) {
        if let data = string.data(using: .utf8) {
            append(data)
        }
    }
}
