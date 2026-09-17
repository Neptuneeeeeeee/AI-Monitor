import AppKit
import SwiftUI
import MonitorCore

enum MonitorPalette {
    static let background = Color.white
    static let card = Color(red: 0.965, green: 0.965, blue: 0.965)
    static let text = Color(red: 0.16, green: 0.16, blue: 0.17)
    static let secondary = Color(red: 0.48, green: 0.48, blue: 0.49)
    static let track = Color(red: 0.87, green: 0.87, blue: 0.88)
    static let blue = Color(red: 0.0, green: 0.48, blue: 1.0)
    static let red = Color(red: 1.0, green: 0.23, blue: 0.21)
}

struct MonitorPanel: View {
    @ObservedObject var store: MonitorStore
    @ObservedObject var api: APIBalanceStore
    init(store: MonitorStore) { self.store = store; self.api = store.api }
    var body: some View {
        VStack(spacing: 0) {
            HStack(spacing: 4) {
                if store.showSettings {
                    ToolbarButton(symbol: "chevron.left", title: "返回额度", identifier: "toolbar.back") { store.backFromSettings() }
                }
                Text(store.showSettings ? (store.apiMode ? "API 设置" : "设置") : (store.apiMode ? "API 余额" : "AI Monitor")).font(.system(size: 12, weight: .semibold))
                    .padding(.leading, store.showSettings ? 0 : 4)
                if !AppRuntime.profile.badge.isEmpty { Text(AppRuntime.profile.badge).font(.system(size:8,weight:.bold)).padding(.horizontal,4).padding(.vertical,2).background(Capsule().fill(Color.orange.opacity(0.15))) }
                Spacer(minLength: 4)
                if !store.preferences.autoRefresh {
                    Image(systemName: "pause.circle").foregroundStyle(MonitorPalette.secondary).help("自动刷新已暂停")
                }
                ToolbarButton(symbol: "arrow.clockwise", title: "安全刷新 · 冷却中的套餐不重复查询", identifier: "toolbar.refresh", busy: store.apiMode ? api.refreshing : store.refreshing) {
                    store.refreshCurrent()
                }.disabled(store.apiMode ? api.refreshing : store.refreshing)
                Button { store.toggleAPI() } label: {
                    Text(store.apiMode ? "Plan" : "API").font(.system(size:10,weight:.semibold)).frame(width:28,height:28)
                }.buttonStyle(ResponsiveButtonStyle()).background(RoundedRectangle(cornerRadius:6).fill(store.apiMode ? MonitorPalette.blue.opacity(0.10) : Color.clear))
                    .foregroundStyle(store.apiMode ? MonitorPalette.blue : MonitorPalette.secondary)
                    .accessibilityLabel(store.apiMode ? "返回订阅套餐" : "切换 API 余额").accessibilityIdentifier("toolbar.api").help(store.apiMode ? "返回订阅套餐" : "切换 API 余额")
                if !store.showSettings {
                    ToolbarButton(symbol: "gearshape", title: "设置", identifier: "toolbar.settings") { store.openSettings() }
                }
                ToolbarButton(symbol: "xmark", title: "关闭面板", identifier: "toolbar.close") { store.dismissPanel?() }
            }.foregroundStyle(MonitorPalette.secondary).font(.system(size: 12))
                .padding(.horizontal, 10).frame(height: 42)
            if store.showSettings {
                if store.apiMode { APISettingsPanel(api: api) } else { SettingsPanel(store: store) }
            } else if store.apiMode {
                APIBalancePanel(api: api, preferences: store.preferences) { store.openAPISettings($0) }
            } else {
                ScrollView {
                    VStack(spacing: store.preferences.compact ? 15 : 20) {
                        if store.visibleProviders.isEmpty {
                            VStack(spacing: 9) {
                                Text(store.activeProviders.isEmpty ? "尚未启用套餐" : "暂无可显示额度").font(.system(size: 12)).foregroundStyle(MonitorPalette.secondary)
                                Button("管理套餐") { store.openSettings("order") }.font(.system(size: 12)).buttonStyle(ResponsiveButtonStyle())
                            }.padding(.vertical, 50)
                        }
                        ForEach(store.visibleProviders) { info in
                            ProviderSection(info: info, result: store.provider(info.id), store: store)
                        }
                    }.padding(.horizontal, 13).padding(.top, 6).padding(.bottom, 12)
                }.scrollIndicators(.automatic).frame(maxWidth: .infinity, maxHeight: .infinity)
                if store.preferences.showUpdatedAt, let updated = store.snapshot?.generatedAt {
                    HStack { Spacer(); Text("更新于 " + Date(timeIntervalSince1970: updated).formatted(date: .omitted, time: .shortened)).font(.system(size: 10)).foregroundStyle(MonitorPalette.secondary) }
                        .padding(.horizontal, 15).padding(.bottom, 9)
                }
            }
        }
        .frame(width: CGFloat(store.preferences.panelWidth), height: store.panelHeight)
        .background(MonitorPalette.background)
        .foregroundStyle(MonitorPalette.text)
        .environment(\.colorScheme, .light)
        .preferredColorScheme(.light)
    }
}

