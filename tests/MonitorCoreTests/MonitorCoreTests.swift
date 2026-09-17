import Foundation
import MonitorCore

final class MonitorCoreTests {
    let now = 1_800_000_000.0
    func provider(_ id: String, minutes: Double? = 300, percent: Double? = 50, status: String = "ok", age: Double = 0) -> ProviderResult {
        ProviderResult(id: id, name: id, status: status, fetchedAt: now-age, windows: [QuotaWindow(id:"window", label:"quota", remainingPercent:percent, resetAt:now+3600, durationMinutes:minutes)])
    }
    func slots(_ providers: [ProviderResult], order: [String] = ProviderInfo.defaultOrder, enabled: Set<String>? = nil) -> [MenuBarSlot] {
        MenuBarMapping.slots(order: order, enabled: enabled ?? Set(providers.map(\.id)), snapshot: Snapshot(generatedAt:now,providers:providers), now:now, maxAge:300)
    }
    func testDefaultLayoutIsNarrowCompact() { let p=DisplayPreferences(); checkEqual(p.panelWidth,340); checkTrue(p.compact); checkEqual(p.iconStyle,"mono") }
    func testZeroSelectionsHaveNoQuotaBars() { checkEqual(slots([]).count,0) }
    func testIconOrderUsesOnlyEnabledProviders() {
        let items=slots([provider("kimi"),provider("claude"),provider("glm")], order:["claude","codex","kimi","glm"], enabled:["kimi","claude","glm"])
        checkEqual(items.map(\.providerID),["claude","kimi","glm"])
    }
    func testDisconnectedPlanKeepsItsRowAndFifthIsIncluded() {
        let items=slots([provider("kimi"),provider("codex",status:"unavailable"),provider("claude"),provider("glm"),provider("copilot")])
        checkEqual(items[1].providerID,"codex"); checkNil(items[1].percent); checkEqual(items[3].providerID,"glm"); checkEqual(items.count,5); checkEqual(items[4].providerID,"copilot")
    }
    func testWeeklyNeverSubstitutesForFiveHours() { checkNil(slots([provider("codex",minutes:10080,percent:95)])[0].percent) }
    func testMonthlyNeverSubstitutesForFiveHours() { checkNil(slots([provider("codex",minutes:43200,percent:90)])[0].percent) }
    func testKnownZeroIsNotUnknown() { let item=slots([provider("kimi",percent:0)])[0]; checkEqual(item.percent,0); checkEqual(item.state,"known") }
    func testMissingPercentIsUnknown() { checkEqual(slots([provider("kimi",percent:nil)])[0].state,"unknown") }
    func testInvalidPercentRejected() { checkNil(slots([provider("kimi",percent:Double.nan)])[0].percent); checkNil(slots([provider("kimi",percent:101)])[0].percent) }
    func testStaleValueNotUsedInIcon() { let x=slots([provider("kimi",status:"stale")])[0]; checkEqual(x.percent,50); checkEqual(x.state,"cached"); checkEqual(slots([provider("kimi",age:301)])[0].percent,50) }
    func testExpiredResetWaitsForProvider() {
        var p=provider("kimi"); p.fetchedAt=now-30; p.windows[0].resetAt=now-10
        checkEqual(slots([p])[0].percent,50);checkEqual(slots([p])[0].state,"cached")
    }
    func testMultipleFiveHourPoolsUseLowestKnownValue() {
        var p=provider("antigravity",percent:90)
        p.windows.append(QuotaWindow(id:"pool2",label:"5h",remainingPercent:15,durationMinutes:300))
        checkEqual(slots([p])[0].percent,15)
    }
    func testMCPNeverUsedForMainFiveHours() { var p=provider("glm");p.windows[0].unit="MCP";checkNil(slots([p])[0].percent) }
    func testOrderNormalizesDuplicateAndUnknownIDs() {
        checkEqual(DisplayPreferences.normalizedOrder(["claude","unknown","claude","kimi"]),["claude","kimi","codex","glm","copilot","antigravity","cursor","minimax","windsurf","kiro"])
    }
    func testMoveUpAndDown() {
        var p=DisplayPreferences();p.move("claude",by:-2);checkEqual(p.providerOrder.first,"claude")
        p.move("claude",by:99);checkEqual(p.providerOrder.last,"claude")
    }
    func testDragDestinationReorders() {
        var p=DisplayPreferences();p.move("kimi",to:"claude")
        checkEqual(Array(p.providerOrder.prefix(3)),["codex","claude","kimi"])
        p.move("unknown",to:"kimi");checkEqual(p.providerOrder.count,ProviderInfo.all.count)
    }
    func testPreferencesPersistWithoutChangingEnabledAccounts() {
        let suite="MonitorCoreTests."+UUID().uuidString;let d=UserDefaults(suiteName:suite)!
        defer { d.removePersistentDomain(forName:suite) }
        d.set(["claude","kimi"],forKey:"enabled")
        var p=DisplayPreferences();p.move("claude",by:-2);p.panelWidth=320;p.showExtra=false;p.iconStyle="mono";p.save(to:d)
        let restored=DisplayPreferences.load(from:UserDefaults(suiteName:suite)!)
        checkEqual(restored,p);checkEqual(d.stringArray(forKey:"enabled"),["claude","kimi"])
    }
    func testPartialPreferencesAdoptNewDefaults() {
        let suite="MonitorCoreTests."+UUID().uuidString;let d=UserDefaults(suiteName:suite)!
        defer { d.removePersistentDomain(forName:suite) }
        d.set(Data("{\"panelWidth\":320,\"providerOrder\":[\"claude\"]}".utf8),forKey:DisplayPreferences.storageKey)
        let p=DisplayPreferences.load(from:d);checkEqual(p.panelWidth,320);checkTrue(p.showExtra);checkEqual(p.providerOrder.count,ProviderInfo.all.count)
    }
    func testUnsafeSettingsNormalize() { var p=DisplayPreferences();p.panelWidth=10000;p.iconStyle="bad";p.lowThreshold=100;p.normalize();checkEqual(p.panelWidth,340);checkEqual(p.iconStyle,"mono");checkEqual(p.lowThreshold,50) }
    func testHideExtraAndScopedModels() {
        let result=ProviderResult(id:"claude",name:"Claude",windows:[QuotaWindow(id:"five_hour",label:"Session",durationMinutes:300),QuotaWindow(id:"extra_usage",label:"Extra",kind:"extra"),QuotaWindow(id:"seven_day_opus",label:"Opus",durationMinutes:10080)])
        var p=DisplayPreferences();checkEqual(p.visibleWindows(result).map(\.id),["five_hour","extra_usage"])
        p.showExtra=false;checkEqual(p.visibleWindows(result).map(\.id),["five_hour"])
        p.showModelWindows=true;checkEqual(p.visibleWindows(result).map(\.id),["five_hour","seven_day_opus"])
    }
    func testUnlimitedHiddenByDefault() {
        let data=ProviderResult(id:"copilot",name:"Copilot",windows:[QuotaWindow(id:"chat",label:"Chat",isUnlimited:true)])
        var p=DisplayPreferences();checkTrue(p.visibleWindows(data).isEmpty);p.showUnlimited=true;checkEqual(p.visibleWindows(data).count,1)
    }
    func testDisplayTogglesDoNotChangeIconMapping() {
        var p=DisplayPreferences();p.showSession=false
        let data=provider("kimi",percent:73)
        checkTrue(p.visibleWindows(data).isEmpty);checkEqual(slots([data])[0].percent,73)
    }
    func testMoneyInMajorUnits() {
        let w=QuotaWindow(id:"extra_usage",label:"Extra",remainingPercent:100,remaining:30,limit:30,kind:"extra",currency:"USD")
        checkEqual(w.remainingText(),"$30.00 剩余");checkEqual(w.resetText(now:now),"$30.00 上限")
    }
    func testSmartPercentAndTinyPositive() {
        checkEqual(QuotaWindow(id:"a",label:"a",remainingPercent:99.3).percentText(),"99.3%")
        checkEqual(QuotaWindow(id:"a",label:"a",remainingPercent:0.2).percentText("whole"),"<1%")
    }
    func testCountdownNeverInventsMissingReset() {
        checkEqual(QuotaWindow(id:"a",label:"a").resetText(now:now),"")
        checkEqual(QuotaWindow(id:"a",label:"a",resetAt:now-1).resetText(now:now),"等待重置确认")
        checkEqual(QuotaWindow(id:"a",label:"a",resetAt:now+3600).resetText(now:now),"1h 0m 后重置")
    }
    func testPaceMarkerOnlyValidForKnownWindow() {
        checkNil(QuotaWindow(id:"a",label:"a",resetAt:now+1).expectedRemaining(now:now))
        checkEqual(QuotaWindow(id:"a",label:"a",resetAt:now+150*60,durationMinutes:300).expectedRemaining(now:now),50)
    }
    func testLegacySnapshotDecodesWithoutExtraFields() throws {
        let data=Data("{\"schemaVersion\":1,\"generatedAt\":1800000000,\"providers\":[{\"id\":\"kimi\",\"name\":\"Kimi\",\"status\":\"ok\",\"source\":\"fixture\",\"message\":\"\",\"windows\":[{\"id\":\"a\",\"label\":\"5h\",\"remainingPercent\":50,\"durationMinutes\":300}]}]}".utf8)
        let decoded=try JSONDecoder().decode(Snapshot.self,from:data);checkNil(decoded.providers[0].windows[0].currency)
    }
    func testUnknownMembershipCodeIsNotShownAsPlanName() { var p=provider("kimi");p.plan="LEVEL_INTERMEDIATE";checkNil(p.friendlyPlan);p.plan="pro";checkEqual(p.friendlyPlan,"Pro") }

