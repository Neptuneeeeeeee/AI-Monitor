import AppKit
import SwiftUI
import Security
import MonitorCore

@MainActor final class AppDelegate: NSObject, NSApplicationDelegate {
    var statusItem: NSStatusItem!
    var popover: NSPopover!
    var store: MonitorStore!
    var dashboardWindow: NSWindow?
    private var keyboardMonitor: Any?
    private let evidenceQueue = DispatchQueue(label: "Monitor.UIState", qos: .utility)
    private var layoutSize: NSSize { NSSize(width: CGFloat(store.preferences.panelWidth), height: store.panelHeight) }
    func applicationDidFinishLaunching(_ notification: Notification) {
        store = MonitorStore()
        statusItem = NSStatusBar.system.statusItem(withLength: MenuBarIcon.itemLength)
        statusItem.autosaveName = AppRuntime.profile.bundleID + ".Usage"
        if let button = statusItem.button {
            button.title = ""; button.imagePosition = .imageOnly
            button.target = self; button.action = #selector(togglePopover)
        }
        popover = NSPopover(); popover.appearance = NSAppearance(named: .aqua)
        popover.animates = false
        popover.contentSize = layoutSize
        popover.contentViewController = MonitorViewController(store: store)
        store.onChange = { [weak self] in self?.updatePresentation() }
        store.api.onChange = { [weak self] in self?.updatePresentation() }
        store.dismissPanel = { [weak self] in self?.dismissPanel() }
        keyboardMonitor = NSEvent.addLocalMonitorForEvents(matching: .keyDown) { [weak self] event in
            guard let self, self.popover.isShown || self.dashboardWindow?.isKeyWindow == true else { return event }
            if event.keyCode == 53 { self.dismissPanel(); return nil }
            if event.modifierFlags.contains(.command) {
                if event.charactersIgnoringModifiers == "r" { self.store.refreshCurrent(); return nil }
                if event.charactersIgnoringModifiers == "," { self.store.openSettings(); return nil }
                if event.charactersIgnoringModifiers == "w" { self.dismissPanel(); return nil }
            }
            return event
        }
        updatePresentation()
        if store.preferences.autoRefresh { store.refresh() }
        if CommandLine.arguments.contains("--show-api") { store.apiMode = true; store.api.refresh() }
        if CommandLine.arguments.contains("--show") || CommandLine.arguments.contains("--show-api") { DispatchQueue.main.asyncAfter(deadline: .now() + 0.6) { self.showDashboard() } }
    }
    private func updatePresentation() {
        guard let button = statusItem?.button else { return }
        statusItem.length = MenuBarIcon.itemLength
        button.title = ""; button.imagePosition = .imageOnly
        button.image = MenuBarIcon.make(slots: store.iconSlots, style: store.preferences.iconStyle, threshold: store.preferences.lowThreshold)
        button.toolTip = store.iconHelp
        button.setAccessibilityLabel("\(AppRuntime.profile.displayName)，\(store.iconSlots.count) 个套餐的剩余额度，按各平台实际窗口显示")
        button.setAccessibilityValue(store.iconHelp)
        popover.behavior = store.preferences.keepPopoverOpen || store.showSettings ? .applicationDefined : .transient
        DispatchQueue.main.async { [weak self] in self?.resizePanels() }
        writeUIState()
    }
    private func resizePanels() {
        let size = layoutSize
        if popover.contentSize != size { popover.contentSize = size }
        if let window = dashboardWindow, window.contentView?.frame.size != size {
            window.setContentSize(size)
            if let screen = window.screen, !screen.visibleFrame.contains(window.frame) {
                let f = screen.visibleFrame
                window.setFrameOrigin(NSPoint(x: min(max(window.frame.minX, f.minX), f.maxX-window.frame.width), y: min(max(window.frame.minY, f.minY), f.maxY-window.frame.height)))
            }
        }
    }
    // Non-sensitive live-instance evidence for local regression checks. No credentials.
    private func writeUIState() {
        guard let image = statusItem.button?.image else { return }
        let slotData = (try? JSONEncoder().encode(store.iconSlots)) ?? Data("[]".utf8)
        let slots = (try? JSONSerialization.jsonObject(with: slotData)) ?? []
        let state: [String: Any] = ["version":AppRuntime.profile.version, "channel":AppRuntime.profile.channel, "bundleID":AppRuntime.profile.bundleID, "apiMode":store.apiMode, "apiAccountCount":store.api.accounts.count, "apiConfiguredCount":store.api.accounts.filter { $0.configured }.count, "apiToolbarPosition":"refresh-api-settings", "updatedAt":Date().timeIntervalSince1970,
            "buttonTitle":statusItem.button?.title ?? "", "itemLength":statusItem.length,
            "imageWidth":image.size.width, "imageHeight":image.size.height, "imageTemplate":image.isTemplate,
            "providerOrder":store.preferences.providerOrder, "enabled":Array(store.enabled).sorted(), "iconSlots":slots,
            "panelWidth":store.preferences.panelWidth, "panelHeight":store.panelHeight,
            "appearance":popover.appearance?.name.rawValue ?? "", "settingsOpen":store.showSettings,
            "queryProtection":true, "stableKeychainComponent":KeychainBridge.executable.path, "refreshMinimum":store.refreshSeconds, "autoRefresh":store.preferences.autoRefresh, "firstClickEnabled":true,
            "barCount":store.iconSlots.count, "brandColors":store.preferences.useBrandColors, "providerLogos":store.preferences.showProviderLogos, "iconStyle":store.preferences.iconStyle,
            "minimumToolbarHitSize":28, "dragScope":"handle-only", "fixedViewport":true]
        let file = store.support.appendingPathComponent("ui-state.json")
        if let data = try? JSONSerialization.data(withJSONObject: state, options: [.sortedKeys]) {
            evidenceQueue.async {
                try? data.write(to: file, options: .atomic)
                try? FileManager.default.setAttributes([.posixPermissions:0o600], ofItemAtPath: file.path)
            }
        }
    }
    private func dismissPanel() { popover.performClose(nil); dashboardWindow?.orderOut(nil) }
    func applicationWillTerminate(_ notification: Notification) {
        if let keyboardMonitor { NSEvent.removeMonitor(keyboardMonitor) }
        store?.shutdown()
    }
    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool { showDashboard(); return true }
    func showDashboard() {
        store.fitPanel(to: NSScreen.screens.first { $0.frame.contains(NSEvent.mouseLocation) } ?? NSScreen.main)
        popover.performClose(nil)
        if dashboardWindow == nil {
            let window = NSWindow(contentRect: NSRect(origin: .zero, size: layoutSize), styleMask: [.titled, .closable, .miniaturizable], backing: .buffered, defer: false)
            window.title = AppRuntime.profile.displayName; window.isReleasedWhenClosed = false
            window.appearance = NSAppearance(named: .aqua); window.backgroundColor = .white
            window.contentViewController = MonitorViewController(store: store); dashboardWindow = window
        }
        NSApp.activate(ignoringOtherApps: true)
        guard let window = dashboardWindow else { return }
        window.makeKeyAndOrderFront(nil); window.setContentSize(layoutSize); window.contentView?.layoutSubtreeIfNeeded()
        let screen = NSScreen.screens.first { $0.frame.contains(NSEvent.mouseLocation) } ?? NSScreen.main
        if let rect = screen?.visibleFrame { window.setFrameOrigin(NSPoint(x: rect.midX-window.frame.width/2, y: rect.midY-window.frame.height/2)) }
        refreshOnOpen()
    }
    private func refreshOnOpen() {
        if store.apiMode { store.api.refresh(); return }
        guard store.preferences.autoRefresh && store.preferences.refreshOnOpen else { return }
        if store.snapshot == nil || store.now - (store.snapshot?.generatedAt ?? 0) > Double(store.refreshSeconds) { store.refresh() }
    }
    @objc func togglePopover() {
        if popover.isShown { popover.performClose(nil); return }
        guard let button = statusItem.button else { return }
        if let frame = button.window?.frame, !NSScreen.screens.contains(where: { $0.frame.intersects(frame) }) { showDashboard(); return }
        dashboardWindow?.orderOut(nil)
        NSApp.activate(ignoringOtherApps: true)
        store.fitPanel(to: button.window?.screen ?? NSScreen.main)
        popover.contentSize = layoutSize
        popover.show(relativeTo: button.bounds, of: button, preferredEdge: .minY)
        if let host = popover.contentViewController?.view, let window = host.window {
            window.makeKey(); window.makeFirstResponder(host)
        }
        refreshOnOpen()
    }
}