struct ProviderSection: View {
    let info: ProviderInfo
    let result: ProviderResult?
    @ObservedObject var store: MonitorStore
    private var rows: [QuotaWindow] { result.map { store.preferences.visibleWindows($0) } ?? [] }
    private var stale: Bool { result?.isStale(now: store.now, maxAge: store.staleAge) == true }
    private var brand: BrandStyle { BrandStyle.forID(info.id) }
    var body: some View {
        VStack(alignment: .leading, spacing: 7) {
            HStack(spacing: 6) {
                ProviderLogo(id: info.id, size: 24, enabled: store.preferences.showProviderLogos)
                    .padding(3).background(Color.white).clipShape(RoundedRectangle(cornerRadius: 8))
                Text(info.name).font(.system(size: 15, weight: .semibold))
                if store.preferences.showPlan, let plan = result?.friendlyPlan {
                    Text(plan).font(.system(size: 10, weight: .medium)).foregroundStyle(store.preferences.useBrandColors ? brand.accent : MonitorPalette.secondary).lineLimit(1)
                        .padding(.horizontal, 6).padding(.vertical, 3)
                        .background(store.preferences.useBrandColors ? brand.accent.opacity(0.08) : MonitorPalette.card).clipShape(Capsule())
                }
                Spacer(minLength: 0)
                if stale {
                    Label(result?.lastValueLabel ?? "上次读数", systemImage: "clock").font(.system(size: 9)).foregroundStyle(MonitorPalette.secondary)
                        .help(result?.fetchedAt.map { "最后成功：" + Date(timeIntervalSince1970: $0).formatted() + "；非实时，等待重新查询。" } ?? "尚未重新验证")
                }
            }.padding(.horizontal, 3)
            if !rows.isEmpty {
                VStack(spacing: store.preferences.compact ? 13 : 19) {
                    ForEach(rows) { window in
                        QuotaRow(window: window, preferences: store.preferences, stale: stale, now: store.now, providerID: info.id)
                    }
                }.padding(.horizontal, 11).padding(.vertical, store.preferences.compact ? 11 : 14)
                    .background(store.preferences.useBrandColors ? brand.wash : MonitorPalette.card)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                    .overlay(RoundedRectangle(cornerRadius: 12).strokeBorder(store.preferences.useBrandColors ? brand.accent.opacity(0.10) : Color.clear))
                    .overlay(alignment: .leading) {
                        if store.preferences.useBrandColors {
                            RoundedRectangle(cornerRadius: 2).fill(brand.accent.opacity(0.65)).frame(width: 3).padding(.vertical, 12).allowsHitTesting(false)
                        }
                    }
            } else {
                HStack {
                    VStack(alignment: .leading, spacing: 4) {
                        Text(emptyText).font(.system(size: 11)).foregroundStyle(MonitorPalette.secondary)
                        if let result, result.nextQueryAt != nil {
                            Text(result.queryScheduleText(now: store.now)).font(.system(size: 10)).foregroundStyle(MonitorPalette.secondary)
                        }
                    }
                    Spacer()
                    Button("设置") { store.openSettings("connections") }.buttonStyle(ResponsiveButtonStyle()).font(.system(size: 11)).foregroundStyle(MonitorPalette.blue)
                }.padding(.horizontal, 11).padding(.vertical, 12)
                    .background(store.preferences.useBrandColors ? brand.wash : MonitorPalette.card).clipShape(RoundedRectangle(cornerRadius: 10))
            }
        }
        .contextMenu {
            Button("官方用量") { store.openWebsite(info.id) }
            Button("连接与诊断") { store.openSettings("connections") }
            Divider()
            Button("上移") { store.move(info.id, by: -1) }.disabled(store.orderedProviders.first?.id == info.id)
            Button("下移") { store.move(info.id, by: 1) }.disabled(store.orderedProviders.last?.id == info.id)
            Button("隐藏此套餐") { store.enabled.remove(info.id) }
        }
    }
    private var emptyText: String {
        guard let result else { return store.refreshing ? "正在读取…" : "等待读取" }
        if ["ok", "partial"].contains(result.status), !result.windows.isEmpty { return "额度项目已隐藏" }
        return result.statusLabel
    }
}

