import SwiftUI
import Combine

@MainActor
class AppState: ObservableObject {
    @Published var isRecording = false
    @Published var recordingDuration: TimeInterval = 0
    @Published var meetings: [Meeting] = []
    @Published var isLoading = false
    @Published var error: String?
    @Published var currentTab: Tab = .record

    // Settings
    @AppStorage("apiKey") var apiKey = ""
    @AppStorage("serverURL") var serverURL = "http://localhost:8000"

    let apiClient = APIClient()
    let recorder = AudioRecorder()

    var isConfigured: Bool {
        !apiKey.isEmpty && !serverURL.isEmpty
    }

    enum Tab {
        case record
        case meetings
        case settings
    }

    func loadMeetings() async {
        guard isConfigured else { return }
        isLoading = true
        error = nil

        do {
            meetings = try await apiClient.listMeetings(baseURL: serverURL, apiKey: apiKey)
        } catch {
            self.error = error.localizedDescription
        }

        isLoading = false
    }

    func startRecording() {
        do {
            try recorder.startRecording()
            isRecording = true
            recordingDuration = 0

            // Update duration every second
            Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { [weak self] timer in
                Task { @MainActor in
                    guard let self, self.isRecording else {
                        timer.invalidate()
                        return
                    }
                    self.recordingDuration += 1
                }
            }
        } catch {
            self.error = "Failed to start recording: \(error.localizedDescription)"
        }
    }

    func stopAndUpload(title: String?) async {
        guard isRecording else { return }
        isRecording = false

        guard let fileURL = recorder.stopRecording() else {
            error = "No recording file found"
            return
        }

        await uploadFile(fileURL: fileURL, title: title ?? "Recording \(Date().formatted())")
    }

    func uploadFile(fileURL: URL, title: String) async {
        guard isConfigured else {
            error = "Please configure API key and server URL in Settings"
            return
        }

        isLoading = true
        error = nil

        do {
            let meeting = try await apiClient.uploadMeeting(
                baseURL: serverURL,
                apiKey: apiKey,
                fileURL: fileURL,
                title: title
            )
            // Add to top of list
            meetings.insert(meeting, at: 0)
        } catch {
            self.error = "Upload failed: \(error.localizedDescription)"
        }

        isLoading = false
    }

    func refreshMeeting(id: String) async {
        guard isConfigured else { return }

        do {
            let updated = try await apiClient.getMeeting(baseURL: serverURL, apiKey: apiKey, id: id)
            if let index = meetings.firstIndex(where: { $0.id == id }) {
                meetings[index] = updated
            }
        } catch {
            self.error = error.localizedDescription
        }
    }

    func deleteMeeting(id: String) async {
        guard isConfigured else { return }

        do {
            try await apiClient.deleteMeeting(baseURL: serverURL, apiKey: apiKey, id: id)
            meetings.removeAll { $0.id == id }
        } catch {
            self.error = error.localizedDescription
        }
    }
}