/// Public facade; private extensions are supplied only by the Local executable.
public enum MonitorApplication {
    @MainActor public static func run(expectedChannel: String, startupExtension: (() -> Void)? = nil) {
        do {
            try AppRuntime.configure(expectedChannel: expectedChannel)
            let args = CommandLine.arguments
            if args.contains("--runtime-info") {
                FileHandle.standardOutput.write(try AppRuntime.runtimeInfo()); return
            }
            if args.contains("--self-test-isolation") { try IsolationSelfCheck.run(); return }
            if args.contains("--self-test-runtime") { try RuntimeSelfCheck.run(); return }
            if args.contains("--experimental-status") { throw AppRuntime.failure("This executable has no private experiment entry point.") }
            let app = NSApplication.shared; app.setActivationPolicy(.accessory)
            if args.contains("--render-preview") { try PreviewSupport.render(args:args); return }
            if args.contains("--demo") { DemoSupport.run(args: args); return }
            startupExtension?()
            let delegate = AppDelegate(); app.delegate = delegate
            withExtendedLifetime(delegate) { app.run() }
        } catch {
            FileHandle.standardError.write(Data("Monitor could not start: \(error.localizedDescription)\nUse the packaged application from scripts/build.sh.\n".utf8))
            exit(1)
        }
    }
}
