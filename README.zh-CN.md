# AI Monitor

在 macOS 菜单栏查看 AI 套餐额度、API 余额与费用。

## 当前状态

本目录是公开工程边界，可单独复制、构建，不依赖私人实验目录。1.9.0 是开发候选版本：未内置 Python、未做 Developer ID 签名/公证，尚未选定开源许可证。不能把现有候选ZIP宣传为所有用户都能直接使用的正式发行版。

界面主要保留中文，文档提供中英文；完整界面多语言尚未实现。

## 构建与安装

需要 macOS 14+、Apple Command Line Tools、Swift 5.9+ 和可用的 `/usr/bin/python3`。使用本机架构构建。

```bash
bash scripts/test.sh
bash scripts/build.sh
```

构建、测试、打包不会安装或启动菜单栏应用，不读取真实账号进行测试，也不复用已安装的旧helper。独立检出时产物在 `dist/`，工作区内在 `../output/public/`。

`bash scripts/install.sh` 只显示计划。增加 `--install` 才安装；增加 `--launch` 才请求启动；替换同版要先退出它并加 `--replace`。不会触及旧 `Monitor.app`。

## 首次使用与限制

首次打开默认未启用任何套餐，请在设置中选择需要连接的服务。API账户未填凭据时不查询。不将未返回的余额、费用或额度伪造为0、100%或无限。

各服务能力不一样：订阅额度不等于API钱包；部分API需组织账单权限；Google AI Studio数字账单仍未接通。详见 `docs/PROVIDER_CAPABILITIES.md`。

## 本地版与公开版

共享模型与界面在 `Sources/MonitorCore`、`Sources/MonitorShared`；本目录只有公开入口 `Sources/Monitor/Main.swift`。私人实验模块不参与公开构建。公开版自己的设置、数据和钥匙串组件与Local和旧版分开，但同一个服务商账号、官方CLI登录和上游限流额度仍可能共享。

源码归属、隐私、安全和发行前检查分别见 `LICENSE_PENDING.md`、`PRIVACY.md`、`SECURITY.md`、`docs/RELEASE_CHECKLIST.md`。

## 候选应用存放说明

输出目录中的 `.app` 是指向本版本独立缓存中签名应用的本机快捷入口；真正的应用保存在 `~/Library/Caches/AIMonitor/<Public或Local>/Candidates/`。这样可以避免桌面同步软件为应用目录添加导致签名校验失败的元数据。输出目录的ZIP是真实文件，不是快捷入口；对外只选择ZIP，不能分享本机快捷入口。清理构建缓存后快捷入口可能失效，重新构建即可恢复；安装脚本会解析快捷入口并复制实际应用。

## 仓库与构建版本

应用名为 **AI Monitor**，计划公开仓库名为 `AI-Monitor`；双版本工作区中只有 `public/` 对应公开仓库。构建不会推送GitHub。BUILD.json记录实际公共提交、Local提交和是否存在未提交修改，并保留源码哈希。详见[Git对应关系](docs/GIT_WORKFLOW.md)。

## 新增套餐（1.9.0）

套餐列表扩展到十项：Kimi、Codex、Claude、GLM、Copilot、Antigravity、Cursor、MiniMax、Windsurf、Kiro。新增项默认关闭，先在套餐排序中启用。Windsurf 明确为本地缓存，MiniMax 的中国/国际订阅 Key 在其登录状态折叠项中分别配置。

账号连接页已删除独立的 Kimi Code、GLM Coding Plan 密钥配置块；对应套餐和已有凭据保留，API 余额页不变。新适配通过合成响应与隔离测试，不等同于用户真实账号已经连接。调研及接口说明见 `docs/PLAN_RESEARCH_2026_09.md`。
