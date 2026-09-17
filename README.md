# AI Monitor

AI subscription quotas, API balances, and costs in your macOS menu bar.

[中文说明](README.zh-CN.md)

## Download and install

Download the **DMG** or application **ZIP** from [GitHub Releases](https://github.com/Neptuneeeeeeee/AI-Monitor/releases/tag/v1.9.4), then drag **AI Monitor.app** into Applications. See [installation instructions](docs/INSTALL.md).

**Apple Silicon, macOS 14 or later.** Release downloads include Python 3.13 and public TLS root certificates; end users do not need Python, Xcode, Homebrew or a compiler. Official provider clients and account login may still be required to read subscriptions. UI text is primarily Chinese.

**Preview / not notarized:** v1.9.4 has an ad-hoc integrity signature, not Developer ID signing or Apple notarization. A first-launch Gatekeeper confirmation can be required. Read the security notice in the release and follow Apple's per-app guidance only after verifying the source and checksum. Never disable system-wide protections.

The owner has requested a downloadable preview, not a new MIT/Apache source license. The general source-license decision and complete third-party review remain pending. Runtime dependency notices are included in the app. This preview is not a stable, universally verified release.

## Requirements and build

Build on macOS 14 or later with Apple Command Line Tools, Swift 5.9 or later, and a working `/usr/bin/python3`. A normal developer build may use system Python. For a self-contained downloadable build, use `bash scripts/build.sh --bundle-python`, then `python3 scripts/package_release.py --preview`. The runtime inputs are SHA-256 pinned in `Config/runtime-lock.json`. Build outputs use the host architecture; only architectures actually tested are supported for a given release.

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

No plan provider is enabled on first launch. Select the providers to connect in Settings; unsupported or unconfigured accounts remain unavailable. Plan collectors now register ten providers: Kimi, Codex, Claude, GLM, Copilot, Antigravity, Cursor, MiniMax, Windsurf and Kiro. Cursor uses actual monthly dashboard data; MiniMax reads Token Plan windows; Kiro uses the official `/usage` output. Windsurf is explicitly a **local cached reading, not live server usage**. The automated suite uses fixtures. Separately, real-account numeric readings on one Mac were verified for Claude, Kimi, Codex, Copilot, and Antigravity. Cursor authentication was also verified, but the tested account reported a zero-capacity plan; it is shown as having no quantifiable allowance, not 100% remaining. This does not guarantee every account or client version works. MiniMax, Windsurf, and Kiro have not yet been verified with live accounts in this release.

API adapters expose different capabilities; they are not equivalent wallets. Some report balances, some require organization billing credentials for costs, and some only validate access. The Google AI Studio adapter currently does **not** display a numeric balance or cost report. See `docs/PROVIDER_CAPABILITIES.md` for implementation limits.

## Privacy and edition boundary

Public uses `com.thalnova.aimonitor` and its own Application Support directory, preferences and credential-helper namespaces. Private experiments are not linked into this executable. Enabling a provider can access its official local client credentials and contact its service directly; upstream client credentials and provider rate limits are not duplicated by the edition separation. Kimi OAuth renewal may update the official CLI credential file.

See `PRIVACY.md`, `SECURITY.md`, and `docs/ARCHITECTURE.md`. No new macOS system permissions are automatically granted. The current build is not App Sandbox confined.

## Distribution checklist

Before a stable release: choose an appropriate source license and complete the third-party review; test a second clean Mac; implement Developer ID signing and notarization; and release only a reviewed version/tag. The explicit preview packager separately requires an embedded runtime, passing tests, relocation/TLS/UI checks and truthful unsigned-preview notes. `scripts/release_preflight.py` reports these blockers rather than claiming a candidate is release-ready. Do not publish private state, signing material, local experiments, or build logs.

### Candidate app storage

The output `.app` is a local shortcut to an immutable signed bundle under this edition’s `~/Library/Caches/AIMonitor/.../Candidates/` directory. This avoids desktop sync software attaching metadata that breaks code-signature verification. The ZIP in the output directory is a real file, not a shortcut. Share the ZIP only; clearing build caches can invalidate the local shortcut until you rebuild. Installation resolves the shortcut and copies the actual bundle.

## Git and build provenance

The product is **AI Monitor**; the suggested repository name is `AI-Monitor`. In the dual workspace only `public/` is this repository. GitHub remote configuration is explicit; builds never push. BUILD.json records `publicGit` (commit/branch/dirty state), and Local builds additionally record `localGit`, alongside source hashes. See [Git workflow](docs/GIT_WORKFLOW.md).

## Expanded plans (1.9.0)

The standalone Kimi Code and GLM Coding Plan credential cards were removed from connection settings; their provider rows and saved credentials remain available. MiniMax has an inline, region-specific subscription-key editor. All added providers remain disabled until selected. See [research and adapter contracts](docs/PLAN_RESEARCH_2026_09.md) for dated popularity evidence, query sources, limitations and the difference between developer tool adoption and paid-plan subscribers. Public/Local continue to share the reviewed library; no private experiment module enters the public app.

## 交互预览 / Interactive preview

`bash scripts/preview.sh` 打开使用模拟数据的可操作窗口，不连接真实账号。关闭窗口或按 ⌘Q 退出。说明见 `docs/INTERACTIVE_PREVIEW.md`。
