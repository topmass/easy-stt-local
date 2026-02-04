import SwiftUI
import AppKit

struct HistoryView: View {
    @ObservedObject var transcriptionService: TranscriptionService
    @State private var selectedEntry: TranscriptionEntry?

    var body: some View {
        NavigationSplitView {
            List(transcriptionService.transcriptionHistory, selection: $selectedEntry) { entry in
                HistoryRowView(entry: entry)
                    .tag(entry)
            }
            .listStyle(.sidebar)
            .frame(minWidth: 250)
        } detail: {
            if let entry = selectedEntry {
                HistoryDetailView(entry: entry)
            } else {
                Text("Select a transcription to view details")
                    .foregroundColor(.secondary)
            }
        }
        .frame(minWidth: 600, minHeight: 400)
    }
}

struct HistoryRowView: View {
    let entry: TranscriptionEntry

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(entry.text)
                .lineLimit(2)
                .font(.body)

            HStack {
                Text(entry.timestamp, style: .relative)
                    .font(.caption)
                    .foregroundColor(.secondary)

                if entry.cleanupUsed {
                    Label("Cleaned", systemImage: "sparkles")
                        .font(.caption2)
                        .foregroundColor(.purple)
                }
            }
        }
        .padding(.vertical, 4)
    }
}

struct HistoryDetailView: View {
    let entry: TranscriptionEntry
    @State private var showOriginal = false
    @State private var isCopied = false

    var hasCleanup: Bool {
        entry.cleanupUsed && entry.originalText != entry.text
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            // Header
            HStack {
                VStack(alignment: .leading) {
                    Text(entry.timestamp, style: .date)
                        .font(.headline)
                    Text(entry.timestamp, style: .time)
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }

                Spacer()

                if hasCleanup {
                    Picker("Version", selection: $showOriginal) {
                        Text("Cleaned").tag(false)
                        Text("Original").tag(true)
                    }
                    .pickerStyle(.segmented)
                    .frame(width: 180)
                }

                Button(action: copyToClipboard) {
                    Label(isCopied ? "Copied" : "Copy", systemImage: isCopied ? "checkmark" : "doc.on.doc")
                }
                .buttonStyle(.bordered)
            }

            Divider()

            // Content
            ScrollView {
                Text(showOriginal ? entry.originalText : entry.text)
                    .font(.body)
                    .textSelection(.enabled)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }

            // Footer
            if hasCleanup && !showOriginal {
                HStack(spacing: 4) {
                    Image(systemName: "sparkles")
                        .font(.caption)
                    Text("Text was cleaned up by LLM")
                        .font(.caption)
                }
                .foregroundColor(.purple)
            }
        }
        .padding()
    }

    func copyToClipboard() {
        let textToCopy = showOriginal ? entry.originalText : entry.text
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(textToCopy, forType: .string)
        isCopied = true
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) {
            isCopied = false
        }
    }
}

class HistoryWindowController: NSWindowController {
    convenience init(transcriptionService: TranscriptionService) {
        let hostingController = NSHostingController(
            rootView: HistoryView(transcriptionService: transcriptionService)
        )

        let window = NSWindow(contentViewController: hostingController)
        window.title = "Transcription History"
        window.setContentSize(NSSize(width: 700, height: 500))
        window.styleMask = [.titled, .closable, .resizable, .miniaturizable]
        window.center()

        self.init(window: window)
    }
}
