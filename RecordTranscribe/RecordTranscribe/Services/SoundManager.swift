import Foundation
import AVFoundation

/// Manages audio feedback sounds for recording start/stop
class SoundManager {
    static let shared = SoundManager()

    private var startPlayer: AVAudioPlayer?
    private var stopPlayer: AVAudioPlayer?

    private init() {
        loadSounds()
    }

    private func loadSounds() {
        // Try bundled resources first, then development paths
        if let startURL = Bundle.main.url(forResource: "start", withExtension: "mp3") {
            startPlayer = try? AVAudioPlayer(contentsOf: startURL)
            startPlayer?.prepareToPlay()
        } else {
            // Development fallback
            let devPath = "/Users/benjaminczegeny/src/github.com/record-transcribe-swiftui/RecordTranscribe/RecordTranscribe/Resources/start.mp3"
            if FileManager.default.fileExists(atPath: devPath) {
                startPlayer = try? AVAudioPlayer(contentsOf: URL(fileURLWithPath: devPath))
                startPlayer?.prepareToPlay()
            }
        }

        if let stopURL = Bundle.main.url(forResource: "stop", withExtension: "mp3") {
            stopPlayer = try? AVAudioPlayer(contentsOf: stopURL)
            stopPlayer?.prepareToPlay()
        } else {
            // Development fallback
            let devPath = "/Users/benjaminczegeny/src/github.com/record-transcribe-swiftui/RecordTranscribe/RecordTranscribe/Resources/stop.mp3"
            if FileManager.default.fileExists(atPath: devPath) {
                stopPlayer = try? AVAudioPlayer(contentsOf: URL(fileURLWithPath: devPath))
                stopPlayer?.prepareToPlay()
            }
        }
    }

    func playStartSound() {
        startPlayer?.currentTime = 0
        startPlayer?.play()
    }

    func playStopSound() {
        stopPlayer?.currentTime = 0
        stopPlayer?.play()
    }
}
