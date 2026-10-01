# 2026-10-01：编码 Agent 自有套餐调研

问题：OpenCode、Pi、Cline 等编码 Agent 是否也有类似 Kimi/GLM/MiniMax Token Plan 的“按时间窗口限额”的订阅？有的话能否用只读方式查询剩余额度。核查日期即本页日期，接口以厂商自己的源码或其官方客户端实际使用的路径为准。

| 工具 | 自有套餐 | 额度形态 | 本版处理 |
|---|---|---|---|
| OpenCode | **OpenCode Go**（$10/月；另有 Go Plus） | 按金额计算的 5 小时 / 每周 / 每月三个窗口，分别为月额度的 20% / 50% / 100% | 新增适配器 `opencode` |
| Cline | **ClinePass**（$9.99/月，开放权重模型） | 滚动 5 小时 / 自然周 / 自然月三个窗口 | 新增适配器 `cline` |
| Pi（pi.dev，badlogic/earendil-works） | 无 | 只登录 Claude Pro/Max、ChatGPT/Codex、GitHub Copilot、Gemini/Antigravity 等现有订阅或 API Key | 不新增；这些订阅本身已有适配器 |
| Kilo Code | Kilo Pass（$19/$49/$199） | 预付余额加赠送 Credits，按量扣费，没有时间窗口限额 | 不新增；钱包余额不是套餐窗口 |

## OpenCode Go

- 用量接口：`GET https://opencode.ai/zen/go/v1/usage`，`Authorization: Bearer <OpenCode 控制台 Key>`。实现见官方仓库 `anomalyco/opencode` 的 `packages/console/app/src/routes/zen/go/v1/usage.ts`：返回 `{"usage":{"rolling"|"weekly"|"monthly":{"status","percent","resetsAt"}}}`，`percent` 为**已用**百分比（服务端 `Math.floor`，达到上限时为 100、`status` 为 `rate-limited`）。
- 无 Key 或 Key 无效：401 `AuthError`；Key 所在工作区没有 Go 订阅：403 `EntitlementError`（本应用显示“未提供额度”，不当作 0%）。
- 凭据来源：OpenCode 执行 `/connect`（`opencode auth login`）后写入 `~/.local/share/opencode/auth.json` 的 `opencode-go` 项（`{"type":"api","key":...}`）；同一工作区的 `opencode`（Zen）Key 也能查询，作为后备。
- 文档：https://opencode.ai/docs/go/ ；公开接口需求与实现讨论：https://github.com/anomalyco/opencode/issues/16017 ，第三方已接入的参考：https://github.com/steipete/CodexBar/pull/2879 。
- 5 小时窗口时长来自服务端配置，官方文档写明为 5 小时；月窗口按订阅日起算，不按自然月。

## ClinePass

- 用量接口：`GET https://api.cline.bot/api/v1/users/me/plan/usage-limits`，返回 `{"success":true,"data":{"limits":[{"type":"five_hour"|"weekly"|"monthly","percentUsed","resetsAt"}]}}`，`percentUsed` 为**已用**百分比。该路径来自 Cline 官方控制台自带的 API 客户端，**未公开文档化**，可能变更。没有订阅时返回 404（no plan history）或空列表，本应用显示“未提供额度”。
- 凭据来源：Cline VS Code 扩展 / CLI 把 Cline 账号登录写入 `~/.cline/data/settings/providers.json` 的 `providers.cline.settings.auth`（ClinePass 同样存于 `cline` 项，旧文件可能在 `cline-pass` 项）。账号接口只接受带 `workos:` 前缀的令牌。
- 令牌约每小时由 Cline 自己续期。本应用**不代为续期**（续期会轮换 Cline 持有的 refresh token），令牌过期时保留上次读数并标为非实时，提示打开 Cline。
- 文档：https://docs.cline.bot/getting-started/clinepass ；控制台：https://app.cline.bot/dashboard/subscription?personal=true 。

## 2026-10-01 线上核对

不带凭据和带无效凭据分别请求两个接口，均返回 JSON 401（OpenCode：`{"type":"error","error":{"type":"AuthError",...}}`；Cline：`{"error":"Unauthorized: ..."}`），与上述源码一致，未遇到浏览器验证页。本机没有 OpenCode Go 订阅 Key，Cline 也未以新版账号登录，因此两项适配器的成功路径仅由按官方源码构造的离线样例验证（`tests/test_agent_plans.py`），尚未用真实订阅账号核对。
