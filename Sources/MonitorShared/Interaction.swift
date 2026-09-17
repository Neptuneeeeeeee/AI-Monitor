import AppKit
import SwiftUI

// Accessory apps normally consume a click merely activating the hosting view.
// The status action also activates the app; this makes the very first click work.
final class FirstClickHostingView<Content: View>: NSHostingView<Content> {
    override func acceptsFirstMouse(for event: NSEvent?) -> Bool { true }
}

@MainActor final class MonitorViewController: NSViewController {
    let store: MonitorStore
    init(store: MonitorStore) { self.store = store; super.init(nibName: nil, bundle: nil) }
    required init?(coder: NSCoder) { fatalError("Not a storyboard controller") }
    override func loadView() {
        let host = FirstClickHostingView(rootView: MonitorPanel(store: store))
        host.frame = NSRect(x: 0, y: 0, width: CGFloat(store.preferences.panelWidth), height: store.panelHeight)
        view = host
    }
}

struct ResponsiveButtonStyle: ButtonStyle {
    var minimum: CGFloat = 28
    func makeBody(configuration: Configuration) -> some View {
        HitSurface(label: configuration.label, pressed: configuration.isPressed, minimum: minimum)
    }
    private struct HitSurface<Label: View>: View {
        let label: Label
        let pressed: Bool
        let minimum: CGFloat
        @State private var hovered = false
        @Environment(\.isEnabled) private var enabled
        var body: some View {
            label.frame(minWidth: minimum, minHeight: minimum)
                .contentShape(Rectangle())
                .background(RoundedRectangle(cornerRadius: 6).fill(Color.black.opacity(enabled ? (pressed ? 0.10 : hovered ? 0.045 : 0) : 0)))
                .opacity(enabled ? 1 : 0.38)
                .onHover { hovered = $0 }
        }
    }
}

struct ToolbarButton: View {
    let symbol: String
    let title: String
    let identifier: String
    var busy = false
    let action: () -> Void
    var body: some View {
        Button(action: action) {
            ZStack {
                Image(systemName: symbol).opacity(busy ? 0 : 1)
                if busy { ProgressView().controlSize(.small).allowsHitTesting(false) }
            }.frame(width: 28, height: 28).contentShape(Rectangle())
        }
        .buttonStyle(ResponsiveButtonStyle())
        .accessibilityLabel(title).accessibilityIdentifier(identifier).help(busy ? "正在刷新额度…" : title)
    }
}

struct SwitchGlyph: View {
    let on: Bool
    var body: some View {
        ZStack {
            Capsule().fill(on ? MonitorPalette.blue : Color.gray.opacity(0.30))
            Circle().fill(.white).frame(width: 12, height: 12).offset(x: on ? 6 : -6)
        }.frame(width: 28, height: 16).allowsHitTesting(false).accessibilityHidden(true)
    }
}

// The entire row is a single button. Tapping either text, whitespace, or the
// switch toggles exactly once; there is no overlapping parent tap gesture.
struct SettingsToggle: View {
    let title: String
    @Binding var isOn: Bool
    var identifier: String = ""
    init(_ title: String, isOn: Binding<Bool>, identifier: String = "") {
        self.title = title; _isOn = isOn; self.identifier = identifier
    }
    var body: some View {
        Button { isOn.toggle() } label: {
            HStack(spacing: 10) {
                Text(title).frame(maxWidth: .infinity, alignment: .leading)
                SwitchGlyph(on: isOn)
            }.frame(minHeight: 32).contentShape(Rectangle())
        }.buttonStyle(ResponsiveButtonStyle(minimum: 32))
            .accessibilityLabel(title).accessibilityValue(isOn ? "已开启" : "已关闭")
            .accessibilityIdentifier(identifier.isEmpty ? "toggle." + title : identifier)
    }
}