    func testAllSelectionCountsFollowExactly() {
        for count in 0...ProviderInfo.all.count {
            let ids = Array(ProviderInfo.defaultOrder.prefix(count))
            let result = slots(ids.map { provider($0) })
            checkEqual(result.count, count); checkEqual(result.compactMap(\.providerID), ids)
        }
    }
    func testSixthPlanAlsoHasRealQuota() {
        let result = slots(ProviderInfo.defaultOrder.prefix(6).map { provider($0, percent: 37) })
        checkEqual(result.count, 6); checkEqual(result.last?.providerID, "antigravity"); checkEqual(result.last?.percent, 37)
    }
    func testUnknownAndDuplicateIDsNeverCreateExtraBars() {
        let result = slots([provider("kimi")], order:["kimi","kimi","unknown"], enabled:["kimi","unknown"])
        checkEqual(result.count,1)
    }
    func testAdaptiveBarGeometryFitsAndDoesNotOverlap() {
        for count in 0...6 {
            let rows = MenuBarGeometry.rows(count: count)
            checkEqual(rows.count,count)
            for row in rows { checkTrue(row.y >= 0); checkTrue(row.y + row.height <= 20); checkTrue(row.height >= 2) }
            for index in 1..<max(1,rows.count) { checkTrue(rows[index].y + rows[index].height < rows[index-1].y) }
        }
    }
    func testBrandColorsAndLogosDefaultOn() {
        let p=DisplayPreferences(); checkTrue(p.useBrandColors); checkTrue(p.showProviderLogos);checkEqual(p.iconStyle,"mono")
    }
    func testColoredPreferencesBecomeMonochrome() {
        let suite="MonitorBrandTests."+UUID().uuidString;let d=UserDefaults(suiteName:suite)!
        defer { d.removePersistentDomain(forName:suite) }
        d.set(Data("{\"iconStyle\":\"provider\",\"useBrandColors\":true,\"showProviderLogos\":true}".utf8),forKey:DisplayPreferences.storageKey)
        var p=DisplayPreferences.load(from:d);checkEqual(p.iconStyle,"mono");checkTrue(p.useBrandColors);checkTrue(p.showProviderLogos)
        p.iconStyle="mono";p.save(to:d);checkEqual(DisplayPreferences.load(from:d).iconStyle,"mono")
    }
    func testCachedAntigravityLabelUsesClaudeAlias() {
        let w=QuotaWindow(id:"group-1-1",label:"Claude / GPT · Session",remainingPercent:57,durationMinutes:300)
        checkEqual(w.shortLabel,"Claude · Session");checkEqual(w.safePercent,57);checkEqual(w.label,"Claude / GPT · Session")
    }
    func testScheduledFifteenMinuteQuotaDoesNotBecomeStaleAtFiveMinutes() {
        var p=provider("claude", age:700);p.pollIntervalSeconds=900
        checkTrue(!p.isStale(now:now,maxAge:300))
        p.fetchedAt=now-1100;checkTrue(p.isStale(now:now,maxAge:300))
    }
    func testCooldownStillMarksLastGoodAsStale() {
        var p=provider("claude",status:"stale");p.pollIntervalSeconds=900;p.nextQueryAt=now+3600
        checkTrue(p.isStale(now:now,maxAge:300))
        checkEqual(slots([p])[0].percent,50);checkEqual(slots([p])[0].state,"cached")
    }
    func testNextQueryDisplayDoesNotInventResetQuota() {
        var p=provider("claude",status:"rate_limited");p.nextQueryAt=now+900;p.queryStatus="cooldown"
        checkTrue(p.queryScheduleText(now:now).hasPrefix("下次可查询"))
        checkTrue(p.queryWaitingText(now:now).contains("15分钟"))
        p.nextQueryAt=now-1;checkEqual(p.queryScheduleText(now:now),"等待下次检查")
    }
    func testLegacyScheduleIsOptional() throws {
        let p=provider("kimi");let data=try JSONEncoder().encode(p)
        let decoded=try JSONDecoder().decode(ProviderResult.self,from:data)
        checkNil(decoded.nextQueryAt);checkNil(decoded.queryStatus)
    }