struct QuotaRow: View {
    let window: QuotaWindow
    let preferences: DisplayPreferences
    let stale: Bool
    let now: Double
    let providerID: String
    private var brand: BrandStyle { BrandStyle.forWindow(window, providerID: providerID) }
    private var isLow: Bool { window.safePercent.map { $0 <= Double(preferences.lowThreshold) } ?? false }
    private var tint: Color { isLow ? MonitorPalette.red : preferences.useBrandColors ? brand.accent : MonitorPalette.blue }
    var body: some View {
        VStack(alignment: .leading, spacing: 5) {
            HStack(spacing: 5) {
                if providerID == "antigravity" && preferences.showProviderLogos {
                    ProviderLogo(id: brand.id, size: 13)
                }
                Text(window.shortLabel).font(.system(size: preferences.compact ? 12 : 13, weight: .semibold)).lineLimit(1)
                    .help(window.shortLabel)
            }
            if window.isUnlimited != true {
                GeometryReader { proxy in
                    ZStack(alignment: .leading) {
                        Capsule().fill(preferences.useBrandColors ? brand.track : MonitorPalette.track)
                        if let percent = window.safePercent, percent > 0 {
                            Capsule().fill(LinearGradient(colors: [tint, tint.opacity(0.82)], startPoint: .leading, endPoint: .trailing)).opacity(stale ? 0.42 : 1).frame(width: max(1, proxy.size.width * percent / 100))
                        }
                        if preferences.showPaceMarker, let expected = window.expectedRemaining(now: now), window.safePercent != nil {
                            RoundedRectangle(cornerRadius: 1).fill(MonitorPalette.secondary).frame(width: 2, height: 10)
                                .offset(x: min(proxy.size.width - 2, max(0, proxy.size.width * expected / 100 - 1)))
                                .help("按时间均匀使用的参考位置，不是服务商预测")
                        }
                    }
                }.frame(height: 5)
            }
            HStack(alignment: .firstTextBaseline, spacing: 4) {
                Text(window.remainingText(preferences.precision)).fontWeight(.medium).foregroundStyle(isLow ? MonitorPalette.red : MonitorPalette.text).layoutPriority(1)
                Spacer(minLength: 4)
                Text(window.resetText(mode: preferences.resetMode, now: now)).foregroundStyle(MonitorPalette.secondary)
            }.font(.system(size: preferences.compact ? 11 : 12)).monospacedDigit().lineLimit(1)
        }
        .accessibilityElement(children: .combine)
        .help(window.resetAt.map { "重置于 " + Date(timeIntervalSince1970: $0).formatted() } ?? "")
    }
}
