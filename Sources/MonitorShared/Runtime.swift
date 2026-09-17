import AppKit
import Security
import LocalAuthentication

// Only explicitly named account services; background reads never ask for UI.
enum Vault {
    static var prefix: String { AppRuntime.profile.keychainPrefix }
    static func read(_ service: String, interactive: Bool = false) -> (OSStatus, String?) {
        if interactive { return (KeychainBridge.grantClaude(), nil) }
        return KeychainBridge.read(service)
    }
    static func save(_ value: String, service: String) -> OSStatus { KeychainBridge.save(value, service: service) }
}

final class PipeCapture: @unchecked Sendable {
    private let group = DispatchGroup()
    private var data = Data()
    init() { group.enter() }
    func start(_ handle: FileHandle) {
        DispatchQueue.global(qos: .utility).async {
            var overflow = false
            while true {
                let chunk = handle.readData(ofLength: 16384)
                if chunk.isEmpty { break }
                if self.data.count + chunk.count <= 2 * 1024 * 1024 && !overflow { self.data.append(chunk) }
                else { overflow = true; self.data.removeAll() }
            }
            self.group.leave()
        }
    }
    func finish() -> Data { group.wait(); return data }
}
