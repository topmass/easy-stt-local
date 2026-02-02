import SwiftUI

@main
struct RecordTranscribeApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    @StateObject private var transcriptionService = TranscriptionService()

    var body: some Scene {
        // Menu bar app - no main window
        MenuBarExtra {
            MenuBarView(transcriptionService: transcriptionService)
        } label: {
            Image(systemName: transcriptionService.isRecording ? "mic.fill" : "mic")
                .symbolRenderingMode(.hierarchical)
                .foregroundColor(transcriptionService.isRecording ? .red : .primary)
        }
        .menuBarExtraStyle(.window)

        // Settings window
        Settings {
            SettingsView(transcriptionService: transcriptionService)
        }
    }
}

class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        // Register global hotkey
        HotkeyManager.shared.registerHotkey()
    }

    func applicationWillTerminate(_ notification: Notification) {
        // Cleanup Python service
        TranscriptionService.shared?.stopService()
    }
}
