# Changelog

## 1.8.0 — development candidate

Split the shared core/UI from the public executable. Centralized per-edition runtime profiles for Swift, Python and credential helpers. Public build is independent of adjacent private packages. Removed implicit use of legacy Monitor paths and live helper reuse. Builds and installations are separate, with explicit edition-scoped install opt-in and rollback of replaced same-edition apps.

First launch enables no plan providers. Added runtime identity output, safe temporary-store/helper self-tests, source/bundle audits and fixture-only network-disabled tests. Corrected Swift test-directory casing and made the login CLI lookup use PATH.

Existing Monitor 1.7.1 installations are not migrated or replaced automatically. Candidate signing remains ad-hoc and Python is not bundled. Full end-user distribution and UI localization remain pending.

## 1.8.0 candidate — build 11

- Rename the workspace to AI-Monitor and products to AI Monitor / AI Monitor Local.
- Keep bundle and owned-Keychain identifiers stable; legacy Monitor installation is not migrated.
- New candidate data and caches use the AI Monitor/AIMonitor names; no pre-existing new-edition data was present.
- Record public/local Git commit provenance in build receipts and document the separate repository mapping.
