// Generates Resources/AppIcon.icns, Monitor's Finder / Launchpad icon.
// The mark echoes the menu-bar glyph (stacked quota bars) drawn in the panel's
// accent colours on a white squircle. Colours only; no provider marks are used.
//
//   swift scripts/make_app_icon.swift Resources/AppIcon.icns [preview.png]
import AppKit
import ImageIO

struct Bar { let rgb: (CGFloat, CGFloat, CGFloat); let fraction: CGFloat }

// Same accents as BrandStyle: claude, kimi, codex, glm.
let bars = [
    Bar(rgb: (0.76, 0.39, 0.27), fraction: 0.78),
    Bar(rgb: (0.12, 0.40, 0.92), fraction: 0.56),
    Bar(rgb: (0.10, 0.52, 0.43), fraction: 0.92),
    Bar(rgb: (0.40, 0.34, 0.80), fraction: 0.36),
]

func color(_ rgb: (CGFloat, CGFloat, CGFloat), white mix: CGFloat = 0, alpha: CGFloat = 1) -> CGColor {
    CGColor(srgbRed: rgb.0 + (1 - rgb.0) * mix, green: rgb.1 + (1 - rgb.1) * mix, blue: rgb.2 + (1 - rgb.2) * mix, alpha: alpha)
}

// Superellipse (n = 5) closely matches the macOS continuous-corner icon body.
func squircle(_ rect: CGRect) -> CGPath {
    let path = CGMutablePath(), steps = 2000
    let a = rect.width / 2, b = rect.height / 2
    for i in 0...steps {
        let t = CGFloat(i) / CGFloat(steps) * 2 * .pi
        let c = cos(t), s = sin(t)
        let point = CGPoint(x: rect.midX + a * copysign(pow(abs(c), 0.4), c),
                            y: rect.midY + b * copysign(pow(abs(s), 0.4), s))
        i == 0 ? path.move(to: point) : path.addLine(to: point)
    }
    path.closeSubpath()
    return path
}

func render(_ px: Int) -> CGImage {
    let space = CGColorSpace(name: CGColorSpace.sRGB)!
    let ctx = CGContext(data: nil, width: px, height: px, bitsPerComponent: 8, bytesPerRow: 0,
                        space: space, bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
    let scale = CGFloat(px) / 1024
    ctx.scaleBy(x: scale, y: scale)
    ctx.interpolationQuality = .high

    // Apple's macOS grid: 824pt body centred on a 1024pt canvas, soft shadow below.
    let body = squircle(CGRect(x: 100, y: 100, width: 824, height: 824))
    ctx.saveGState()
    // Shadow geometry is in device space, so it is scaled by hand.
    ctx.setShadow(offset: CGSize(width: 0, height: -12 * scale), blur: 28 * scale,
                  color: CGColor(gray: 0, alpha: 0.30))
    ctx.addPath(body); ctx.setFillColor(CGColor(gray: 1, alpha: 1)); ctx.fillPath()
    ctx.restoreGState()

    ctx.saveGState()
    ctx.addPath(body); ctx.clip()
    let ground = CGGradient(colorsSpace: space, colors: [
        CGColor(srgbRed: 1, green: 1, blue: 1, alpha: 1),
        CGColor(srgbRed: 0.918, green: 0.933, blue: 0.957, alpha: 1)] as CFArray, locations: [0, 1])!
    ctx.drawLinearGradient(ground, start: CGPoint(x: 0, y: 924), end: CGPoint(x: 0, y: 100), options: [])

    // Small sizes get three thicker bars so they stay legible in list views.
    let shown = px <= 32 ? Array(bars.prefix(3)) : bars
    let height: CGFloat = px <= 32 ? 120 : 84, gap: CGFloat = px <= 32 ? 72 : 50
    let x0: CGFloat = 232, width: CGFloat = 560
    let total = CGFloat(shown.count) * height + CGFloat(shown.count - 1) * gap
    for (index, bar) in shown.enumerated() {
        let y = 512 + total / 2 - CGFloat(index + 1) * height - CGFloat(index) * gap
        let track = CGPath(roundedRect: CGRect(x: x0, y: y, width: width, height: height),
                           cornerWidth: height / 2, cornerHeight: height / 2, transform: nil)
        ctx.addPath(track); ctx.setFillColor(color(bar.rgb, white: 0.84)); ctx.fillPath()

        // Same direction as the panel's quota bars: full tint fading slightly to the right.
        let fillRect = CGRect(x: x0, y: y, width: width * bar.fraction, height: height)
        ctx.saveGState()
        ctx.addPath(CGPath(roundedRect: fillRect, cornerWidth: height / 2, cornerHeight: height / 2, transform: nil))
        ctx.clip()
        let tint = CGGradient(colorsSpace: space, colors: [color(bar.rgb), color(bar.rgb, white: 0.20)] as CFArray, locations: [0, 1])!
        ctx.drawLinearGradient(tint, start: CGPoint(x: fillRect.minX, y: 0), end: CGPoint(x: fillRect.maxX, y: 0), options: [])
        let sheen = CGGradient(colorsSpace: space, colors: [CGColor(gray: 1, alpha: 0.22), CGColor(gray: 1, alpha: 0)] as CFArray, locations: [0, 1])!
        ctx.drawLinearGradient(sheen, start: CGPoint(x: 0, y: fillRect.maxY), end: CGPoint(x: 0, y: fillRect.midY), options: [])
        ctx.restoreGState()
    }

    // Hairline edge keeps the white body defined on light Launchpad backdrops.
    ctx.addPath(body); ctx.setStrokeColor(CGColor(gray: 0, alpha: 0.09)); ctx.setLineWidth(4); ctx.strokePath()
    ctx.restoreGState()
    return ctx.makeImage()!
}

func writePNG(_ image: CGImage, to url: URL) {
    let dest = CGImageDestinationCreateWithURL(url as CFURL, "public.png" as CFString, 1, nil)!
    CGImageDestinationAddImage(dest, image, nil)
    guard CGImageDestinationFinalize(dest) else { fatalError("Could not write \(url.path)") }
}

let args = CommandLine.arguments
let output = URL(fileURLWithPath: args.count > 1 ? args[1] : "Resources/AppIcon.icns")
let iconset = FileManager.default.temporaryDirectory.appendingPathComponent("MonitorAppIcon-\(getpid()).iconset")
try FileManager.default.createDirectory(at: iconset, withIntermediateDirectories: true)
defer { try? FileManager.default.removeItem(at: iconset) }
for base in [16, 32, 128, 256, 512] {
    writePNG(render(base), to: iconset.appendingPathComponent("icon_\(base)x\(base).png"))
    writePNG(render(base * 2), to: iconset.appendingPathComponent("icon_\(base)x\(base)@2x.png"))
}
if args.count > 2 { writePNG(render(1024), to: URL(fileURLWithPath: args[2])) }

let iconutil = Process()
iconutil.executableURL = URL(fileURLWithPath: "/usr/bin/iconutil")
iconutil.arguments = ["-c", "icns", iconset.path, "-o", output.path]
try iconutil.run(); iconutil.waitUntilExit()
guard iconutil.terminationStatus == 0 else { fatalError("iconutil failed") }
print("Wrote \(output.path)")
