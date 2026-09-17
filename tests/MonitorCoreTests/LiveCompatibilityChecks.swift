import Foundation
import MonitorCore

extension MonitorCoreTests {
    func testCodexOfficialThirtyDayPrimaryDisplaysRealZero() {
        let p = ProviderResult(id:"codex", name:"Codex", plan:"free", fetchedAt:now,
            windows:[QuotaWindow(id:"primary",label:"30 天窗口",remainingPercent:0,
                resetAt:now+86400,durationMinutes:43200)])
        let slot=slots([p])[0]
        checkEqual(slot.percent,0)
        checkEqual(slot.state,"known")
        checkEqual(slot.period,"provider")
        checkTrue(slot.reason.contains("30 天"))
        checkTrue(!slot.reason.contains("5 小时"))
    }
    func testCodexPrimaryStillPrefersActualFiveHourWindow() {
        let p = ProviderResult(id:"codex", name:"Codex", plan:"pro", fetchedAt:now,
            windows:[QuotaWindow(id:"primary",label:"当前 5 小时",remainingPercent:63,durationMinutes:300),
                     QuotaWindow(id:"secondary",label:"每周",remainingPercent:12,durationMinutes:10080)])
        checkEqual(slots([p])[0].percent,63)
        checkEqual(slots([p])[0].period,"5h")
    }
    func testCodexMissingPrimaryDurationRemainsUnknown() {
        let p = ProviderResult(id:"codex", name:"Codex", fetchedAt:now,
            windows:[QuotaWindow(id:"primary",label:"unknown",remainingPercent:50)])
        checkNil(slots([p])[0].percent)
    }
}
