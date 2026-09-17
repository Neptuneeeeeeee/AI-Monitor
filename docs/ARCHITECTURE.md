# Architecture and invariants

`MonitorCore` exports models, display preferences, geometry and RuntimeProfile. `MonitorShared` exports only the application facade and contains the shared AppKit/SwiftUI interface, lifecycle, collectors' process orchestration and credential-helper installation. `Monitor` is the public executable entry.

A private package can link MonitorShared and supply a startup extension. Private experiments are compiled in that private package, not in MonitorShared. The public product has no path dependency; its build must pass in a directory without the private package.

`Config/profile.json` is the build source of truth. It is copied to the app's RuntimeProfile.json and collector/runtime.json. The build substitutes its namespace and helper ID into signed helper templates; helper identities cannot be changed by shell environment variables. Both helper manifests pin their signed executable hashes, bundle identifiers and channel.

The app validates entry channel, bundle ID and runtime profile before creating stores. `--runtime-info` only describes identities and paths. `--self-test-isolation` installs helper copies and persists synthetic API settings under a temporary home, with zero enabled accounts; it never reads credentials. Its temporary preferences suite is removed afterwards. These assertions are implementation checks, not an OS sandbox.

The Python runner blocks network connections and clears inherited API/CLI credentials for unit tests. Swift checks use temporary preference suites. Tests must not use production account storage. A same-account provider queried by two running editions still shares upstream quotas and may share official CLI login files.
