import Foundation

struct Meeting: Codable, Identifiable {
    let id: String
    let title: String?
    let status: String
    let errorMessage: String?
    let audioDurationSec: Int?
    let language: String
    let source: String
    let createdAt: String
    let updatedAt: String?
    let transcript: Transcript?
    let summary: Summary?

    enum CodingKeys: String, CodingKey {
        case id, title, status, language, source, transcript, summary
        case errorMessage = "error_message"
        case audioDurationSec = "audio_duration_sec"
        case createdAt = "created_at"
        case updatedAt = "updated_at"
    }

    var statusIcon: String {
        switch status {
        case "done": return "checkmark.circle.fill"
        case "error": return "xmark.circle.fill"
        case "transcribing": return "waveform"
        case "summarizing": return "brain"
        case "uploading": return "arrow.up.circle"
        default: return "questionmark.circle"
        }
    }

    var statusColor: String {
        switch status {
        case "done": return "green"
        case "error": return "red"
        default: return "orange"
        }
    }

    var displayTitle: String {
        title ?? "Untitled"
    }

    var formattedDate: String {
        // Parse ISO date and format nicely
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let date = formatter.date(from: createdAt) {
            let display = DateFormatter()
            display.dateFormat = "dd.MM.yyyy HH:mm"
            return display.string(from: date)
        }
        // Try without fractional seconds
        formatter.formatOptions = [.withInternetDateTime]
        if let date = formatter.date(from: createdAt) {
            let display = DateFormatter()
            display.dateFormat = "dd.MM.yyyy HH:mm"
            return display.string(from: date)
        }
        return String(createdAt.prefix(16))
    }
}

struct Transcript: Codable {
    let fullText: String
    let wordCount: Int
    let segments: [[String: AnyCodableValue]]?

    enum CodingKeys: String, CodingKey {
        case fullText = "full_text"
        case wordCount = "word_count"
        case segments
    }
}

struct Summary: Codable {
    let summaryText: String
    let actionItems: [ActionItem]?
    let keyDecisions: [KeyDecision]?
    let participants: [String]?
    let modelUsed: String

    enum CodingKeys: String, CodingKey {
        case summaryText = "summary_text"
        case actionItems = "action_items"
        case keyDecisions = "key_decisions"
        case participants
        case modelUsed = "model_used"
    }
}

struct ActionItem: Codable {
    let task: String
    let assignee: String?
    let deadline: String?
}

struct KeyDecision: Codable {
    let decision: String
    let context: String?
}

struct MeetingListResponse: Codable {
    let meetings: [Meeting]
    let total: Int
}

struct UploadResponse: Codable {
    let meetingId: String
    let status: String
    let message: String

    enum CodingKeys: String, CodingKey {
        case meetingId = "meeting_id"
        case status, message
    }
}

// Helper for dynamic JSON values in segments
enum AnyCodableValue: Codable {
    case string(String)
    case int(Int)
    case double(Double)
    case bool(Bool)
    case null

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if let v = try? container.decode(String.self) { self = .string(v) }
        else if let v = try? container.decode(Int.self) { self = .int(v) }
        else if let v = try? container.decode(Double.self) { self = .double(v) }
        else if let v = try? container.decode(Bool.self) { self = .bool(v) }
        else { self = .null }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .string(let v): try container.encode(v)
        case .int(let v): try container.encode(v)
        case .double(let v): try container.encode(v)
        case .bool(let v): try container.encode(v)
        case .null: try container.encodeNil()
        }
    }
}
