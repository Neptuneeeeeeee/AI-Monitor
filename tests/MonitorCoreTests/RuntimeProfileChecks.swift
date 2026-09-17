import Foundation
import MonitorCore
extension MonitorCoreTests {
    func runtimeFixture(channel: String = "public", overrides: [String:Any] = [:]) throws -> RuntimeProfile {
        let local = channel == "local"
        var doc: [String:Any] = ["schema":1,"channel":channel,"bundleID":"com.thalnova.aimonitor" + (local ? ".local" : ""),
            "displayName":"Thalnova AI Monitor" + (local ? " Local" : ""),"dataDirectoryName":"Thalnova AI Monitor" + (local ? " Local" : ""),
            "executableName":"ThalnovaAIMonitor" + (local ? "Local" : ""),"version":"1.8.0","buildNumber":"10",
            "defaultEnabledProviders":[String](),"badge":local ? "LOCAL" : "","experimentalModules":local ? ["LocalExperiments"] : [String]()]
        doc.merge(overrides) { _, new in new }
        return try JSONDecoder().decode(RuntimeProfile.self,from:JSONSerialization.data(withJSONObject:doc))
    }
    func testRuntimePublicIdentity() throws {
        let value = try runtimeFixture();try value.validate(expectedChannel:"public")
        checkEqual(value.keychainPrefix,"com.thalnova.aimonitor.");checkTrue(value.defaultEnabledProviders.isEmpty)
    }
    func testRuntimeLocalIdentitySeparate() throws {
        let a = try runtimeFixture(), b = try runtimeFixture(channel:"local");try b.validate(expectedChannel:"local")
        checkTrue(a.bundleID != b.bundleID);checkTrue(a.keychainHelperID != b.keychainHelperID);checkTrue(a.apiHelperID != b.apiHelperID)
        checkTrue(a.supportURL(home:URL(fileURLWithPath:"/synthetic")) != b.supportURL(home:URL(fileURLWithPath:"/synthetic")))
    }
    func testRuntimeCrossChannelRejected() throws {
        do { try runtimeFixture(channel:"local").validate(expectedChannel:"public");checkTrue(false) } catch { checkTrue(true) }
    }
    func testRuntimePathTraversalRejected() throws {
        do { try runtimeFixture(overrides:["dataDirectoryName":"../Monitor"]).validate(expectedChannel:"public");checkTrue(false) } catch { checkTrue(true) }
    }
    func testRuntimePublicPrivateModuleRejected() throws {
        do { try runtimeFixture(overrides:["experimentalModules":["LocalExperiments"]]).validate(expectedChannel:"public");checkTrue(false) } catch { checkTrue(true) }
    }
    func testRuntimeLegacyIdentityRejected() throws {
        do { try runtimeFixture(overrides:["bundleID":"local.thalnova.Monitor"]).validate(expectedChannel:"public");checkTrue(false) } catch { checkTrue(true) }
    }
}
