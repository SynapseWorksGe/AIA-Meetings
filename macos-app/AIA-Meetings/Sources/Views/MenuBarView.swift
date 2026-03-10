import SwiftUI

struct MenuBarView: View {
    @EnvironmentObject var appState: AppState

    var body: some View {
        VStack(spacing: 0) {
            // Header tabs
            HStack(spacing: 0) {
                TabButton(title: "Record", icon: "mic.fill", tab: .record)
                TabButton(title: "Meetings", icon: "list.bullet", tab: .meetings)
                TabButton(title: "Settings", icon: "gear", tab: .settings)
            }
            .padding(.horizontal, 8)
            .padding(.top, 8)

            Divider().padding(.vertical, 4)

            // Content
            Group {
                switch appState.currentTab {
                case .record:
                    RecordView()
                case .meetings:
                    MeetingsListView()
                case .settings:
                    SettingsView()
                }
            }
            .frame(width: 380)

            // Error banner
            if let error = appState.error {
                HStack {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .foregroundColor(.orange)
                    Text(error)
                        .font(.caption)
                        .lineLimit(2)
                    Spacer()
                    Button {
                        appState.error = nil
                    } label: {
                        Image(systemName: "xmark.circle.fill")
                            .foregroundColor(.secondary)
                    }
                    .buttonStyle(.plain)
                }
                .padding(8)
                .background(.orange.opacity(0.1))
            }

            Divider()

            // Footer
            HStack {
                if appState.isLoading {
                    ProgressView()
                        .scaleEffect(0.6)
                }
                Spacer()
                Button("Quit") {
                    NSApplication.shared.terminate(nil)
                }
                .buttonStyle(.plain)
                .foregroundColor(.secondary)
                .font(.caption)
            }
            .padding(8)
        }
    }
}

struct TabButton: View {
    let title: String
    let icon: String
    let tab: AppState.Tab
    @EnvironmentObject var appState: AppState

    var isSelected: Bool {
        appState.currentTab == tab
    }

    var body: some View {
        Button {
            appState.currentTab = tab
        } label: {
            VStack(spacing: 2) {
                Image(systemName: icon)
                    .font(.system(size: 14))
                Text(title)
                    .font(.caption2)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 6)
            .background(isSelected ? Color.accentColor.opacity(0.15) : Color.clear)
            .cornerRadius(6)
        }
        .buttonStyle(.plain)
    }
}
