import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var appState: AppState
    @State private var testResult: String?
    @State private var isTesting = false

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Settings")
                .font(.headline)

            VStack(alignment: .leading, spacing: 6) {
                Text("Server URL")
                    .font(.caption)
                    .foregroundColor(.secondary)
                TextField("http://localhost:8000", text: $appState.serverURL)
                    .textFieldStyle(.roundedBorder)
            }

            VStack(alignment: .leading, spacing: 6) {
                Text("API Key")
                    .font(.caption)
                    .foregroundColor(.secondary)
                SecureField("aia_...", text: $appState.apiKey)
                    .textFieldStyle(.roundedBorder)
            }

            HStack {
                Button {
                    Task { await testConnection() }
                } label: {
                    if isTesting {
                        ProgressView()
                            .scaleEffect(0.6)
                    } else {
                        Text("Test Connection")
                    }
                }
                .buttonStyle(.bordered)
                .disabled(isTesting || !appState.isConfigured)

                if let result = testResult {
                    Text(result)
                        .font(.caption)
                        .foregroundColor(result.contains("OK") ? .green : .red)
                }
            }

            Divider()

            VStack(alignment: .leading, spacing: 4) {
                Text("How to get an API key:")
                    .font(.caption)
                    .fontWeight(.medium)
                Text("curl -X POST http://your-server:8000/api/v1/auth/keys?name=mac-app")
                    .font(.system(size: 11, design: .monospaced))
                    .foregroundColor(.secondary)
                    .textSelection(.enabled)
            }
        }
        .padding(16)
        .frame(width: 380)
    }

    private func testConnection() async {
        isTesting = true
        testResult = nil

        do {
            _ = try await appState.apiClient.listMeetings(
                baseURL: appState.serverURL,
                apiKey: appState.apiKey,
                limit: 1
            )
            testResult = "OK — Connected!"
        } catch {
            testResult = "Error: \(error.localizedDescription)"
        }

        isTesting = false
    }
}
