import Foundation
import CryptoKit
import Security

// Stable broker, separate from the frequently rebuilt SwiftUI application.
// Installation copies an immutable signed bundle and verifies its pinned bytes.
enum APIVault {
    static var root: URL { AppRuntime.support.appendingPathComponent("APIAuth") }
    static var appURL: URL { root.appendingPathComponent(AppRuntime.profile.apiAppName) }
    static var executable: URL { appURL.appendingPathComponent("Contents/MacOS/MonitorAPIVault") }
    private static let installLock = NSLock()
    static func ensureInstalled() -> Bool {
        installLock.lock(); defer { installLock.unlock() }
        guard let source = Bundle.main.resourceURL?.appendingPathComponent("APIVault"),
              let manifest = try? Data(contentsOf: source.appendingPathComponent("identity.json")),
              let doc = try? JSONSerialization.jsonObject(with:manifest) as? [String:Any],
              let expected = doc["binarySHA256"] as? String,
              doc["bundleID"] as? String == AppRuntime.profile.apiHelperID,
              doc["channel"] as? String == AppRuntime.profile.channel else { return false }
        func matches(_ url: URL) -> Bool {
            guard let data = try? Data(contentsOf:url) else { return false }
            return SHA256.hash(data:data).map { String(format:"%02x",$0) }.joined() == expected
        }
        if matches(executable), let info = NSDictionary(contentsOf:appURL.appendingPathComponent("Contents/Info.plist")), info["CFBundleIdentifier"] as? String == AppRuntime.profile.apiHelperID { return true }
        let package = source.appendingPathComponent(AppRuntime.profile.apiAppName)
        guard matches(package.appendingPathComponent("Contents/MacOS/MonitorAPIVault")) else { return false }
        let fm = FileManager.default
        do {
            try fm.createDirectory(at:root, withIntermediateDirectories:true, attributes:[.posixPermissions:0o700])
            let staging = root.appendingPathComponent("staging-" + UUID().uuidString + ".app")
            try fm.copyItem(at:package,to:staging)
            defer { try? fm.removeItem(at:staging) }
            if fm.fileExists(atPath:appURL.path) {
                let info = NSDictionary(contentsOf:appURL.appendingPathComponent("Contents/Info.plist"))
                guard info?["CFBundleIdentifier"] as? String == AppRuntime.profile.apiHelperID else { return false }
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
    static func save(_ value: String, id: String) -> OSStatus {
        guard UUID(uuidString:id) != nil else { return errSecParam }
        let (_,data)=call(["--save",id],input:Data(value.utf8),timeout:120)
        guard let d=try? JSONSerialization.jsonObject(with:data) as? [String:Any], let code=d["status"] as? Int else { return errSecNotAvailable }
        return OSStatus(code)
    }
    static func remove(_ id: String) -> Bool { call(["--delete",id],timeout:60).0 == 0 }
    static func grant(_ id: String) -> Bool {
        guard call(["--grant",id],timeout:120).0 == 0 else { return false }
        return call(["--status",id]).0 == 0
    }
}
