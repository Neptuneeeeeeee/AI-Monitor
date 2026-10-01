# Implemented capability boundaries

This table describes the checked-in adapters, not a guarantee of current upstream API availability or successful live-account verification on every platform.

| Adapter | Implemented data | Important limits |
|---|---|---|
| Claude Code / Kimi Code / Codex / GLM / Copilot / Antigravity | Selected provider's plan quota windows | Official client/login requirements differ; windows are not forced into a universal five-hour/week model. Copilot can use its real monthly quota. |
| Cursor | Individual monthly allowance, separate reported pools | Uses the local Cursor application session; internal dashboard endpoint may change; no browser credential import. |
| MiniMax | Reported Token Plan 5-hour/weekly windows | Region-specific subscription key; remaining-count semantics validated; no wallet or concurrency-limit substitution. |
| Windsurf | Local application cached daily/weekly allowance or legacy counts | Always non-real-time; cache file modification time is not quota measurement time. |
| Kiro | Official CLI monthly credit usage and cap | No inference request; plan-only output stays unavailable; estimates are labeled; CLI may refresh its own login. |
| OpenCode Go | Server-computed 5-hour, weekly and subscription-month used percentages from `GET /zen/go/v1/usage` | Uses the key OpenCode saved with `/connect`; a workspace without Go is reported as unsupported, and Zen balance is never shown as plan quota. |
| ClinePass | 5-hour, weekly and monthly `percentUsed` windows from Cline's account usage-limits endpoint | Undocumented endpoint used by Cline's own dashboard; reads Cline's sign-in without refreshing it, so an expired token keeps the last reading marked as cached until Cline renews it. Pay-as-you-go credits are not plan quota. |

Missing, stale or permission-denied data must remain distinguishable from measured zero.

API balance and daily-cost adapters (DeepSeek, Kimi API, OpenAI/Claude organization costs, SiliconFlow, OpenRouter, Google AI Studio) and their key management were removed in 1.10.0. Pi has no plan of its own; its Claude, ChatGPT/Codex, Copilot and Gemini/Antigravity logins are the subscriptions already covered above. See `PLAN_RESEARCH_2026_10.md`.

Original providers retain their existing quota semantics. New 1.9.0 adapters use mocked fixtures and temporary official-state-shaped databases rather than live account validation. Revalidate provider endpoints and permissions against official documentation before each public release.

Kimi/GLM standalone credential cards have been removed without deleting their adapters or saved keys. See `PLAN_RESEARCH_2026_09.md` for the dated source and compatibility matrix.

### Cursor zero-capacity responses (1.9.3)

An explicit nonpositive or invalid plan limit takes precedence over placeholder percentages. Such accounts return no quota windows. A zero upper bound is not a full unused plan, nor evidence of unlimited access. Percentage-only contracts without an explicit limit remain supported.
