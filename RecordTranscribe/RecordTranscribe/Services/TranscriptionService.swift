import Foundation
import AVFoundation
import AppKit
import Combine
import SwiftUI

enum ServiceStatus {
    case idle
    case recording
    case transcribing
    case error
    case loading
}

/// Manages the Python transcription service and audio recording
class TranscriptionService: ObservableObject {
    static var shared: TranscriptionService?

    @Published var status: ServiceStatus = .loading
    @Published var isRecording = false
    @Published var lastTranscription: String?
    @Published var errorMessage: String?
    @Published var transcriptionHistory: [TranscriptionEntry] = []

    // Settings
    @AppStorage("cleanupEnabled") private var cleanupEnabled = true

    private var pythonProcess: Process?
    private var inputPipe: Pipe?
    private var outputPipe: Pipe?
    private var audioRecorder: AudioRecorder?
    private var outputBuffer = ""

    init() {
        TranscriptionService.shared = self
        startService()
    }

    // MARK: - Python Service Management

    func startService() {
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            self?.launchPythonService()
        }
    }

    func stopService() {
        pythonProcess?.terminate()
        pythonProcess = nil
    }

    private func launchPythonService() {
        let bundle = Bundle.main
        var pythonPath: String = ""
        var scriptPath: String = ""

        // Check if running from bundled app (has python-env in Resources)
        if let bundledPython = bundle.path(forResource: "python-env/bin/python3", ofType: nil, inDirectory: "Resources"),
           let bundledScript = bundle.path(forResource: "transcription_service", ofType: "py", inDirectory: "Resources/PythonService") {
            pythonPath = bundledPython
            scriptPath = bundledScript
        } else {
            // Development mode - try known paths
            let devPaths: [(python: String, script: String)] = [
                // Primary: easy-stt-local venv + swiftui project script
                (
                    "/Users/benjaminczegeny/src/github.com/easy-stt-local/.venv/bin/python3",
                    "/Users/benjaminczegeny/src/github.com/record-transcribe-swiftui/RecordTranscribe/PythonService/transcription_service.py"
                ),
                // Alternative: swiftui project's own venv
                (
                    "/Users/benjaminczegeny/src/github.com/record-transcribe-swiftui/.venv/bin/python3",
                    "/Users/benjaminczegeny/src/github.com/record-transcribe-swiftui/RecordTranscribe/PythonService/transcription_service.py"
                )
            ]

            for paths in devPaths {
                if FileManager.default.fileExists(atPath: paths.python) &&
                   FileManager.default.fileExists(atPath: paths.script) {
                    pythonPath = paths.python
                    scriptPath = paths.script
                    break
                }
            }
        }

        launchWithPython(pythonPath, script: scriptPath)
    }

    private func launchWithPython(_ pythonPath: String, script scriptPath: String) {
        guard !pythonPath.isEmpty, FileManager.default.fileExists(atPath: pythonPath) else {
            DispatchQueue.main.async {
                self.status = .error
                self.errorMessage = "Python not found. Run: cd Scripts && ./bundle_python.sh"
            }
            return
        }

        guard !scriptPath.isEmpty, FileManager.default.fileExists(atPath: scriptPath) else {
            DispatchQueue.main.async {
                self.status = .error
                self.errorMessage = "Service script not found at: \(scriptPath)"
            }
            return
        }

        let process = Process()
        process.executableURL = URL(fileURLWithPath: pythonPath)
        process.arguments = ["-u", scriptPath]  // -u for unbuffered output

        // Set up environment
        var env = ProcessInfo.processInfo.environment
        env["PYTHONUNBUFFERED"] = "1"
        process.environment = env

        // Set up pipes for communication
        inputPipe = Pipe()
        outputPipe = Pipe()
        process.standardInput = inputPipe
        process.standardOutput = outputPipe
        process.standardError = FileHandle.nullDevice

        // Handle output
        outputPipe?.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            if !data.isEmpty, let output = String(data: data, encoding: .utf8) {
                self?.handlePythonOutput(output)
            }
        }

        // Handle termination
        process.terminationHandler = { [weak self] _ in
            DispatchQueue.main.async {
                self?.status = .error
                self?.errorMessage = "Transcription service stopped unexpectedly"
            }
        }

        do {
            try process.run()
            pythonProcess = process
        } catch {
            DispatchQueue.main.async {
                self.status = .error
                self.errorMessage = "Failed to start service: \(error.localizedDescription)"
            }
        }
    }

    private func handlePythonOutput(_ output: String) {
        outputBuffer += output

        // Process complete JSON lines
        while let newlineIndex = outputBuffer.firstIndex(of: "\n") {
            let line = String(outputBuffer[..<newlineIndex])
            outputBuffer = String(outputBuffer[outputBuffer.index(after: newlineIndex)...])

            if let data = line.data(using: .utf8),
               let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
                handleMessage(json)
            }
        }
    }

    private func handleMessage(_ message: [String: Any]) {
        guard let type = message["type"] as? String else { return }

        DispatchQueue.main.async { [weak self] in
            guard let self = self else { return }

            switch type {
            case "ready":
                self.status = .idle
                self.errorMessage = nil

            case "transcription":
                if let text = message["text"] as? String {
                    self.lastTranscription = text
                    self.addToHistory(text: text, cleanup: message["cleanup_used"] as? Bool ?? false)

                    // Auto-copy to clipboard
                    NSPasteboard.general.clearContents()
                    NSPasteboard.general.setString(text, forType: .string)

                    // Play completion sound
                    SoundManager.shared.playStopSound()
                }
                self.status = .idle

            case "status":
                if let statusStr = message["status"] as? String {
                    switch statusStr {
                    case "transcribing":
                        self.status = .transcribing
                    case "ready":
                        self.status = .idle
                    default:
                        break
                    }
                }

            case "error":
                self.status = .error
                self.errorMessage = message["message"] as? String

            default:
                break
            }
        }
    }

    private func sendCommand(_ command: [String: Any]) {
        guard let inputPipe = inputPipe,
              let data = try? JSONSerialization.data(withJSONObject: command),
              let jsonString = String(data: data, encoding: .utf8) else {
            return
        }

        let message = jsonString + "\n"
        inputPipe.fileHandleForWriting.write(message.data(using: .utf8)!)
    }

    // MARK: - Recording

    func toggleRecording() {
        if isRecording {
            stopRecording()
        } else {
            startRecording()
        }
    }

    func startRecording() {
        guard status == .idle else { return }

        // Play start sound
        SoundManager.shared.playStartSound()

        isRecording = true
        status = .recording

        // Initialize audio recorder if needed
        if audioRecorder == nil {
            audioRecorder = AudioRecorder()
        }

        audioRecorder?.startRecording { [weak self] audioData in
            // Called when recording stops
            self?.processRecording(audioData)
        }

        // Notify Python service
        sendCommand(["command": "start_streaming"])
    }

    func stopRecording() {
        guard isRecording else { return }

        isRecording = false
        status = .transcribing

        audioRecorder?.stopRecording()
    }

    private func processRecording(_ audioData: Data) {
        // Send audio to Python service for transcription
        let base64Audio = audioData.base64EncodedString()
        sendCommand([
            "command": "transcribe",
            "audio": base64Audio,
            "sample_rate": 16000,
            "cleanup": cleanupEnabled
        ])
    }

    // MARK: - History

    private func addToHistory(text: String, cleanup: Bool) {
        let entry = TranscriptionEntry(
            id: UUID(),
            text: text,
            timestamp: Date(),
            cleanupUsed: cleanup
        )
        transcriptionHistory.insert(entry, at: 0)

        // Keep only last 50 entries
        if transcriptionHistory.count > 50 {
            transcriptionHistory = Array(transcriptionHistory.prefix(50))
        }
    }

    func showHistoryWindow() {
        // TODO: Open history window
    }
}

struct TranscriptionEntry: Identifiable {
    let id: UUID
    let text: String
    let timestamp: Date
    let cleanupUsed: Bool
}
