import Foundation

public struct DisplayPreferences: Codable, Equatable {
    public static let storageKey = "displayPreferences.v2"
    public var providerOrder = ProviderInfo.defaultOrder
    public var panelWidth = 340
    public var maxHeight = 860
    public var tallPanelRevision = 1
    public var compact = true
    public var iconStyle = "mono"
    public var brandThemeRevision = 2
    public var useBrandColors = true
    public var showProviderLogos = true
    public var precision = "smart"
    public var resetMode = "relative"
    public var showPlan = true
    public var showSession = true
    public var showWeekly = true
    public var showExtra = true
    public var showOther = true
    public var showModelWindows = false
    public var showUnlimited = false
    public var showUnavailable = true
    public var showPaceMarker = false
    public var showUpdatedAt = false
    public var lowThreshold = 25
    public var autoRefresh = true
    public var refreshOnOpen = true
    public var refreshOnWake = true
    public var keepPopoverOpen = false
    public init() {}
    public mutating func normalize() {
        providerOrder = Self.normalizedOrder(providerOrder)
        if ![320, 340, 360, 380].contains(panelWidth) { panelWidth = 340 }
        if ![480, 560, 620, 680, 720, 760, 860, 960].contains(maxHeight) { maxHeight = 860 }
        iconStyle = "mono" // Menu bar is always an Apple-style monochrome template.
        if !["smart", "whole", "one"].contains(precision) { precision = "smart" }
        if !["relative", "absolute", "hidden"].contains(resetMode) { resetMode = "relative" }
        lowThreshold = min(50, max(1, lowThreshold))
    }
    public static func normalizedOrder(_ input: [String]) -> [String] {
        var seen = Set<String>()
        return (input + ProviderInfo.defaultOrder).filter { ProviderInfo.defaultOrder.contains($0) && seen.insert($0).inserted }
    }
    public static func load(from defaults: UserDefaults) -> DisplayPreferences {
        let standard = DisplayPreferences()
        guard let data = defaults.data(forKey: storageKey),
              let current = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let baseData = try? JSONEncoder().encode(standard),
              var base = try? JSONSerialization.jsonObject(with: baseData) as? [String: Any] else { return standard }
        base.merge(current) { _, newer in newer }
        if current["tallPanelRevision"] == nil { base["maxHeight"] = max(current["maxHeight"] as? Int ?? 620, 860) }
        // Keep brand colors inside the panel, never on the macOS status bar.
        base["iconStyle"] = "mono"
        base["brandThemeRevision"] = 2
        guard let merged = try? JSONSerialization.data(withJSONObject: base),
              var preferences = try? JSONDecoder().decode(DisplayPreferences.self, from: merged) else { return standard }
        preferences.normalize(); return preferences
    }
    public func save(to defaults: UserDefaults) {
        if let data = try? JSONEncoder().encode(self) { defaults.set(data, forKey: Self.storageKey) }
    }
    public mutating func move(_ id: String, by offset: Int) {
        providerOrder = Self.normalizedOrder(providerOrder)
        guard let index = providerOrder.firstIndex(of: id) else { return }
        let destination = min(providerOrder.count - 1, max(0, index + offset))
        providerOrder.remove(at: index); providerOrder.insert(id, at: destination)
    }
    public mutating func move(_ id: String, to target: String) {
        guard id != target, let source = providerOrder.firstIndex(of: id), let destination = providerOrder.firstIndex(of: target) else { return }
        providerOrder.remove(at: source); providerOrder.insert(id, at: destination)
    }
    public func visibleWindows(_ result: ProviderResult) -> [QuotaWindow] {
        result.windows.filter { window in
            if window.isUnlimited == true && !showUnlimited { return false }
            if window.isExtra { return showExtra }
            if window.isScoped { return showModelWindows }
            if window.durationMinutes == 300 { return showSession }
            if window.durationMinutes == 10080 { return showWeekly }
            return showOther
        }.enumerated().sorted { a, b in
            func priority(_ w: QuotaWindow) -> Int {
                if w.isExtra { return 4 }
                if w.isScoped { return 3 }
                if w.durationMinutes == 300 { return 0 }
                if w.durationMinutes == 10080 { return 1 }
                return 2
            }
            let x = priority(a.element), y = priority(b.element)
            return x == y ? a.offset < b.offset : x < y
        }.map(\.element)
    }
}

