import SwiftUI

struct RecordView: View {
    @EnvironmentObject var appState: AppState
    @State private var meetingTitle = ""
    @State private var showFilePicker = false

    var body: some View {
        VStack(spacing: 16) {
            if !appState.isConfigured {
                NotConfiguredBanner()
            } else {
                // Title input
                TextField("Meeting title (optional)", text: $meetingTitle)
                    .textFieldStyle(.roundedBorder)
                    .padding(.horizontal)

                // Record button
                VStack(spacing: 8) {
                    Button {
                        if appState.isRecording {
                            Task {
                                await appState.stopAndUpload(title: meetingTitle.isEmpty ? nil : meetingTitle)
                                meetingTitle = ""
                            }
                        } else {
                            appState.startRecording()
                        }
                    } label: {
                        ZStack {
                            Circle()
                                .fill(appState.isRecording ? Color.red : Color.accentColor)
                                .frame(width: 64, height: 64)

                            Image(systemName: appState.isRecording ? "stop.fill" : "mic.fill")
                                .font(.system(size: 24))
                                .foregroundColor(.white)
                        }
                    }
                    .buttonStyle(.plain)

                    if appState.isRecording {
                        Text(formatDuration(appState.recordingDuration))
                            .font(.system(.title2, design: .monospaced))
                            .foregroundColor(.red)

                        Text("Recording... Click to stop and upload")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    } else {
                        Text("Click to start recording")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }

                Divider().padding(.horizontal)

                // Upload file button
                Button {
                    showFilePicker = true
                } label: {
                    Label("Upload audio file", systemImage: "doc.badge.plus")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.bordered)
                .padding(.horizontal)
                .fileImporter(
                    isPresented: $showFilePicker,
                    allowedContentTypes: [.audio, .mpeg4Audio, .mp3, .wav],
                    allowsMultipleSelection: false
                ) { result in
                    switch result {
                    case .success(let urls):
                        if let url = urls.first {
                            let title = meetingTitle.isEmpty ? url.deletingPathExtension().lastPathComponent : meetingTitle
                            Task {
                                _ = url.startAccessingSecurityScopedResource()
                                await appState.uploadFile(fileURL: url, title: title)
                                url.stopAccessingSecurityScopedResource()
                                meetingTitle = ""
                            }
                        }
                    case .failure(let error):
                        appState.error = error.localizedDescription
                    }
                }
            }
        }
        .padding(.vertical, 12)
    }

    private func formatDuration(_ seconds: TimeInterval) -> String {
        let mins = Int(seconds) / 60
        let secs = Int(seconds) % 60
        return String(format: "%02d:%02d", mins, secs)
    }
}

struct NotConfiguredBanner: View {
    @EnvironmentObject var appState: AppState

    var body: some View {
        VStack(spacing: 8) {
            Image(systemName: "gear.badge.xmark")
                .font(.system(size: 32))
                .foregroundColor(.orange)

            Text("Not Configured")
                .font(.headline)

            Text("Set your API key and server URL in Settings to get started.")
                .font(.caption)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)

            Button("Open Settings") {
                appState.currentTab = .settings
            }
            .buttonStyle(.borderedProminent)
        }
        .padding()
    }
}
