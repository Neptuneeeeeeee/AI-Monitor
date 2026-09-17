import AppKit
import SwiftUI
import MonitorCore

/// Uses the real production views with synthetic data and disconnected services.
/// It never constructs the normal application delegate or accesses account stores.
@MainActor enum DemoSupport {
    static func makeStore(defaults: UserDefaults) -> MonitorStore {
        var preferences = DisplayPreferences()
        preferences.autoRefresh = false
        preferences.providerOrder = ["cursor", "minimax", "windsurf", "kiro"] + ProviderInfo.defaultOrder
        preferences.normalize()
        preferences.save(to: defaults)
        defaults.set(["cursor", "minimax", "windsurf", "kiro"], forKey: "enabled")
        let store = MonitorStore(defaults: defaults, servicesEnabled: false)
        let now = Date().timeIntervalSince1970
        store.previewNow = now
        var providers = PreviewSupport.expandedFixtures(now: now).providers + PreviewSupport.fixtures(now: now).providers
        providers.append(ProviderResult(id: "copilot", name: "Copilot", plan: "Pro", fetchedAt: now,
            windows: [QuotaWindow(id: "premium_interactions", label: "Premium · 每月", remainingPercent: 72, resetAt: now + 12 * 86400, kind: "monthly")]))
        providers.append(ProviderResult(id: "antigravity", name: "Antigravity", fetchedAt: now,
            windows: [QuotaWindow(id: "group-demo", label: "Claude · 5 小时", remainingPercent: 54, resetAt: now + 10800, durationMinutes: 300)]))
        for i in providers.indices { providers[i].source = "交互预览 · 合成数据，不是实际账号" }
        store.snapshot = Snapshot(generatedAt: now, providers: providers)
        populateAPI(store.api, now: now)
        return store
    }
    static func populateAPI(_ api: APIBalanceStore, now: Double) {
        let balances: [APIProvider: Double] = [.deepseek: 82.4, .kimi: 120, .siliconflow: 88.88, .openrouter: 18.5]
        let spent: [APIProvider: Double] = [.openai: 4.2, .claude: 1.35, .openrouter: 3.2]
        var observations: [APIObservation] = []
        for i in api.accounts.indices {
            var account = api.accounts[i]
            account.credentialRevision = "synthetic-interactive-demo"
            if account.provider.supportsDailyCost { account.dailyBudget = 10 }
            if [.deepseek, .kimi, .siliconflow].contains(account.provider) { account.balanceReference = 200 }
            api.accounts[i] = account
            observations.append(APIObservation(id: account.id, context: account.context,
                status: account.provider == .google ? "unsupported" : "ok", currency: account.selectedCurrency,
                balance: balances[account.provider], balanceLabel: account.provider == .openrouter ? "Key 剩余额度" : "账户余额",
                dailySpent: spent[account.provider], dayUTC: APIObservation.day(Date(timeIntervalSince1970: now)),
                keyLimit: account.provider == .openrouter ? 20 : nil, fetchedAt: now,
                source: "交互预览 · 合成数据", message: "模拟展示，不是你的实际余额。"))
        }
        api.snapshot = APIBalanceSnapshot(generatedAt: now, accounts: observations)
    }
    static func run(args: [String]) {
        let delegate = DemoDelegate(args: args)
        NSApp.delegate = delegate
        withExtendedLifetime(delegate) { NSApp.run() }
    }
}

