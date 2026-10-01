import AppKit
import SwiftUI
import UniformTypeIdentifiers
import Security
import MonitorCore

struct SettingsPanel: View {
    @ObservedObject var store: MonitorStore
    @State private var clearConfirmation = false
    @State private var resetConfirmation = false
    var body: some View {
        VStack(spacing: 10) {
            Picker(L10n.tr("设置分类"), selection: $store.settingsTab) {
                Text(L10n.tr("套餐排序")).tag("order")
                Text(L10n.tr("显示与刷新")).tag("display")
                Text(L10n.tr("账号连接")).tag("connections")
            }.pickerStyle(.segmented).labelsHidden().controlSize(.regular).frame(minHeight: 30).padding(.horizontal, 13).accessibilityIdentifier("settings.tabs")
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    if store.settingsTab == "order" { ordering }
                    else if store.settingsTab == "display" { displaySettings }
                    else { connections }
                    if !store.banner.isEmpty { Text(L10n.tr(store.banner)).font(.system(size: 11)).foregroundStyle(MonitorPalette.secondary).fixedSize(horizontal: false, vertical: true) }
                }.padding(.horizontal, 13).padding(.bottom, 16)
            }.scrollIndicators(.automatic).frame(maxWidth: .infinity, maxHeight: .infinity)
        }.font(.system(size: 12))
        .confirmationDialog(L10n.tr("只清除额度缓存？登录、Key 与限流等待时间保留。"), isPresented: $clearConfirmation) { Button(L10n.tr("清除额度缓存")) { store.clearQuotaCache() } }
        .confirmationDialog(L10n.tr("恢复默认显示与排序？已启用账号及 Key 保持不变。"), isPresented: $resetConfirmation) { Button(L10n.tr("恢复默认")) { store.resetAppearance() } }
    }
    private var ordering: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(L10n.tr("拖动或用箭头排序；开关决定是否显示并查询。菜单栏按此顺序显示前 {0} 个已启用的套餐。", MenuBarGeometry.maxRows))
                .font(.system(size: 11)).foregroundStyle(MonitorPalette.secondary).fixedSize(horizontal: false, vertical: true)
            VStack(spacing: 5) {
                ForEach(Array(store.orderedProviders.enumerated()), id: \.element.id) { index, info in
                    HStack(spacing: 3) {
                        Image(systemName: "line.3.horizontal").font(.system(size: 11))
                            .foregroundStyle(MonitorPalette.secondary).frame(width: 20, height: 30)
                            .contentShape(Rectangle()).draggable(info.id).help(L10n.tr("拖动以排序"))
                            .accessibilityLabel(L10n.tr("拖动 {0}", info.name)).accessibilityIdentifier("order.drag." + info.id)
                        ProviderLogo(id: info.id, size: 18, enabled: store.preferences.showProviderLogos)
                        Text(info.name).font(.system(size: 12, weight: .medium)).lineLimit(1)
                        Spacer(minLength: 0)
                        Button { store.move(info.id, by: -1) } label: { Image(systemName: "chevron.up").frame(width: 28, height: 30).contentShape(Rectangle()) }
                            .disabled(index == 0).help(L10n.tr("上移")).accessibilityLabel(L10n.tr("上移 {0}", info.name)).accessibilityIdentifier("order.up." + info.id)
                        Button { store.move(info.id, by: 1) } label: { Image(systemName: "chevron.down").frame(width: 28, height: 30).contentShape(Rectangle()) }
                            .disabled(index == store.orderedProviders.count - 1).help(L10n.tr("下移")).accessibilityLabel(L10n.tr("下移 {0}", info.name)).accessibilityIdentifier("order.down." + info.id)
                        Button {
                            if store.enabled.contains(info.id) { store.enabled.remove(info.id) } else { store.enabled.insert(info.id) }
                        } label: { SwitchGlyph(on: store.enabled.contains(info.id)).frame(width: 34, height: 30).contentShape(Rectangle()) }
                            .help(L10n.tr("显示并查询此套餐")).accessibilityLabel(L10n.tr("启用 {0}", info.name))
                            .accessibilityValue(store.enabled.contains(info.id) ? L10n.tr("已开启") : L10n.tr("已关闭")).accessibilityIdentifier("order.enable." + info.id)
                    }.buttonStyle(ResponsiveButtonStyle()).padding(.horizontal, 7).padding(.vertical, 5)
                        .background(MonitorPalette.card).clipShape(RoundedRectangle(cornerRadius: 8))
                        .dropDestination(for: String.self) { items, _ in
                            guard let id = items.first, ProviderInfo.defaultOrder.contains(id) else { return false }
                            store.move(id, to: info.id); return true
                        }
                }
            }
            SettingsGroup("菜单栏预览") {
                HStack(spacing: 12) {
                    Image(nsImage: MenuBarIcon.make(slots: store.iconSlots, style: store.preferences.iconStyle, threshold: store.preferences.lowThreshold))
                        .frame(width: 26, height: 26)
                    VStack(alignment: .leading, spacing: 4) {
                        ForEach(Array(store.iconSlots.enumerated()), id: \.offset) { i, slot in
                            HStack { Text("\(i + 1) · \(slot.name)"); Spacer(); Text(slot.percent.map { String(format: "%.0f%%", $0) } ?? "—").monospacedDigit() }
                        }
                    }.font(.system(size: 10)).foregroundStyle(MonitorPalette.secondary)
                }
                Text(L10n.tr("菜单栏最多 {0} 条横杠，取排序在前的已启用套餐；其余套餐仍在面板中显示。", MenuBarGeometry.maxRows)).font(.system(size: 10)).foregroundStyle(MonitorPalette.secondary)
                Text(L10n.tr("菜单栏按各平台的真实窗口显示：5 小时、月度或每日缓存。已有额度保持清晰实线，缓存时间见悬停提示和面板；虚线表示暂无额度读数。")).font(.system(size: 10)).foregroundStyle(MonitorPalette.secondary)
            }
        }
    }
    private var displaySettings: some View {
        VStack(spacing: 13) {
            SettingsGroup("语言") {
                Picker(L10n.tr("显示语言"), selection: $store.preferences.language) {
                    ForEach(AppLanguage.allCases) { Text($0.nativeName).tag($0.rawValue) }
                }.accessibilityIdentifier("settings.language")
                Text(L10n.tr("品牌、套餐名以及 Session、Weekly 等英文术语保持原样。")).font(.system(size: 10)).foregroundStyle(MonitorPalette.secondary)
            }
            SettingsGroup("外观") {
                Picker(L10n.tr("面板宽度"), selection: $store.preferences.panelWidth) { Text("320").tag(320); Text("340").tag(340); Text("360").tag(360); Text("380").tag(380) }
                Picker(L10n.tr("最大高度"), selection: $store.preferences.maxHeight) { Text("480").tag(480); Text("560").tag(560); Text("620").tag(620); Text("720").tag(720); Text("760").tag(760); Text("860").tag(860); Text("960").tag(960) }
                SettingsToggle("品牌色卡片与进度条", isOn: $store.preferences.useBrandColors)
                SettingsToggle("显示官方品牌标志", isOn: $store.preferences.showProviderLogos)
                SettingsToggle("紧凑间距", isOn: $store.preferences.compact)
                HStack { Text(L10n.tr("菜单栏图标")); Spacer(); Text(L10n.tr("系统黑白")).foregroundStyle(MonitorPalette.secondary) }
                Picker(L10n.tr("百分比精度"), selection: $store.preferences.precision) { Text(L10n.tr("自动")).tag("smart"); Text(L10n.tr("整数")).tag("whole"); Text(L10n.tr("1 位小数")).tag("one") }
                Picker(L10n.tr("重置时间"), selection: $store.preferences.resetMode) { Text(L10n.tr("倒计时")).tag("relative"); Text(L10n.tr("具体时间")).tag("absolute"); Text(L10n.tr("隐藏")).tag("hidden") }
                SettingsToggle("显示套餐名称", isOn: $store.preferences.showPlan)
                SettingsToggle("显示最后更新时间", isOn: $store.preferences.showUpdatedAt)
                Text(L10n.tr("额度面板固定为白色；单色图标仍随系统菜单栏明暗变化。")).font(.system(size: 10)).foregroundStyle(MonitorPalette.secondary)
            }
            SettingsGroup("显示哪些额度") {
                SettingsToggle("Session · 5 小时", isOn: $store.preferences.showSession)
                SettingsToggle("Weekly · 每周", isOn: $store.preferences.showWeekly)
                SettingsToggle("Extra Usage · 额外预算", isOn: $store.preferences.showExtra)
                SettingsToggle("其他官方计费窗口", isOn: $store.preferences.showOther)
                SettingsToggle("各模型的独立额度", isOn: $store.preferences.showModelWindows)
                SettingsToggle("不限量项目", isOn: $store.preferences.showUnlimited)
                SettingsToggle("尚未连接的套餐", isOn: $store.preferences.showUnavailable)
            }
            SettingsGroup("低余量与参考线") {
                Picker(L10n.tr("变红阈值"), selection: $store.preferences.lowThreshold) { Text("10%").tag(10); Text("20%").tag(20); Text("25%").tag(25); Text("30%").tag(30); Text("50%").tag(50) }
                SettingsToggle("显示按时间均匀使用参考线", isOn: $store.preferences.showPaceMarker)
                Text(L10n.tr("参考线不是耗尽预测。不会凭几个读数推算还可用多少 token。")).font(.system(size: 10)).foregroundStyle(MonitorPalette.secondary)
            }
            SettingsGroup("刷新与启动") {
                SettingsToggle("自动刷新", isOn: $store.preferences.autoRefresh)
                Picker(L10n.tr("查询最小间隔"), selection: $store.refreshSeconds) { Text(L10n.tr("5 分钟")).tag(300); Text(L10n.tr("10 分钟")).tag(600); Text(L10n.tr("15 分钟")).tag(900); Text(L10n.tr("30 分钟")).tag(1800) }
                Text(L10n.tr("Claude、Copilot、Cursor、MiniMax、ClinePass 至少 10 分钟，Kiro 至少 15 分钟，其余至少 5 分钟。手动刷新不绕过限流等待。"))
                    .font(.system(size: 10)).foregroundStyle(MonitorPalette.secondary).fixedSize(horizontal: false, vertical: true)
                SettingsToggle("打开面板时更新过期数据", isOn: $store.preferences.refreshOnOpen)
                SettingsToggle("Mac 唤醒后刷新", isOn: $store.preferences.refreshOnWake)
                SettingsToggle("点击外部时保持面板", isOn: $store.preferences.keepPopoverOpen)
                SettingsToggle("登录 Mac 时启动", isOn: Binding(get: { store.launchAtLogin }, set: { store.toggleLogin($0) }))
            }
            Button(L10n.tr("恢复默认显示与排序")) { resetConfirmation = true }.font(.system(size: 11)).buttonStyle(ResponsiveButtonStyle())
        }.toggleStyle(.switch).controlSize(.small)
    }
    private var connections: some View {
        VStack(spacing: 13) {
            SettingsGroup("登录状态") {
                Text(L10n.tr("仅在你启用后读取对应官方客户端或已保存的订阅凭据，不自动改变系统权限。缓存、估计与服务商实际窗口会分别标明。"))
                    .font(.system(size:10)).foregroundStyle(MonitorPalette.secondary).fixedSize(horizontal:false, vertical:true)
                ForEach(store.orderedProviders) { info in
                    DisclosureGroup {
                        VStack(alignment: .leading, spacing: 7) {
                            Text(info.connectionHint).fixedSize(horizontal: false, vertical: true)
                            if info.id == "minimax" { MiniMaxConnectionEditor(store: store) }
                            if info.id == "glm" { Picker(L10n.tr("账号区域"), selection: $store.glmRegion) { Text(L10n.tr("中国 BigModel")).tag("cn"); Text(L10n.tr("国际 Z.ai")).tag("global") } }
                            if let result = store.provider(info.id) {
                                Text(result.queryScheduleText(now: store.now))
                                if let fetched = result.fetchedAt { Text(L10n.tr("上次成功：{0}", Date(timeIntervalSince1970: fetched).formatted(date: .omitted, time: .standard))) }
                                if !result.source.isEmpty { Text(L10n.tr(result.source)) }
                                if !result.message.isEmpty { Text(L10n.tr(result.message)) }
                                if let note = result.note { Text(L10n.tr(note)) }
                            } else { Text(L10n.tr("尚未查询，启用套餐后刷新。")) }
                            HStack {
                                Button(info.id == "claude" ? L10n.tr("检查 Claude 读取") : info.id == "antigravity" ? L10n.tr("打开应用") : L10n.tr("连接")) { store.reconnect(info.id) }
                                if info.id == "claude" && store.provider("claude")?.status == "auth_required" {
                                    Button(L10n.tr("重新登录")) { store.renewClaudeLogin() }
                                }
                                Spacer(); Button(L10n.tr("官方用量 ↗")) { store.openWebsite(info.id) }
                            }
                        }.font(.system(size: 10)).foregroundStyle(MonitorPalette.secondary).padding(.top, 5)
                    } label: {
                        HStack { Text(info.name); Spacer(); Text(store.provider(info.id)?.statusLabel ?? L10n.tr("未查询")).font(.system(size: 10)).foregroundStyle(MonitorPalette.secondary) }
                    }
                }
                Button(L10n.tr("重新检查连接")) { store.refresh(force: true) }.disabled(store.refreshing)
            }
            SettingsGroup("本机数据") {
                Button(L10n.tr("导出脱敏诊断…")) { store.diagnostic() }
                Button(L10n.tr("打开数据目录")) { store.openDataDirectory() }
                Button(L10n.tr("清除额度缓存…")) { clearConfirmation = true }.disabled(store.refreshing)
                Text(L10n.tr("没有遥测，不解析或上传聊天内容。仅在启用后读取对应应用的指定状态；MiniMax 订阅 Key 保存在本机钥匙串，凭证只发给所属服务商。")).font(.system(size: 10)).foregroundStyle(MonitorPalette.secondary)
            }
            HStack {
                Text("AI Monitor \(AppRuntime.profile.version) · " + (AppRuntime.profile.channel == "local" ? "Local" : L10n.tr("公开版候选"))).font(.system(size: 10)).foregroundStyle(MonitorPalette.secondary)
                Spacer()
                Button(L10n.tr("退出 AI Monitor")) { NSApp.terminate(nil) }
            }
        }.controlSize(.regular).buttonStyle(ResponsiveButtonStyle())
    }

}

struct SettingsGroup<Content: View>: View {
    let title: String
    let content: () -> Content
    init(_ title: String, @ViewBuilder content: @escaping () -> Content) { self.title = title; self.content = content }
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(L10n.tr(title)).font(.system(size: 11, weight: .semibold)).foregroundStyle(MonitorPalette.secondary)
            VStack(alignment: .leading, spacing: 10, content: content)
                .frame(maxWidth: .infinity, alignment: .leading).padding(11)
                .background(MonitorPalette.card).clipShape(RoundedRectangle(cornerRadius: 10))
        }
    }
}
