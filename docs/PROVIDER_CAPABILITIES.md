# Implemented capability boundaries

This table describes the checked-in adapters, not a guarantee of current upstream API availability or successful live-account verification on every platform.

| Adapter | Implemented data | Important limits |
|---|---|---|
| Claude Code / Kimi Code / Codex / GLM / Copilot / Antigravity | Selected provider's plan quota windows | Official client/login requirements differ; windows are not forced into a universal five-hour/week model. Copilot can use its real monthly quota. |
| Cursor | Individual monthly allowance, separate reported pools | Uses the local Cursor application session; internal dashboard endpoint may change; no browser credential import. |
| MiniMax | Reported Token Plan 5-hour/weekly windows | Region-specific subscription key; remaining-count semantics validated; no wallet or concurrency-limit substitution. |
| Windsurf | Local application cached daily/weekly allowance or legacy counts | Always non-real-time; cache file modification time is not quota measurement time. |
| Kiro | Official CLI monthly credit usage and cap | No inference request; plan-only output stays unavailable; estimates are labeled; CLI may refresh its own login. |
| DeepSeek / Kimi API / SiliconFlow | Reported balance | No invented daily spend from balance differences. Region/currency must match. |
| OpenRouter | Key usage/limits or management-account credits, according to configured mode | Key limits and the account wallet are different measures. |
| OpenAI API / Claude API | Implemented organization cost endpoints | Requires suitable organization/admin billing access; not an individual model key wallet. |
| Google AI Studio | Key access check and official billing link | Numeric balance and daily cost are not implemented. |

Daily-cost presentation follows the adapters' UTC-day convention. Missing, stale, paginated-incomplete or permission-denied data must remain distinguishable from measured zero. Local display budgets do not prevent upstream charges.

Original providers retain their existing quota semantics. New 1.9.0 adapters use mocked fixtures and temporary official-state-shaped databases rather than live account validation. Revalidate provider endpoints and permissions against official documentation before each public release.

Kimi/GLM standalone credential cards have been removed without deleting their adapters or saved keys. See `PLAN_RESEARCH_2026_09.md` for the dated source and compatibility matrix.

### Cursor zero-capacity responses (1.9.3)

An explicit nonpositive or invalid plan limit takes precedence over placeholder percentages. Such accounts return no quota windows. A zero upper bound is not a full unused plan, nor evidence of unlimited access. Percentage-only contracts without an explicit limit remain supported.
