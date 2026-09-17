# AI Monitor

AI subscription quotas, API balances, and costs in your macOS menu bar.

[中文说明](README.zh-CN.md)

## Status

This checkout is the public-source boundary of a two-edition workspace. Version 1.8.0 is a **development candidate**, not yet a notarized, end-user-ready distribution. No open-source license has been selected; see `LICENSE_PENDING.md`.

The app retains a native SwiftUI/AppKit interface and Python standard-library collectors. It displays plan quotas separately from API balances/costs. Missing provider data is not presented as zero, unlimited usage, or a full balance. UI text is currently primarily Chinese; the README is bilingual, but full UI localization is not implemented.

## Requirements and build

Build on macOS 14 or later with Apple Command Line Tools, Swift 5.9 or later, and a working `/usr/bin/python3`. The candidate package does not yet embed Python. Build outputs use the host architecture; only architectures actually tested are supported for a given release.

```bash
bash scripts/test.sh
bash scripts/build.sh
```

The public checkout can build on its own. It has no dependency on a private adjacent checkout. Outputs go to `dist/` when standalone, or the workspace's `output/public/`. The build runs unit tests, validates resource boundaries and verifies the packaged runtime and helper identities. It never installs or launches the menu-bar app and never copies a helper from a live installation.

To inspect an installation plan without changing anything:

```bash
bash scripts/install.sh
```

To explicitly install the candidate (no automatic launch):

```bash
bash scripts/install.sh --install
```

Replacement requires `--replace` and the same edition must already be quit. `--launch` is an additional explicit option. Legacy `Monitor.app` is never the target.

## Connections and feature limits

No plan provider is enabled on first launch. Select the providers to connect in Settings; unsupported or unconfigured accounts remain unavailable. Plan collectors support the existing Claude Code, Kimi Code, Codex, GLM, Copilot and Antigravity adapters, subject to upstream interface changes and the user's client/login setup.

API adapters expose different capabilities; they are not equivalent wallets. Some report balances, some require organization billing credentials for costs, and some only validate access. The Google AI Studio adapter currently does **not** display a numeric balance or cost report. See `docs/PROVIDER_CAPABILITIES.md` for implementation limits.

## Privacy and edition boundary

Public uses `com.thalnova.aimonitor` and its own Application Support directory, preferences and credential-helper namespaces. Private experiments are not linked into this executable. Enabling a provider can access its official local client credentials and contact its service directly; upstream client credentials and provider rate limits are not duplicated by the edition separation. Kimi OAuth renewal may update the official CLI credential file.

See `PRIVACY.md`, `SECURITY.md`, and `docs/ARCHITECTURE.md`. No new macOS system permissions are automatically granted. The current build is not App Sandbox confined.

## Distribution checklist

Choose an appropriate source license and review third-party code/assets; embed or otherwise explicitly support the Python runtime; test a clean Mac; implement Developer ID signing and notarization; and release only a reviewed version/tag. `scripts/release_preflight.py` reports these blockers rather than claiming a candidate is release-ready. Do not publish private state, signing material, local experiments, or build logs.

### Candidate app storage

The output `.app` is a local shortcut to an immutable signed bundle under this edition’s `~/Library/Caches/AIMonitor/.../Candidates/` directory. This avoids desktop sync software attaching metadata that breaks code-signature verification. The ZIP in the output directory is a real file, not a shortcut. Share the ZIP only; clearing build caches can invalidate the local shortcut until you rebuild. Installation resolves the shortcut and copies the actual bundle.

## Git and build provenance

The product is **AI Monitor**; the suggested repository name is `AI-Monitor`. In the dual workspace only `public/` is this repository. GitHub remote configuration is explicit; builds never push. BUILD.json records `publicGit` (commit/branch/dirty state), and Local builds additionally record `localGit`, alongside source hashes. See [Git workflow](docs/GIT_WORKFLOW.md).
