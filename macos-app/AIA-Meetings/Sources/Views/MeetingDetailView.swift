import SwiftUI

struct MeetingDetailView: View {
    let meeting: Meeting
    let onBack: () -> Void

    @State private var showFullTranscript = false

    var body: some View {
        VStack(spacing: 0) {
            // Header with back button
            HStack {
                Button {
                    onBack()
                } label: {
                    HStack(spacing: 4) {
                        Image(systemName: "chevron.left")
                        Text("Back")
                    }
                }
                .buttonStyle(.plain)
                .foregroundColor(.accentColor)

                Spacer()

                // Copy summary
                if meeting.summary != nil {
                    Button {
                        copyToClipboard()
                    } label: {
                        Image(systemName: "doc.on.doc")
                    }
                    .buttonStyle(.plain)
                    .foregroundColor(.secondary)
                    .help("Copy summary to clipboard")
                }
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 8)

            Divider()

            ScrollView {
                VStack(alignment: .leading, spacing: 12) {
                    // Title & status
                    VStack(alignment: .leading, spacing: 4) {
                        Text(meeting.displayTitle)
                            .font(.headline)

                        HStack(spacing: 8) {
                            Image(systemName: meeting.statusIcon)
                                .foregroundColor(meeting.status == "done" ? .green : meeting.status == "error" ? .red : .orange)
                            Text(meeting.status.capitalized)
                                .font(.subheadline)

                            Spacer()

                            Text(meeting.formattedDate)
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                    }

                    if meeting.status == "error" {
                        Text(meeting.errorMessage ?? "Unknown error")
                            .font(.caption)
                            .foregroundColor(.red)
                            .padding(8)
                            .background(Color.red.opacity(0.1))
                            .cornerRadius(6)
                    }

                    if let summary = meeting.summary {
                        Divider()

                        // Summary
                        SectionHeader(icon: "doc.text", title: "Summary")
                        Text(summary.summaryText)
                            .font(.system(size: 13))

                        // Participants
                        if let participants = summary.participants, !participants.isEmpty {
                            SectionHeader(icon: "person.2", title: "Participants")
                            Text(participants.joined(separator: ", "))
                                .font(.system(size: 13))
                        }

                        // Action items
                        if let items = summary.actionItems, !items.isEmpty {
                            SectionHeader(icon: "checkmark.circle", title: "Action Items")
                            ForEach(Array(items.enumerated()), id: \.offset) { i, item in
                                HStack(alignment: .top, spacing: 6) {
                                    Text("\(i + 1).")
                                        .font(.system(size: 12, weight: .bold))
                                        .foregroundColor(.accentColor)
                                        .frame(width: 18, alignment: .trailing)

                                    VStack(alignment: .leading, spacing: 2) {
                                        Text(item.task)
                                            .font(.system(size: 13))

                                        HStack(spacing: 8) {
                                            if let assignee = item.assignee {
                                                Label(assignee, systemImage: "person")
                                            }
                                            if let deadline = item.deadline {
                                                Label(deadline, systemImage: "calendar")
                                            }
                                        }
                                        .font(.caption)
                                        .foregroundColor(.secondary)
                                    }
                                }
                            }
                        }

                        // Key decisions
                        if let decisions = summary.keyDecisions, !decisions.isEmpty {
                            SectionHeader(icon: "key", title: "Key Decisions")
                            ForEach(Array(decisions.enumerated()), id: \.offset) { _, decision in
                                VStack(alignment: .leading, spacing: 2) {
                                    HStack(alignment: .top, spacing: 6) {
                                        Text("•")
                                            .foregroundColor(.accentColor)
                                        Text(decision.decision)
                                            .font(.system(size: 13))
                                    }
                                    if let context = decision.context {
                                        Text(context)
                                            .font(.caption)
                                            .foregroundColor(.secondary)
                                            .padding(.leading, 14)
                                    }
                                }
                            }
                        }
                    }

                    // Transcript
                    if let transcript = meeting.transcript {
                        Divider()

                        HStack {
                            SectionHeader(icon: "text.alignleft", title: "Transcript (\(transcript.wordCount) words)")
                            Spacer()
                            Button(showFullTranscript ? "Hide" : "Show") {
                                showFullTranscript.toggle()
                            }
                            .buttonStyle(.bordered)
                            .controlSize(.small)
                        }

                        if showFullTranscript {
                            Text(transcript.fullText)
                                .font(.system(size: 12))
                                .textSelection(.enabled)
                                .padding(8)
                                .background(Color(nsColor: .textBackgroundColor))
                                .cornerRadius(6)
                        }
                    }
                }
                .padding(12)
            }
            .frame(maxHeight: 450)
        }
    }

    private func copyToClipboard() {
        var text = "# \(meeting.displayTitle)\n\n"

        if let summary = meeting.summary {
            text += "## Summary\n\(summary.summaryText)\n\n"

            if let participants = summary.participants, !participants.isEmpty {
                text += "## Participants\n\(participants.joined(separator: ", "))\n\n"
            }

            if let items = summary.actionItems, !items.isEmpty {
                text += "## Action Items\n"
                for (i, item) in items.enumerated() {
                    var line = "\(i + 1). \(item.task)"
                    if let a = item.assignee { line += " [\(a)]" }
                    if let d = item.deadline { line += " (due: \(d))" }
                    text += line + "\n"
                }
                text += "\n"
            }

            if let decisions = summary.keyDecisions, !decisions.isEmpty {
                text += "## Key Decisions\n"
                for d in decisions {
                    text += "- \(d.decision)\n"
                }
            }
        }

        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(text, forType: .string)
    }
}

struct SectionHeader: View {
    let icon: String
    let title: String

    var body: some View {
        Label(title, systemImage: icon)
            .font(.system(size: 13, weight: .semibold))
            .foregroundColor(.primary)
    }
}
