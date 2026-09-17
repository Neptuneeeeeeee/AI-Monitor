import Foundation
import Darwin

// A tiny dependency-free assertion runner: Command Line Tools does not ship XCTest.
private var failures = 0
func checkEqual<T: Equatable>(_ a: T, _ b: T, file: String = #filePath, line: UInt = #line) {
    if a != b { failures += 1; print("FAIL \(file):\(line): \(a) != \(b)") }
}
func checkTrue(_ value: Bool, file: String = #filePath, line: UInt = #line) {
    if !value { failures += 1; print("FAIL \(file):\(line): expected true") }
}
func checkNil<T>(_ value: T?, file: String = #filePath, line: UInt = #line) {
    if value != nil { failures += 1; print("FAIL \(file):\(line): expected nil") }
}
@main struct CoreCheckRunner {
    static func main() {
        let suite = MonitorCoreTests()
        let cases: [(String, () throws -> Void)] = [
            ("testOfficialEstimateVisibleInMenuHint", suite.testOfficialEstimateVisibleInMenuHint),
            ("testExpandedRegistryKeepsOriginalOrder", suite.testExpandedRegistryKeepsOriginalOrder),
            ("testExpandedGeometryIsReadable", suite.testExpandedGeometryIsReadable),
            ("testCursorMonthlyIsNotFiveHours", suite.testCursorMonthlyIsNotFiveHours),
            ("testCursorSeparatePoolsNotAverage", suite.testCursorSeparatePoolsNotAverage),
            ("testKiroUsesRealMonthlyCredits", suite.testKiroUsesRealMonthlyCredits),
            ("testWindsurfAlwaysMarkedCache", suite.testWindsurfAlwaysMarkedCache),
            ("testWindsurfWeekNeverPretendsDaily", suite.testWindsurfWeekNeverPretendsDaily),
            ("testMiniMaxWindowKeepsQuotaName", suite.testMiniMaxWindowKeepsQuotaName),
            ("testExpandedOrderDoesNotEnableAccounts", suite.testExpandedOrderDoesNotEnableAccounts),
            ("testEmptyExpandedProviderNotFullAllowance", suite.testEmptyExpandedProviderNotFullAllowance),

            ("testRuntimePublicIdentity", suite.testRuntimePublicIdentity),
            ("testRuntimeLocalIdentitySeparate", suite.testRuntimeLocalIdentitySeparate),
            ("testRuntimeCrossChannelRejected", suite.testRuntimeCrossChannelRejected),
            ("testRuntimePathTraversalRejected", suite.testRuntimePathTraversalRejected),
            ("testRuntimePublicPrivateModuleRejected", suite.testRuntimePublicPrivateModuleRejected),
            ("testRuntimeLegacyIdentityRejected", suite.testRuntimeLegacyIdentityRejected),
            ("testDefaultLayoutIsNarrowCompact", suite.testDefaultLayoutIsNarrowCompact),
            ("testZeroSelectionsHaveNoQuotaBars", suite.testZeroSelectionsHaveNoQuotaBars),
            ("testIconOrderUsesOnlyEnabledProviders", suite.testIconOrderUsesOnlyEnabledProviders),
            ("testDisconnectedPlanKeepsItsRowAndFifthIsIncluded", suite.testDisconnectedPlanKeepsItsRowAndFifthIsIncluded),
            ("testWeeklyNeverSubstitutesForFiveHours", suite.testWeeklyNeverSubstitutesForFiveHours),
            ("testMonthlyNeverSubstitutesForFiveHours", suite.testMonthlyNeverSubstitutesForFiveHours),
            ("testKnownZeroIsNotUnknown", suite.testKnownZeroIsNotUnknown),
            ("testMissingPercentIsUnknown", suite.testMissingPercentIsUnknown),
            ("testInvalidPercentRejected", suite.testInvalidPercentRejected),
            ("testStaleValueNotUsedInIcon", suite.testStaleValueNotUsedInIcon),
            ("testExpiredResetWaitsForProvider", suite.testExpiredResetWaitsForProvider),
            ("testMultipleFiveHourPoolsUseLowestKnownValue", suite.testMultipleFiveHourPoolsUseLowestKnownValue),
            ("testMCPNeverUsedForMainFiveHours", suite.testMCPNeverUsedForMainFiveHours),
            ("testOrderNormalizesDuplicateAndUnknownIDs", suite.testOrderNormalizesDuplicateAndUnknownIDs),
            ("testMoveUpAndDown", suite.testMoveUpAndDown),
            ("testDragDestinationReorders", suite.testDragDestinationReorders),
            ("testPreferencesPersistWithoutChangingEnabledAccounts", suite.testPreferencesPersistWithoutChangingEnabledAccounts),
            ("testPartialPreferencesAdoptNewDefaults", suite.testPartialPreferencesAdoptNewDefaults),
            ("testUnsafeSettingsNormalize", suite.testUnsafeSettingsNormalize),
            ("testHideExtraAndScopedModels", suite.testHideExtraAndScopedModels),
            ("testUnlimitedHiddenByDefault", suite.testUnlimitedHiddenByDefault),
            ("testDisplayTogglesDoNotChangeIconMapping", suite.testDisplayTogglesDoNotChangeIconMapping),
            ("testMoneyInMajorUnits", suite.testMoneyInMajorUnits),
            ("testSmartPercentAndTinyPositive", suite.testSmartPercentAndTinyPositive),
            ("testCountdownNeverInventsMissingReset", suite.testCountdownNeverInventsMissingReset),
            ("testPaceMarkerOnlyValidForKnownWindow", suite.testPaceMarkerOnlyValidForKnownWindow),
            ("testLegacySnapshotDecodesWithoutExtraFields", suite.testLegacySnapshotDecodesWithoutExtraFields),
            ("testUnknownMembershipCodeIsNotShownAsPlanName", suite.testUnknownMembershipCodeIsNotShownAsPlanName),
            ("testAllSelectionCountsFollowExactly", suite.testAllSelectionCountsFollowExactly),
            ("testSixthPlanAlsoHasRealQuota", suite.testSixthPlanAlsoHasRealQuota),
            ("testUnknownAndDuplicateIDsNeverCreateExtraBars", suite.testUnknownAndDuplicateIDsNeverCreateExtraBars),
            ("testAdaptiveBarGeometryFitsAndDoesNotOverlap", suite.testAdaptiveBarGeometryFitsAndDoesNotOverlap),
            ("testBrandColorsAndLogosDefaultOn", suite.testBrandColorsAndLogosDefaultOn),
            ("testColoredPreferencesBecomeMonochrome", suite.testColoredPreferencesBecomeMonochrome),
            ("testCachedAntigravityLabelUsesClaudeAlias", suite.testCachedAntigravityLabelUsesClaudeAlias),
            ("testScheduledFifteenMinuteQuotaDoesNotBecomeStaleAtFiveMinutes", suite.testScheduledFifteenMinuteQuotaDoesNotBecomeStaleAtFiveMinutes),
            ("testCooldownStillMarksLastGoodAsStale", suite.testCooldownStillMarksLastGoodAsStale),
            ("testNextQueryDisplayDoesNotInventResetQuota", suite.testNextQueryDisplayDoesNotInventResetQuota),
            ("testLegacyScheduleIsOptional", suite.testLegacyScheduleIsOptional),
            ("testCopilotMonthlyIsSolidMeasuredQuota", suite.testCopilotMonthlyIsSolidMeasuredQuota),
            ("testCopilotMonthlyCacheKeepsLastValue", suite.testCopilotMonthlyCacheKeepsLastValue),
            ("testUnlimitedCopilotDoesNotInventQuota", suite.testUnlimitedCopilotDoesNotInventQuota),
            ("testMonthlyFallbackIsOnlyForCopilot", suite.testMonthlyFallbackIsOnlyForCopilot),
            ("testTallerPanelUpgradeIsPersistent", suite.testTallerPanelUpgradeIsPersistent),
            ("testAPISevenDefaultsNoCredentials", suite.testAPISevenDefaultsNoCredentials),
            ("testAPIDailyBudgetIsNotWallet", suite.testAPIDailyBudgetIsNotWallet),
            ("testAPINoBudgetHasNoInventedPercentage", suite.testAPINoBudgetHasNoInventedPercentage),
            ("testAPIOnlyBalanceDoesNotInventDailyCost", suite.testAPIOnlyBalanceDoesNotInventDailyCost),
            ("testAPICrossDayNeverReusesYesterdaySpend", suite.testAPICrossDayNeverReusesYesterdaySpend),
            ("testAPIBudgetOverspendIsExplicit", suite.testAPIBudgetOverspendIsExplicit),
            ("testAPIWalletOverReferenceClampsOnlyBar", suite.testAPIWalletOverReferenceClampsOnlyBar),
            ("testAPIChangedKeyCannotDisplayOldBalance", suite.testAPIChangedKeyCannotDisplayOldBalance),
            ("testAPIDisabledAccountKeepsIndependentIdentity", suite.testAPIDisabledAccountKeepsIndependentIdentity),
            ("testAPICurrencyMismatchNoBudgetMath", suite.testAPICurrencyMismatchNoBudgetMath),
            ("testAPIKeyLimitNotWalletBudget", suite.testAPIKeyLimitNotWalletBudget),
            ("testAPIUnconfiguredEmptyTrack", suite.testAPIUnconfiguredEmptyTrack),
            ("testAPIRealZeroTodayIsSupported", suite.testAPIRealZeroTodayIsSupported),
            ("testAPINaNDoesNotPaintBar", suite.testAPINaNDoesNotPaintBar),
        ]
        for (name, run) in cases {
            let before = failures
            do { try run() } catch { failures += 1; print("FAIL \(name): \(error)") }
            if failures == before { print("PASS \(name)") }
        }
        print("Executed \(cases.count) Swift core checks; \(failures) failures.")
        exit(failures == 0 ? 0 : 1)
    }
}
