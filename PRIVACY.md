# Privacy and credentials

This implementation stores its own settings and sanitized quota/balance snapshots locally. It does not implement a project-operated telemetry backend. Queries go to provider endpoints or a selected provider's local client. Network access is required for live readings; offline fixtures are not live results.

No plan is enabled by default. Selecting a provider permits its existing adapter to use the supported official-client login source. Depending on the adapter this can mean local account files, a selected CLI, a local app endpoint, or the explicitly named Claude Code keychain item. Kimi OAuth refresh can update the official Kimi CLI credential file. Edition separation does not create separate upstream client logins.

Keys entered for this app use its own per-edition Keychain/API Vault helper and service namespace. Secret values pass through private process pipes, not command-line arguments or source files. API account metadata does not contain the key, but quota/balance data and account aliases can still be private.

Public user data: `~/Library/Application Support/AI Monitor/`. Preferences domain: `com.thalnova.aimonitor`. Helper roots: `Auth/` and `APIAuth/` under that data directory. Other editions use different namespaces. Existing legacy credentials/settings are not automatically imported.

The app does not grant itself Accessibility, Full Disk Access, automation consent, or other system privileges. Current candidates are not App Sandbox confined. A separate folder is an accidental-overwrite boundary, not a security boundary against other processes running as the same user.

Do not attach raw logs, snapshots, keys, authorization headers, official client credential files, or private build backups to public issue reports. Review even a redacted diagnostic before sharing it.

## Additional plan adapters (1.9.0)

Cursor reads only the selected application's `cursorAuth/accessToken` row and sends an in-memory session cookie only to `https://cursor.com/api/usage-summary`. It never scans browser storage or rotates the official login. Windsurf queries only `windsurf.settings.cachedPlanInfo` and does not make a network request. To avoid changing the original SQLite sidecars, these readers use a bounded DB/WAL copy in an owner-only temporary directory. That copy may contain other database bytes; no chat content is parsed or uploaded, and the copy is deleted after the query.

MiniMax's subscription key is stored in this edition's Keychain helper with separate China/international service names. `plan-connections.json` contains only the selected region and a random credential revision. A key is never automatically retried against another region. Key changes invalidate the affected cached context without clearing rate-limit gates or API balance accounts.

Kiro runs the exact official `kiro-cli chat --no-interactive /usage` command with a deadline, no prompt and no tool-trust escalation. Kiro CLI can refresh its own authentication; installing custom CLI hooks/settings is outside this app's control. No new adapter is enabled automatically. Usage returned as an estimate or local cache is marked accordingly.
