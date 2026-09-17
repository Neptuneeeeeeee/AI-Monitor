import Foundation

public enum APIProvider: String, Codable, CaseIterable, Identifiable {
    case deepseek, kimi, openai, claude, siliconflow, openrouter, google
    public var id: String { rawValue }
    public var name: String {
        switch self {
        case .deepseek: return "DeepSeek"
        case .kimi: return "Kimi API"
        case .openai: return "OpenAI API"
        case .claude: return "Claude API"
        case .siliconflow: return "SiliconFlow"
        case .openrouter: return "OpenRouter"
        case .google: return "Google AI Studio"
        }
    }
    public var brandID: String { self == .openai ? "codex" : self == .google ? "gemini" : rawValue }
    public var requiresAdmin: Bool { self == .openai || self == .claude }
    public var hasRegions: Bool { self == .kimi || self == .siliconflow }
    public var supportsDailyCost: Bool { [.openai, .claude, .openrouter].contains(self) }
    public var credentialLabel: String { requiresAdmin ? "Admin Key（账单权限）" : "API Key" }
    public var capabilities: String {
        switch self {
        case .deepseek: return "官方接口提供账户余额，不提供今日费用。不会把余额变化当成消费。"
        case .kimi: return "使用 Kimi 开放平台 Key，不是 Kimi Code。支持账户余额；此接口不提供今日费用。"
        case .siliconflow: return "余额按所选中国/国际站查询；接口未提供今日费用。"
        case .openrouter: return "普通 Key：今日费用与 Key 剩余额度；Management Key：账户余额。日统计按 UTC。"
        case .openai: return "需 Admin Key 读取 Costs。默认组织费用，可选项目 ID；不等于单个调用 Key 的消费，不提供钱包余额。"
        case .claude: return "需组织账单权限，建议 Admin Key；个人账户和工作区 Key 不适用。读取组织费用（不含 Priority Tier），不提供钱包余额。"
        case .google: return "Key 只能验证模型列表访问。余额与今日费用需 AI Studio / Cloud Billing 账单权限；本版不抓取浏览器账单。"
        }
    }
    public var billingURL: String {
        switch self {
        case .deepseek: return "https://platform.deepseek.com/usage"
        case .kimi: return "https://platform.moonshot.cn/console/account"
        case .openai: return "https://platform.openai.com/usage"
        case .claude: return "https://platform.claude.com/settings/cost"
        case .siliconflow: return "https://cloud.siliconflow.cn/account/balance"
        case .openrouter: return "https://openrouter.ai/settings/credits"
        case .google: return "https://aistudio.google.com/usage?tab=billing"
        }
    }
}

public struct APIAccount: Codable, Identifiable, Equatable {
    public var id: String
    public var provider: APIProvider
    public var alias = ""
    public var enabled = true
    public var region = "cn"
    public var currency = "USD"
    public var dailyBudget: Double?
    public var balanceReference: Double?
    public var mode = "key"
    public var projectID = ""
    public var credentialRevision = ""
    public init(provider: APIProvider, id: String = UUID().uuidString.lowercased()) {
        self.id = id; self.provider = provider
        currency = [.deepseek, .kimi, .siliconflow].contains(provider) ? "CNY" : "USD"
        mode = provider.requiresAdmin ? "admin" : "key"
    }
    public var configured: Bool { !credentialRevision.isEmpty }
    public var displayName: String { alias.isEmpty ? provider.name : alias }
    public var selectedCurrency: String {
        if provider.hasRegions { return region == "cn" ? "CNY" : "USD" }
        return provider == .deepseek ? currency : "USD"
    }
    public var context: String { [provider.rawValue, region, mode, projectID, selectedCurrency, credentialRevision].joined(separator: "|") }
    public static func defaults() -> [APIAccount] { APIProvider.allCases.map { APIAccount(provider: $0) } }
}

