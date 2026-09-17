# Privacy and credentials

This implementation stores its own settings and sanitized quota/balance snapshots locally. It does not implement a project-operated telemetry backend. Queries go to provider endpoints or a selected provider's local client. Network access is required for live readings; offline fixtures are not live results.

No plan is enabled by default. Selecting a provider permits its existing adapter to use the supported official-client login source. Depending on the adapter this can mean local account files, a selected CLI, a local app endpoint, or the explicitly named Claude Code keychain item. Kimi OAuth refresh can update the official Kimi CLI credential file. Edition separation does not create separate upstream client logins.

Keys entered for this app use its own per-edition Keychain/API Vault helper and service namespace. Secret values pass through private process pipes, not command-line arguments or source files. API account metadata does not contain the key, but quota/balance data and account aliases can still be private.

Public user data: `~/Library/Application Support/Thalnova AI Monitor/`. Preferences domain: `com.thalnova.aimonitor`. Helper roots: `Auth/` and `APIAuth/` under that data directory. Other editions use different namespaces. Existing legacy credentials/settings are not automatically imported.

The app does not grant itself Accessibility, Full Disk Access, automation consent, or other system privileges. Current candidates are not App Sandbox confined. A separate folder is an accidental-overwrite boundary, not a security boundary against other processes running as the same user.

Do not attach raw logs, snapshots, keys, authorization headers, official client credential files, or private build backups to public issue reports. Review even a redacted diagnostic before sharing it.