public struct MenuBarSlot: Codable, Equatable {
    public var providerID: String?
    public var name: String
    public var percent: Double?
    public var state: String
    public var period: String?
    public var measuredAt: Double?
    public var reason: String
    public init(providerID: String? = nil, name: String = "未分配", percent: Double? = nil, state: String = "empty", reason: String = "未分配", period: String? = nil, measuredAt: Double? = nil) {
        self.providerID = providerID; self.name = name; self.percent = percent; self.state = state; self.reason = reason; self.period = period; self.measuredAt = measuredAt
    }
}

public enum MenuBarMapping {
    public static func slots(order: [String], enabled: Set<String>, snapshot: Snapshot?, now: Double, maxAge: Double) -> [MenuBarSlot] {
        let selected = DisplayPreferences.normalizedOrder(order).filter { enabled.contains($0) }
        let slots = selected.map { id -> MenuBarSlot in
            let name = ProviderInfo.all.first { $0.id == id }?.name ?? id
            guard let provider = snapshot?.providers.first(where: { $0.id == id }) else {
                return MenuBarSlot(providerID: id, name: name, state: "unknown", reason: "等待读取")
            }
            guard ["ok", "partial", "stale"].contains(provider.status), let measuredAt = provider.fetchedAt else {
                return MenuBarSlot(providerID:id, name:name, state:"unknown", reason:provider.statusLabel)
            }
            var candidates = provider.windows.filter { $0.durationMinutes == 300 && !$0.isExtra && $0.unit != "MCP" }
            var period = "5h", label = "5 小时"
            if candidates.isEmpty && id == "copilot" {
                candidates = provider.windows.filter { $0.id == "premium_interactions" && $0.safePercent != nil }
                period = "month"; label = "每月 Premium"
            }
            if candidates.isEmpty && id == "cursor" {
                let total = provider.windows.filter { $0.id == "cursor-monthly" && $0.safePercent != nil }
                candidates = total.isEmpty ? provider.windows.filter { ["cursor-auto", "cursor-api"].contains($0.id) && $0.safePercent != nil } : total
                period = "month"; label = total.isEmpty ? "月度额度池" : "月度套餐"
            }
            if candidates.isEmpty && id == "kiro" {
                candidates = provider.windows.filter { $0.id == "kiro-monthly" && $0.safePercent != nil }
                period = "month"; label = "每月 Credits"
                if candidates.contains(where: { $0.label.contains("官方估计") }) { label += "（官方估计）" }
            }
            if candidates.isEmpty && id == "windsurf" {
                candidates = provider.windows.filter { $0.id == "windsurf-daily" && $0.safePercent != nil }
                period = "day"; label = "每日额度缓存"
                if candidates.isEmpty {
                    candidates = provider.windows.filter { ["windsurf-messages", "windsurf-actions"].contains($0.id) && $0.safePercent != nil }
                    period = "provider"; label = "服务商窗口缓存"
                }
            }
            let percentages = candidates.compactMap(\.safePercent)
            guard let percent = percentages.min() else {
                return MenuBarSlot(providerID:id, name:name, state:"unknown", reason:["cursor", "kiro", "copilot"].contains(id) ? "没有可量化的月额度" : id == "windsurf" ? "没有可量化的主窗口缓存" : "未提供 5 小时额度")
            }
            let resetPassed = candidates.contains { ($0.resetAt ?? Double.infinity) <= now && measuredAt < ($0.resetAt ?? 0) }
            let cached = provider.isStale(now:now,maxAge:maxAge) || resetPassed || provider.queryStatus == "cooldown"
            var reason = label + (percentages.count > 1 ? "多个池最低余量" : "剩余")
            if cached { reason += " · " + provider.lastValueLabel + "（非实时）" }
            return MenuBarSlot(providerID:id, name:name, percent:percent, state:cached ? "cached" : "known", reason:reason, period:period, measuredAt:measuredAt)

        }
        return slots
    }
}
