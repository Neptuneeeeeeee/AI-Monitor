# 2026-09-17：套餐扩展依据与支持边界

## 不能把不同用户量口径拼成排行榜

国际有可参考的开发者工具采用率，但它不等于 Token Plan 付费订阅人数。JetBrains Developer Ecosystem Survey 2026 调查了全球超过 15,000 名专业开发者；2026 年 5—7 月工作场景采用率包括 Claude Code 39%、GitHub Copilot 21%、Codex 16%、Cursor 12%、JetBrains AI/Junie 9%、OpenCode 7%、Antigravity 6%。这是可重叠的工具使用率，不是某档订阅的市场份额，也不代表全球所有用户。

Microsoft 2026-01-28 FY26 Q2 财报电话会披露 GitHub Copilot 付费订阅者超过 470 万。这是有明确日期的付费人数，不能与上述使用率直接相加或排序；也不能混淆为 Microsoft 365 Copilot 的席位数。

国内未查到 Kimi、GLM、MiniMax、阿里云百炼、火山方舟、腾讯 CodeBuddy 各自 Token/Coding Plan 统一口径且可比较的付费订阅人数。因此不声称任何一家“国内第一”，不把聊天 App 月活、模型 API 调用量、开发者注册数当成 Coding Plan 购买人数。

调研入口（核查日期为本页日期）：
- JetBrains 原始调查：https://blog.jetbrains.com/research/2026/08/ai-coding-agent-adoption-2026/
- Microsoft 原始披露：https://www.microsoft.com/en-us/investor/events/fy-2026/earnings-fy-2026-q2
- 阿里云百炼 Coding Plan：https://help.aliyun.com/zh/model-studio/coding-plan
- MiniMax 中国 Token Plan：https://platform.minimax.cn/docs/token-plan/faq
- MiniMax 国际 Token Plan：https://platform.minimax.io/docs/token-plan/faq

## 本轮新增四个适配器，不宣称它们是用户量前四

原有六个提供商保留：Kimi、Codex、Claude、GLM、Copilot、Antigravity。新增 Cursor、MiniMax、Windsurf、Kiro。选择兼顾实际使用范围与可验证的额度来源；没有可信查询路径的服务，不用占位卡片冒充已接通。

| 服务 | 本轮实现 | 凭据/连接 | 限制 |
|---|---|---|---|
| Cursor | 个人套餐月度百分比；必要时保留 Auto/API 独立池 | 显式启用后提取 Cursor 应用自己的 accessToken，查询 `GET https://cursor.com/api/usage-summary` | 内部控制台接口可能变更；不读取浏览器、不续期 token、不把 team/on-demand 余额混入个人套餐 |
| MiniMax | Token Plan 5 小时与周窗口 | 在登录状态的 MiniMax 折叠项内选中国/国际并保存订阅 Key | Key 仅发往选定区域；`usage_count` 字段表示剩余量，不当作已使用；直接百分比优先；不把余额、并发、倒计时当额度 |
| Windsurf | 本地 `cachedPlanInfo` 中的每日/每周百分比，或旧版消息/操作计数 | 显式启用后读取官方应用指定状态项 | 始终是非实时缓存；显示状态文件修改时间，不宣称是服务器实测时间；没有实现网页会话提取 |
| Kiro | 官方 CLI `/usage` 明确返回的本月 Credits 用量/上限 | 先自行 `kiro-cli login`，再启用 | 只有计划名或百分比而没有分子分母时不虚构额度；不合并赠额/超额消费；不根据月日字符串推测重置时区；Estimated Usage 明确显示为官方估计 |

MiniMax 当前官方接口：`GET https://www.minimaxi.com/v1/token_plan/remains`（中国）与 `GET https://www.minimax.io/v1/token_plan/remains`（国际）。均使用本区域订阅 Key。平台普通按量 API 余额与订阅额度分开。固定/滚动窗口按区域及服务商实际返回解释，不能以本机时间猜测 reset。

Kiro 精确命令：`kiro-cli chat --no-interactive /usage`。不发送提示词、不传 trust-all-tools、不恢复工作对话、不用模型请求测试额度。CLI 可自行续期其官方登录，因此不能声称官方 CLI 自身完全零写入。文档：https://kiro.dev/docs/reference/slash-commands/ 与 https://kiro.dev/docs/reference/cli-commands/ 。

