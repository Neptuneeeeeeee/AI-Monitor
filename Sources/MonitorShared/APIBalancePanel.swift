import SwiftUI
import AppKit
import MonitorCore

struct APIBalancePanel: View {
    @ObservedObject var api: APIBalanceStore
    let preferences: DisplayPreferences
    let configure: (String?) -> Void
    var body: some View {
        ScrollView {
            VStack(spacing:14) {
                HStack {
                    Text("今日费用按 UTC · 余额为账户当前可用金额").font(.system(size:9)).foregroundStyle(MonitorPalette.secondary)
                    Spacer(minLength:0)
                }.padding(.horizontal,3)
                if api.visible.isEmpty {
                    VStack(spacing:12) {
                        Image(systemName:"creditcard").font(.system(size:24)).foregroundStyle(MonitorPalette.secondary)
                        Text("还没有启用 API 账户").font(.system(size:12))
                        Button("添加 API 账户") { configure(nil) }.buttonStyle(ResponsiveButtonStyle())
                    }.frame(maxWidth:.infinity).padding(.vertical,40)
                }
                ForEach(api.visible) { account in
                    APIBalanceCard(account:account, observation:api.observation(account),preferences:preferences) { configure(account.id) }
                        .contextMenu {
                            Button("账户设置") {configure(account.id)}
                            Button("官方账单 ↗") {api.openBilling(account)}
                            Button("隐藏此账户") {api.enable(account.id,false)}
                        }
                }
            }.padding(.horizontal,13).padding(.top,5).padding(.bottom,16)
        }.scrollIndicators(.automatic).frame(maxWidth:.infinity,maxHeight:.infinity)
    }
}

struct APIBalanceCard: View {
    let account: APIAccount
    let observation: APIObservation?
    let preferences: DisplayPreferences
    let configure: () -> Void
    private var brand: BrandStyle {BrandStyle.forID(account.provider.brandID)}
    private var metrics: APICardMetrics {APICardMetrics(account:account,observation:observation)}
    private var stale: Bool {
        observation?.status=="stale" || observation?.fetchedAt.map {Date().timeIntervalSince1970-$0>3900} == true
    }
    var body: some View {
        VStack(alignment:.leading,spacing:7) {
            HStack(spacing:6) {
                ProviderLogo(id:account.provider.brandID,size:24,enabled:preferences.showProviderLogos)
                    .padding(3).background(Color.white).clipShape(RoundedRectangle(cornerRadius:8))
                Text(account.displayName).font(.system(size:14,weight:.semibold)).lineLimit(1)
                Text(account.selectedCurrency).font(.system(size:9,weight:.medium)).foregroundStyle(brand.accent)
                    .padding(.horizontal,5).padding(.vertical,3).background(brand.accent.opacity(0.08)).clipShape(Capsule())
                Spacer(minLength:0)
                Button(action:configure) {Image(systemName:"slider.horizontal.3").font(.system(size:11))}
                    .buttonStyle(ResponsiveButtonStyle()).foregroundStyle(MonitorPalette.secondary)
                    .accessibilityLabel(account.provider.name+" API 设置").accessibilityIdentifier("api.configure."+account.provider.rawValue)
            }.padding(.horizontal,3)
            VStack(alignment:.leading,spacing:7) {
                HStack {
                    Text(metrics.title).font(.system(size:12,weight:.semibold))
                    Spacer(minLength:2)
                    if stale, let stamp=observation?.fetchedAt {
                        Text("上次 "+Date(timeIntervalSince1970:stamp).formatted(date:.omitted,time:.shortened)).font(.system(size:9)).foregroundStyle(MonitorPalette.secondary)
                    } else if !account.configured {
                        Text("待连接").font(.system(size:9)).foregroundStyle(MonitorPalette.secondary)
                    }
                }
                GeometryReader { proxy in
                    ZStack(alignment:.leading) {
                        Capsule().fill(preferences.useBrandColors ? brand.track : MonitorPalette.track)
                        if let f=metrics.remainingFraction,f>0 {
                            Capsule().fill(metrics.low ? MonitorPalette.red : preferences.useBrandColors ? brand.accent : MonitorPalette.blue)
                                .opacity(stale ? 0.45 : 1).frame(width:max(1,proxy.size.width*f))
                        }
                    }
                }.frame(height:5).help(metrics.progressMeaning).accessibilityLabel(metrics.progressMeaning)
                HStack(alignment:.firstTextBaseline,spacing:4) {
                    Text(metrics.left).fontWeight(.medium).foregroundStyle(metrics.low ? MonitorPalette.red : MonitorPalette.text)
                    Spacer(minLength:3)
                    Text(metrics.right).foregroundStyle(MonitorPalette.secondary)
                }.font(.system(size:11)).monospacedDigit().lineLimit(1).minimumScaleFactor(0.82)
                if !metrics.footnote.isEmpty {
                    Text(metrics.footnote).font(.system(size:9)).foregroundStyle(MonitorPalette.secondary).lineLimit(2).fixedSize(horizontal:false,vertical:true)
                }
            }.padding(.horizontal,11).padding(.vertical,11)
                .background(preferences.useBrandColors ? brand.wash : MonitorPalette.card)
                .clipShape(RoundedRectangle(cornerRadius:12))
                .overlay(RoundedRectangle(cornerRadius:12).strokeBorder(brand.accent.opacity(0.10)))
                .contentShape(Rectangle()).onTapGesture {configure()}
                .accessibilityIdentifier("api.card."+account.provider.rawValue)
        }
    }
}