@MainActor struct DemoRoot: View {
    @ObservedObject var store: MonitorStore
    var body: some View {
        VStack(spacing: 0) {
            VStack(alignment: .leading, spacing: 7) {
                Label("交互预览 · 模拟数据", systemImage: "eye")
                    .font(.system(size: 12, weight: .semibold))
                Text("不连接账号，不保存密钥，不改变正式设置。")
                    .font(.system(size: 10)).foregroundStyle(.secondary)
                HStack {
                    Button("新增套餐") { store.enabled = ["cursor", "minimax", "windsurf", "kiro"]; store.apiMode = false; store.showSettings = false }
                        .accessibilityIdentifier("demo.new-plans")
                    Button("全部套餐") { store.enabled = Set(ProviderInfo.defaultOrder); store.apiMode = false; store.showSettings = false }
                        .accessibilityIdentifier("demo.all-plans")
                    Spacer()
                    Image(nsImage: MenuBarIcon.make(slots: store.iconSlots, style: "mono", threshold: 25))
                        .help("菜单栏图标预览，仍为黑白")
                }.buttonStyle(.bordered).controlSize(.small)
            }.padding(12).frame(maxWidth: .infinity, alignment: .leading).background(Color(nsColor: .controlBackgroundColor))
            Divider()
            MonitorPanel(store: store)
        }.frame(width: CGFloat(store.preferences.panelWidth)).background(Color.white)
         .environment(\.colorScheme, .light)
    }
}

