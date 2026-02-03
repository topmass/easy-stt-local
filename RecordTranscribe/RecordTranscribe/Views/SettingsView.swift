import SwiftUI

struct SettingsView: View {
    @ObservedObject var transcriptionService: TranscriptionService
    @AppStorage("cleanupEnabled") private var cleanupEnabled = true
    @AppStorage("autoCopyToClipboard") private var autoCopyToClipboard = true
    @AppStorage("playFeedbackSounds") private var playFeedbackSounds = true
    @AppStorage("hotkey") private var hotkey = "option"
    @AppStorage("cleanupPrompt") private var cleanupPrompt = """
        You are a transcription cleanup assistant. Clean up the following transcription by:
        - Removing filler words (um, uh, like, you know)
        - Fixing grammar and punctuation
        - Preserving the original meaning and tone
        - Keeping it concise

        Only output the cleaned text, nothing else.
        """

    var body: some View {
        TabView {
            GeneralSettingsView(
                cleanupEnabled: $cleanupEnabled,
                autoCopyToClipboard: $autoCopyToClipboard,
                playFeedbackSounds: $playFeedbackSounds
            )
            .tabItem {
                Label("General", systemImage: "gear")
            }

            HotkeySettingsView(hotkey: $hotkey)
                .tabItem {
                    Label("Hotkey", systemImage: "keyboard")
                }

            CleanupPromptView(cleanupPrompt: $cleanupPrompt)
                .tabItem {
                    Label("Cleanup Prompt", systemImage: "text.bubble")
                }

            ModelsView()
                .tabItem {
                    Label("Models", systemImage: "cpu")
                }

            AboutView()
                .tabItem {
                    Label("About", systemImage: "info.circle")
                }
        }
        .frame(width: 500, height: 380)
    }
}

struct GeneralSettingsView: View {
    @Binding var cleanupEnabled: Bool
    @Binding var autoCopyToClipboard: Bool
    @Binding var playFeedbackSounds: Bool

    var body: some View {
        Form {
            Section {
                Toggle("Enable LLM cleanup", isOn: $cleanupEnabled)
                    .toggleStyle(.switch)
                    .tint(.blue)
                Text("Removes filler words and improves grammar using a local LLM")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }

            Section {
                Toggle("Auto-copy to clipboard", isOn: $autoCopyToClipboard)
                    .toggleStyle(.switch)
                    .tint(.blue)
                Toggle("Play feedback sounds", isOn: $playFeedbackSounds)
                    .toggleStyle(.switch)
                    .tint(.blue)
            }
        }
        .formStyle(.grouped)
        .padding()
    }
}

struct HotkeySettingsView: View {
    @Binding var hotkey: String

    let hotkeyOptions = [
        ("option", "Option (⌥)"),
        ("command", "Command (⌘)"),
        ("control", "Control (⌃)"),
        ("shift", "Shift (⇧)"),
        ("f9", "F9"),
        ("f10", "F10"),
        ("f11", "F11"),
        ("f12", "F12")
    ]

    var body: some View {
        Form {
            Section {
                Picker("Activation hotkey", selection: $hotkey) {
                    ForEach(hotkeyOptions, id: \.0) { option in
                        Text(option.1).tag(option.0)
                    }
                }
                .pickerStyle(.radioGroup)

                Text("Double-tap to start recording, single tap to stop")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
        }
        .formStyle(.grouped)
        .padding()
    }
}

struct CleanupPromptView: View {
    @Binding var cleanupPrompt: String
    @State private var isEditing = false

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Cleanup Prompt")
                    .font(.headline)
                Spacer()
                Button("Reset to Default") {
                    cleanupPrompt = """
                        You are a transcription cleanup assistant. Clean up the following transcription by:
                        - Removing filler words (um, uh, like, you know)
                        - Fixing grammar and punctuation
                        - Preserving the original meaning and tone
                        - Keeping it concise

                        Only output the cleaned text, nothing else.
                        """
                }
                .buttonStyle(.bordered)
                .controlSize(.small)
            }

            Text("This prompt is sent to the cleanup LLM along with your transcription.")
                .font(.caption)
                .foregroundColor(.secondary)

            TextEditor(text: $cleanupPrompt)
                .font(.system(.body, design: .monospaced))
                .frame(minHeight: 200)
                .border(Color.secondary.opacity(0.3), width: 1)
        }
        .padding()
    }
}

struct ModelsView: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Models")
                .font(.headline)

            GroupBox {
                VStack(alignment: .leading, spacing: 8) {
                    HStack {
                        Image(systemName: "waveform")
                            .foregroundColor(.blue)
                            .frame(width: 24)
                        Text("Speech-to-Text")
                            .fontWeight(.medium)
                    }

                    VStack(alignment: .leading, spacing: 4) {
                        ModelInfoRow(label: "Model", value: "Parakeet TDT 0.6B v3")
                        ModelInfoRow(label: "Source", value: "mlx-community/parakeet-tdt-0.6b-v3")
                        ModelInfoRow(label: "Framework", value: "MLX (Apple Silicon optimized)")
                        ModelInfoRow(label: "Size", value: "~600 MB")
                        ModelInfoRow(label: "Features", value: "Streaming transcription")
                    }
                    .padding(.leading, 32)
                }
            }

            GroupBox {
                VStack(alignment: .leading, spacing: 8) {
                    HStack {
                        Image(systemName: "sparkles")
                            .foregroundColor(.purple)
                            .frame(width: 24)
                        Text("Cleanup LLM")
                            .fontWeight(.medium)
                    }

                    VStack(alignment: .leading, spacing: 4) {
                        ModelInfoRow(label: "Model", value: "Qwen 2.5 1.5B Instruct")
                        ModelInfoRow(label: "Source", value: "mlx-community/Qwen2.5-1.5B-Instruct-4bit")
                        ModelInfoRow(label: "Framework", value: "MLX-LM")
                        ModelInfoRow(label: "Size", value: "~1.5 GB (4-bit quantized)")
                        ModelInfoRow(label: "Purpose", value: "Grammar & filler word cleanup")
                    }
                    .padding(.leading, 32)
                }
            }

            Spacer()

            Text("Models are downloaded automatically on first use and cached locally.")
                .font(.caption)
                .foregroundColor(.secondary)
        }
        .padding()
    }
}

struct ModelInfoRow: View {
    let label: String
    let value: String

    var body: some View {
        HStack(alignment: .top) {
            Text(label + ":")
                .foregroundColor(.secondary)
                .frame(width: 80, alignment: .leading)
            Text(value)
                .textSelection(.enabled)
        }
        .font(.caption)
    }
}

struct AboutView: View {
    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: "mic.fill")
                .font(.system(size: 64))
                .foregroundColor(.blue)

            Text("RecordTranscribe")
                .font(.title)
                .fontWeight(.bold)

            Text("Version 1.0.0")
                .font(.subheadline)
                .foregroundColor(.secondary)

            Text("Local voice transcription powered by Apple MLX")
                .font(.caption)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)

            Divider()
                .padding(.horizontal, 40)

            VStack(spacing: 4) {
                Text("Built with")
                    .font(.caption)
                    .foregroundColor(.secondary)

                HStack(spacing: 16) {
                    Label("SwiftUI", systemImage: "swift")
                    Label("MLX", systemImage: "cpu")
                    Label("Python", systemImage: "chevron.left.forwardslash.chevron.right")
                }
                .font(.caption)
            }

            Spacer()
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .padding()
    }
}

#Preview {
    SettingsView(transcriptionService: TranscriptionService())
}
