import Foundation
import MonitorCore

extension MonitorCoreTests {
    func apiAccount(_ provider: APIProvider = .openrouter) -> APIAccount {
        var a=APIAccount(provider:provider,id:"00000000-0000-0000-0000-000000000001");a.credentialRevision="fixture";return a
    }
    func apiObservation(_ a: APIAccount,spent: Double?=4,balance: Double?=80,day: String?=nil) -> APIObservation {
        APIObservation(id:a.id,context:a.context,currency:a.selectedCurrency,balance:balance,balanceLabel:"账户余额",dailySpent:spent,
                       dayUTC:day ?? APIObservation.day(Date(timeIntervalSince1970:now)),fetchedAt:now)
    }
    func testAPISevenDefaultsNoCredentials() {
        let accounts=APIAccount.defaults();checkEqual(accounts.count,7);checkTrue(accounts.allSatisfy{!$0.configured});checkEqual(Set(accounts.map(\.id)).count,7)
    }
    func testAPIDailyBudgetIsNotWallet() {
        var a=apiAccount();a.dailyBudget=10
        let m=APICardMetrics(account:a,observation:apiObservation(a),now:Date(timeIntervalSince1970:now))
        checkEqual(m.remainingFraction,0.6);checkTrue(m.left.contains("6.00"));checkTrue(m.footnote.contains("80.00"));checkTrue(m.title.contains("本地"))
    }
    func testAPINoBudgetHasNoInventedPercentage() {
        let a=apiAccount();let m=APICardMetrics(account:a,observation:apiObservation(a),now:Date(timeIntervalSince1970:now));checkNil(m.remainingFraction)
    }
    func testAPIOnlyBalanceDoesNotInventDailyCost() {
        var a=apiAccount(.deepseek);a.dailyBudget=10;a.balanceReference=100
        let m=APICardMetrics(account:a,observation:apiObservation(a,spent:nil),now:Date(timeIntervalSince1970:now))
        checkEqual(m.remainingFraction,0.8);checkEqual(m.title,"账户余额");checkEqual(m.right,"今日消费未提供")
    }
    func testAPICrossDayNeverReusesYesterdaySpend() {
        let a=apiAccount();let o=apiObservation(a,day:"2000-01-01");checkNil(o.spentToday(at:Date(timeIntervalSince1970:now)))
        let m=APICardMetrics(account:a,observation:o,now:Date(timeIntervalSince1970:now));checkEqual(m.right,"今日待更新")
    }
    func testAPIBudgetOverspendIsExplicit() {
        var a=apiAccount();a.dailyBudget=10
        let m=APICardMetrics(account:a,observation:apiObservation(a,spent:14),now:Date(timeIntervalSince1970:now))
        checkEqual(m.remainingFraction,0);checkTrue(m.footnote.contains("超出预算"));checkTrue(m.low)
    }
    func testAPIWalletOverReferenceClampsOnlyBar() {
        var a=apiAccount();a.balanceReference=50
        let m=APICardMetrics(account:a,observation:apiObservation(a,spent:nil,balance:100),now:Date(timeIntervalSince1970:now))
        checkEqual(m.remainingFraction,1);checkTrue(m.left.contains("100.00"))
    }
    func testAPIChangedKeyCannotDisplayOldBalance() {
        var a=apiAccount();let o=apiObservation(a);a.credentialRevision="different"
        let m=APICardMetrics(account:a,observation:o,now:Date(timeIntervalSince1970:now));checkNil(m.remainingFraction);checkTrue(!m.left.contains("80"))
    }
    func testAPIDisabledAccountKeepsIndependentIdentity() {
        var a=apiAccount();let old=a.context;a.enabled=false;a.alias="alias";checkEqual(a.context,old)
    }
    func testAPICurrencyMismatchNoBudgetMath() {
        var a=apiAccount(.deepseek);a.dailyBudget=20;var o=apiObservation(a);o.currency="USD"
        let m=APICardMetrics(account:a,observation:o,now:Date(timeIntervalSince1970:now));checkNil(m.remainingFraction)
    }
    func testAPIKeyLimitNotWalletBudget() {
        let a=apiAccount();var o=apiObservation(a);o.balance=15;o.keyLimit=20;o.balanceLabel="Key 剩余额度";o.limitPeriod="每月"
        let m=APICardMetrics(account:a,observation:o,now:Date(timeIntervalSince1970:now));checkEqual(m.remainingFraction,0.75);checkEqual(m.title,"Key 剩余额度")
    }
    func testAPIUnconfiguredEmptyTrack() {
        let a=APIAccount(provider:.google);let m=APICardMetrics(account:a,observation:nil);checkNil(m.remainingFraction);checkEqual(m.left,"待添加 Key")
    }
    func testAPIRealZeroTodayIsSupported() {
        var a=apiAccount(.openai);a.dailyBudget=10
        let m=APICardMetrics(account:a,observation:apiObservation(a,spent:0,balance:nil),now:Date(timeIntervalSince1970:now));checkEqual(m.remainingFraction,1);checkTrue(m.right.contains("0.00"))
    }
    func testAPINaNDoesNotPaintBar() {
        var a=apiAccount();a.dailyBudget=Double.nan;a.balanceReference=Double.infinity
        let m=APICardMetrics(account:a,observation:apiObservation(a),now:Date(timeIntervalSince1970:now));checkNil(m.remainingFraction)
    }
}
