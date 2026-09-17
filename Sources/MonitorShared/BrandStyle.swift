import AppKit
import SwiftUI
import MonitorCore

// These are Monitor's accent choices, not a claim about official brand palettes.
// The actual provider marks are unmodified, bundled first-party assets.
struct BrandStyle {
    let id: String
    let color: NSColor
    var accent: Color { Color(nsColor: color) }
    var wash: Color { Color(nsColor: color.blended(withFraction: 0.955, of: .white) ?? .white) }
    var track: Color { Color(nsColor: color.blended(withFraction: 0.84, of: .white) ?? .lightGray) }
    static func forID(_ id: String) -> BrandStyle {
        let rgb: (Double, Double, Double)
        switch id {
        case "claude": rgb = (0.76, 0.39, 0.27)
        case "kimi": rgb = (0.12, 0.40, 0.92)
        case "codex": rgb = (0.10, 0.52, 0.43)
        case "glm": rgb = (0.40, 0.34, 0.80)
        case "copilot": rgb = (0.50, 0.28, 0.77)
        case "antigravity": rgb = (0.15, 0.48, 0.79)
        case "gemini": rgb = (0.22, 0.47, 0.90)
        case "deepseek": rgb = (0.19, 0.35, 0.89)
        case "siliconflow": rgb = (0.48, 0.31, 0.84)
        case "openrouter": rgb = (0.34, 0.39, 0.60)
        default: rgb = (0.28, 0.39, 0.58)
        }
        return BrandStyle(id: id, color: NSColor(srgbRed: rgb.0, green: rgb.1, blue: rgb.2, alpha: 1))
    }
    static func forWindow(_ window: QuotaWindow, providerID: String) -> BrandStyle {
        guard providerID == "antigravity" else { return forID(providerID) }
        if window.label.lowercased().contains("claude") { return forID("claude") }
        if window.label.lowercased().contains("gemini") { return forID("gemini") }
        return forID(providerID)
    }
}

enum BrandAssets {
    static let ids = ProviderInfo.defaultOrder + ["gemini"]
    private static let images: [String: NSImage] = {
        var output: [String: NSImage] = [:]
        for id in ids {
            guard let url = Bundle.main.resourceURL?.appendingPathComponent("BrandAssets/" + id + ".png"),
                  let image = NSImage(contentsOf: url) else { continue }
            image.isTemplate = false
            output[id] = image
        }
        return output
    }()
    static func image(_ id: String) -> NSImage? { images[id] }
}

struct ProviderLogo: View {
    let id: String
    var size: CGFloat = 24
    var enabled = true
    var body: some View {
        Group {
            if enabled, let image = BrandAssets.image(id) {
                Image(nsImage: image).resizable().renderingMode(.original).interpolation(.high).scaledToFit()
            } else if ["deepseek", "siliconflow", "openrouter"].contains(id) {
                // Local monograms distinguish providers without imitating official logos.
                Text(["deepseek":"D", "siliconflow":"Si", "openrouter":"OR"][id] ?? "API")
                    .font(.system(size:size * (id == "deepseek" ? 0.68 : 0.44),weight:.bold,design:.rounded))
                    .frame(width:size,height:size)
                    .foregroundStyle(BrandStyle.forID(id).accent)
                    .background(RoundedRectangle(cornerRadius:size * 0.25).fill(BrandStyle.forID(id).accent.opacity(0.11)))
            } else {
                Image(systemName: ProviderInfo.all.first { $0.id == id }?.symbol ?? "sparkles")
                    .resizable().scaledToFit().padding(size * 0.10).foregroundStyle(BrandStyle.forID(id).accent)
            }
        }.frame(width: size, height: size).accessibilityHidden(true)
    }
}
