# Analytics Rollout Plan

Also see:

- [Analytics.md](Analytics.md)
- [AnalyticsQuestions.md](AnalyticsQuestions.md) - what are we trying to answer with analytics
- [AnalyticsArchitecture.md](AnalyticsArchitecture.md)

## Tracks

Each track answers a different slice of the questions in [AnalyticsQuestions.md](AnalyticsQuestions.md) using a different data source. Tracks are independent and ship as appetite allows.

- **[AnalyticsUntypedEventsPlan.md](AnalyticsUntypedEventsPlan.md)** — SDK skeleton + pageview firehose from the browser. Privacy lockdown lives here. This is the launch path — "slap PostHog in and call it a day."
- **[AnalyticsTypedEventsPlan.md](AnalyticsTypedEventsPlan.md)** — typed, named events for questions the firehose can't answer. Strictly sequential internal phases: Backend Pseudonym → Backend Events → Frontend Events.
- **[AnalyticsDbStatsPlan.md](AnalyticsDbStatsPlan.md)** — SQL against the production database for "what's in the system right now" stats (signups, edits, retention, the 80/20 editor curve). No PostHog involvement, no charting library.

## Which track answers which question

The high-level questions from [AnalyticsQuestions.md § Root questions](AnalyticsQuestions.md#root-questions), mapped to the track that answers them. ✅ marks questions answered by the launch (Untyped Events) — i.e. "slap PostHog in and call it a day." Everything else is deferred until appetite calls for it.

| High-level question                                                | Track that answers it                                                                                                   |
| ------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------- |
| Are we growing?                                                    | ✅ [Untyped Events](AnalyticsUntypedEventsPlan.md) for traffic; [DB Stats](AnalyticsDbStatsPlan.md) for signups + edits |
| What's driving growth? — external sources                          | ✅ [Untyped Events](AnalyticsUntypedEventsPlan.md) (referrer breakdown)                                                 |
| What's driving growth? — our content                               | ✅ [Untyped Events](AnalyticsUntypedEventsPlan.md) (per-URL pageview counts)                                            |
| Theses borne out? — title-vs-model market                          | [Typed Events](AnalyticsTypedEventsPlan.md) (search-click target)                                                       |
| Theses borne out? — browsing-as-discovery                          | ✅ [Untyped Events](AnalyticsUntypedEventsPlan.md) (session pageview depth, free from the firehose)                     |
| Theses borne out? — personas                                       | Not telemetry-answerable; user research                                                                                 |
| Editor community healthy / engaged / growing?                      | [DB Stats](AnalyticsDbStatsPlan.md) (active contributors, retention, 80/20 curve)                                       |
| Right features? — page-level usage                                 | ✅ [Untyped Events](AnalyticsUntypedEventsPlan.md)                                                                      |
| Right features? — in-page usage (claim revert, edit history, etc.) | [Typed Events](AnalyticsTypedEventsPlan.md) (generic `feature_used`)                                                    |
| Right features? — missing the mark / drop-off                      | [Typed Events](AnalyticsTypedEventsPlan.md) for flow-starts; [DB Stats](AnalyticsDbStatsPlan.md) for flow-completions   |
| Right features? — missing features                                 | Mostly user research; zero-result on-site searches via [Typed Events](AnalyticsTypedEventsPlan.md) hint at catalog gaps |

## Definition of Done

Each track's plan owns its own DoD. The cross-cutting requirements that hold across every PostHog-touching track:

- PostHog receives no PII, no IP, no fingerprinting-grade properties (verified by inspecting a real event payload, not just by reading the init config).
- Joining the PostHog dataset to the `User` table requires both the database and `ANALYTICS_PSEUDONYM_KEY` — there is no FK or table that bridges them.
- Lint pins prevent `posthog-js` / `posthog` imports outside the adapter modules.
- The locked-down init config is asserted by an integration test on each side; weakening any option fails the test.
