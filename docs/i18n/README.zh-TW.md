# AI Monitor

在 macOS 選單列，一眼查看 AI 訂閱額度與 API 餘額。

[English](../../README.md) · [简体中文](../../README.zh-CN.md) · **繁體中文** · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Português](README.pt-BR.md)

**[下載 Mac 版](https://github.com/Neptuneeeeeeee/AI-Monitor/releases/download/v1.9.4/AI-Monitor-v1.9.4-macos-arm64.dmg)** · [ZIP 壓縮檔](https://github.com/Neptuneeeeeeee/AI-Monitor/releases/download/v1.9.4/AI-Monitor-v1.9.4-macos-arm64.zip) · [版本說明](https://github.com/Neptuneeeeeeee/AI-Monitor/releases/tag/v1.9.4)

**Apple Silicon（M 系列）· macOS 14 以上 · 已內建 Python**

開啟 DMG，將 **AI Monitor.app** 拖入 **應用程式**，再到設定中選擇要顯示的訂閱服務。無須另裝 Python、Xcode 或 Homebrew；部分平台仍需官方用戶端及有效登入。

> **預覽版本：** 尚無 Developer ID 發行簽章，也未經 Apple 公證。首次開啟可能被 macOS 阻擋，請先閱讀[安裝說明](../INSTALL.md)，確認來源後再決定是否開啟，不要關閉系統安全防護。

![AI Monitor 訂閱、設定與 API 餘額介面](../images/zh-CN/hero.png)

*圖片中的數值均為範例。v1.9.4 應用程式介面主要為簡體中文；英文圖片是文件用的翻譯預覽。上方語言連結只切換 README，不會改變應用程式語言。*

## 主要功能

- 查看剩餘額度與重設時間，選單列採用簡潔的黑白橫條。
- 自由選擇顯示的訂閱服務，並調整順序。
- 切換查看 API 餘額或當日費用，依平台提供的資料而定。

## 支援的平台

**訂閱服務:** Claude · Codex · Kimi · GitHub Copilot · Antigravity · Cursor · GLM · MiniMax · Windsurf · Kiro

**API 連線:** DeepSeek · Kimi · OpenAI · Claude · SiliconFlow · OpenRouter. Google AI Studio 僅檢查存取權限，不顯示數字帳單.

各平台與帳號提供的資料不同。Windsurf 顯示本機快取，而非即時查詢；限制與連線需求請見[支援詳情](../PROVIDER_CAPABILITIES.md)。

<details>
<summary>更多介面圖片</summary>

<p>
<img src="../images/zh-CN/plans.png" alt="訂閱額度範例" width="31%">
<img src="../images/zh-CN/settings.png" alt="訂閱選擇與排序" width="31%">
<img src="../images/zh-CN/api-balance.png" alt="API 餘額與費用範例" width="31%">
</p>

</details>

[安裝說明](../INSTALL.md) · [支援詳情](../PROVIDER_CAPABILITIES.md) · [隱私說明](../../PRIVACY.md) · [更新紀錄](../../CHANGELOG.md) · [從原始碼建置](../DEVELOPMENT.md)

原始碼授權條款尚未選定，請見[授權說明](../../LICENSE_PENDING.md)及[第三方聲明](../../THIRD_PARTY_NOTICES.md)。
