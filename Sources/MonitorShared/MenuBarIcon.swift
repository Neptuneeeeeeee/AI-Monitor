import AppKit
import MonitorCore

// One compact status item; one horizontal quota bar for every enabled plan.
enum MenuBarIcon {
    static let itemLength: CGFloat = 28
    static func make(slots: [MenuBarSlot], style: String, threshold: Int) -> NSImage {
        let rows = MenuBarGeometry.rows(count: slots.count)
        let image = NSImage(size: NSSize(width: 20, height: 20), flipped: false) { _ in
            if rows.isEmpty {
                // Neutral settings entry, not a fake quota bar. The app remains reachable.
                NSColor.black.setStroke()
                let ring = NSBezierPath(ovalIn: NSRect(x: 6, y: 6, width: 8, height: 8))
                ring.lineWidth = 1.5; ring.stroke()
            }
            for (index, row) in rows.enumerated() {
                let slot = slots[index]
                let y = CGFloat(row.y), height = CGFloat(row.height)
                let rect = NSRect(x: 1, y: y, width: 18, height: height)
                let fill = NSColor.black
                if let percent = slot.percent, percent.isFinite {
                    fill.withAlphaComponent(0.22).setFill()
                    NSBezierPath(roundedRect: rect, xRadius: 1, yRadius: 1).fill()
                    if percent > 0 {
                        fill.withAlphaComponent(slot.state == "cached" ? 0.62 : 1).setFill()
                        let width = max(0.4, 18 * CGFloat(min(100, percent) / 100))
                        NSBezierPath(roundedRect: NSRect(x: 1, y: y, width: width, height: height), xRadius: min(1, width / 2), yRadius: 1).fill()
                    }
                } else {
                    // Unknown quota keeps its selected row and brand but is dashed.
                    fill.withAlphaComponent(0.30).setFill()
                    for segment in 0..<3 {
                        NSBezierPath(roundedRect: NSRect(x: 1 + CGFloat(segment) * 6.6, y: y, width: 4.8, height: height), xRadius: 1, yRadius: 1).fill()
                    }
                }
            }
            return true
        }
        image.isTemplate = true
        image.accessibilityDescription = slots.isEmpty ? "未启用套餐，点击打开设置" : "\(slots.count) 个套餐的剩余额度（Copilot 为每月）"
        return image
    }
}