struct APISettingsPanel: View {
    @ObservedObject var api: APIBalanceStore
    var body: some View {
        ScrollView {
            VStack(alignment:.leading,spacing:14) {
                if let id=api.editingID,let account=api.accounts.first(where:{$0.id==id}) {
                    APIAccountEditor(api:api,account:account).id(id)
                } else {
                    Text("API 账户独立于订阅套餐。添加 Key 后自动查询；此页排序不改变菜单栏套餐横杠。").font(.system(size:11)).foregroundStyle(MonitorPalette.secondary)
                    ForEach(Array(api.accounts.enumerated()),id:\.element.id) {index,account in
                        HStack(spacing:5) {
                            Image(systemName:"line.3.horizontal").frame(width:20,height:28).contentShape(Rectangle()).draggable(account.id)
                            ProviderLogo(id:account.provider.brandID,size:19)
                            Button {api.editingID=account.id} label: {
                                VStack(alignment:.leading,spacing:3) {
                                    Text(account.displayName).font(.system(size:12,weight:.medium)).lineLimit(1)
                                    Text(account.configured ? "Key 已保存" : "待添加 Key").font(.system(size:9)).foregroundStyle(MonitorPalette.secondary)
                                }.frame(maxWidth:.infinity,alignment:.leading)
                            }.buttonStyle(ResponsiveButtonStyle()).accessibilityIdentifier("api.edit."+account.provider.rawValue)
                            Button {api.move(account.id,by:-1)} label:{Image(systemName:"chevron.up")}.disabled(index==0).buttonStyle(ResponsiveButtonStyle())
                            Button {api.move(account.id,by:1)} label:{Image(systemName:"chevron.down")}.disabled(index==api.accounts.count-1).buttonStyle(ResponsiveButtonStyle())
                            Button {api.enable(account.id,!account.enabled)} label:{SwitchGlyph(on:account.enabled)}.buttonStyle(ResponsiveButtonStyle())
                                .accessibilityLabel("显示 "+account.displayName)
                        }.font(.system(size:10)).padding(8).background(MonitorPalette.card).clipShape(RoundedRectangle(cornerRadius:9))
                            .dropDestination(for:String.self) {items,_ in guard let id=items.first else{return false};api.move(id,to:account.id);return true}
                    }
                    Menu("添加另一个 API 账户") { ForEach(APIProvider.allCases) {p in Button(p.name) {api.add(p)} } }
                    Text("同一充值账户下的多个 Key 可能共用余额；不会合计成一个总钱包。余额接口、组织费用和 Key 费用分别标注。").font(.system(size:10)).foregroundStyle(MonitorPalette.secondary)
                }
                if !api.message.isEmpty {Text(api.message).font(.system(size:10)).foregroundStyle(MonitorPalette.secondary).fixedSize(horizontal:false,vertical:true)}
            }.padding(.horizontal,13).padding(.top,5).padding(.bottom,18)
        }.frame(maxWidth:.infinity,maxHeight:.infinity)
    }
}

