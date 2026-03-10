import SwiftUI

struct MeetingsListView: View {
    @EnvironmentObject var appState: AppState
    @State private var selectedMeeting: Meeting?

    var body: some View {
        VStack(spacing: 0) {
            if let meeting = selectedMeeting {
                MeetingDetailView(meeting: meeting) {
                    selectedMeeting = nil
                }
            } else {
                meetingsList
            }
        }
        .task {
            await appState.loadMeetings()
        }
    }

    var meetingsList: some View {
        VStack(spacing: 0) {
            if appState.meetings.isEmpty && !appState.isLoading {
                VStack(spacing: 8) {
                    Image(systemName: "tray")
                        .font(.system(size: 32))
                        .foregroundColor(.secondary)
                    Text("No meetings yet")
                        .foregroundColor(.secondary)
                    Text("Record or upload an audio file to get started")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                .padding(24)
            } else {
                ScrollView {
                    LazyVStack(spacing: 1) {
                        ForEach(appState.meetings) { meeting in
                            MeetingRow(meeting: meeting)
                                .onTapGesture {
                                    Task {
                                        await appState.refreshMeeting(id: meeting.id)
                                        if let updated = appState.meetings.first(where: { $0.id == meeting.id }) {
                                            selectedMeeting = updated
                                        }
                                    }
                                }
                                .contextMenu {
                                    Button("Refresh") {
                                        Task { await appState.refreshMeeting(id: meeting.id) }
                                    }
                                    Button("Copy ID") {
                                        NSPasteboard.general.clearContents()
                                        NSPasteboard.general.setString(meeting.id, forType: .string)
                                    }
                                    Divider()
                                    Button("Delete", role: .destructive) {
                                        Task { await appState.deleteMeeting(id: meeting.id) }
                                    }
                                }
                        }
                    }
                }
                .frame(maxHeight: 350)
            }

            Divider()

            HStack {
                Text("\(appState.meetings.count) meetings")
                    .font(.caption)
                    .foregroundColor(.secondary)
                Spacer()
                Button {
                    Task { await appState.loadMeetings() }
                } label: {
                    Image(systemName: "arrow.clockwise")
                }
                .buttonStyle(.plain)
                .foregroundColor(.secondary)
            }
            .padding(8)
        }
    }
}

struct MeetingRow: View {
    let meeting: Meeting

    var body: some View {
        HStack(spacing: 10) {
            Image(systemName: meeting.statusIcon)
                .foregroundColor(statusColor)
                .frame(width: 20)

            VStack(alignment: .leading, spacing: 2) {
                Text(meeting.displayTitle)
                    .font(.system(size: 13, weight: .medium))
                    .lineLimit(1)

                HStack(spacing: 4) {
                    Text(meeting.formattedDate)
                    if let duration = meeting.audioDurationSec {
                        Text("·")
                        Text("\(duration / 60) min")
                    }
                    Text("·")
                    Text(meeting.status)
                }
                .font(.caption)
                .foregroundColor(.secondary)
            }

            Spacer()

            if meeting.status != "done" && meeting.status != "error" {
                ProgressView()
                    .scaleEffect(0.5)
            }
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .background(Color(nsColor: .controlBackgroundColor))
    }

    var statusColor: Color {
        switch meeting.status {
        case "done": return .green
        case "error": return .red
        default: return .orange
        }
    }
}
