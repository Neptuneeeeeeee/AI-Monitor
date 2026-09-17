// swift-tools-version: 5.9
import PackageDescription
let package = Package(
    name: "ThalnovaAIMonitor", platforms: [.macOS(.v14)],
    products: [
        .library(name: "MonitorCore", targets: ["MonitorCore"]),
        .library(name: "MonitorShared", targets: ["MonitorShared"]),
        .executable(name: "ThalnovaAIMonitor", targets: ["Monitor"]),
        .executable(name: "MonitorCoreChecks", targets: ["MonitorCoreChecks"])
    ],
    targets: [
        .target(name: "MonitorCore", path: "Sources/MonitorCore"),
        .target(name: "MonitorShared", dependencies: ["MonitorCore"], path: "Sources/MonitorShared"),
        .executableTarget(name: "Monitor", dependencies: ["MonitorShared"], path: "Sources/Monitor"),
        .executableTarget(name: "MonitorCoreChecks", dependencies: ["MonitorCore"], path: "tests/MonitorCoreTests")
    ]
)
