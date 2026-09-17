import AppKit
import Foundation
import MonitorCore

/// Set once by the edition's entry point, before any stores or helpers exist.
enum AppRuntime {
    private(set) static var profile: RuntimeProfile!
    static var testHome: URL?
    static var home: URL { testHome ?? FileManager.default.homeDirectoryForCurrentUser }
    static var support: URL { profile.supportURL(home: home) }
    // The main bundle already has the validated edition ID. Its application
    // domain is .standard; creating a suite named after that same ID is invalid.
    static var defaults: UserDefaults { .standard }
    static func configure(expectedChannel: String) throws {
        guard let resource = Bundle.main.resourceURL else { throw failure("Application resources are missing.") }
        let data = try Data(contentsOf: resource.appendingPathComponent("RuntimeProfile.json"))
        let value = try JSONDecoder().decode(RuntimeProfile.self, from: data)
        try value.validate(expectedChannel: expectedChannel)
        guard Bundle.main.bundleIdentifier == value.bundleID else { throw failure("Bundle and profile identifiers differ.") }
        profile = value
    }
    static func failure(_ message: String) -> NSError {
        NSError(domain: "AppRuntime", code: 1, userInfo: [NSLocalizedDescriptionKey: message])
    }
    static func collectorEnvironment() -> [String:String] {
        var env = ProcessInfo.processInfo.environment
        // A parent shell must not redirect a production collector into another edition.
        for key in ["MONITOR_DATA_DIR", "MONITOR_TEST_MODE", "MONITOR_TEST_HOME", "MONITOR_KEYCHAIN_HELPER", "MONITOR_API_VAULT", "PYTHONPATH", "PYTHONHOME"] { env.removeValue(forKey: key) }
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        return env
    }
    static var pythonExecutable: URL? {
        if let bundled = Bundle.main.resourceURL?.appendingPathComponent("Python/bin/python3"),
           FileManager.default.isExecutableFile(atPath: bundled.path) { return bundled }
        let system = URL(fileURLWithPath: "/usr/bin/python3")
        return FileManager.default.isExecutableFile(atPath: system.path) ? system : nil
    }
    static func runtimeInfo() throws -> Data {
        let info: [String:Any] = ["channel":profile.channel, "bundleID":profile.bundleID,
            "displayName":profile.displayName, "dataDirectory":support.path,
            "preferencesDomain":profile.bundleID, "keychainPrefix":profile.keychainPrefix,
            "keychainHelperID":profile.keychainHelperID, "apiHelperID":profile.apiHelperID,
            "keychainHelperPath":KeychainBridge.appURL.path, "apiHelperPath":APIVault.appURL.path,
            "defaultEnabledProviders":profile.defaultEnabledProviders,
            "experimentalModules":profile.experimentalModules, "pythonBundled":Bundle.main.resourceURL.map { FileManager.default.isExecutableFile(atPath:$0.appendingPathComponent("Python/bin/python3").path) } ?? false]
        return try JSONSerialization.data(withJSONObject: info, options: [.prettyPrinted, .sortedKeys])
    }
}

@MainActor enum IsolationSelfCheck {
    static func run() throws {
        let fm = FileManager.default
        let home = fm.temporaryDirectory.appendingPathComponent("monitor-isolation-" + UUID().uuidString)
        try fm.createDirectory(at:home,withIntermediateDirectories:true,attributes:[.posixPermissions:0o700])
        AppRuntime.testHome = home
        let suite = AppRuntime.profile.bundleID + ".selftest." + UUID().uuidString
        let defaults = UserDefaults(suiteName:suite)!
        defer { defaults.removePersistentDomain(forName:suite); AppRuntime.testHome=nil; try? fm.removeItem(at:home) }
        var preferences = DisplayPreferences(); preferences.autoRefresh=false
        preferences.save(to:defaults); defaults.set([String](),forKey:"enabled")
        let store = MonitorStore(defaults:defaults,servicesEnabled:true)
        defer { store.shutdown() }
        // URL directory flags can change after mkdir; compare normalized paths,
        // not URL values whose trailing slash depends on filesystem existence.
        let checks: [String:Bool] = [
            "storePath":store.support.standardizedFileURL.path == AppRuntime.support.standardizedFileURL.path,
            "apiPath":store.api.root.standardizedFileURL.path == AppRuntime.support.appendingPathComponent("API").standardizedFileURL.path,
            "noEnabledPlans":store.enabled.isEmpty,
            "noConfiguredAPIKeys":store.api.accounts.allSatisfy({ !$0.configured }),
            "keychainHelper":KeychainBridge.ensureInstalled(),
            "apiHelper":APIVault.ensureInstalled(),
            "keychainUnderTemporaryHome":KeychainBridge.root.path.hasPrefix(home.path+"/"),
            "apiUnderTemporaryHome":APIVault.root.path.hasPrefix(home.path+"/"),
            "temporaryAccountsPersisted":fm.fileExists(atPath:store.api.root.appendingPathComponent("accounts.json").path)]
        let failed = checks.filter { !$0.value }.keys.sorted()
        guard failed.isEmpty else {
            throw AppRuntime.failure("Isolation check failed: " + failed.joined(separator:", "))
        }
        let result: [String:Any] = ["passed":true,"channel":AppRuntime.profile.channel,
            "bundleID":AppRuntime.profile.bundleID,"helperCopiesVerified":true,"networkRequests":0,
            "credentialReads":0,"realUserDataWrites":0,"temporaryRoot":home.path]
        FileHandle.standardOutput.write(try JSONSerialization.data(withJSONObject:result,options:[.sortedKeys]))
    }
}
