import Foundation
import Security
import LocalAuthentication

// Edition-specific helper. The build pins its namespace and signs this component.
// Own entries are separate; official Claude Code credentials remain upstream-owned.
// Grant/status operations never return credential bytes.
let prefix = "__KEYCHAIN_PREFIX__"
let own = Set(["kimi", "glm-cn", "glm-global", "copilot", "minimax-cn", "minimax-global"])
let claudeService = "Claude Code-credentials"
let allowed = Set(own.map { prefix + $0 }).union([claudeService])

enum Outcome {
    case ok(Data), missing, locked, denied(OSStatus), failed(OSStatus)
    var status: OSStatus {
        switch self {
        case .ok: return errSecSuccess
        case .missing: return errSecItemNotFound
        case .locked: return errSecInteractionNotAllowed
        case .denied(let code), .failed(let code): return code
        }
    }
    var reason: String {
        switch self {
        case .ok: return "ok"
        case .missing: return "missing"
        case .locked: return "locked"
        case .denied: return "denied"
        case .failed: return "failed"
        }
    }
    // Exit protocol shared with collector/credentials.py and Sources/Monitor/KeychainBridge.swift.
    var exitCode: Int32 {
        switch self {
        case .ok: return 0
        case .missing: return 2
        case .denied: return 3
        case .failed: return 4
        case .locked: return 5
        }
    }
}

func loginKeychainUnlocked() -> Bool {
    var status = SecKeychainStatus()
    guard SecKeychainGetStatus(nil, &status) == errSecSuccess else { return false }
    return status & SecKeychainStatus(kSecUnlockStateStatus) != 0
}

// Runs /usr/bin/security with a private stdout pipe and a watchdog, so a stuck
// SecurityAgent dialog can never outlive this process. Returns (exit code, stdout).
func securityTool(_ arguments: [String], timeout: Double = 20) -> (Int32, Data) {
    let process = Process(), output = Pipe()
    process.executableURL = URL(fileURLWithPath: "/usr/bin/security")
    process.arguments = arguments
    process.standardInput = FileHandle.nullDevice
    process.standardOutput = output
    process.standardError = FileHandle.nullDevice
    let watchdog = DispatchWorkItem {
        guard process.isRunning else { return }
        process.terminate()
        DispatchQueue.global().asyncAfter(deadline: .now() + 0.5) {
            if process.isRunning { Darwin.kill(process.processIdentifier, SIGKILL) }
        }
    }
    DispatchQueue.global().asyncAfter(deadline: .now() + timeout, execute: watchdog)
    do { try process.run() } catch { return (-1, Data()) }
    let data = output.fileHandleForReading.readDataToEndOfFile()
    process.waitUntilExit()
    watchdog.cancel()
    if process.terminationReason != .exit { return (-1, Data()) }
    return (process.terminationStatus, data)
}

func readClaude(interactive: Bool) -> Outcome {
    // Background reads must never raise the keychain unlock dialog either.
    if !interactive && !loginKeychainUnlocked() { return .locked }
    var code: Int32 = 44, data = Data()
    // The official CLI stores the item under the POSIX user name; fall back to service only.
    for arguments in [["find-generic-password", "-s", claudeService, "-a", NSUserName(), "-w"],
                      ["find-generic-password", "-s", claudeService, "-w"]] {
        (code, data) = securityTool(arguments)
        if code != 44 { break }
    }
    // The tool exits with the low byte of the OSStatus it hit.
    switch code {
    case 0:
        while let last = data.last, last == 0x0A || last == 0x0D { data.removeLast() }
        return data.isEmpty ? .missing : .ok(data)
    case 44: return .missing
    case 36: return .denied(errSecInteractionNotAllowed)
    case 51: return .denied(errSecAuthFailed)
    case 128: return .denied(errSecUserCanceled)
    default: return .failed(errSecNotAvailable)
    }
}

func readOwn(_ service: String, interactive: Bool) -> Outcome {
    var query: [String: Any] = [kSecClass as String:kSecClassGenericPassword,
        kSecAttrService as String:service, kSecReturnData as String:true,
        kSecMatchLimit as String:kSecMatchLimitOne]
    if !interactive {
        let context = LAContext(); context.interactionNotAllowed = true
        query[kSecUseAuthenticationContext as String] = context
        // The legacy file-based keychain also needs its own no-UI switch.
        query[kSecUseAuthenticationUI as String] = kSecUseAuthenticationUIFail
    }
    var object: CFTypeRef?
    let status = SecItemCopyMatching(query as CFDictionary, &object)
    switch status {
    case errSecSuccess: return .ok(object as? Data ?? Data())
    case errSecItemNotFound: return .missing
    case errSecInteractionNotAllowed, errSecAuthFailed, errSecUserCanceled: return .denied(status)
    default: return .failed(status)
    }
}

func readItem(_ service: String, interactive: Bool) -> Outcome {
    guard allowed.contains(service) else { return .failed(errSecParam) }
    return service == claudeService ? readClaude(interactive:interactive) : readOwn(service, interactive:interactive)
}

func saveItem(_ service: String, data: Data) -> OSStatus {
    guard own.contains(service), data.count <= 65536 else { return errSecParam }
    let key: [String: Any] = [kSecClass as String:kSecClassGenericPassword,
        kSecAttrService as String:prefix+service, kSecAttrAccount as String:"personal"]
    if data.isEmpty { return SecItemDelete(key as CFDictionary) }
    let attrs: [String: Any] = [kSecValueData as String:data]
    let status = SecItemUpdate(key as CFDictionary, attrs as CFDictionary)
    return status == errSecItemNotFound ? SecItemAdd(key.merging(attrs) { _, b in b } as CFDictionary, nil) : status
}

func statusJSON(_ status: OSStatus, reason: String) {
    let value: [String: Any] = ["status":status, "authorized":status == errSecSuccess, "reason":reason, "protocolVersion":2]
    if let data = try? JSONSerialization.data(withJSONObject:value) { FileHandle.standardOutput.write(data) }
}
func finish(_ outcome: Outcome, report: Bool) -> Never {
    if report { statusJSON(outcome.status, reason:outcome.reason) }
    exit(outcome.exitCode)
}
func exitFor(_ status: OSStatus) -> Never {
    if status == errSecSuccess { exit(0) }
    if status == errSecItemNotFound { exit(2) }
    if status == errSecInteractionNotAllowed || status == errSecAuthFailed || status == errSecUserCanceled { exit(3) }
    exit(4)
}

let args = CommandLine.arguments
if args.count == 2 && args[1] == "--identity" { print("__HELPER_ID__|__KEYCHAIN_PREFIX__"); exit(0) }
if args.count == 2 && args[1] == "--version" { print("MonitorKeychainBridge/2"); exit(0) }
if args.count == 2 && args[1] == "--grant-claude" {
    finish(readItem(claudeService, interactive:true), report:true)
}
if args.count == 3 && args[1] == "--status" {
    finish(readItem(args[2], interactive:false), report:true)
}
if args.count == 3 && args[1] == "--keychain-read" {
    let outcome = readItem(args[2], interactive:false)
    if case .ok(let data) = outcome { FileHandle.standardOutput.write(data) }
    // Only the parent reads this private pipe. Never echo it in diagnostics.
    finish(outcome, report:false)
}
if args.count == 3 && args[1] == "--save-own" {
    let data = FileHandle.standardInput.readDataToEndOfFile()
    let status = saveItem(args[2], data:data); statusJSON(status, reason:status == errSecSuccess ? "ok" : "failed"); exitFor(status)
}
statusJSON(errSecParam, reason:"usage"); exit(64)