    func testCopilotMonthlyIsSolidMeasuredQuota() {
        let p=ProviderResult(id:"copilot",name:"Copilot",fetchedAt:now,windows:[QuotaWindow(id:"premium_interactions",label:"Premium · 每月",remainingPercent:99.3,resetAt:now+86400,kind:"monthly")])
        let x=slots([p])[0];checkEqual(x.percent,99.3);checkEqual(x.period,"month");checkEqual(x.state,"known")
    }
    func testCopilotMonthlyCacheKeepsLastValue() {
        let p=ProviderResult(id:"copilot",name:"Copilot",status:"stale",fetchedAt:now-600,windows:[QuotaWindow(id:"premium_interactions",label:"Premium",remainingPercent:0,kind:"monthly")])
        let x=slots([p])[0];checkEqual(x.percent,0);checkEqual(x.state,"cached");checkEqual(x.period,"month")
    }
    func testUnlimitedCopilotDoesNotInventQuota() {
        let p=ProviderResult(id:"copilot",name:"Copilot",fetchedAt:now,windows:[QuotaWindow(id:"chat",label:"Chat",isUnlimited:true)])
        checkNil(slots([p])[0].percent)
    }
    func testMonthlyFallbackIsOnlyForCopilot() {
        let p=ProviderResult(id:"codex",name:"Codex",fetchedAt:now,windows:[QuotaWindow(id:"premium_interactions",label:"Month",remainingPercent:40,kind:"monthly")])
        checkNil(slots([p])[0].percent)
    }
    func testTallerPanelUpgradeIsPersistent() {
        let suite="MonitorCoreTests."+UUID().uuidString;let d=UserDefaults(suiteName:suite)!
        defer { d.removePersistentDomain(forName:suite) }
        d.set(Data("{\"maxHeight\":620}".utf8),forKey:DisplayPreferences.storageKey)
        var p=DisplayPreferences.load(from:d);checkEqual(p.maxHeight,860)
        p.maxHeight=720;p.save(to:d);checkEqual(DisplayPreferences.load(from:d).maxHeight,720)
    }
}
