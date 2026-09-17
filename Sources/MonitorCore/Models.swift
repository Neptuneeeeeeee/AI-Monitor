import Foundation

public struct QuotaWindow: Codable, Identifiable, Equatable {
    public var id: String
    public var label: String
    public var remainingPercent: Double?
    public var resetAt: Double?
    public var durationMinutes: Double?
    public var unit: String?
    public var remaining: Double?
    public var limit: Double?
    public var isUnlimited: Bool?
    public var kind: String?
    public var currency: String?
    public init(id: String, label: String, remainingPercent: Double? = nil, resetAt: Double? = nil,
                durationMinutes: Double? = nil, unit: String? = nil, remaining: Double? = nil,
                limit: Double? = nil, isUnlimited: Bool? = nil, kind: String? = nil, currency: String? = nil) {
        self.id = id; self.label = label; self.remainingPercent = remainingPercent; self.resetAt = resetAt
        self.durationMinutes = durationMinutes; self.unit = unit; self.remaining = remaining; self.limit = limit
        self.isUnlimited = isUnlimited; self.kind = kind; self.currency = currency
    }
    public var isExtra: Bool { kind == "extra" || id == "extra_usage" }
    public var isScoped: Bool { kind == "model" || id.hasPrefix("seven_day_") || id.hasPrefix("model-") }
    public var shortLabel: String {
        if isExtra { return "Extra Usage" }
        if id.hasPrefix("seven_day_") { return "Weekly · " + id.replacingOccurrences(of: "seven_day_", with: "").replacingOccurrences(of: "_", with: " ").capitalized }
        if durationMinutes == 300 { return id.hasPrefix("group-") ? label.replacingOccurrences(of: "Claude / GPT", with: "Claude") : "Session" }
        if durationMinutes == 10080 { return id.hasPrefix("group-") ? label.replacingOccurrences(of: "Claude / GPT", with: "Claude") : "Weekly" }
        return label.replacingOccurrences(of: " · 计费周期", with: "").replacingOccurrences(of: "当前 ", with: "")
    }
    public var safePercent: Double? {
        guard isUnlimited != true, let p = remainingPercent, p.isFinite, p >= 0, p <= 100 else { return nil }
        return p
    }
    public func percentText(_ precision: String = "smart") -> String {
        guard let p = safePercent else { return isUnlimited == true ? "不限量" : "—" }
        let decimal = precision == "one" || (precision == "smart" && abs(p - p.rounded()) > 0.05)
        if precision == "whole" && p > 0 && p < 1 { return "<1%" }
        return String(format: decimal ? "%.1f%%" : "%.0f%%", p)
    }
    public func remainingText(_ precision: String = "smart") -> String {
        if isUnlimited == true { return "不限量" }
        if isExtra, let amount = remaining, amount.isFinite, let currency {
            return Self.money(max(0, amount), currency: currency) + " 剩余"
        }
        return safePercent == nil ? "—" : percentText(precision) + " 剩余"
    }
    public static func money(_ amount: Double, currency: String) -> String {
        let f = NumberFormatter(); f.locale = Locale(identifier: "en_US"); f.numberStyle = .currency
        f.currencyCode = currency; f.minimumFractionDigits = 2; f.maximumFractionDigits = 2
        return f.string(from: NSNumber(value: amount)) ?? String(format: "%@ %.2f", currency, amount)
    }
    public func resetText(mode: String = "relative", now: Double = Date().timeIntervalSince1970) -> String {
        if isExtra, let limit, let currency { return Self.money(limit, currency: currency) + " 上限" }
        guard mode != "hidden", let resetAt, resetAt.isFinite else { return "" }
        if resetAt <= now { return "等待重置确认" }
        if mode == "absolute" {
            let f = DateFormatter(); f.locale = Locale(identifier: "zh_CN"); f.dateFormat = "M/d HH:mm"
            return f.string(from: Date(timeIntervalSince1970: resetAt)) + " 重置"
        }
        let minutes = max(1, Int(ceil((resetAt - now) / 60)))
        if minutes >= 1440 { return "\(minutes / 1440)d \((minutes % 1440) / 60)h 后重置" }
        if minutes >= 60 { return "\(minutes / 60)h \(minutes % 60)m 后重置" }
        return "\(minutes)m 后重置"
    }
    // A pacing reference, NOT a forecast of future consumption or provider policy.
    public func expectedRemaining(now: Double) -> Double? {
        guard !isExtra, let resetAt, let durationMinutes, durationMinutes > 0 else { return nil }
        let ratio = (resetAt - now) / (durationMinutes * 60)
        guard ratio >= 0, ratio <= 1, ratio.isFinite else { return nil }
        return ratio * 100
    }
}

