import Foundation

/// Starts the packaged interpreter through the same runtime selection as the UI.
/// Uses disposable storage and does not initialize any provider or account store.
enum RuntimeSelfCheck {
    static func run() throws {
        guard let resources = Bundle.main.resourceURL,
              let python = AppRuntime.pythonExecutable,
              python.standardizedFileURL.path.hasPrefix(resources.appendingPathComponent("Python").path + "/") else {
            throw AppRuntime.failure("This package does not contain its required Python runtime.")
        }
        let fm = FileManager.default
        let home = fm.temporaryDirectory.appendingPathComponent("ai-monitor-runtime-check-" + UUID().uuidString)
        try fm.createDirectory(at: home, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
        defer { try? fm.removeItem(at: home) }
        var env = AppRuntime.collectorEnvironment()
        env["HOME"] = home.path
        env["PATH"] = "/usr/bin:/bin:/usr/sbin:/sbin"
        env["MONITOR_TEST_MODE"] = "1"
        env["MONITOR_DATA_DIR"] = home.appendingPathComponent("state").path
        let process = Process(), output = Pipe(), errors = Pipe()
        process.executableURL = python
        process.arguments = ["-B", resources.appendingPathComponent("collector/runtime_smoke.py").path]
        process.currentDirectoryURL = home
        process.environment = env
        process.standardOutput = output; process.standardError = errors
        try process.run()
        let deadline = Date().addingTimeInterval(40)
        while process.isRunning && Date() < deadline { Thread.sleep(forTimeInterval: 0.02) }
        if process.isRunning {
            process.terminate()
            Thread.sleep(forTimeInterval: 0.2)
            if process.isRunning { Darwin.kill(process.processIdentifier, SIGKILL) }
            process.waitUntilExit()
            throw AppRuntime.failure("Bundled runtime check timed out.")
        }
        process.waitUntilExit()
        let data = output.fileHandleForReading.readDataToEndOfFile()
        let stderr = errors.fileHandleForReading.readDataToEndOfFile()
        guard process.terminationStatus == 0,
              let report = try JSONSerialization.jsonObject(with: data) as? [String: Any],
              report["passed"] as? Bool == true else {
            throw AppRuntime.failure("Bundled runtime check failed: " + (String(data: stderr.prefix(3000), encoding: .utf8) ?? "unreadable runtime error"))
        }
        FileHandle.standardOutput.write(data)
    }
}
