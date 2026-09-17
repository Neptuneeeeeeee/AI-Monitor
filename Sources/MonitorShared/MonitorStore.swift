import AppKit
import SwiftUI
import Security
import ServiceManagement
import MonitorCore

@MainActor final class MonitorStore: ObservableObject {
    let api: APIBalanceStore
    @Published var apiMode = false { didSet { onChange?() } }
    @Published var snapshot: Snapshot?
    @Published var refreshing = false
    @Published var authorizingClaude = false
    @Published var minimaxRegion = "cn"
    @Published var savingPlanCredential = false
    @Published var banner = ""
    @Published var showSettings = false { didSet { onChange?() } }
    @Published var settingsTab = "order"
    @Published var preferences: DisplayPreferences {
        didSet { preferences.save(to: defaults); if oldValue.autoRefresh != preferences.autoRefresh { reschedule() }; onChange?() }
    }
    @Published var refreshSeconds: Int { didSet { defaults.set(refreshSeconds, forKey: "refreshSeconds"); reschedule() } }
    @Published var enabled: Set<String> {
        didSet {
            defaults.set(Array(enabled).sorted(), forKey: "enabled"); onChange?()
            enableRefresh?.cancel()
            if servicesEnabled {
                let work = DispatchWorkItem { [weak self] in self?.refresh() }
                enableRefresh = work
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.8, execute: work)
            }
        }
    }
    @Published var glmRegion: String { didSet { defaults.set(glmRegion, forKey: "glmRegion") } }
    @Published var launchAtLogin = false
    var onChange: (() -> Void)?
    var dismissPanel: (() -> Void)?
    let defaults: UserDefaults
    let servicesEnabled: Bool
    @Published var availablePanelHeight: CGFloat = 1200
    var previewNow: Double?
    var now: Double { previewNow ?? Date().timeIntervalSince1970 }
    var staleAge: Double { Double(max(300, refreshSeconds * 2)) }
    private var lastDispatch = -Double.infinity
    private var enableRefresh: DispatchWorkItem?
    private var timer: Timer?
    private var clock: Timer?
    private var process: Process?
    private var wakeObserver: NSObjectProtocol?
    var support: URL { AppRuntime.support }

    init(defaults: UserDefaults = AppRuntime.defaults, servicesEnabled: Bool = true) {
        self.defaults = defaults; self.servicesEnabled = servicesEnabled
        self.api = APIBalanceStore(servicesEnabled: servicesEnabled)
        preferences = DisplayPreferences.load(from: defaults)
        refreshSeconds = max(300, defaults.object(forKey: "refreshSeconds") as? Int ?? 300)
        enabled = Set(defaults.stringArray(forKey: "enabled") ?? AppRuntime.profile.defaultEnabledProviders)
        glmRegion = defaults.string(forKey: "glmRegion") ?? "cn"
        if servicesEnabled {
            defaults.set(refreshSeconds, forKey: "refreshSeconds")
            preferences.save(to: defaults)
        }
        guard servicesEnabled else { return }
        launchAtLogin = SMAppService.mainApp.status == .enabled
        if let bytes = try? Data(contentsOf: support.appendingPathComponent("plan-connections.json")),
           bytes.count < 16384, let settings = try? JSONSerialization.jsonObject(with: bytes) as? [String: String],
           let region = settings["minimaxRegion"], ["cn", "global"].contains(region) { minimaxRegion = region }
        availablePanelHeight = max(360, (NSScreen.main?.visibleFrame.height ?? 982) - 64)
        if !KeychainBridge.ensureInstalled() { banner = "固定钥匙串组件未安装，请重新安装 Monitor。" }
        try? FileManager.default.createDirectory(at: support, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
        if let data = try? Data(contentsOf: support.appendingPathComponent("snapshot.json")), let old = try? JSONDecoder().decode(Snapshot.self, from: data) { snapshot = old }
        // Revalidate new-account context before reusing a disk snapshot at launch.
        snapshot?.providers.removeAll { ["cursor", "minimax", "windsurf", "kiro"].contains($0.id) }
        reschedule()
        clock = Timer.scheduledTimer(withTimeInterval: 30, repeats: true) { [weak self] _ in
            Task { @MainActor in self?.objectWillChange.send(); self?.onChange?() }
        }
        wakeObserver = NSWorkspace.shared.notificationCenter.addObserver(forName: NSWorkspace.didWakeNotification, object: nil, queue: .main) { [weak self] _ in
            Task { @MainActor in if self?.preferences.autoRefresh == true && self?.preferences.refreshOnWake == true { self?.refresh() } }
        }
    }
    func shutdown() {
        api.shutdown()
        timer?.invalidate(); clock?.invalidate(); enableRefresh?.cancel()
        if let wakeObserver { NSWorkspace.shared.notificationCenter.removeObserver(wakeObserver) }
        guard let process, process.isRunning else { return }
        process.terminate()
        let deadline = Date().addingTimeInterval(3)
        while process.isRunning && Date() < deadline { Thread.sleep(forTimeInterval: 0.05) }
        if process.isRunning { Darwin.kill(process.processIdentifier, SIGKILL) }
    }
    func reschedule() {
        timer?.invalidate()
        guard servicesEnabled && preferences.autoRefresh else { return }
        let deadlines = activeProviders.compactMap { provider($0.id)?.nextQueryAt }.filter { $0.isFinite }
        let next = deadlines.min() ?? now + Double(refreshSeconds)
        timer = Timer.scheduledTimer(withTimeInterval: max(30, next - now + 1), repeats: false) { [weak self] _ in
            Task { @MainActor in self?.refresh() }
        }
        timer?.tolerance = 5
    }
    func refresh(force: Bool = false) {
        guard servicesEnabled && !refreshing && !savingPlanCredential else { return }
        let uptime = ProcessInfo.processInfo.systemUptime
        guard uptime - lastDispatch >= 3 else { return }
        lastDispatch = uptime
        guard !activeProviders.isEmpty else { banner = "尚未启用套餐。"; return }
        guard let script = Bundle.main.resourceURL?.appendingPathComponent("collector/monitor.py"), FileManager.default.fileExists(atPath: script.path) else { banner = "采集程序缺失，请重新安装。"; return }
        let p = Process(), out = Pipe(), capture = PipeCapture()
        guard let python = AppRuntime.pythonExecutable else { banner = "缺少 Python 运行环境，请安装开发依赖或使用包含运行时的发行包。"; return }
        p.executableURL = python
        p.arguments = [script.path, "--providers", activeProviders.map(\.id).joined(separator: ","), "--glm-region", glmRegion, "--interval-seconds", String(refreshSeconds)]
        if force { p.arguments?.append("--force") }
        var env = AppRuntime.collectorEnvironment()
        env["MONITOR_KEYCHAIN_HELPER"] = KeychainBridge.executable.path
        env["MONITOR_CLAUDE_KEYCHAIN_ALLOWED"] = defaults.bool(forKey: "claudeKeychainAllowed") ? "1" : "0"
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PATH"] = NSHomeDirectory() + "/.kimi-code/bin:" + NSHomeDirectory() + "/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
        p.environment = env; p.currentDirectoryURL = support
        p.standardOutput = out; p.standardError = FileHandle.nullDevice
        refreshing = true; banner = ""; process = p; onChange?()
        p.terminationHandler = { [weak self] child in
            let data = capture.finish()
            Task { @MainActor in
                guard let self else { return }
                self.refreshing = false; self.process = nil
                if child.terminationStatus == 0, let decoded = try? JSONDecoder().decode(Snapshot.self, from: data) {
                    self.snapshot = decoded
                } else {
                    self.banner = "采集未完成（退出码 \(child.terminationStatus)）。详细状态见连接设置。"
                    if var old = self.snapshot {
                        old.providers = old.providers.map { var p = $0; if !p.windows.isEmpty { p.status = "stale" }; return p }; self.snapshot = old
                    }
                }
                self.reschedule(); self.onChange?()
            }
        }
        do {
            try p.run(); capture.start(out.fileHandleForReading)
            DispatchQueue.main.asyncAfter(deadline: .now() + 160) { [weak p] in
                guard let p, p.isRunning else { return }; p.terminate()
                DispatchQueue.main.asyncAfter(deadline: .now() + 3) { if p.isRunning { Darwin.kill(p.processIdentifier, SIGKILL) } }
            }
        } catch { refreshing = false; process = nil; banner = "无法启动本地采集程序。"; reschedule(); onChange?() }
    }
    func toggleLogin(_ value: Bool) {
        guard servicesEnabled else { banner = "交互预览不执行账号连接、系统设置或真实数据操作。"; return }
        do {
            if value { try SMAppService.mainApp.register() } else { try SMAppService.mainApp.unregister() }
            launchAtLogin = SMAppService.mainApp.status == .enabled
            if SMAppService.mainApp.status == .requiresApproval { banner = "请在系统设置的登录项中允许 Monitor。"; SMAppService.openSystemSettingsLoginItems() }
        } catch { banner = "登录项设置未成功，请在系统设置中检查。" }
    }
    func grantClaude() {
        guard servicesEnabled else { banner = "交互预览不执行账号连接、系统设置或真实数据操作。"; return }
        guard !authorizingClaude else { return }; authorizingClaude = true
        banner = "正在检查 Claude 登录凭证读取…"
        Task {
            let status = await Task.detached { KeychainBridge.grantClaude() }.value
            authorizingClaude = false
            banner = status == errSecSuccess ? "Claude 登录凭证可以无弹窗读取。额度查询仍遵守现有冷却时间。" : status == errSecNotAvailable ? "钥匙串组件忙或超时，未判定为拒绝。稍后再试。" : status == errSecInteractionNotAllowed ? "登录钥匙串已锁定，解锁后再试；后台不会弹窗。" : status == errSecItemNotFound ? "本机没有 Claude Code 的登录条目。请在官方 CLI 运行 claude auth login。" : "未能读取 Claude 登录凭证（系统状态 \(status)）。"
            if status == errSecSuccess {
                defaults.set(true, forKey: "claudeKeychainAllowed")
                if let data = try? JSONSerialization.data(withJSONObject:["authorizedAt": Date().timeIntervalSince1970, "component":"MonitorKeychainBridge/2"]) {
                    let target = support.appendingPathComponent("claude-authorization.json")
                    try? data.write(to:target,options:.atomic)
                    try? FileManager.default.setAttributes([.posixPermissions:0o600],ofItemAtPath:target.path)
                }
                refresh(force:true)
            }
        }
    }
    func openWebsite(_ id: String) {
        guard servicesEnabled else { banner = "交互预览不执行账号连接、系统设置或真实数据操作。"; return }
        if id == "minimax" && minimaxRegion == "global" {
            NSWorkspace.shared.open(URL(string: "https://platform.minimax.io/subscribe/token-plan")!); return
        }
        let text = id == "glm" && glmRegion == "global" ? "https://z.ai/manage-apikey/coding-plan/personal/my-plan" : ProviderInfo.all.first { $0.id == id }?.website
        if let text, let url = URL(string: text) { NSWorkspace.shared.open(url) }
    }
    func reconnect(_ id: String) {
        guard servicesEnabled else { banner = "交互预览不执行账号连接、系统设置或真实数据操作。"; return }
        if ["cursor", "windsurf"].contains(id) {
            let name = id == "cursor" ? "Cursor.app" : "Windsurf.app"
            let roots = [URL(fileURLWithPath: "/Applications"), FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Applications")]
            if let app = roots.map({ $0.appendingPathComponent(name) }).first(where: { FileManager.default.fileExists(atPath: $0.path) }) {
                NSWorkspace.shared.openApplication(at: app, configuration: NSWorkspace.OpenConfiguration()) { _, _ in }
                banner = "在官方应用登录后刷新。"
            } else { banner = "请先安装对应官方应用，再启用套餐。" }
            return
        }
        if id == "kiro" { banner = "请在终端运行 kiro-cli login；登录完成后返回刷新。"; return }

        if id == "claude" { grantClaude(); return }
        if id == "antigravity" {
            NSWorkspace.shared.openApplication(at: URL(fileURLWithPath: "/Applications/Antigravity.app"), configuration: NSWorkspace.OpenConfiguration()) { _, _ in }
            banner = "在 Antigravity 登录后点击刷新。"; return
        }
        let commands = ["kimi": "if command -v kimi >/dev/null 2>&1; then kimi login; else printf '未找到 Kimi CLI，请先安装官方客户端。\\n'; fi", "codex": "if command -v codex >/dev/null 2>&1; then codex login; else printf '未找到 Codex CLI，请先安装官方客户端。\\n'; fi"]
        guard let command = commands[id] else { openSettings("connections"); return }
        let file = support.appendingPathComponent("login-\(id).command")
        let body = "#!/bin/zsh\nexport PATH=\"$HOME/.kimi-code/bin:$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH\"\ncd \"$HOME\"\n\(command)\nprintf '\\n登录完成后回到 Monitor 点击刷新。\\n'\n"
        do {
            try body.write(to: file, atomically: true, encoding: .utf8)
            try FileManager.default.setAttributes([.posixPermissions: 0o700], ofItemAtPath: file.path); NSWorkspace.shared.open(file)
        } catch { banner = "无法打开登录入口，请在官方终端登录。" }
    }
    func openDataDirectory() {
        guard servicesEnabled else { banner = "交互预览不访问正式数据目录。"; return }
        NSWorkspace.shared.open(support)
    }
    func diagnostic() {
        guard servicesEnabled else { banner = "交互预览不执行账号连接、系统设置或真实数据操作。"; return }
        let panel = NSSavePanel(); panel.nameFieldStringValue = "Monitor-diagnostics.json"; panel.title = "导出脱敏诊断"
        if panel.runModal() == .OK, let url = panel.url, let snapshot {
            let encoder = JSONEncoder(); encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
            do { try encoder.encode(snapshot).write(to: url, options: .atomic); banner = "已导出，不包含凭证。" } catch { banner = "导出失败。" }
        }
    }
    var orderedProviders: [ProviderInfo] { preferences.providerOrder.compactMap { id in ProviderInfo.all.first { $0.id == id } } }
    var activeProviders: [ProviderInfo] { orderedProviders.filter { enabled.contains($0.id) } }
    var visibleProviders: [ProviderInfo] {
        activeProviders.filter { info in
            guard let data = provider(info.id) else { return preferences.showUnavailable }
            return preferences.showUnavailable || ["ok", "partial", "stale"].contains(data.status)
        }
    }
    func provider(_ id: String) -> ProviderResult? { snapshot?.providers.first { $0.id == id } }
    func move(_ id: String, by offset: Int) { preferences.move(id, by: offset) }
    func move(_ id: String, to target: String) { preferences.move(id, to: target) }
    var iconSlots: [MenuBarSlot] { MenuBarMapping.slots(order: preferences.providerOrder, enabled: enabled, snapshot: snapshot, now: now, maxAge: staleAge) }
    var iconHelp: String {
        if iconSlots.isEmpty { return "未启用套餐，点击打开设置" }
        return iconSlots.enumerated().map { index, slot in
            let value = slot.percent.map { String(format: "%.1f%%", $0) } ?? "—"
            return "\(index + 1). \(slot.name) · \(slot.reason) \(value)"
        }.joined(separator: "\n")
    }
    // Network updates must not move click targets under the pointer.
    // A stable viewport scrolls overflow within the height chosen in Settings.
    var panelHeight: CGFloat { min(CGFloat(preferences.maxHeight), availablePanelHeight) }
    func fitPanel(to screen: NSScreen?) {
        guard let screen else { return }
        let height = max(300, screen.visibleFrame.height - 64)
        if height != availablePanelHeight { availablePanelHeight = height }
    }
    func openSettings(_ tab: String = "order") { settingsTab = tab; api.editingID = nil; showSettings = true }
    func openAPISettings(_ id: String?) { apiMode = true; api.editingID = id; showSettings = true }
    func toggleAPI() { showSettings = false; api.editingID = nil; apiMode.toggle(); if apiMode { api.refresh() } }
    func backFromSettings() { if apiMode && api.editingID != nil { api.editingID=nil } else { showSettings=false } }
    func refreshCurrent() {
        guard servicesEnabled else { banner = "这里只展示模拟数据，未发起真实查询。"; return }
        if apiMode { api.refresh() } else { refresh(force:true) }
    }
    func clearQuotaCache() {
        guard servicesEnabled else { banner = "交互预览不执行账号连接、系统设置或真实数据操作。"; return }
        guard !refreshing else { banner = "请等待本轮刷新结束。"; return }
        for name in ["snapshot.json", "provider-state.json"] { try? FileManager.default.removeItem(at: support.appendingPathComponent(name)) }
        snapshot = nil; banner = "额度缓存已清除；账号、钥匙串与防限流等待时间保持不变。"; onChange?(); refresh(force: true)
    }
    func resetAppearance() {
        preferences = DisplayPreferences(); banner = "已恢复默认显示与排序，保留已启用账号。"
    }
}
