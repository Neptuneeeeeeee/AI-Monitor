# 1.9.1 — Official-source icons and disconnected interactive preview

## 1.11.0 — Claude: desktop sign-in and a clear expired-login state

- Read Claude's quota with the Claude desktop app's sign-in once you allow it (Settings → 账号连接 → 检查 Claude 读取, one macOS keychain prompt). The desktop app keeps that login current, so Claude no longer goes stale whenever the terminal CLI has not run for a few hours. Only the Keychain helper decrypts it and returns one `user:profile` token; the CLI login stays the fallback. See PRIVACY.md.
- Recognise an expired Claude CLI login from its stored expiry before querying. The card now says the login expired (it used to say the query was rate limited), no request is spent on it, and a button offers the fix: use the desktop sign-in, or run the official `claude auth login`.
- Pass the macOS system proxy to CLIs started from the app's sign-in scripts. Terminal CLIs ignore the system proxy, so without a TUN a sign-in or token renewal could leave from a blocked region and fail with 403.
- Run background reads of another app's keychain item with keychain UI disabled; the no-UI query flags alone still let macOS show the access dialog.

## 1.10.0 — Plan quotas only; OpenCode Go and ClinePass

- Remove the API balance view and its key management: the API/Plan toolbar switch, API settings and key editor, the separate API Vault helper and the DeepSeek, Kimi API, OpenAI/Claude cost, SiliconFlow, OpenRouter and Google AI Studio balance adapters. Existing `API/` and `APIAuth/` folders are no longer read; keys saved through that view stay in the login keychain until removed there. The MiniMax Token Plan key editor stays, since that key is the plan's own credential.
- Add OpenCode Go: 5-hour, weekly and subscription-month windows from `opencode.ai/zen/go/v1/usage`, using the key OpenCode saved with `/connect`.
- Add ClinePass: 5-hour, weekly and monthly windows from Cline's account usage-limits endpoint, using the Cline sign-in without refreshing it. An expired token keeps the last reading marked as cached.
- Parse ISO timestamps with 1–9 fractional digits on the system Python 3.9 runtime.
- Pi has no plan of its own and Kilo Pass is prepaid credit, so neither gets an adapter; see `docs/PLAN_RESEARCH_2026_10.md`.
- Add a display-language setting (Settings → Display): follow the system, Simplified or Traditional Chinese, English, Japanese, Korean, Spanish, French, German or Brazilian Portuguese. Brand and plan names and upstream English terms such as Session and Weekly stay untranslated. Collector messages are translated at display time from `Resources/Localization/Localizable.json`, so a switch applies immediately.
- Remove the "bar N" labels from the plan ordering list.

## 1.9.5 — Menu bar limited to four quota bars

- Draw at most four bars in the status item. A selection of four or fewer is unchanged; a longer one keeps the first plans in the user's own order, so reordering in Settings decides which plans reach the menu bar.
- Apply the limit when the slots are mapped, so the icon, its tooltip, the accessibility label and the Settings preview all describe the same bars. Every enabled plan still appears in the panel.
- Keep row thickness constant at four bars or fewer instead of thinning rows as more plans are selected.
- Fix a test-mode storage guard that compared a resolved candidate path against unresolved production paths, so a symlinked route to a production directory was not rejected. Both sides are now resolved before comparison.

## 1.9.4 — Downloadable Apple Silicon preview

- Add pinned standalone CPython 3.13 and Mozilla public CA roots to the DMG/ZIP build; no separate Python or developer tools are required at runtime.
- Add a native bundled-interpreter self-check, relocated-app/TLS tests and a drag-to-Applications disk image.
- Preserve third-party runtime notices, include bilingual installation instructions and keep missing/zero allowance semantics unchanged.
- Package as an explicitly unnotarized preview. Current local installation is not automatically upgraded by release creation.

## 1.9.3 — Correct zero-capacity Cursor accounts

- A Cursor response with an explicit zero, negative or invalid plan limit no longer becomes 100% remaining from placeholder percentage fields.
- Zero-capacity accounts display a successful-connection/no-allowance explanation, without a fabricated progress bar. Existing valid 100%-used positive-capacity accounts still display a real 0%.
- Retained old full-quota observations cannot reappear during the query cooldown after the account reports no allowance.
- Real-account verification distinguishes five measured providers from a connected Cursor account without a positive subscription pool.

## 1.9.2 — Real-client compatibility fixes

- Allow bounded APFS copy-on-write snapshots for larger Cursor state databases; only the selected login row is queried, never chat rows. Large byte-copy fallbacks remain disallowed.
- Scope Cursor cache generation to its login-session digest instead of unrelated application database modification times.
- Keep Codex app-server and Antigravity local process discovery bounded, while allowing cold-start delays on a busy Mac.
- Display an official non-five-hour Codex primary window with its own label; a real zero is not treated as missing data.
- These changes do not alter credentials, the private Local boundary, or release permissions.

Four new plan logos are bundled from vendor sources. A labelled --demo window uses production views with isolated preferences and denies real account/keychain/system actions.

# Changelog

## 1.9.0 — Expanded plan adapters (development candidate)

Added Cursor monthly usage, MiniMax Token Plan China/international windows, Windsurf explicitly cached local quotas, and Kiro official CLI monthly credits. Removed standalone Kimi Code and GLM Coding Plan key cards without removing their provider support or stored credentials. Added per-provider menu-window mapping, ten-provider geometry, new synthetic protocol/security/UI checks and dated market evidence. No live-account verification or formal distribution is implied by this entry.

## 1.8.0 — development candidate

Split the shared core/UI from the public executable. Centralized per-edition runtime profiles for Swift, Python and credential helpers. Public build is independent of adjacent private packages. Removed implicit use of legacy Monitor paths and live helper reuse. Builds and installations are separate, with explicit edition-scoped install opt-in and rollback of replaced same-edition apps.

First launch enables no plan providers. Added runtime identity output, safe temporary-store/helper self-tests, source/bundle audits and fixture-only network-disabled tests. Corrected Swift test-directory casing and made the login CLI lookup use PATH.

Existing Monitor 1.7.1 installations are not migrated or replaced automatically. Candidate signing remains ad-hoc and Python is not bundled. Full end-user distribution and UI localization remain pending.

## 1.8.0 candidate — build 11

- Rename the workspace to AI-Monitor and products to AI Monitor / AI Monitor Local.
- Keep bundle and owned-Keychain identifiers stable; legacy Monitor installation is not migrated.
- New candidate data and caches use the AI Monitor/AIMonitor names; no pre-existing new-edition data was present.
- Record public/local Git commit provenance in build receipts and document the separate repository mapping.
