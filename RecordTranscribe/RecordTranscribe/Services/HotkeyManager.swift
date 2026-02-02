import Foundation
import Carbon
import Cocoa

/// Manages global hotkey registration for recording activation
class HotkeyManager {
    static let shared = HotkeyManager()

    private var lastOptionPressTime: Date?
    private var eventMonitor: Any?
    private let doubleTapThreshold: TimeInterval = 0.3

    private init() {}

    func registerHotkey() {
        // Monitor for Option key events globally
        eventMonitor = NSEvent.addGlobalMonitorForEvents(matching: [.flagsChanged]) { [weak self] event in
            self?.handleFlagsChanged(event)
        }

        // Also monitor local events (when app is focused)
        NSEvent.addLocalMonitorForEvents(matching: [.flagsChanged]) { [weak self] event in
            self?.handleFlagsChanged(event)
            return event
        }
    }

    func unregisterHotkey() {
        if let monitor = eventMonitor {
            NSEvent.removeMonitor(monitor)
            eventMonitor = nil
        }
    }

    private func handleFlagsChanged(_ event: NSEvent) {
        // Check for Option key
        let optionPressed = event.modifierFlags.contains(.option)

        guard optionPressed else {
            return  // Only care about Option key down
        }

        let now = Date()

        if let lastPress = lastOptionPressTime {
            let timeSinceLastPress = now.timeIntervalSince(lastPress)

            if timeSinceLastPress < doubleTapThreshold {
                // Double-tap detected!
                handleDoubleTap()
                lastOptionPressTime = nil
                return
            }
        }

        lastOptionPressTime = now

        // Schedule check for single tap (to stop recording)
        DispatchQueue.main.asyncAfter(deadline: .now() + doubleTapThreshold) { [weak self] in
            guard let self = self,
                  let lastPress = self.lastOptionPressTime,
                  Date().timeIntervalSince(lastPress) >= self.doubleTapThreshold else {
                return
            }

            // Single tap - stop recording if active
            self.handleSingleTap()
            self.lastOptionPressTime = nil
        }
    }

    private func handleDoubleTap() {
        // Start recording
        DispatchQueue.main.async {
            guard let service = TranscriptionService.shared,
                  !service.isRecording else { return }
            service.startRecording()
        }
    }

    private func handleSingleTap() {
        // Stop recording
        DispatchQueue.main.async {
            guard let service = TranscriptionService.shared,
                  service.isRecording else { return }
            service.stopRecording()
        }
    }
}