public struct ProviderResult: Codable, Identifiable, Equatable {
    public var id: String
    public var name: String
    public var status: String
    public var source: String
    public var message: String
    public var plan: String?
    public var fetchedAt: Double?
    public var attemptedAt: Double?
    public var windows: [QuotaWindow]
    public var note: String?
    public var liveStatus: String?
    public var historical: Bool?
    public var nextQueryAt: Double?
    public var pollIntervalSeconds: Double?
    public var queryStatus: String?
    public init(id: String, name: String, status: String = "ok", source: String = "", message: String = "", plan: String? = nil,
                fetchedAt: Double? = nil, attemptedAt: Double? = nil, windows: [QuotaWindow] = [], note: String? = nil,
                nextQueryAt: Double? = nil, pollIntervalSeconds: Double? = nil, queryStatus: String? = nil, liveStatus: String? = nil, historical: Bool? = nil) {
        self.id = id; self.name = name; self.status = status; self.source = source; self.message = message
        self.plan = plan; self.fetchedAt = fetchedAt; self.attemptedAt = attemptedAt; self.windows = windows; self.note = note
        self.liveStatus = liveStatus; self.historical = historical
        self.nextQueryAt = nextQueryAt; self.pollIntervalSeconds = pollIntervalSeconds; self.queryStatus = queryStatus
    }
    public var statusLabel: String {
        switch status {
        case "ok": return "已连接"
        case "partial": return "部分数据"
        case "stale": return "上次读数"
        case "auth_required": return "需要登录"
        case "permission_required": return "需要授权"
        case "network_error": return "暂时离线"
        case "rate_limited": return "查询冷却中"
        case "unsupported": return "未提供额度"
        case "unavailable": return "未就绪"
        default: return "待检查"
        }
    }
    public var lastValueLabel: String {
        guard let fetchedAt else { return "暂无历史数据" }
        let f = DateFormatter(); f.locale = Locale(identifier:"zh_CN"); f.dateFormat = "M/d HH:mm"
        return "上次 " + f.string(from: Date(timeIntervalSince1970:fetchedAt))
    }
    public func queryScheduleText(now: Double) -> String {
        guard let deadline = nextQueryAt, deadline.isFinite else { return "" }
        if deadline <= now { return "等待下次检查" }
        let date = Date(timeIntervalSince1970: deadline)
        let format = DateFormatter(); format.locale = Locale(identifier: "zh_CN"); format.dateFormat = "HH:mm"
        return "下次可查询 " + format.string(from: date)
    }
    public func queryWaitingText(now: Double) -> String {
        guard let deadline = nextQueryAt, deadline.isFinite, deadline > now else { return statusLabel }
        let minutes = max(1, Int(ceil((deadline - now) / 60)))
        return (queryStatus == "cooldown" ? "查询暂停 · " : "更新间隔 · ") + "约\(minutes)分钟后可查询"
    }
    public var friendlyPlan: String? {
        guard let text = plan?.trimmingCharacters(in: .whitespacesAndNewlines), !text.isEmpty, !text.hasPrefix("LEVEL_") else { return nil }
        let names = ["pro":"Pro", "max":"Max", "free":"Free", "team":"Team", "enterprise":"Enterprise", "individual":"个人", "plus":"Plus"]
        return names[text.lowercased()] ?? text.replacingOccurrences(of: "_", with: " ").capitalized
    }
    public func isStale(now: Double, maxAge: Double) -> Bool {
        let interval = pollIntervalSeconds.flatMap { $0.isFinite && $0 > 0 ? $0 : nil } ?? 0
        return status == "stale" || fetchedAt.map { now - $0 > max(maxAge, interval + 120) } == true
    }
}

public struct Snapshot: Codable, Equatable {
    public var schemaVersion: Int
    public var generatedAt: Double
    public var providers: [ProviderResult]
    public init(schemaVersion: Int = 1, generatedAt: Double, providers: [ProviderResult]) {
        self.schemaVersion = schemaVersion; self.generatedAt = generatedAt; self.providers = providers
    }
}

public struct ProviderInfo: Identifiable, Equatable {
    public let id: String
    public let name: String
    public let symbol: String
    public let website: String
    public static let all = [
        ProviderInfo(id: "kimi", name: "Kimi", symbol: "moon.stars", website: "https://www.kimi.com/code/console"),
        ProviderInfo(id: "codex", name: "Codex", symbol: "terminal", website: "https://chatgpt.com/codex/settings/usage"),
        ProviderInfo(id: "claude", name: "Claude", symbol: "sun.max", website: "https://claude.ai/settings/usage"),
        ProviderInfo(id: "glm", name: "GLM", symbol: "square.stack.3d.up", website: "https://bigmodel.cn/coding-plan/personal/usage"),
        ProviderInfo(id: "copilot", name: "Copilot", symbol: "chevron.left.forwardslash.chevron.right", website: "https://github.com/settings/billing"),
        ProviderInfo(id: "antigravity", name: "Antigravity", symbol: "a.circle", website: "https://antigravity.google/")
    ]
    public static var defaultOrder: [String] { all.map(\.id) }
}
