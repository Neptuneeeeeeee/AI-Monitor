import Foundation
import MonitorCore

extension MonitorCoreTests {
    func withCatalog(_ language: String, _ body: () -> Void) {
        let catalog = URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
            .appendingPathComponent("Resources/Localization/Localizable.json")
        do { try L10n.load(from: catalog) } catch { checkTrue(false); return }
        L10n.setLanguage(language)
        defer { L10n.setLanguage("zh-Hans") }
        body()
    }
    func testLanguageResolution() {
        checkEqual(AppLanguage.resolve("system", preferred: ["zh-Hans-US", "en-US"]), .zhHans)
        checkEqual(AppLanguage.resolve("system", preferred: ["zh-Hant-TW"]), .zhHant)
        checkEqual(AppLanguage.resolve("system", preferred: ["zh-HK"]), .zhHant)
        checkEqual(AppLanguage.resolve("system", preferred: ["pt-PT"]), .ptBR)
        checkEqual(AppLanguage.resolve("system", preferred: ["el-GR", "de-DE"]), .de)
        checkEqual(AppLanguage.resolve("system", preferred: ["el-GR"]), .en)
        checkEqual(AppLanguage.resolve("ja", preferred: ["fr-FR"]), .ja)
        checkEqual(AppLanguage.resolve("unknown", preferred: ["ko-KR"]), .ko)
        checkEqual(AppLanguage.allCases.count, 10)
    }
    func testLanguagePreferenceDefaultsToSystem() {
        var p = DisplayPreferences(); checkEqual(p.language, "system")
        p.language = "xx"; p.normalize(); checkEqual(p.language, "system")
        p.language = "pt-BR"; p.normalize(); checkEqual(p.language, "pt-BR")
    }
    func testEnglishTranslatesStatusButKeepsUpstreamTerms() {
        withCatalog("en") {
            checkEqual(ProviderResult(id: "kimi", name: "Kimi", status: "ok").statusLabel, "Connected")
            checkEqual(QuotaWindow(id: "five_hour", label: "当前 5 小时", durationMinutes: 300).shortLabel, "Session")
            checkEqual(QuotaWindow(id: "seven_day", label: "每周 · 全部模型", durationMinutes: 10080).shortLabel, "Weekly")
            checkEqual(QuotaWindow(id: "premium_interactions", label: "Premium · 每月", kind: "monthly").shortLabel, "Premium · Monthly")
            checkEqual(QuotaWindow(id: "x", label: "y", remainingPercent: 63).remainingText(), "63% left")
            checkEqual(L10n.tr("ClinePass"), "ClinePass")
        }
    }
    func testCollectorTextIsTranslatedFromItsParts() {
        withCatalog("en") {
            checkEqual(QuotaWindow(id: "minimax-0-5h", label: "general · 当前窗口").shortLabel, "general · current window")
            checkEqual(L10n.tr("30 天窗口"), "30-day window")
            checkEqual(L10n.tr("套餐 Credits · 本月（官方估计）"), "Plan Credits · this month (official estimate)")
            checkEqual(L10n.tr("额度接口返回 HTTP 418，未记录响应正文。"), "The quota endpoint returned HTTP 418; the response body was not logged.")
            checkEqual(L10n.tr("上次成功读数，非实时。当前账号尚未重新验证。"), "Last successful reading, not live. The current account has not been re-verified yet.")
            checkEqual(L10n.tr("未知的新消息"), "未知的新消息")
        }
        withCatalog("ja") { checkEqual(L10n.tr("套餐 · 本月（官方估计）"), "プラン · 今月（公式推定）") }
    }
    func testMenuReasonFollowsLanguage() {
        withCatalog("de") {
            let reason = slots([provider("kimi", percent: 40)])[0].reason
            checkEqual(reason, "5-Stunden-Fenster übrig")
        }
        checkEqual(slots([provider("kimi", percent: 40)])[0].reason, "5 小时剩余")
    }
}