Cursor/Windsurf 是应用内部状态/控制台契约；MiniMax 使用公开说明的接口，JSON 字段用公开实现交叉核验。适配器为本项目独立编写，以下仅为协议研究来源，没有引入其库或复制其实现：
- https://raw.githubusercontent.com/steipete/CodexBar/main/Sources/CodexBarCore/Providers/Cursor/CursorAppAuth.swift
- https://raw.githubusercontent.com/steipete/CodexBar/main/Sources/CodexBarCore/Providers/Cursor/CursorStatusProbe.swift
- https://raw.githubusercontent.com/steipete/CodexBar/main/Sources/CodexBarCore/Providers/Windsurf/WindsurfStatusProbe.swift
- https://raw.githubusercontent.com/steipete/CodexBar/main/Sources/CodexBarCore/Providers/MiniMax/MiniMaxUsageFetcher.swift
- https://raw.githubusercontent.com/steipete/CodexBar/main/Sources/CodexBarCore/Providers/Kiro/KiroStatusProbe.swift

## 已知变更和未接入项

Google 已宣布 2026-06-18 停止个人用户及 Google AI Pro/Ultra 通过旧 Gemini CLI/IDE Code Assist 的消费者 OAuth 访问；Standard/Enterprise 不属于该消费者退役范围。因此本轮不把旧消费者 Gemini CLI 接口作为新的通用订阅适配。原有 Antigravity 适配保留。来源：https://developers.google.com/gemini-code-assist/docs/deprecations/code-assist-individuals 。

Copilot 从 2026-06-01 转向 AI Credits 用量计费。现有适配保留真实返回的窗口；对于 token-based 账号未提供可量化百分比的情况，明确显示未提供，不猜 Premium 额度。来源：https://github.blog/news-insights/company-news/github-copilot-is-moving-to-usage-based-billing/ 。

JetBrains AI/Junie、阿里云百炼、火山方舟、腾讯 CodeBuddy/WorkBuddy、TRAE、Qoder 可继续评估。此清单不是当前支持列表。未取得稳定、范围明确且经验证的个人额度查询路径时，不添加假的数值展示，也不为覆盖它们自动读取浏览器或要求完整磁盘权限。

## 本次界面与隐私边界

账号连接中已删除独立的“Kimi Code”和“GLM Coding Plan”密钥配置块。登录状态列表里的 Kimi/GLM 提供商保留；Kimi 使用官方 CLI 或已有订阅 Key，GLM 使用原区域凭据或对应环境变量，区域选择保留在 GLM 折叠项内。不会删除已保存密钥，不更改 API 余额页。

新增服务默认未启用。Cursor/Windsurf 为避免改写官方 SQLite 的 WAL/SHM，先在权限 0700 的临时目录复制 DB/WAL 快照，查询指定 ItemTable 键后关闭连接并清理。这个临时数据库副本可能包含其他数据库字节，但程序不解析或上传聊天内容；不得将此描述为“数据库其他内容从未被读取到内存或磁盘”。不创建官方数据库的 sidecar，不扫描浏览器。

MiniMax Key 经 stdin 私有管道进入本版本钥匙串辅助组件，明文不写入设置、JSON、日志或命令行。连接 JSON 只含区域和随机版本标记。账号切换期间的旧额度不跨账号延用，不清空服务商限流记录。并发仍为 2，单轮有上限；Cursor/MiniMax 至少间隔 10 分钟，Kiro 至少 15 分钟，Windsurf 缓存至少 5 分钟。限制为本项目保守查询策略，不声称是厂商官方频率。

## 验证口径

自动验收使用明确的合成响应、临时 SQLite 数据库、假 CLI/网络调用、隔离 Swift 偏好和模拟界面。真正的用户账号尚未逐一完成连接测试；不得把单元测试或看到新卡片当作真实厂商授权/账单已验证。候选包仍受原有发行检查约束：Python 打包、正式签名/公证、许可证与第三方资源审查、干净 Mac 安装测试仍需完成。
