# Implemented capability boundaries

This table describes the checked-in adapters, not a guarantee of current upstream API availability or successful live-account verification on every platform.

| Adapter | Implemented data | Important limits |
|---|---|---|
| Claude Code / Kimi Code / Codex / GLM / Copilot / Antigravity | Selected provider's plan quota windows | Official client/login requirements differ; windows are not forced into a universal five-hour/week model. Copilot can use its real monthly quota. |
| DeepSeek / Kimi API / SiliconFlow | Reported balance | No invented daily spend from balance differences. Region/currency must match. |
| OpenRouter | Key usage/limits or management-account credits, according to configured mode | Key limits and the account wallet are different measures. |
| OpenAI API / Claude API | Implemented organization cost endpoints | Requires suitable organization/admin billing access; not an individual model key wallet. |
| Google AI Studio | Key access check and official billing link | Numeric balance and daily cost are not implemented. |

Daily-cost presentation follows the adapters' UTC-day convention. Missing, stale, paginated-incomplete or permission-denied data must remain distinguishable from measured zero. Local display budgets do not prevent upstream charges.

The copied collectors preserve their prior algorithms. This workspace migration uses mocked fixtures rather than live account validation. Revalidate provider endpoints and permissions against official documentation before each public release.
