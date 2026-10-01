import AppKit
import SwiftUI
import MonitorCore

// Renders our own SwiftUI views offscreen, without screen recording or account requests.
@MainActor enum PreviewSupport {
    static func render(args: [String]) throws {
        NSApp.finishLaunching()
        guard let index = args.firstIndex(of: "--render-preview"), args.indices.contains(index + 1) else {
            throw NSError(domain: "MonitorPreview", code: 1, userInfo: [NSLocalizedDescriptionKey:"Missing output directory"])
        }
        let output = URL(fileURLWithPath: args[index + 1], isDirectory: true)
        try FileManager.default.createDirectory(at: output, withIntermediateDirectories: true, attributes: [.posixPermissions:0o700])
        if args.contains("--check-ui-only") { try UIInteractionChecks.run(output:output); return }
        let suiteName = AppRuntime.profile.bundleID + ".preview." + UUID().uuidString
        let isolated = UserDefaults(suiteName: suiteName)!
        defer { isolated.removePersistentDomain(forName: suiteName) }
        var preferences = DisplayPreferences()
        let fixture = !args.contains("--snapshot")
        if fixture {
            preferences = DisplayPreferences()
            preferences.providerOrder = ["claude", "kimi", "codex", "glm", "copilot", "antigravity"]
            isolated.set(["claude", "kimi", "codex", "glm"], forKey: "enabled")
        } else {
            preferences = DisplayPreferences.load(from: AppRuntime.defaults)
            isolated.set(AppRuntime.defaults.stringArray(forKey: "enabled") ?? ProviderInfo.defaultOrder, forKey: "enabled")
        }
        if let pos = args.firstIndex(of: "--language"), args.indices.contains(pos + 1),
           AppLanguage(rawValue: args[pos + 1]) != nil { preferences.language = args[pos + 1] }
        preferences.save(to: isolated)
        let store = MonitorStore(defaults: isolated, servicesEnabled: false)
        if let pos = args.firstIndex(of: "--snapshot"), args.indices.contains(pos+1) {
            let data = try Data(contentsOf: URL(fileURLWithPath: args[pos+1]))
            guard data.count <= 2 * 1024 * 1024 else { throw NSError(domain: "MonitorPreview", code: 2) }
            store.snapshot = try JSONDecoder().decode(Snapshot.self, from: data)
            // Compare appearance using one frozen instant; a minute boundary must
            // not look like a dark/light theme regression in countdown text.
            store.previewNow = Date().timeIntervalSince1970
        } else {
            let now = Date().timeIntervalSince1970; store.previewNow = now; store.snapshot = fixtures(now: now)
        }
        let source = fixture ? "fixture" : "live"
        try png(MonitorPanel(store: store), output.appendingPathComponent("quota-\(source).png"))
        try png(MonitorPanel(store: store).environment(\.colorScheme, .dark), output.appendingPathComponent("quota-\(source)-dark-system.png"))
        if !fixture, store.provider("antigravity") != nil {
            let selection = store.enabled
            store.enabled = ["antigravity"]
            try png(MonitorPanel(store: store), output.appendingPathComponent("quota-antigravity-live.png"))
            store.enabled = selection
        }
        store.showSettings = true
        for tab in ["order", "display", "connections"] {
            store.settingsTab = tab
            try png(MonitorPanel(store: store), output.appendingPathComponent("settings-\(tab)-\(source).png"))
        }
        let icon = MenuBarIcon.make(slots: store.iconSlots, style: store.preferences.iconStyle, threshold: store.preferences.lowThreshold)
        try png(Image(nsImage: icon).padding(6).background(Color.white).environment(\.colorScheme, .light), output.appendingPathComponent("menu-icon-\(source).png"))
        if fixture {
            for count in 0...MenuBarGeometry.maxRows {
                let testSlots = ProviderInfo.defaultOrder.prefix(count).map { MenuBarSlot(providerID: $0, name: $0, percent: 100, state: "known", reason: "synthetic count test") }
                let testIcon = MenuBarIcon.make(slots: testSlots, style: "mono", threshold: 25)
                try png(Image(nsImage: testIcon).padding(6).background(Color.white).environment(\.colorScheme, .light), output.appendingPathComponent("menu-count-\(count).png"))
            }
        }
        let slots = try JSONEncoder().encode(store.iconSlots)
        try slots.write(to: output.appendingPathComponent("icon-mapping-\(source).json"), options: .atomic)
        if fixture {
            store.showSettings = false
            let stamp = store.now
            let savedSnapshot = store.snapshot; let savedEnabled = store.enabled
            store.enabled = ["cursor", "minimax", "windsurf", "kiro"]
            store.snapshot = expandedFixtures(now: stamp)
            try png(MonitorPanel(store:store), output.appendingPathComponent("expanded-plans-fixture.png"))
            try png(MiniMaxConnectionEditor(store:store).padding(16).frame(width:340).background(Color.white), output.appendingPathComponent("minimax-editor-fixture.png"))
            store.enabled = ["opencode", "cline"]
            store.snapshot = agentPlanFixtures(now: stamp)
            try png(MonitorPanel(store:store), output.appendingPathComponent("agent-plans-fixture.png"))
            store.snapshot=savedSnapshot; store.enabled=savedEnabled
            let demoSuite = AppRuntime.profile.bundleID + ".demo-render." + UUID().uuidString
            let demoDefaults = UserDefaults(suiteName: demoSuite)!
            defer { demoDefaults.removePersistentDomain(forName: demoSuite) }
            let demo = DemoSupport.makeStore(defaults: demoDefaults)
            try png(DemoRoot(store: demo), output.appendingPathComponent("interactive-demo-fixture.png"))
            demo.openSettings("connections")
            try png(DemoRoot(store: demo), output.appendingPathComponent("demo-connections-fixture.png"))
            demo.shutdown()
            try UIInteractionChecks.run(output: output)
        }
        print("Rendered \(source) native quota panel, dark-system panel, three settings tabs and dynamic-bar icon. No network requests.")
    }
    static func expandedFixtures(now: Double) -> Snapshot {
        Snapshot(generatedAt: now, providers: [
                ProviderResult(id:"cursor",name:"Cursor",plan:"pro",fetchedAt:now,windows:[
                    QuotaWindow(id:"cursor-monthly",label:"套餐 · 本月",remainingPercent:68,resetAt:now+12*86400,kind:"monthly")]),
                ProviderResult(id:"minimax",name:"MiniMax",plan:"Max",fetchedAt:now,windows:[
                    QuotaWindow(id:"minimax-0-5h",label:"general · 当前窗口",remainingPercent:42,resetAt:now+7200,durationMinutes:300),
                    QuotaWindow(id:"minimax-0-weekly",label:"general · 每周",remainingPercent:73,resetAt:now+4*86400,durationMinutes:10080)]),
                ProviderResult(id:"windsurf",name:"Windsurf",status:"stale",plan:"pro",fetchedAt:now-1800,windows:[
                    QuotaWindow(id:"windsurf-daily",label:"每日额度 · 缓存",remainingPercent:80,resetAt:now+8*3600,durationMinutes:1440),
                    QuotaWindow(id:"windsurf-weekly",label:"每周额度 · 缓存",remainingPercent:60,resetAt:now+3*86400,durationMinutes:10080)],note:"仅为模拟缓存，非实时读数。"),
                ProviderResult(id:"kiro",name:"Kiro",status:"partial",plan:"KIRO PRO",fetchedAt:now,windows:[
                    QuotaWindow(id:"kiro-monthly",label:"套餐 Credits · 本月（官方估计）",remainingPercent:37.5,unit:"credits",remaining:375,limit:1000,kind:"monthly")])])
    }
    static func agentPlanFixtures(now: Double) -> Snapshot {
        Snapshot(generatedAt: now, providers: [
            ProviderResult(id:"opencode",name:"OpenCode Go",fetchedAt:now,windows:[
                QuotaWindow(id:"opencode-5h",label:"当前 5 小时",remainingPercent:63,resetAt:now+3*3600,durationMinutes:300),
                QuotaWindow(id:"opencode-weekly",label:"每周",remainingPercent:71,resetAt:now+3*86400,durationMinutes:10080),
                QuotaWindow(id:"opencode-monthly",label:"每月 · 订阅周期",remainingPercent:84,resetAt:now+19*86400,kind:"monthly")]),
            ProviderResult(id:"cline",name:"ClinePass",fetchedAt:now,windows:[
                QuotaWindow(id:"cline-5h",label:"当前 5 小时",remainingPercent:88,resetAt:now+4*3600,durationMinutes:300),
                QuotaWindow(id:"cline-weekly",label:"每周",remainingPercent:56,resetAt:now+5*86400,durationMinutes:10080),
                QuotaWindow(id:"cline-monthly",label:"每月",remainingPercent:47,resetAt:now+12*86400,kind:"monthly")])])
    }
    private static func png<V: View>(_ view: V, _ url: URL) throws {
        // ImageRenderer omits AppKit-backed ScrollView/Picker content. Render the
        // actual hosting view instead, including native controls and scroll areas.
        let host = FirstClickHostingView(rootView: view)
        let size = host.fittingSize
        guard size.width > 0, size.height > 0 else { throw NSError(domain: "MonitorPreview", code: 3) }
        let window = NSWindow(contentRect: NSRect(origin: NSPoint(x: -12000, y: -12000), size: size), styleMask: .borderless, backing: .buffered, defer: false)
        window.isReleasedWhenClosed = false
        window.appearance = NSAppearance(named: .aqua); window.backgroundColor = .white
        window.contentView = host; window.setContentSize(size); host.setFrameSize(size)
        window.orderFront(nil)
        defer { window.orderOut(nil); window.contentView = nil; window.close() }
        host.layoutSubtreeIfNeeded(); window.displayIfNeeded()
        RunLoop.current.run(until: Date().addingTimeInterval(0.25))
        host.layoutSubtreeIfNeeded(); host.displayIfNeeded()
        guard let bitmap = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: Int(size.width * 2), pixelsHigh: Int(size.height * 2), bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0) else { throw NSError(domain: "MonitorPreview", code: 4) }
        bitmap.size = size
        host.cacheDisplay(in: host.bounds, to: bitmap)
        guard let data = bitmap.representation(using: .png, properties: [:]) else { throw NSError(domain: "MonitorPreview", code: 5) }
        try data.write(to: url, options: .atomic)
        try FileManager.default.setAttributes([.posixPermissions:0o600], ofItemAtPath: url.path)
    }
    static func fixtures(now: Double) -> Snapshot {
        // Deliberately synthetic. Only files named '*fixture*' use these numbers.
        Snapshot(generatedAt: now, providers: [
            ProviderResult(id:"claude", name:"Claude", plan:"pro", fetchedAt:now, windows:[
                QuotaWindow(id:"five_hour", label:"当前 5 小时", remainingPercent:100, resetAt:now+4*3600+38*60, durationMinutes:300),
                QuotaWindow(id:"seven_day", label:"每周", remainingPercent:25, resetAt:now+2*86400+20*3600, durationMinutes:10080),
                QuotaWindow(id:"extra_usage", label:"Extra Usage", remainingPercent:100, remaining:30, limit:30, kind:"extra", currency:"USD")]),
            ProviderResult(id:"kimi", name:"Kimi", fetchedAt:now, windows:[
                QuotaWindow(id:"short", label:"Session", remainingPercent:76, resetAt:now+2*3600+12*60, durationMinutes:300),
                QuotaWindow(id:"weekly", label:"Weekly", remainingPercent:64, resetAt:now+6*86400, durationMinutes:10080)]),
            ProviderResult(id:"codex", name:"Codex", plan:"pro", fetchedAt:now, windows:[
                QuotaWindow(id:"primary", label:"Session", remainingPercent:42, resetAt:now+3*3600, durationMinutes:300),
                QuotaWindow(id:"secondary", label:"Weekly", remainingPercent:81, resetAt:now+5*86400, durationMinutes:10080)]),
            ProviderResult(id:"glm", name:"GLM", fetchedAt:now, windows:[
                QuotaWindow(id:"short", label:"Session", remainingPercent:15, resetAt:now+3600, durationMinutes:300),
                QuotaWindow(id:"weekly", label:"Weekly", remainingPercent:52, resetAt:now+4*86400, durationMinutes:10080)])
        ])
    }
}
