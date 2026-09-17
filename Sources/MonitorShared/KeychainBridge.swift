import Foundation
import CryptoKit
import Security

// Stable broker, separate from the frequently rebuilt SwiftUI application.
// Installation copies an immutable signed bundle and verifies its pinned bytes.
// Reads the explicitly selected Claude Code item through /usr/bin/security.
// System authorization behavior can vary; this helper does not grant permissions.
// Helper exit codes: 0 ok, 2 missing, 3 denied, 4 unavailable, 5 login keychain locked.
enum KeychainBridge {
    static var root: URL { AppRuntime.support.appendingPathComponent("Auth") }
    static var appURL: URL { root.appendingPathComponent(AppRuntime.profile.keychainAppName) }
    static var executable: URL { appURL.appendingPathComponent("Contents/MacOS/MonitorKeychain") }
    private static let installLock = NSLock()
    static func ensureInstalled() -> Bool {
        installLock.lock(); defer { installLock.unlock() }
        guard let source = Bundle.main.resourceURL?.appendingPathComponent("AuthBridge"),
              let manifest = try? Data(contentsOf: source.appendingPathComponent("identity.json")),
              let doc = try? JSONSerialization.jsonObject(with:manifest) as? [String:Any],
              let expected = doc["binarySHA256"] as? String,
              doc["bundleID"] as? String == AppRuntime.profile.keychainHelperID,
              doc["channel"] as? String == AppRuntime.profile.channel else { return false }
        func matches(_ url: URL) -> Bool {
            guard let data = try? Data(contentsOf:url) else { return false }
            return SHA256.hash(data:data).map { String(format:"%02x",$0) }.joined() == expected
        }
        if matches(executable), let info = NSDictionary(contentsOf:appURL.appendingPathComponent("Contents/Info.plist")), info["CFBundleIdentifier"] as? String == AppRuntime.profile.keychainHelperID { return true }
        let package = source.appendingPathComponent(AppRuntime.profile.keychainAppName)
        guard matches(package.appendingPathComponent("Contents/MacOS/MonitorKeychain")) else { return false }
        let fm = FileManager.default
        do {
            try fm.createDirectory(at:root, withIntermediateDirectories:true, attributes:[.posixPermissions:0o700])
            let staging = root.appendingPathComponent("staging-" + UUID().uuidString + ".app")
            try fm.copyItem(at:package,to:staging)
            defer { try? fm.removeItem(at:staging) }
            if fm.fileExists(atPath:appURL.path) {
                let info = NSDictionary(contentsOf:appURL.appendingPathComponent("Contents/Info.plist"))
                guard info?["CFBundleIdentifier"] as? String == AppRuntime.profile.keychainHelperID else { return false }
                try fm.removeItem(at:appURL)
            }
            try fm.moveItem(at:staging,to:appURL)
            try manifest.write(to:root.appendingPathComponent("identity.json"),options:.atomic)
            try fm.setAttributes([.posixPermissions:0o600],ofItemAtPath:root.appendingPathComponent("identity.json").path)
            return matches(executable)
        } catch { return false }
    }
    static func call(_ args: [String], input: Data? = nil, timeout: Double = 25) -> (Int32, Data) {
        guard ensureInstalled() else { return (4,Data()) }
        let p=Process(), output=Pipe(), capture=PipeCapture()
        p.executableURL=executable; p.arguments=args; p.standardOutput=output; p.standardError=FileHandle.nullDevice
        let pipe = input == nil ? nil : Pipe()
        if let pipe { p.standardInput=pipe } else { p.standardInput=FileHandle.nullDevice }
        do {
            try p.run(); capture.start(output.fileHandleForReading)
            if let input, let pipe { pipe.fileHandleForWriting.write(input); try? pipe.fileHandleForWriting.close() }
            let deadline=Date().addingTimeInterval(timeout)
            while p.isRunning && Date() < deadline { Thread.sleep(forTimeInterval:0.025) }
            if p.isRunning {
                p.terminate(); Thread.sleep(forTimeInterval:0.15)
                if p.isRunning { Darwin.kill(p.processIdentifier,SIGKILL) }
                p.waitUntilExit(); _=capture.finish(); return (124,Data())
            }
            return (p.terminationStatus,capture.finish())
        } catch { return (4,Data()) }
    }
    static func grantClaude() -> OSStatus {
        let (code,data)=call(["--grant-claude"],timeout:180)
        guard code != 124 else { return errSecNotAvailable }
        guard let doc=try? JSONSerialization.jsonObject(with:data) as? [String:Any], let status=doc["status"] as? Int else { return errSecNotAvailable }
        if status != 0 { return OSStatus(status) }
        // A second process repeats the exact non-interactive background read path.
        let (verified,_) = call(["--status","Claude Code-credentials"])
        switch verified {
        case 0: return errSecSuccess
        case 3: return errSecAuthFailed
        case 5: return errSecInteractionNotAllowed
        default: return errSecNotAvailable
        }
    }
    static func read(_ service:String) -> (OSStatus,String?) {
        let (code,data)=call(["--keychain-read",service])
        switch code {
        case 0:return (errSecSuccess,String(data:data,encoding:.utf8))
        case 2:return (errSecItemNotFound,nil)
        case 3:return (errSecInteractionNotAllowed,nil)
        case 5:return (errSecNotAvailable,nil)
        default:return (errSecNotAvailable,nil)
        }
    }
    static func save(_ value:String, service:String) -> OSStatus {
        let (_,data)=call(["--save-own",service],input:Data(value.utf8),timeout:180)
        guard let doc=try? JSONSerialization.jsonObject(with:data) as? [String:Any],let code=doc["status"] as? Int else { return errSecNotAvailable }
        return OSStatus(code)
    }
}
