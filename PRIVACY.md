# Privacy and credentials

This implementation stores its own settings and sanitized quota snapshots locally. It does not implement a project-operated telemetry backend. Queries go to provider endpoints or a selected provider's local client. Network access is required for live readings; offline fixtures are not live results.

No plan is enabled by default. Selecting a provider permits its existing adapter to use the supported official-client login source. Depending on the adapter this can mean local account files, a selected CLI, a local app endpoint, or the explicitly named Claude Code keychain item. Kimi OAuth refresh can update the official Kimi CLI credential file. Edition separation does not create separate upstream client logins.

The only key entered in this app is a MiniMax Token Plan subscription key; it uses this edition's own Keychain helper and service namespace. Secret values pass through private process pipes, not command-line arguments or source files. Quota data can still be private.

The API balance view and its separate API Vault helper were removed in 1.10.0. Earlier versions may have left an `API/` folder (account list without keys) and an `APIAuth/` helper copy in the data directory; the app no longer reads or writes them, and they can be deleted. Keys saved through that view stay in the login keychain under `com.thalnova.aimonitor.api.<id>` until removed in Keychain Access.

Public user data: `~/Library/Application Support/AI Monitor/`. Preferences domain: `com.thalnova.aimonitor`. Helper root: `Auth/` under that data directory. Other editions use different namespaces. Existing legacy credentials/settings are not automatically imported.

The app does not grant itself Accessibility, Full Disk Access, automation consent, or other system privileges. Current candidates are not App Sandbox confined. A separate folder is an accidental-overwrite boundary, not a security boundary against other processes running as the same user.

Do not attach raw logs, snapshots, keys, authorization headers, official client credential files, or private build backups to public issue reports. Review even a redacted diagnostic before sharing it.

## Additional plan adapters (1.9.0)

Cursor reads only the selected application's `cursorAuth/accessToken` row and sends an in-memory session cookie only to `https://cursor.com/api/usage-summary`. It never scans browser storage or rotates the official login. Windsurf queries only `windsurf.settings.cachedPlanInfo` and does not make a network request. To avoid changing the original SQLite sidecars, these readers use a bounded DB/WAL copy in an owner-only temporary directory. That copy may contain other database bytes; no chat content is parsed or uploaded, and the copy is deleted after the query.

MiniMax's subscription key is stored in this edition's Keychain helper with separate China/international service names. `plan-connections.json` contains only the selected region and a random credential revision. A key is never automatically retried against another region. Key changes invalidate the affected cached context without clearing rate-limit gates.

Kiro runs the exact official `kiro-cli chat --no-interactive /usage` command with a deadline, no prompt and no tool-trust escalation. Kiro CLI can refresh its own authentication; installing custom CLI hooks/settings is outside this app's control. No new adapter is enabled automatically. Usage returned as an estimate or local cache is marked accordingly.

### Large local application databases

On macOS/APFS, the collector uses copy-on-write database/WAL snapshots in an owner-only temporary directory, then queries only the allowlisted login or quota row. The snapshot can contain unrelated database blocks, but chat rows are not queried or uploaded. Source databases are never checkpointed or modified by the collector. Snapshots have a 2 GiB ceiling; without clone support, byte-copy fallback remains capped at 128 MiB. Temporary files are removed after each read.

## Coding-agent subscriptions (1.10.0)

OpenCode Go reads only the `opencode-go` entry (or, failing that, the `opencode` entry) of the `auth.json` file OpenCode keeps under `~/.local/share/opencode/` (or `$XDG_DATA_HOME/opencode/`), and sends that key only to `https://opencode.ai/zen/go/v1/usage`. ClinePass reads only the Cline account sign-in from `~/.cline/data/settings/providers.json` and sends it only to `https://api.cline.bot/api/v1/users/me/plan/usage-limits`. Neither file is ever written. The Cline token is not refreshed here, because a refresh would rotate the token Cline itself holds; an expired token is reported and left for Cline to renew. Cache identity uses a digest of the OpenCode key or of Cline's server-issued account id, never the secret itself. Other entries in those files are parsed only as part of the JSON document; they are never used, stored or sent.
