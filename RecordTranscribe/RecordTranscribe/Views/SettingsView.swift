import SwiftUI

struct SettingsView: View {
    @ObservedObject var transcriptionService: TranscriptionService
    @AppStorage("cleanupEnabled") private var cleanupEnabled = true
    @AppStorage("autoCopyToClipboard") private var autoCopyToClipboard = true
    @AppStorage("playFeedbackSounds") private var playFeedbackSounds = true
    @AppStorage("hotkey") private var hotkey = "option"

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

            AboutView()
                .tabItem {
                    Label("About", systemImage: "info.circle")
                }
        }
        .frame(width: 450, height: 300)
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
                Text("Removes filler words and improves grammar using a local LLM")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }

            Section {
                Toggle("Auto-copy to clipboard", isOn: $autoCopyToClipboard)
                Toggle("Play feedback sounds", isOn: $playFeedbackSounds)
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

struct AboutView: View {
    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: "mic.badge.xmark")
                .font(.system(size: 64))
                .foregroundColor(.accentColor)

            Text("RecordTranscribe")
                .font(.title)
                .fontWeight(.bold)

            Text("Version 1.0.0")
                .font(.subheadline)
                .foregroundColor(.secondary)

            Text("Local voice transcription powered by Parakeet-MLX")
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
                    Label("Parakeet", systemImage: "waveform")
                }
                .font(.caption)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .padding()
    }
}

#Preview {
    SettingsView(transcriptionService: TranscriptionService())
}
