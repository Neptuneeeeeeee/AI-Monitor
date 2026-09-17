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
            Picker("设置分类", selection: $store.settingsTab) {
                Text("套餐排序").tag("order")
                Text("显示与刷新").tag("display")
                Text("账号连接").tag("connections")
            }.pickerStyle(.segmented).labelsHidden().controlSize(.regular).frame(minHeight: 30).padding(.horizontal, 13).accessibilityIdentifier("settings.tabs")
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    if store.settingsTab == "order" { ordering }
                    else if store.settingsTab == "display" { displaySettings }
                    else { connections }
                    if !store.banner.isEmpty { Text(store.banner).font(.system(size: 11)).foregroundStyle(MonitorPalette.secondary).fixedSize(horizontal: false, vertical: true) }
                }.padding(.horizontal, 13).padding(.bottom, 16)
            }.scrollIndicators(.automatic).frame(maxWidth: .infinity, maxHeight: .infinity)
        }.font(.system(size: 12))
        .confirmationDialog("只清除额度缓存？登录、Key 与限流等待时间保留。", isPresented: $clearConfirmation) { Button("清除额度缓存") { store.clearQuotaCache() } }
        .confirmationDialog("恢复默认显示与排序？已启用账号及 Key 保持不变。", isPresented: $resetConfirmation) { Button("恢复默认") { store.resetAppearance() } }
    }
    private var ordering: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("拖动或用箭头排序。启用几个套餐，菜单栏就显示几条横杠，顺序从上到下一致。")
                .font(.system(size: 11)).foregroundStyle(MonitorPalette.secondary).fixedSize(horizontal: false, vertical: true)
            VStack(spacing: 5) {
                ForEach(Array(store.orderedProviders.enumerated()), id: \.element.id) { index, info in
                    HStack(spacing: 3) {
                        Image(systemName: "line.3.horizontal").font(.system(size: 11))
                            .foregroundStyle(MonitorPalette.secondary).frame(width: 20, height: 30)
                            .contentShape(Rectangle()).draggable(info.id).help("拖动以排序")
                            .accessibilityLabel("拖动 " + info.name).accessibilityIdentifier("order.drag." + info.id)
                        ProviderLogo(id: info.id, size: 18, enabled: store.preferences.showProviderLogos)
                        Text(info.name).font(.system(size: 12, weight: .medium)).lineLimit(1)
                        Spacer(minLength: 0)
                        if let row = store.activeProviders.firstIndex(where: { $0.id == info.id }) {
                            Text("杠 \(row + 1)").font(.system(size: 9)).foregroundStyle(MonitorPalette.secondary)
                        }
                        Button { store.move(info.id, by: -1) } label: { Image(systemName: "chevron.up").frame(width: 28, height: 30).contentShape(Rectangle()) }
                            .disabled(index == 0).help("上移").accessibilityLabel("上移 " + info.name).accessibilityIdentifier("order.up." + info.id)
                        Button { store.move(info.id, by: 1) } label: { Image(systemName: "chevron.down").frame(width: 28, height: 30).contentShape(Rectangle()) }
                            .disabled(index == store.orderedProviders.count - 1).help("下移").accessibilityLabel("下移 " + info.name).accessibilityIdentifier("order.down." + info.id)
                        Button {
                            if store.enabled.contains(info.id) { store.enabled.remove(info.id) } else { store.enabled.insert(info.id) }
                        } label: { SwitchGlyph(on: store.enabled.contains(info.id)).frame(width: 34, height: 30).contentShape(Rectangle()) }
                            .help("显示并查询此套餐").accessibilityLabel("启用 " + info.name)
                            .accessibilityValue(store.enabled.contains(info.id) ? "已开启" : "已关闭").accessibilityIdentifier("order.enable." + info.id)
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
                Text("菜单栏按各平台的真实窗口显示：5 小时、月度或每日缓存，不将月额度假装成 Session。浅色实线表示缓存。").font(.system(size: 10)).foregroundStyle(MonitorPalette.secondary)
            }
        }
    }
    private var displaySettings: some View {
        VStack(spacing: 13) {
            SettingsGroup("外观") {
                Picker("面板宽度", selection: $store.preferences.panelWidth) { Text("320").tag(320); Text("340").tag(340); Text("360").tag(360); Text("380").tag(380) }
                Picker("最大高度", selection: $store.preferences.maxHeight) { Text("480").tag(480); Text("560").tag(560); Text("620").tag(620); Text("720").tag(720); Text("760").tag(760); Text("860").tag(860); Text("960").tag(960) }
                SettingsToggle("品牌色卡片与进度条", isOn: $store.preferences.useBrandColors)
                SettingsToggle("显示官方品牌标志", isOn: $store.preferences.showProviderLogos)
                SettingsToggle("紧凑间距", isOn: $store.preferences.compact)
                HStack { Text("菜单栏图标"); Spacer(); Text("系统黑白").foregroundStyle(MonitorPalette.secondary) }
                Picker("百分比精度", selection: $store.preferences.precision) { Text("自动").tag("smart"); Text("整数").tag("whole"); Text("1 位小数").tag("one") }
                Picker("重置时间", selection: $store.preferences.resetMode) { Text("倒计时").tag("relative"); Text("具体时间").tag("absolute"); Text("隐藏").tag("hidden") }
                SettingsToggle("显示套餐名称", isOn: $store.preferences.showPlan)
                SettingsToggle("显示最后更新时间", isOn: $store.preferences.showUpdatedAt)
                Text("额度面板固定为白色；单色图标仍随系统菜单栏明暗变化。").font(.system(size: 10)).foregroundStyle(MonitorPalette.secondary)
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
                Picker("变红阈值", selection: $store.preferences.lowThreshold) { Text("10%").tag(10); Text("20%").tag(20); Text("25%").tag(25); Text("30%").tag(30); Text("50%").tag(50) }
                SettingsToggle("显示按时间均匀使用参考线", isOn: $store.preferences.showPaceMarker)
                Text("参考线不是耗尽预测。不会凭几个读数推算还可用多少 token。").font(.system(size: 10)).foregroundStyle(MonitorPalette.secondary)
            }
            SettingsGroup("刷新与启动") {
                SettingsToggle("自动刷新", isOn: $store.preferences.autoRefresh)
                Picker("查询最小间隔", selection: $store.refreshSeconds) { Text("5 分钟").tag(300); Text("10 分钟").tag(600); Text("15 分钟").tag(900); Text("30 分钟").tag(1800) }
                Text("Claude、Copilot、Cursor、MiniMax 至少 10 分钟，Kiro 至少 15 分钟，其余至少 5 分钟。手动刷新不绕过限流等待。")
                    .font(.system(size: 10)).foregroundStyle(MonitorPalette.secondary).fixedSize(horizontal: false, vertical: true)
                SettingsToggle("打开面板时更新过期数据", isOn: $store.preferences.refreshOnOpen)
                SettingsToggle("Mac 唤醒后刷新", isOn: $store.preferences.refreshOnWake)
                SettingsToggle("点击外部时保持面板", isOn: $store.preferences.keepPopoverOpen)
                SettingsToggle("登录 Mac 时启动", isOn: Binding(get: { store.launchAtLogin }, set: { store.toggleLogin($0) }))
            }
            Button("恢复默认显示与排序") { resetConfirmation = true }.font(.system(size: 11)).buttonStyle(ResponsiveButtonStyle())
        }.toggleStyle(.switch).controlSize(.small)
    }
    private var connections: some View {
        VStack(spacing: 13) {
            SettingsGroup("登录状态") {
                Text("仅在你启用后读取对应官方客户端或已保存的订阅凭据，不自动改变系统权限。缓存、估计与服务商实际窗口会分别标明。")
                    .font(.system(size:10)).foregroundStyle(MonitorPalette.secondary).fixedSize(horizontal:false, vertical:true)
                ForEach(store.orderedProviders) { info in
                    DisclosureGroup {
                        VStack(alignment: .leading, spacing: 7) {
                            Text(info.connectionHint).fixedSize(horizontal: false, vertical: true)
                            if info.id == "minimax" { MiniMaxConnectionEditor(store: store) }
                            if info.id == "glm" { Picker("账号区域", selection: $store.glmRegion) { Text("中国 BigModel").tag("cn"); Text("国际 Z.ai").tag("global") } }
                            if let result = store.provider(info.id) {
                                Text(result.queryScheduleText(now: store.now))
                                if let fetched = result.fetchedAt { Text("上次成功：" + Date(timeIntervalSince1970: fetched).formatted(date: .omitted, time: .standard)) }
                                if !result.source.isEmpty { Text(result.source) }
                                if !result.message.isEmpty { Text(result.message) }
                                if let note = result.note { Text(note) }
                            } else { Text("尚未查询，启用套餐后刷新。") }
                            HStack {
                                Button(info.id == "claude" ? "检查 Claude 读取" : info.id == "antigravity" ? "打开应用" : "连接") { store.reconnect(info.id) }
                                Spacer(); Button("官方用量 ↗") { store.openWebsite(info.id) }
                            }
                        }.font(.system(size: 10)).foregroundStyle(MonitorPalette.secondary).padding(.top, 5)
                    } label: {
                        HStack { Text(info.name); Spacer(); Text(store.provider(info.id)?.statusLabel ?? "未查询").font(.system(size: 10)).foregroundStyle(MonitorPalette.secondary) }
                    }
                }
                Button("重新检查连接") { store.refresh(force: true) }.disabled(store.refreshing)
            }
            SettingsGroup("本机数据") {
                Button("导出脱敏诊断…") { store.diagnostic() }
                Button("打开数据目录") { store.openDataDirectory() }
                Button("清除额度缓存…") { clearConfirmation = true }.disabled(store.refreshing)
                Text("没有遥测，不解析或上传聊天内容。仅在启用后读取对应应用的指定状态；Key 保存在本机钥匙串，凭证只发给所属服务商。").font(.system(size: 10)).foregroundStyle(MonitorPalette.secondary)
            }
            HStack {
                Text("AI Monitor \(AppRuntime.profile.version) · \(AppRuntime.profile.channel == "local" ? "Local" : "公开版候选")").font(.system(size: 10)).foregroundStyle(MonitorPalette.secondary)
                Spacer()
                Button("退出 AI Monitor") { NSApp.terminate(nil) }
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
            Text(title).font(.system(size: 11, weight: .semibold)).foregroundStyle(MonitorPalette.secondary)
            VStack(alignment: .leading, spacing: 10, content: content)
                .frame(maxWidth: .infinity, alignment: .leading).padding(11)
                .background(MonitorPalette.card).clipShape(RoundedRectangle(cornerRadius: 10))
        }
    }
}
