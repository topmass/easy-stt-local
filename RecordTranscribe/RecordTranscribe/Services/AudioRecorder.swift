import Foundation
import AVFoundation

/// Records audio from the microphone and provides raw PCM data
class AudioRecorder {
    private var audioEngine: AVAudioEngine?
    private var audioData: [Float] = []
    private var completionHandler: ((Data) -> Void)?
    private let sampleRate: Double = 16000

    func startRecording(completion: @escaping (Data) -> Void) {
        completionHandler = completion
        audioData = []

        // Request microphone permission
        AVCaptureDevice.requestAccess(for: .audio) { [weak self] granted in
            if granted {
                self?.setupAndStartRecording()
            } else {
                print("Microphone access denied")
            }
        }
    }

    private func setupAndStartRecording() {
        audioEngine = AVAudioEngine()
        guard let audioEngine = audioEngine else { return }

        let inputNode = audioEngine.inputNode
        let inputFormat = inputNode.outputFormat(forBus: 0)

        // Create format for 16kHz mono
        guard let outputFormat = AVAudioFormat(
            commonFormat: .pcmFormatFloat32,
            sampleRate: sampleRate,
            channels: 1,
            interleaved: false
        ) else {
            print("Failed to create output format")
            return
        }

        // Create converter if needed
        let converter = AVAudioConverter(from: inputFormat, to: outputFormat)

        inputNode.installTap(onBus: 0, bufferSize: 1024, format: inputFormat) { [weak self] buffer, _ in
            guard let self = self else { return }

            if let converter = converter {
                // Convert to 16kHz mono
                let frameCount = AVAudioFrameCount(Double(buffer.frameLength) * self.sampleRate / inputFormat.sampleRate)
                guard let convertedBuffer = AVAudioPCMBuffer(pcmFormat: outputFormat, frameCapacity: frameCount) else {
                    return
                }

                var error: NSError?
                let inputBlock: AVAudioConverterInputBlock = { _, outStatus in
                    outStatus.pointee = .haveData
                    return buffer
                }

                converter.convert(to: convertedBuffer, error: &error, withInputFrom: inputBlock)

                if let channelData = convertedBuffer.floatChannelData?[0] {
                    let samples = Array(UnsafeBufferPointer(start: channelData, count: Int(convertedBuffer.frameLength)))
                    self.audioData.append(contentsOf: samples)
                }
            } else {
                // No conversion needed
                if let channelData = buffer.floatChannelData?[0] {
                    let samples = Array(UnsafeBufferPointer(start: channelData, count: Int(buffer.frameLength)))
                    self.audioData.append(contentsOf: samples)
                }
            }
        }

        do {
            try audioEngine.start()
        } catch {
            print("Failed to start audio engine: \(error)")
        }
    }

    func stopRecording() {
        audioEngine?.stop()
        audioEngine?.inputNode.removeTap(onBus: 0)
        audioEngine = nil

        // Convert float array to Data (16-bit PCM for compatibility)
        let pcmData = convertToInt16PCM(audioData)
        completionHandler?(pcmData)
    }

    private func convertToInt16PCM(_ floatSamples: [Float]) -> Data {
        var data = Data(capacity: floatSamples.count * 2)

        for sample in floatSamples {
            // Clamp and convert to 16-bit
            let clamped = max(-1.0, min(1.0, sample))
            var int16Sample = Int16(clamped * Float(Int16.max))
            data.append(contentsOf: withUnsafeBytes(of: &int16Sample) { Array($0) })
        }

        return data
    }
}
