import Foundation

/// Build identity shared by native UI, collectors and credential brokers.
public struct RuntimeProfile: Codable, Equatable {
    public let schema: Int
    public let channel: String
    public let bundleID: String
    public let displayName: String
    public let dataDirectoryName: String
    public let executableName: String
    public let version: String
    public let buildNumber: String
    public let defaultEnabledProviders: [String]
    public let badge: String
    public let experimentalModules: [String]
    public var keychainPrefix: String { bundleID + "." }
    public var keychainHelperID: String { bundleID + ".Keychain.v1" }
    public var apiHelperID: String { bundleID + ".APIVault.v1" }
    public var keychainAppName: String { displayName + " Keychain.app" }
    public var apiAppName: String { displayName + " API Vault.app" }
    public func supportURL(home: URL) -> URL {
        home.appendingPathComponent("Library/Application Support", isDirectory: true)
            .appendingPathComponent(dataDirectoryName, isDirectory: true)
    }
    public func validate(expectedChannel: String) throws {
        let validID = bundleID.range(of: "^[A-Za-z0-9]+(?:[.-][A-Za-z0-9]+)+$", options: .regularExpression) != nil
        let expectedID = expectedChannel == "public" ? "com.thalnova.aimonitor" : "com.thalnova.aimonitor.local"
        let expectedName = expectedChannel == "public" ? "Thalnova AI Monitor" : "Thalnova AI Monitor Local"
        guard schema == 1, ["public", "local"].contains(channel), channel == expectedChannel,
              validID, bundleID == expectedID, displayName == expectedName, dataDirectoryName == expectedName,
              !executableName.isEmpty, !executableName.contains("/"),
              Set(defaultEnabledProviders).isSubset(of: Set(ProviderInfo.defaultOrder)),
              channel != "public" || (experimentalModules.isEmpty && badge.isEmpty) else {
            throw NSError(domain: "RuntimeProfile", code: 1, userInfo: [NSLocalizedDescriptionKey: "Invalid or cross-edition runtime profile."])
        }
    }
}