struct APIAccountEditor: View {
    @ObservedObject var api: APIBalanceStore
    @State var draft: APIAccount
    @State private var key=""
    @State private var budget=""
    @State private var reference=""
    @State private var validation=""
    @State private var confirmingRemoval=false
    init(api: APIBalanceStore,account: APIAccount) {
        self.api=api;_draft=State(initialValue:account)
        _budget=State(initialValue:account.dailyBudget.map{String(format:"%g",$0)} ?? "")
        _reference=State(initialValue:account.balanceReference.map{String(format:"%g",$0)} ?? "")
    }
    var body: some View {
        VStack(alignment:.leading,spacing:14) {
            HStack {ProviderLogo(id:draft.provider.brandID,size:24);Text(draft.provider.name).font(.system(size:16,weight:.semibold));Spacer()}
            Text(draft.provider.capabilities).font(.system(size:11)).foregroundStyle(MonitorPalette.secondary).fixedSize(horizontal:false,vertical:true)
            SettingsGroup("账户与凭证") {
                TextField("账户别名（可选）",text:$draft.alias).textFieldStyle(.roundedBorder)
                if draft.provider.hasRegions {
                    Picker("Key 所属区域",selection:$draft.region) {Text("中国站").tag("cn");Text("国际站").tag("global")}
                }
                if draft.provider == .deepseek {
                    Picker("余额币种",selection:$draft.currency) {Text("人民币 CNY").tag("CNY");Text("美元 USD").tag("USD")}
                }
                if draft.provider == .openrouter {
                    Picker("凭证类型",selection:$draft.mode) {Text("普通 Key · 今日费用").tag("key");Text("Management · 账户余额").tag("management")}
                }
                if draft.provider.requiresAdmin {
                    Text(draft.provider == .claude ? "需组织账单权限，建议使用 Admin Key；工作区 Key 不适用。" : "这里需要 Admin Key，不是普通模型调用 Key。").font(.system(size:10)).foregroundStyle(.orange)
                    TextField(draft.provider == .openai ? "项目 ID（可选；空白为全组织）" : "工作区 ID（可选；空白为全组织）",text:$draft.projectID).textFieldStyle(.roundedBorder)
                }
                SecureField(draft.configured ? "已保存，留空保留原 Key" : draft.provider.credentialLabel,text:$key).textFieldStyle(.roundedBorder)
                    .accessibilityIdentifier("api.key.input")
                Text("仅保存到本机独立 API 钥匙串组件；不回显、不写入配置、不调用模型测试。").font(.system(size:9)).foregroundStyle(MonitorPalette.secondary)
                HStack {
                    if api.saving {ProgressView().controlSize(.small)}
                    Button("保存并检查") {save()}.disabled(api.saving).buttonStyle(ResponsiveButtonStyle()).accessibilityIdentifier("api.save")
                    Spacer()
                    if draft.configured {Button("移除 Key…") {confirmingRemoval=true}.disabled(api.saving).buttonStyle(ResponsiveButtonStyle())}
                }
                if draft.configured { Button("授权 API 钥匙串组件") {Task {await api.grant(draft.id)}}.disabled(api.saving).buttonStyle(ResponsiveButtonStyle()) }
            }
            SettingsGroup("单进度条 · "+draft.selectedCurrency) {
                HStack {Text("本地日预算");Spacer();TextField("可选",text:$budget).frame(width:100).textFieldStyle(.roundedBorder)}
                Text("有今日费用时：剩余日预算 / 本地日预算。仅用于展示，不会停止 API 调用。").font(.system(size:10)).foregroundStyle(MonitorPalette.secondary)
                HStack {Text("余额显示基准");Spacer();TextField("可选",text:$reference).frame(width:100).textFieldStyle(.roundedBorder)}
                Text("只有余额时：余额 / 显示基准。都未设置时保留金额，进度条不伪造比例。").font(.system(size:10)).foregroundStyle(MonitorPalette.secondary)
                Text("日统计按 UTC 00:00 起算。过日后等待新的账单，不把昨日费用当成今日。").font(.system(size:10)).foregroundStyle(MonitorPalette.secondary)
            }
            SettingsGroup("查询状态") {
                if let o=api.observation(draft) {
                    Text(o.statusText).fontWeight(.medium)
                    Text(o.message).font(.system(size:10)).foregroundStyle(MonitorPalette.secondary).fixedSize(horizontal:false,vertical:true)
                    if let t=o.fetchedAt {Text("最后读取 "+Date(timeIntervalSince1970:t).formatted()).font(.system(size:9)).foregroundStyle(MonitorPalette.secondary)}
                    if let t=o.nextQueryAt {Text("下次可查询 "+Date(timeIntervalSince1970:t).formatted()).font(.system(size:9)).foregroundStyle(MonitorPalette.secondary)}
                } else {Text(draft.configured ? "等待查询" : "未添加 Key，不会发送请求").foregroundStyle(MonitorPalette.secondary)}
                Button("打开官方账单 ↗") {api.openBilling(draft)}.buttonStyle(ResponsiveButtonStyle())
                Text("余额一般至少间隔 15 分钟，组织账单至少 30 分钟；手动刷新和重启不绕过冷却。").font(.system(size:9)).foregroundStyle(MonitorPalette.secondary)
            }
            if !validation.isEmpty {Text(validation).foregroundStyle(.orange).font(.system(size:11))}
        }.font(.system(size:12)).controlSize(.small)
        .confirmationDialog("从本机钥匙串移除此 API Key？不会撤销服务商端的 Key。",isPresented:$confirmingRemoval){
            Button("移除本机 Key",role:.destructive){Task {await api.removeKey(draft.id);if let saved=api.accounts.first(where:{$0.id==draft.id}) {draft=saved};key=""}}
        }
    }
    private func save() {
        func positive(_ text:String) -> Double? {let v=Double(text.trimmingCharacters(in:.whitespaces));return v.flatMap{$0.isFinite && $0>0 && $0<1e12 ? $0 : nil}}
        guard budget.isEmpty || positive(budget) != nil, reference.isEmpty || positive(reference) != nil else {validation="预算和显示基准需为正数；留空表示不设置。";return}
        draft.dailyBudget=positive(budget);draft.balanceReference=positive(reference);validation=""
        let input=key
        Task {
            if await api.save(draft,key:input) {key="";if let saved=api.accounts.first(where:{$0.id==draft.id}){draft=saved}}
        }
    }
}
