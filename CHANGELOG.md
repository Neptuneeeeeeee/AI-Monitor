# 1.9.1 — Official-source icons and disconnected interactive preview

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
