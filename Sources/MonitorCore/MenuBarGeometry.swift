import Foundation

// Keep a single compact 20pt image, adapting row thickness to the selected count.
// Zero selections deliberately means no quota rows, not one invented empty plan.
// Four rows is the readable ceiling for a 20pt status item, so a longer selection
// keeps its first four plans on the menu bar and the rest stay in the panel.
public struct MenuBarRow: Equatable {
    public let y: Double
    public let height: Double
}
public enum MenuBarGeometry {
    public static let maxRows = 4
    public static func rows(count: Int) -> [MenuBarRow] {
        guard count > 0 else { return [] }
        let count = min(count, maxRows)
        let gap = 1.6
        let height = min(3.2, (18.0 - Double(count - 1) * gap) / Double(count))
        let total = Double(count) * height + Double(count - 1) * gap
        let top = (20.0 + total) / 2
        return (0..<count).map { index in
            MenuBarRow(y: top - height - Double(index) * (height + gap), height: height)
        }
    }
}
