# Thalnova AI Monitor

在 macOS 菜单栏查看 AI 套餐额度、API 余额与费用。

## 当前状态

本目录是公开工程边界，可单独复制、构建，不依赖私人实验目录。1.8.0 是开发候选版本：未内置 Python、未做 Developer ID 签名/公证，尚未选定开源许可证。不能把现有候选ZIP宣传为所有用户都能直接使用的正式发行版。

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
