import AppKit
import SwiftUI
import Security
import MonitorCore

@MainActor final class APIBalanceStore: ObservableObject {
    @Published var accounts: [APIAccount]
    @Published var snapshot: APIBalanceSnapshot?
    @Published var refreshing=false
    @Published var saving=false
    @Published var message=""
    @Published var editingID: String?
    let servicesEnabled: Bool
    let root = AppRuntime.support.appendingPathComponent("API")
    private var process: Process?
    private var timer: Timer?
    private var lastDispatch = -Double.infinity
    var onChange: (() -> Void)?
    init(servicesEnabled: Bool=true) {
        self.servicesEnabled=servicesEnabled
        if servicesEnabled, let data=try? Data(contentsOf:root.appendingPathComponent("accounts.json")),
           let parsed=try? JSONDecoder().decode([APIAccount].self,from:data), parsed.count<=28 {
            accounts=parsed
        } else { accounts=APIAccount.defaults() }
        guard servicesEnabled else { return }
        if let data=try? Data(contentsOf:root.appendingPathComponent("snapshot.json")) { snapshot=try? JSONDecoder().decode(APIBalanceSnapshot.self,from:data) }
        _=persist()
        if !APIVault.ensureInstalled() { message="API 钥匙串组件待安装，请重新打开 Monitor。" }
        schedule()
    }
    var visible: [APIAccount] { accounts.filter(\.enabled) }
    func observation(_ account: APIAccount) -> APIObservation? {
        snapshot?.accounts.first { $0.id==account.id && $0.context==account.context }
    }
    func persist() -> Bool {
        guard servicesEnabled else { return true }
        do {
            try FileManager.default.createDirectory(at:root,withIntermediateDirectories:true,attributes:[.posixPermissions:0o700])
            let data=try JSONEncoder().encode(accounts)
            let path=root.appendingPathComponent("accounts.json")
            try data.write(to:path,options:.atomic)
            try FileManager.default.setAttributes([.posixPermissions:0o600],ofItemAtPath:path.path)
            return true
        } catch { message="API 设置保存失败；请检查本机目录权限。";return false }
    }
    func move(_ id: String, by offset: Int) {
        guard let from=accounts.firstIndex(where:{$0.id==id}) else { return }
        let to=min(accounts.count-1,max(0,from+offset))
        let item=accounts.remove(at:from);accounts.insert(item,at:to);_=persist();onChange?()
    }
    func move(_ id: String, to target: String) {
        guard let index=accounts.firstIndex(where:{$0.id==id}),let dest=accounts.firstIndex(where:{$0.id==target}),index != dest else { return }
        let item=accounts.remove(at:index);accounts.insert(item,at:dest);_=persist();onChange?()
    }
    func enable(_ id: String,_ value: Bool) {
        guard let i=accounts.firstIndex(where:{$0.id==id}) else { return }
        accounts[i].enabled=value;_=persist();schedule();onChange?()
    }
    func add(_ provider: APIProvider) {
        guard accounts.count<28 else { message="最多显示 28 个 API 账户。";return }
        let a=APIAccount(provider:provider);accounts.append(a);_=persist();editingID=a.id;onChange?()
    }
    func save(_ draft: APIAccount, key: String) async -> Bool {
        guard !saving, accounts.contains(where:{$0.id==draft.id}) else { return false }
        saving=true;defer { saving=false }
        var account=draft
        account.alias=String(account.alias.trimmingCharacters(in:.whitespacesAndNewlines).prefix(40))
        account.projectID=account.projectID.trimmingCharacters(in:.whitespacesAndNewlines)
        if account.projectID.range(of:"^[A-Za-z0-9_-]{0,120}$",options:.regularExpression)==nil { message="项目/工作区 ID 格式不正确。";return false }
        let clean=key.trimmingCharacters(in:.whitespacesAndNewlines)
        if !clean.isEmpty {
            guard clean.utf8.count<=8192,clean.unicodeScalars.allSatisfy({$0.value>=33 && $0.value<=126}) else { message="Key 不能包含空白或换行。";return false }
            let id=account.id
            let status=await Task.detached { APIVault.save(clean,id:id) }.value
            guard status==errSecSuccess else { message="API Key 保存未完成（系统状态 \(status)）。旧值没有显示在界面中。";return false }
            account.credentialRevision=UUID().uuidString
        }
        guard let index=accounts.firstIndex(where:{$0.id==account.id}) else { message="账户已移除，未改写其他账户。";return false }
        accounts[index]=account
        guard persist() else { return false }
        message="已保存。查询余额不会调用模型，冷却期间保留上次读数。"
        onChange?();refresh();return true
    }
    func removeKey(_ id: String) async {
        guard !saving else { return };saving=true;defer { saving=false }
        let ok=await Task.detached { APIVault.remove(id) }.value
        guard ok,let i=accounts.firstIndex(where:{$0.id==id}) else { message="密钥移除未完成。";return }
        accounts[i].credentialRevision="";snapshot?.accounts.removeAll{$0.id==id};_=persist()
        message="已移除该 API Key；查询冷却记录保留。";onChange?()
    }
    func grant(_ id: String) async {
        guard !saving else { return };saving=true;defer { saving=false }
        let ok=await Task.detached { APIVault.grant(id) }.value
        message=ok ? "API 钥匙串授权已验证。" : "API 钥匙串未完成授权。"
        if ok { refresh() }
    }
    func openBilling(_ account: APIAccount) {
        var value=account.provider.billingURL
        if account.region=="global" && account.provider == .kimi { value="https://platform.moonshot.ai/console/account" }
        if account.region=="global" && account.provider == .siliconflow { value="https://cloud.siliconflow.com/account/balance" }
        if let url=URL(string:value) { NSWorkspace.shared.open(url) }
    }
    func schedule() {
        timer?.invalidate()
        guard servicesEnabled,accounts.contains(where:{$0.enabled && $0.configured}) else { return }
        let now=Date().timeIntervalSince1970
        let next=accounts.filter{$0.enabled && $0.configured}.compactMap { observation($0)?.nextQueryAt }.min() ?? now+900
        timer=Timer.scheduledTimer(withTimeInterval:max(30,next-now+1),repeats:false){[weak self] _ in Task { @MainActor in self?.refresh() } }
        timer?.tolerance=10
    }
    func refresh() {
        guard servicesEnabled,!refreshing,ProcessInfo.processInfo.systemUptime-lastDispatch>=3 else { return }
        lastDispatch=ProcessInfo.processInfo.systemUptime
        guard persist(),let script=Bundle.main.resourceURL?.appendingPathComponent("collector/api_monitor.py") else { return }
        let p=Process(),out=Pipe(),capture=PipeCapture()
        guard let python=AppRuntime.pythonExecutable else { message="缺少 Python 运行环境。";return };p.executableURL=python;p.arguments=[script.path]
        var env=AppRuntime.collectorEnvironment();env["MONITOR_API_VAULT"]=APIVault.executable.path;env["PYTHONDONTWRITEBYTECODE"]="1"
        p.environment=env;p.currentDirectoryURL=root;p.standardOutput=out;p.standardError=FileHandle.nullDevice
        p.standardInput=FileHandle.nullDevice;refreshing=true;process=p;onChange?()
        p.terminationHandler={ [weak self] child in
            let data=capture.finish()
            Task { @MainActor in
                guard let self else { return };self.refreshing=false;self.process=nil
                if child.terminationStatus==0,let value=try? JSONDecoder().decode(APIBalanceSnapshot.self,from:data) { self.snapshot=value }
                else {
                    self.message="API 查询未完成（\(child.terminationStatus)），保留上次读数。"
                    if var old=self.snapshot { old.accounts=old.accounts.map { var a=$0;if a.fetchedAt != nil { a.status="stale" };return a };self.snapshot=old }
                }
                self.schedule();self.onChange?()
            }
        }
        do {
            try p.run();capture.start(out.fileHandleForReading)
            DispatchQueue.main.asyncAfter(deadline:.now()+120) { [weak p] in
                guard let p,p.isRunning else{return};p.terminate()
                DispatchQueue.main.asyncAfter(deadline:.now()+3){ if p.isRunning { Darwin.kill(p.processIdentifier,SIGKILL) } }
            }
        } catch { refreshing=false;process=nil;message="无法启动 API 账单采集。";schedule();onChange?() }
    }
    func shutdown() {
        timer?.invalidate()
        guard let p=process,p.isRunning else {return};p.terminate()
        let deadline=Date().addingTimeInterval(3)
        while p.isRunning && Date()<deadline { Thread.sleep(forTimeInterval:0.05) }
        if p.isRunning { Darwin.kill(p.processIdentifier,SIGKILL) }
    }
}
