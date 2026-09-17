# AI Monitor — macOS installation / 安装说明

## Download the application, not the source archive

Use **AI-Monitor-v1.9.4-macos-arm64.dmg** (recommended) or the matching `.zip` in this GitHub Release's **Assets** section. GitHub's automatic `Source code (zip)` is source code, not an installed application.

**Requirements:** Apple Silicon (M-series), macOS 14 Sonoma or later. This release is not an Intel Mac or Windows build. The interface is currently primarily Chinese.

The download includes a private CPython 3.13 runtime and public TLS root certificates. You do **not** need to install Python, Xcode, Command Line Tools, Homebrew, or run a build command to launch the app. Provider-specific clients and active account login may still be needed to read those providers' quotas.

## Install

1. Open the `.dmg`, then drag **AI Monitor.app** onto **Applications**. With the ZIP, extract it and move the app into Applications.
2. Eject the disk image and open AI Monitor from Applications. It runs in the menu bar. Click its icon, open the settings gear, then **套餐排序** to enable the providers you actually use.
3. Open **账号连接** for the relevant connection instructions. New installations do not automatically read every installed account. Do not enter keys into the demonstration preview.

**Unsigned preview notice:** this build has an ad-hoc integrity signature, not a Developer ID distribution signature, and is **not notarized by Apple**. macOS can therefore block its first launch. Only after verifying the repository, file checksum and source, and deciding you trust this preview, you can try opening it, then go to **System Settings → Privacy & Security → Open Anyway** and confirm this specific app. Follow Apple's guidance: https://support.apple.com/102445 . On a managed Mac the administrator may prohibit this. Do not disable Gatekeeper globally, remove quarantine in bulk, or ignore a malware warning.

Closing a preview or a panel is not uninstalling the app. To quit, use **设置 → 账号连接 → 退出 AI Monitor**. Before replacing an older copy, quit that same edition. Public and Local use separate data directories; this package does not include the private Local edition.

## Account requirements

| Provider | What must already be available |
|---|---|
| Claude | Your official Claude Code login; approve this app's specific credential-read request when needed. |
| Kimi | Official Kimi CLI login or your existing subscription credential. |
| Codex | Official Codex CLI with the account whose quota you want to view. An API-key login is not a subscription plan. |
| Copilot | GitHub CLI login with a suitable Copilot account. |
| Antigravity | Official Antigravity application running and logged in. |
| Cursor | Official Cursor application login. A plan with an explicit zero allowance is shown as unquantifiable, not 100% remaining. |
| MiniMax | The correct regional Token Plan subscription key, configured inside MiniMax's connection section. |
| Windsurf | Official application's cached plan state; readings are explicitly non-live. |
| Kiro | Official kiro-cli installed and logged in; estimates remain labeled as estimates. |
| GLM | A supported existing regional subscription credential or documented environment configuration. |

No quota is inferred from an absent account. The app does not run a model prompt to test an allowance. Rate limits and cache timestamps are displayed honestly. Not every provider exposes every type of quota, API balance, or daily cost.

## 中文快速说明

本包适用于 **Apple Silicon（M 系列）Mac、macOS 14 及以上**。双击 DMG，把 **AI Monitor.app** 拖进 **Applications / 应用程序**，推出磁盘映像后再打开应用。ZIP 也可使用；不要下载 GitHub 自动生成的 Source code 当作安装包。

**已经内置 Python**，无需安装 Xcode、Python、Homebrew 或编译源码。但读取 Claude、Kimi、Codex 等套餐仍需对应官方客户端及你自己的有效登录。首次打开在 **设置 → 套餐排序** 中启用需要的平台；菜单栏只显示已选择的平台。

这是**未经过 Apple 公证的预发布版**，不是无提示的正式签名发行。macOS 首次拦截时，先核对来源和 SHA-256，并确认你愿意信任此预览版，再按 Apple 指引在 **系统设置 → 隐私与安全 → 仍要打开** 中对这个应用单独确认。不要关闭系统整体安全保护。企业管理设备可能不允许打开此类软件。

## Privacy and distribution status

No real account, secret, private Local code, or user's quota log is bundled. Original provider trademarks belong to their owners and do not indicate endorsement. This preview is published at the owner's request; the project's general source-code license remains undecided. CPython, its dependencies, and the Mozilla CA bundle retain their own notices under `AI Monitor.app/Contents/Resources/Python/licenses/`.

This package has passed local build, runtime relocation, isolated-home, TLS, parser and native UI checks. These checks do **not** substitute for testing on every macOS version, a second clean Mac, or Apple notarization. Verify `SHA256SUMS` against the downloaded file; only the listed release assets are application packages.
