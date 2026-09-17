import AppKit
import SwiftUI
import MonitorCore
import CoreGraphics

// Exercises only an isolated in-process test window. It never queries accounts,
// changes real preferences, posts events to other apps, or needs Accessibility permission.
@MainActor enum UIInteractionChecks {
    // AppKit and SwiftUI implement accessibility via informal Objective-C
    // selectors too; runtime protocol conformance alone misses their nodes.
    struct Control {
        let object: NSObject
        func accessibilityIdentifier() -> String? {
            let selector = NSSelectorFromString("accessibilityIdentifier")
            guard object.responds(to: selector) else { return nil }
            return object.perform(selector)?.takeUnretainedValue() as? String
        }
        func children() -> [Any] {
            let selector = NSSelectorFromString("accessibilityChildren")
            guard object.responds(to: selector) else { return [] }
            return object.perform(selector)?.takeUnretainedValue() as? [Any] ?? []
        }
        func accessibilityFrame() -> NSRect {
            guard object.responds(to: NSSelectorFromString("accessibilityFrame")) else { return .zero }
            return (object.value(forKey: "accessibilityFrame") as? NSValue)?.rectValue ?? .zero
        }
        func accessibilityPerformPress() -> Bool {
            let selector = NSSelectorFromString("accessibilityPerformPress")
            guard object.responds(to: selector), let implementation = object.method(for: selector) else { return false }
            typealias Action = @convention(c) (AnyObject, Selector) -> Bool
            return unsafeBitCast(implementation, to: Action.self)(object, selector)
        }
    }
    static func run(output: URL) throws {
        let name = AppRuntime.profile.bundleID + ".ui-check." + UUID().uuidString
        let defaults = UserDefaults(suiteName: name)!
        defer { defaults.removePersistentDomain(forName: name) }
        let store = MonitorStore(defaults: defaults, servicesEnabled: false)
        store.enabled = Set(ProviderInfo.defaultOrder)
        store.preferences.maxHeight = 620 // Match this isolated interaction window's actual viewport.
        let session = CGSessionCopyCurrentDictionary() as? [String:Any] ?? [:]
        if (session["CGSSessionScreenIsLocked"] as? NSNumber)?.boolValue == true {
            // A locked desktop exposes no native AX tree or key window. Verify
            // view-model transitions without claiming native click verification.
            var checks: [[String:Any]] = []
            func verify(_ name: String, _ good: Bool) throws {
                checks.append(["check":name,"passed":good])
                guard good else { throw NSError(domain:"MonitorState",code:1,userInfo:[NSLocalizedDescriptionKey:name]) }
            }
            let bars=store.iconSlots; let order=store.preferences.providerOrder
            store.toggleAPI()
            try verify("API mode opens",store.apiMode && !store.showSettings)
            try verify("seven unconfigured providers",store.api.accounts.count == 7 && store.api.accounts.allSatisfy{!$0.configured})
            try verify("API mode preserves menu quotas",store.iconSlots == bars)
            let id=store.api.accounts[0].id
            store.openAPISettings(id)
            try verify("account editor opens",store.showSettings && store.api.editingID == id)
            store.backFromSettings()
            try verify("back opens API account list",store.showSettings && store.api.editingID == nil)
            store.backFromSettings()
            try verify("back returns to API cards",store.apiMode && !store.showSettings)
            store.api.move(id,by:1)
            try verify("API sorting is independent",store.preferences.providerOrder == order && store.api.accounts[1].id == id)
            store.toggleAPI()
            try verify("Plan page restored",!store.apiMode && !store.showSettings && store.iconSlots == bars)
            try verify("isolated checks made no requests",!store.api.refreshing && !store.refreshing)
            let doc: [String:Any] = ["passed":false,"skipped":true,"count":0,"reason":"macOS desktop is locked; native click/AX verification unavailable", "stateChecksPassed":true,"stateCheckCount":checks.count,"stateChecks":checks]
            try JSONSerialization.data(withJSONObject:doc,options:[.prettyPrinted,.sortedKeys]).write(to:output.appendingPathComponent("ui-interaction-checks.json"),options:.atomic)
            print("Native click checks skipped: Mac is locked. Passed \(checks.count) isolated view-model transition checks; no external requests.")
            return
        }
        let controller = MonitorViewController(store: store)
        let window = NSWindow(contentRect: NSRect(x: 140, y: 100, width: 340, height: 620), styleMask: [.titled, .closable], backing: .buffered, defer: false)
        window.isReleasedWhenClosed = false; window.appearance = NSAppearance(named: .aqua)
        window.title = "Monitor · 界面自检"
        window.contentViewController = controller; window.setContentSize(NSSize(width: 340, height: 620))
        NSApp.activate(ignoringOtherApps: true); window.makeKeyAndOrderFront(nil)
        defer { window.orderOut(nil); window.contentViewController = nil; window.close() }
        let host = controller.view
        func settle() {
            host.layoutSubtreeIfNeeded(); window.displayIfNeeded(); host.displayIfNeeded()
            RunLoop.current.run(until: Date().addingTimeInterval(0.25))
            host.layoutSubtreeIfNeeded()
            _ = host.accessibilityHitTest(window.convertPoint(toScreen: NSPoint(x: 250, y: 590)))
        }
        func all(_ object: Any, depth: Int = 0) -> [Control] {
            guard depth < 25, let object = object as? NSObject else { return [] }
            let node = Control(object: object)
            return [node] + node.children().flatMap { all($0, depth: depth + 1) }
        }
        var checks: [[String: Any]] = []
        func record(_ title: String, _ passed: Bool) throws {
            checks.append(["check": title, "passed": passed])
            guard passed else { throw NSError(domain: "MonitorUI", code: 1, userInfo: [NSLocalizedDescriptionKey:title]) }
        }
        func target(_ id: String) throws -> Control {
            // Native accessibility trees may publish after the first layout pass.
            for _ in 0..<12 {
                settle()
                if let node = all(host).first(where: { $0.accessibilityIdentifier() == id }) { return node }
            }
            guard let node = all(host).first(where: { $0.accessibilityIdentifier() == id }) else {
                let ids = all(host).compactMap { $0.accessibilityIdentifier() }
                func views(_ v: NSView, depth: Int = 0) -> [[String:Any]] {
                    guard depth < 5 else { return [] }
                    return [["class":String(describing:type(of:v)),"frame":NSStringFromRect(v.frame),"axChildren":Control(object:v).children().count]] + v.subviews.flatMap { views($0,depth:depth+1) }
                }
                let detail: [String:Any] = ["ids":ids,"windowFrame":NSStringFromRect(window.frame),"visible":window.isVisible,"key":window.isKeyWindow,"appActive":NSApp.isActive,"hostTree":views(host),"windowNodes":all(window).compactMap{$0.accessibilityIdentifier()}]
                try JSONSerialization.data(withJSONObject: detail, options:[.prettyPrinted]).write(to: output.appendingPathComponent("ui-found-identifiers.json"))
                throw NSError(domain: "MonitorUI", code: 2, userInfo: [NSLocalizedDescriptionKey:"Missing control " + id])
            }
            return node
        }
        for id in BrandAssets.ids { try record("bundled official logo: " + id, BrandAssets.image(id) != nil) }
        for style in ["mono", "provider", "quota"] {
            let image = MenuBarIcon.make(slots: store.iconSlots, style: style, threshold: 25)
            try record("status icon always uses monochrome template: " + style, image.isTemplate)
        }
        try record("panel brand colors remain enabled", store.preferences.useBrandColors)
        for count in 0...ProviderInfo.all.count {
            store.enabled = Set(ProviderInfo.defaultOrder.prefix(count))
            try record("live selection maps to exactly \(count) bars", store.iconSlots.count == count)
        }
        store.enabled = Set(ProviderInfo.defaultOrder)
        settle()
        try record("hosting view accepts first mouse", host.acceptsFirstMouse(for: nil))
        try record("ten plan providers are registered", ProviderInfo.all.count == 10)
        try record("new provider connection hints are present", ProviderInfo.all.filter { ["cursor", "minimax", "windsurf", "kiro"].contains($0.id) }.allSatisfy { !$0.connectionHint.isEmpty })
        store.setMiniMaxRegion("global")
        try record("MiniMax region changes in an isolated model", store.minimaxRegion == "global")
        store.setMiniMaxRegion("cn")
        try record("MiniMax fixture does not start collection", !store.refreshing && !store.savingPlanCredential)
        let initialSlots = store.iconSlots
        let apiToggle = try target("toolbar.api")
        let refreshButton = try target("toolbar.refresh")
        let settingsButton = try target("toolbar.settings")
        try record("API toggle is between refresh and settings", refreshButton.accessibilityFrame().midX < apiToggle.accessibilityFrame().midX && apiToggle.accessibilityFrame().midX < settingsButton.accessibilityFrame().midX)
        try record("API toggle has 28pt hit area", apiToggle.accessibilityFrame().width >= 28 && apiToggle.accessibilityFrame().height >= 28)
        try record("API toggle press accepted", apiToggle.accessibilityPerformPress())
        settle(); try record("API view opens", store.apiMode)
        try record("API view has seven default providers", store.api.accounts.count == 7)
        try record("Unconfigured API providers do not have keys", store.api.accounts.allSatisfy { !$0.configured })
        try record("API mode preserves menu plan bars", store.iconSlots == initialSlots)
        let apiSettings = try target("toolbar.settings")
        try record("API settings press accepted", apiSettings.accessibilityPerformPress())
        settle(); try record("API account settings open", store.apiMode && store.showSettings)
        let first = try target("api.edit.deepseek")
        try record("API account editor press accepted", first.accessibilityPerformPress())
        settle(); try record("API key editor opens without a key query", store.api.editingID == store.api.accounts.first?.id && !store.api.refreshing)
        let backToPlan = try target("toolbar.api")
        try record("API switch returns to Plan", backToPlan.accessibilityPerformPress())
        settle(); try record("Plan mode restored without settings", !store.apiMode && !store.showSettings)
        let settings = try target("toolbar.settings")
        let frame = settings.accessibilityFrame()
        try record("toolbar target >=28pt", frame.width >= 28 && frame.height >= 28)
        try record("settings press accepted", settings.accessibilityPerformPress())
        settle(); try record("one press opens settings", store.showSettings)
        let initial = store.preferences.providerOrder
        let down = try target("order.down.kimi")
        try record("ordering arrow target >=28pt", down.accessibilityFrame().width >= 28 && down.accessibilityFrame().height >= 28)
        try record("ordering press accepted", down.accessibilityPerformPress())
        settle(); try record("arrow moves exactly one place", store.preferences.providerOrder.firstIndex(of: "kimi") == 1)
        try record("ordering did not toggle provider", store.enabled.contains("kimi"))
        let toggle = try target("order.enable.kimi")
        try record("enable target >=28pt", toggle.accessibilityFrame().width >= 28 && toggle.accessibilityFrame().height >= 28)
        try record("enable press accepted", toggle.accessibilityPerformPress())
        settle(); try record("enable toggles once without dragging", !store.enabled.contains("kimi"))
        try record("toggle does not reorder", store.preferences.providerOrder.firstIndex(of: "kimi") == 1)
        store.openSettings("display"); settle()
        let compact = try target("toggle.紧凑间距")
        try record("settings switch has a full row target", compact.accessibilityFrame().width >= 240 && compact.accessibilityFrame().height >= 32)
        let oldCompact = store.preferences.compact
        try record("full row press accepted", compact.accessibilityPerformPress())
        settle(); try record("full row toggles exactly once", store.preferences.compact != oldCompact)
        let fixed = store.panelHeight
        store.snapshot = Snapshot(generatedAt: Date().timeIntervalSince1970, providers: [])
        store.showSettings = false; settle()
        try record("refresh and navigation retain viewport height", store.panelHeight == fixed)
        var dismissed = false; store.dismissPanel = { dismissed = true }
        let close = try target("toolbar.close")
        try record("close button press accepted", close.accessibilityPerformPress())
        try record("close action invoked", dismissed)
        store.preferences.providerOrder = initial
        let doc: [String: Any] = ["passed":true, "count":checks.count, "checks":checks, "method":"In-process native accessibility actions and actual rendered hit bounds; isolated preferences, no external event injection"]
        try JSONSerialization.data(withJSONObject: doc, options: [.prettyPrinted, .sortedKeys]).write(to: output.appendingPathComponent("ui-interaction-checks.json"), options: .atomic)
        print("Passed \(checks.count) native UI interaction checks.")
    }
}
