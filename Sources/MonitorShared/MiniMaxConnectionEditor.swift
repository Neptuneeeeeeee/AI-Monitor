import AppKit
import SwiftUI
import Security

/// No plaintext credential is persisted in preferences or connection metadata.
struct MiniMaxConnectionEditor: View {
    @ObservedObject var store: MonitorStore
    @State private var key = ""
    @State private var removeConfirmation = false
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Picker("账号区域", selection: Binding(get: { store.minimaxRegion }, set: { store.setMiniMaxRegion($0) })) {
                Text("中国").tag("cn")
                Text("国际").tag("global")
            }.accessibilityIdentifier("minimax.region")
            SecureField("Token Plan 订阅 Key", text: $key)
                .textFieldStyle(.roundedBorder).accessibilityIdentifier("minimax.key").disabled(!store.servicesEnabled)
            HStack {
                Button("保存到钥匙串") {
                    let candidate = key
                    Task { if await store.saveMiniMaxCredential(candidate) { key = "" } }
                }.disabled(!store.servicesEnabled || key.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                    .accessibilityIdentifier("minimax.save")
                Spacer()
                Button("移除本区域 Key") { removeConfirmation = true }
                    .accessibilityIdentifier("minimax.remove").disabled(!store.servicesEnabled)
            }
            Text("只用于查询订阅用量，不调用模型；不会把 Key 尝试发送到另一个区域。保存后仍需在套餐排序中启用 MiniMax。")
                .font(.system(size: 10)).foregroundStyle(MonitorPalette.secondary)
                .fixedSize(horizontal: false, vertical: true)
        }.disabled(store.refreshing || store.savingPlanCredential)
        .onChange(of: store.minimaxRegion) { _, _ in key = "" }
        .confirmationDialog("仅移除当前区域的 MiniMax 订阅 Key？", isPresented: $removeConfirmation) {
            Button("移除 Key", role: .destructive) { Task { _ = await store.saveMiniMaxCredential("") } }
        }
    }
}

extension MonitorStore {
    /// Updating this marker invalidates only MiniMax's cached account context.
    private func invalidateMiniMaxContext(region: String) throws {
        guard ["cn", "global"].contains(region), servicesEnabled else { return }
        let fm = FileManager.default
        try fm.createDirectory(at: support, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
        let metadata: [String: String] = ["minimaxRegion": region, "credentialRevision": UUID().uuidString]
        let path = support.appendingPathComponent("plan-connections.json")
        let data = try JSONSerialization.data(withJSONObject: metadata, options: [.sortedKeys])
        try data.write(to: path, options: .atomic)
        try fm.setAttributes([.posixPermissions: 0o600], ofItemAtPath: path.path)
        // The collector checks the new context before reusing any disk snapshot.
        // Do not clear gates or unrelated provider data, and never modify API accounts.
        snapshot?.providers.removeAll { $0.id == "minimax" }
        onChange?()
    }
    func setMiniMaxRegion(_ region: String) {
        guard ["cn", "global"].contains(region), region != minimaxRegion,
              !refreshing, !savingPlanCredential else { return }
        do {
            try invalidateMiniMaxContext(region: region)
            minimaxRegion = region
            banner = "已选择 MiniMax 区域；两地订阅凭据独立保存。"
        } catch { banner = "MiniMax 区域保存失败，未更改当前连接。" }
    }
    func saveMiniMaxCredential(_ value: String) async -> Bool {
        guard servicesEnabled, !refreshing, !savingPlanCredential else { return false }
        let clean = value.trimmingCharacters(in: .whitespacesAndNewlines)
        guard clean.utf8.count <= 8192, clean.unicodeScalars.allSatisfy({ $0.value >= 33 && $0.value <= 126 }) else {
            banner = "Key 格式无效，不能包含空白或控制字符。"; return false
        }
        savingPlanCredential = true
        defer { savingPlanCredential = false }
        let region = minimaxRegion
        do {
            // Persist invalidation BEFORE credential mutation, including interrupted saves.
            try invalidateMiniMaxContext(region: region)
            let status = await Task.detached { Vault.save(clean, service: "minimax-" + region) }.value
            guard status == errSecSuccess || (clean.isEmpty && status == errSecItemNotFound) else {
                banner = "MiniMax Key 更新未完成（系统状态 \(status)），请重试。"; return false
            }
            banner = clean.isEmpty ? "已移除本区域 MiniMax Key。" : "MiniMax Key 已保存；下次刷新仍遵守原有查询间隔。"
            return true
        } catch { banner = "无法保存连接元数据，未更新 Key。"; return false }
    }
}
