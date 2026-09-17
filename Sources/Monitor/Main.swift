import MonitorShared
@main struct PublicMain {
    @MainActor static func main() { MonitorApplication.run(expectedChannel: "public") }
}