public struct APIObservation: Codable, Identifiable, Equatable {
    public var id: String
    public var context: String
    public var status: String
    public var currency: String
    public var balance: Double?
    public var balanceLabel: String?
    public var dailySpent: Double?
    public var dayUTC: String?
    public var keyLimit: Double?
    public var limitPeriod: String?
    public var fetchedAt: Double?
    public var nextQueryAt: Double?
    public var source: String
    public var message: String
    public init(id: String, context: String = "", status: String = "ok", currency: String = "USD", balance: Double? = nil,
                balanceLabel: String? = nil, dailySpent: Double? = nil, dayUTC: String? = nil, keyLimit: Double? = nil,
                limitPeriod: String? = nil, fetchedAt: Double? = nil, nextQueryAt: Double? = nil, source: String = "", message: String = "") {
        self.id=id; self.context=context; self.status=status; self.currency=currency; self.balance=balance
        self.balanceLabel=balanceLabel; self.dailySpent=dailySpent; self.dayUTC=dayUTC; self.keyLimit=keyLimit
        self.limitPeriod=limitPeriod; self.fetchedAt=fetchedAt; self.nextQueryAt=nextQueryAt; self.source=source; self.message=message
    }
    public static func day(_ date: Date = Date()) -> String {
        let f=DateFormatter(); f.locale=Locale(identifier:"en_US_POSIX"); f.timeZone=TimeZone(secondsFromGMT:0); f.dateFormat="yyyy-MM-dd"
        return f.string(from:date)
    }
    public func spentToday(at date: Date) -> Double? {
        guard dayUTC == Self.day(date), let v = dailySpent, v.isFinite else { return nil }; return v
    }
    public var statusText: String {
        switch status {
        case "ok": return "已连接"
        case "partial": return "部分数据"
        case "stale": return "上次读数"
        case "not_configured": return "待添加 Key"
        case "permission_required": return "需账单权限"
        case "auth_required": return "请检查 Key"
        case "rate_limited": return "查询冷却中"
        case "unsupported": return "账单未接通"
        case "disabled": return "已暂停"
        default: return "暂不可用"
        }
    }
}
public struct APIBalanceSnapshot: Codable {
    public var schemaVersion: Int = 1
    public var generatedAt: Double
    public var accounts: [APIObservation]
    public init(generatedAt: Double, accounts: [APIObservation]) { self.generatedAt=generatedAt; self.accounts=accounts }
}

// Exactly one progress measure per card. A missing numerator/denominator is nil,
// never 0/100. Wallet balance and a local daily budget are not interchangeable.
public struct APICardMetrics {
    public var title: String
    public var left: String
    public var right: String
    public var footnote: String
    public var remainingFraction: Double?
    public var low: Bool
    public var progressMeaning: String
    public init(account: APIAccount, observation: APIObservation?, now: Date = Date()) {
        let o = observation?.context == account.context ? observation : nil
        let currency = o?.currency ?? account.selectedCurrency
        let spent = o?.spentToday(at:now)
        let balance = o?.balance.flatMap { $0.isFinite ? $0 : nil }
        let money: (Double) -> String = { QuotaWindow.money($0, currency: currency) }
        let budget = account.dailyBudget.flatMap { $0.isFinite && $0 > 0 && currency == account.selectedCurrency ? $0 : nil }
        title = "账户余额"; left = balance.map { money($0) + " 可用" } ?? "余额 —"
        right = spent.map { "今日 " + money($0) } ?? "今日消费 —"
        footnote = ""; remainingFraction = nil; low = false; progressMeaning = "暂无比例数据"
        if let spent, let budget {
            title = "今日预算 · 本地"
            left = money(max(0, budget-spent)) + " 剩余"
            remainingFraction = min(1, max(0, (budget-spent)/budget))
            footnote = spent > budget ? "超出预算 " + money(spent-budget) : "日预算 " + money(budget) + " · UTC"
            if let balance { footnote += " · " + (o?.balanceLabel ?? "余额") + " " + money(balance) }
            progressMeaning = "剩余本地日预算 / 本地日预算；不会限制服务商调用"
        } else if let balance {
            title = o?.balanceLabel ?? "账户余额"
            if let cap = o?.keyLimit, cap.isFinite, cap > 0 {
                remainingFraction = min(1,max(0,balance/cap)); footnote = "Key 上限 " + money(cap) + " · " + (o?.limitPeriod ?? "不限周期")
                progressMeaning = "服务商 Key 剩余额度 / Key 限额"
            } else if let reference = account.balanceReference, reference.isFinite, reference > 0, currency == account.selectedCurrency {
                remainingFraction = min(1,max(0,balance/reference)); footnote = "显示基准 " + money(reference) + "（非日预算）"
                progressMeaning = "账户余额 / 本地显示基准，不代表每日额度"
            } else { footnote = "未设置余额显示基准" }
            if spent == nil { right = o?.dayUTC != nil && o?.dayUTC != APIObservation.day(now) ? "今日待更新" : "今日消费未提供" }
        } else if let spent {
            title = "今日费用 · UTC"; left = "余额未提供"; right = money(spent) + " 已用"
            footnote = "设置日预算后显示剩余比例"
        } else {
            title = "API 余额"
            left = account.configured ? "余额 —" : "待添加 Key"
            right = "今日消费 —"
            footnote = account.configured ? (o?.statusText ?? "等待查询") : "在设置中连接账户"
        }
        low = remainingFraction.map { $0 <= 0.2 } ?? (balance.map { $0 <= 0 } ?? false)
    }
}