@MainActor final class DemoDelegate: NSObject, NSApplicationDelegate, NSWindowDelegate {
    let args: [String]
    let suite = AppRuntime.profile.bundleID + ".demo." + UUID().uuidString
    var store: MonitorStore!
    var window: NSWindow!
    var defaults: UserDefaults!
    private var keyMonitor: Any?
    private var cleaned = false
    init(args: [String]) { self.args = args }
    private var receiptURL: URL? {
        guard let i = args.firstIndex(of: "--demo-receipt"), args.indices.contains(i + 1), args[i + 1].hasPrefix("/") else { return nil }
        return URL(fileURLWithPath: args[i + 1])
    }
    func applicationDidFinishLaunching(_ notification: Notification) {
        defaults = UserDefaults(suiteName: suite)!
        store = DemoSupport.makeStore(defaults: defaults)
        // Leave room for the demo banner, title bar, Dock and menu bar.
        store.availablePanelHeight = max(300, min(860, (NSScreen.main?.visibleFrame.height ?? 900) - 160))
        let root = DemoRoot(store: store)
        let host = FirstClickHostingView(rootView: root)
        window = NSWindow(contentRect: NSRect(origin: .zero, size: host.fittingSize), styleMask: [.titled, .closable, .miniaturizable], backing: .buffered, defer: false)
        window.title = "AI Monitor · 交互预览（模拟数据）"
        window.isReleasedWhenClosed = false
        window.appearance = NSAppearance(named: .aqua)
        window.backgroundColor = .white
        window.contentView = host
        window.delegate = self
        store.dismissPanel = { NSApp.terminate(nil) }
        store.onChange = { [weak self] in self?.fit() }
        store.api.onChange = { [weak self] in self?.fit() }
        keyMonitor = NSEvent.addLocalMonitorForEvents(matching: .keyDown) { [weak self] event in
            guard let self, self.window.isKeyWindow, event.modifierFlags.contains(.command) else { return event }
            switch event.charactersIgnoringModifiers {
            case "w", "q": NSApp.terminate(nil); return nil
            case ",": self.store.openSettings(); return nil
            case "r": self.store.refreshCurrent(); return nil
            default: return event
            }
        }
        window.center(); window.makeKeyAndOrderFront(nil); NSApp.activate(ignoringOtherApps: true)
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) { [weak self] in
            guard let self else { return }
            self.writeReceipt(status: "ready")
            if self.args.contains("--demo-self-test") {
                Task { await self.selfTest() }
            }
        }
    }
    private func fit() {
        DispatchQueue.main.async { [weak self] in
            guard let self, let content = self.window?.contentView else { return }
            content.layoutSubtreeIfNeeded()
            let size = content.fittingSize
            if size.width > 0, size.height > 0, self.window.contentView?.frame.size != size { self.window.setContentSize(size) }
        }
    }
    private func writeReceipt(status: String, checks: Int? = nil) {
        let info: [String: Any] = ["mode": "synthetic-demo", "status": status, "pid": ProcessInfo.processInfo.processIdentifier,
            "windowTitle": window?.title ?? "", "windowVisible": window?.isVisible ?? false,
            "windowNumber": window?.windowNumber ?? 0, "servicesEnabled": store?.servicesEnabled ?? false,
            "apiServicesEnabled": store?.api.servicesEnabled ?? false,
            "suite": suite, "checkCount": checks ?? 0, "updatedAt": Date().timeIntervalSince1970]
        guard let bytes = try? JSONSerialization.data(withJSONObject: info, options: [.prettyPrinted, .sortedKeys]) else { return }
        if let path = receiptURL { try? bytes.write(to: path, options: .atomic); try? FileManager.default.setAttributes([.posixPermissions: 0o600], ofItemAtPath: path.path) }
        print("DEMO_STATE " + String(data: bytes, encoding: .utf8)!)
        fflush(stdout)
    }
    private func selfTest() async {
        var count = 0
        func check(_ good: Bool, _ label: String) {
            guard good else { fputs("DEMO_CHECK_FAILED: \(label)\n", stderr); cleanup(); exit(1) }
            count += 1
        }
        check(!store.servicesEnabled && !store.api.servicesEnabled, "real services disabled")
        check(window.isVisible && !window.title.isEmpty, "visible demo window")
        check(store.snapshot?.providers.count == 10, "all ten synthetic providers")
        check(store.enabled.count == 4, "new plans first")
        for id in ProviderInfo.defaultOrder { check(BrandAssets.image(id) != nil, "official bundled logo \(id)") }
        let apiBefore = store.api.accounts
        store.toggleLogin(true); check(!store.launchAtLogin, "login item mutation blocked")
        store.grantClaude(); check(!store.authorizingClaude, "keychain grant blocked")
        for id in ProviderInfo.defaultOrder { store.reconnect(id); store.openWebsite(id) }
        store.refresh(force: true); check(!store.refreshing, "no plan collector")
        store.api.refresh(); check(!store.api.refreshing, "no API collector")
        let account = store.api.accounts[0]
        let saved = await store.api.save(account, key: "synthetic-demo-only")
        check(!saved, "API secret save rejected")
        await store.api.removeKey(account.id); await store.api.grant(account.id); store.api.openBilling(account)
        check(store.api.accounts == apiBefore, "account secret operations leave state unchanged")
        let planSaved = await store.saveMiniMaxCredential("synthetic-demo-only")
        check(!planSaved, "plan secret save rejected")
        store.clearQuotaCache(); check(store.snapshot != nil, "real cache deletion blocked")
        store.toggleAPI(); check(store.apiMode, "API navigation works")
        store.openAPISettings(account.id); check(store.showSettings && store.api.editingID == account.id, "API editor navigation works")
        store.backFromSettings(); store.backFromSettings(); store.toggleAPI(); check(!store.apiMode, "return to plans")
        store.enabled = Set(ProviderInfo.defaultOrder); check(store.iconSlots.count == 10, "ten menu bars")
        store.move("kiro", by: -1); check(store.preferences.providerOrder.contains("kiro"), "ordering works")
        store.preferences.compact.toggle(); check(!store.preferences.compact, "display setting works")
        check(MenuBarIcon.make(slots: store.iconSlots, style: "mono", threshold: 25).isTemplate, "monochrome menu icon")
        store.banner = ""; store.api.message = ""
        writeReceipt(status: "checks-passed", checks: count)
        print("DEMO_CHECKS_PASSED \(count)"); fflush(stdout)
        NSApp.terminate(nil)
    }
    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool { window?.makeKeyAndOrderFront(nil); NSApp.activate(ignoringOtherApps: true); return true }
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }
    func windowWillClose(_ notification: Notification) { NSApp.terminate(nil) }
    private func cleanup() {
        guard !cleaned else { return }; cleaned = true
        if let keyMonitor { NSEvent.removeMonitor(keyMonitor) }
        store?.shutdown(); defaults?.removePersistentDomain(forName: suite)
    }
    func applicationWillTerminate(_ notification: Notification) { cleanup() }
}
