import Foundation
import MonitorCore

extension MonitorCoreTests {
    func expanded(_ id: String, _ windows: [QuotaWindow], status: String = "ok") -> ProviderResult {
        ProviderResult(id: id, name: id, status: status, fetchedAt: now, windows: windows)
    }
    func testExpandedRegistryKeepsOriginalOrder() {
        checkEqual(ProviderInfo.defaultOrder, ["kimi", "codex", "claude", "glm", "copilot", "antigravity", "cursor", "minimax", "windsurf", "kiro"])
        checkEqual(Set(ProviderInfo.defaultOrder).count, 10)
    }
    func testExpandedGeometryIsReadable() {
        for count in 7...10 {
            let rows = MenuBarGeometry.rows(count: count)
            checkEqual(rows.count, count)
            for row in rows { checkTrue(row.height >= 1.2); checkTrue(row.y >= 0); checkTrue(row.y + row.height <= 20) }
            for index in 1..<count { checkTrue(rows[index].y + rows[index].height < rows[index-1].y) }
        }
    }
    func testCursorMonthlyIsNotFiveHours() {
        let p = expanded("cursor", [QuotaWindow(id:"cursor-monthly",label:"本月",remainingPercent:75,kind:"monthly")])
        let slot = slots([p])[0]
        checkEqual(slot.percent,75); checkEqual(slot.period,"month"); checkTrue(slot.reason.contains("月度"))
    }
    func testCursorSeparatePoolsNotAverage() {
        var p = expanded("cursor", [QuotaWindow(id:"cursor-auto",label:"Auto",remainingPercent:80,kind:"monthly"),QuotaWindow(id:"cursor-api",label:"API",remainingPercent:20,kind:"monthly")])
        checkEqual(slots([p])[0].percent,20)
        p.windows.append(QuotaWindow(id:"cursor-monthly",label:"总池",remainingPercent:60,kind:"monthly"))
        checkEqual(slots([p])[0].percent,60)
    }
    func testKiroUsesRealMonthlyCredits() {
        let p = expanded("kiro", [QuotaWindow(id:"kiro-monthly",label:"本月",remainingPercent:25,remaining:250,limit:1000,kind:"monthly")])
        let slot = slots([p])[0]
        checkEqual(slot.percent,25); checkEqual(slot.period,"month"); checkTrue(slot.reason.contains("Credits"))
    }
    func testWindsurfAlwaysMarkedCache() {
        let p = expanded("windsurf", [QuotaWindow(id:"windsurf-daily",label:"每日额度 · 缓存",remainingPercent:80,durationMinutes:1440)],status:"stale")
        checkEqual(slots([p])[0].state,"cached"); checkEqual(slots([p])[0].period,"day")
        checkEqual(p.statusLabel,"本地缓存"); checkTrue(p.lastValueLabel.hasPrefix("缓存文件"))
    }
    func testWindsurfWeekNeverPretendsDaily() {
        let p = expanded("windsurf", [QuotaWindow(id:"windsurf-weekly",label:"每周",remainingPercent:80,durationMinutes:10080)],status:"stale")
        checkNil(slots([p])[0].percent)
    }
    func testMiniMaxWindowKeepsQuotaName() {
        let w = QuotaWindow(id:"minimax-0-5h",label:"general · 当前窗口",remainingPercent:40,durationMinutes:300)
        checkEqual(w.shortLabel,"general · 当前窗口")
        checkEqual(slots([expanded("minimax",[w])])[0].percent,40)
    }
    func testExpandedOrderDoesNotEnableAccounts() {
        let suite = "MonitorExpandedChecks."+UUID().uuidString
        let defaults = UserDefaults(suiteName:suite)!
        defer { defaults.removePersistentDomain(forName:suite) }
        defaults.set(["kimi"],forKey:"enabled")
        var preferences = DisplayPreferences(); preferences.providerOrder = ["kimi", "claude"]
        preferences.save(to:defaults)
        checkEqual(DisplayPreferences.load(from:defaults).providerOrder.count,10)
        checkEqual(defaults.stringArray(forKey:"enabled"),["kimi"])
    }
    func testEmptyExpandedProviderNotFullAllowance() {
        for id in ["cursor", "minimax", "windsurf", "kiro"] { checkNil(slots([expanded(id,[])])[0].percent) }
    }
}
