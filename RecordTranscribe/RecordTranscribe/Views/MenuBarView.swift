import SwiftUI

struct MenuBarView: View {
    @ObservedObject var transcriptionService: TranscriptionService
    @State private var isHovering = false

    var body: some View {
        VStack(spacing: 0) {
            // Status header
            StatusHeader(transcriptionService: transcriptionService)

            Divider()
                .padding(.vertical, 8)

            // Recording button
            RecordingButton(transcriptionService: transcriptionService)
                .padding(.horizontal, 16)

            // Last transcription preview
            if let lastTranscription = transcriptionService.lastTranscription {
                Divider()
                    .padding(.vertical, 8)

                LastTranscriptionView(text: lastTranscription)
                    .padding(.horizontal, 16)
            }

            Divider()
                .padding(.vertical, 8)

            // Bottom actions
            HStack {
                Button("History") {
                    transcriptionService.showHistoryWindow()
                }
                .buttonStyle(.plain)

                Spacer()

                Button {
                    NSApp.sendAction(Selector(("showSettingsWindow:")), to: nil, from: nil)
                } label: {
                    Image(systemName: "gear")
                }
                .buttonStyle(.plain)

                Button {
                    NSApplication.shared.terminate(nil)
                } label: {
                    Image(systemName: "power")
                }
                .buttonStyle(.plain)
            }
            .padding(.horizontal, 16)
            .padding(.bottom, 12)
        }
        .frame(width: 320)
    }
}

struct StatusHeader: View {
    @ObservedObject var transcriptionService: TranscriptionService

    var body: some View {
        HStack(spacing: 12) {
            // Status indicator
            Circle()
                .fill(statusColor)
                .frame(width: 10, height: 10)

            VStack(alignment: .leading, spacing: 2) {
                Text(statusTitle)
                    .font(.headline)

                Text(statusSubtitle)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }

            Spacer()

            // Hotkey hint
            Text("⌥ ⌥")
                .font(.system(.caption, design: .monospaced))
                .padding(.horizontal, 8)
                .padding(.vertical, 4)
                .background(Color.secondary.opacity(0.2))
                .cornerRadius(4)
        }
        .padding(.horizontal, 16)
        .padding(.top, 12)
    }

    var statusColor: Color {
        switch transcriptionService.status {
        case .idle: return .green
        case .recording: return .red
        case .transcribing: return .orange
        case .error: return .red
        case .loading: return .yellow
        }
    }

    var statusTitle: String {
        switch transcriptionService.status {
        case .idle: return "Ready"
        case .recording: return "Recording..."
        case .transcribing: return "Transcribing..."
        case .error: return "Error"
        case .loading: return "Loading..."
        }
    }

    var statusSubtitle: String {
        switch transcriptionService.status {
        case .idle: return "Double-tap Option to record"
        case .recording: return "Tap Option to stop"
        case .transcribing: return "Processing audio..."
        case .error: return transcriptionService.errorMessage ?? "Unknown error"
        case .loading: return "Starting transcription service..."
        }
    }
}

struct RecordingButton: View {
    @ObservedObject var transcriptionService: TranscriptionService

    var body: some View {
        Button(action: {
            transcriptionService.toggleRecording()
        }) {
            HStack {
                Image(systemName: transcriptionService.isRecording ? "stop.fill" : "mic.fill")
                Text(transcriptionService.isRecording ? "Stop Recording" : "Start Recording")
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 10)
            .background(transcriptionService.isRecording ? Color.red : Color.accentColor)
            .foregroundColor(.white)
            .cornerRadius(8)
        }
        .buttonStyle(.plain)
    }
}

struct LastTranscriptionView: View {
    let text: String
    @State private var isCopied = false

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text("Last Transcription")
                    .font(.caption)
                    .foregroundColor(.secondary)

                Spacer()

                Button(action: copyToClipboard) {
                    Image(systemName: isCopied ? "checkmark" : "doc.on.doc")
                        .font(.caption)
                }
                .buttonStyle(.plain)
            }

            Text(text)
                .font(.system(.body, design: .default))
                .lineLimit(3)
                .frame(maxWidth: .infinity, alignment: .leading)
        }
        .padding(12)
        .background(Color.secondary.opacity(0.1))
        .cornerRadius(8)
    }

    func copyToClipboard() {
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(text, forType: .string)
        isCopied = true
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) {
            isCopied = false
        }
    }
}

#Preview {
    MenuBarView(transcriptionService: TranscriptionService())
        .frame(width: 320, height: 400)
}
