# Viltrum — Frontend Route Tree

Next.js 14 App Router pages under `frontend/src/app/`. Every file-based
route plus a one-liner describing what it renders.

For the dashboard's 35 widgets (each with its endpoint + renderer
component), see [`DASHBOARD_WIDGETS.md`](./DASHBOARD_WIDGETS.md).

---

## Route tree

```
/                                  src/app/page.tsx              Landing / marketing; redirects to /dashboard when logged in
/loading                           src/app/loading.tsx           Root loading state (spinning-logo loader)

/auth
├── /login                         app/auth/login/page.tsx       Username + password login
└── /register                      app/auth/register/page.tsx    Account creation

/onboarding                        app/onboarding/page.tsx       Multi-step onboarding wizard
                                                                 (profile → measurements → strength baselines → preferences → complete)

/dashboard                         app/dashboard/page.tsx        35-widget customizable dashboard with drag-and-drop
                                                                 reorder, Edit Dashboard toggle, localStorage persistence
                                                                 (`cpos_card_order`, `cpos_card_viz`)

/training                          app/training/page.tsx         Today's workout — gym mode, Now Playing, plate calculator,
                                                                 session-in-progress state machine
/training/exercises                app/training/exercises/page.tsx   Exercise catalog + custom-exercise creation
/training/history                  app/training/history/page.tsx     Session history, per-day drill-down
/training/program                  app/training/program/page.tsx     Macrocycle / mesocycle / microcycle overlays;
                                                                 PPM plan visualization when PPM enabled
/training/analytics                app/training/analytics/page.tsx   Volume trends + strength progression charts

/nutrition                         app/nutrition/page.tsx        Daily macros, meal plan, logging UI
/nutrition/peak-week               app/nutrition/peak-week/page.tsx  7-day peak-week protocol card

/checkin                           app/checkin/page.tsx          Daily + weekly check-in forms
                                                                 (quick / full / Fit3D modes, HRV ingest)
/checkin/review                    app/checkin/review/page.tsx   Weekly coaching review dashboard

/progress                          app/progress/page.tsx         Weight trend with 7d rolling avg, PDS history,
                                                                 progress-photo stack with pose-overlay
/progress/growth                   app/progress/growth/page.tsx  V3 — per-muscle circumference timeline (reads
                                                                 /insights/muscle-timeline/{site})

/timeline                          app/timeline/page.tsx         Combined event feed (check-ins, sessions, photos,
                                                                 milestones)

/archive                           app/archive/page.tsx          V3 — PPM cycle archive; per-cycle Prep Replay
                                                                 reconstruction (reads /insights/archive/cycles
                                                                 and /insights/archive/cycle/{n})

/settings                          app/settings/page.tsx         Profile + training + nutrition + food preferences +
                                                                 PPM controls (target tier, training factors,
                                                                 nutrition_mode_override, structural_priority_muscles,
                                                                 Telegram link, HealthKit API keys)

/admin                             app/admin/page.tsx            Admin-only — system health scan, user drill-down,
                                                                 cron log viewer, one-click fixes
```

---

## Layout + chrome

- **`app/layout.tsx`** — root layout: fonts (Contrail One, Crimson Pro, Inter, Tegaki), city-skyline backdrop, global providers.
- **`app/globals.css`** — Viltrum theme tokens: light marble background, Viltrumite-red (`#b8232a`-ish) accent, laurel/aureus/adriatic/centurion status colors.
- **`app/icon.tsx`, `app/apple-icon.tsx`** — favicon + PWA icon.

---

## Auth-gated vs public

| Page | Auth required |
|---|---|
| `/`, `/auth/*` | public |
| `/onboarding` | ✓ (but prior to `onboarding_complete`) |
| Everything else | ✓ |
| `/admin` | ✓ + admin role |

Enforcement is client-side: `hooks/useAuth.ts` redirects unauthenticated
users to `/auth/login`. The backend re-enforces every request via
`dependencies.get_current_user`.

---

## Notable component hubs

| File | Role |
|---|---|
| `src/components/PPMCards.tsx` | CycleProgress, ParityCheck, ChestWaist, CarbCycle, ConditioningStyle, NaturalCeiling, Illusion, UnilateralPriority, Conditioning, BFConfidence, TierReadinessSummary |
| `src/components/TierReadinessCard.tsx` | 10-gate breakdown with 4-tier status (Met / Close / Developing / Far) |
| `src/components/V3InsightCards.tsx` | TierTimingCard, LeverSensitivityCard, WeightTrendCard |
| `src/components/ScoreInfoModal.tsx` | Central score-glossary modal (17 entries) |
| `src/components/TierBadge.tsx` | Achieved → target tier chip |
| `src/components/SortableCard.tsx` | Dashboard drag-reorder wrapper |
| `src/components/SpiderChart.tsx`, `MuscleHeatmap.tsx`, `MiniLineChart.tsx`, `MacroAdherenceChart.tsx`, `WeeklyVolumeChart.tsx`, `RecoveryTrendChart.tsx`, `StrengthProgressionChart.tsx`, `BodyWeightTrendChart.tsx` | Per-widget chart components |

---

## API client

- `src/lib/api.ts` — fetch wrapper that injects `Authorization: Bearer` from `useAuth` and points at `NEXT_PUBLIC_API_URL` (dev) or relative `/api/v1` (prod, proxied via Next).
- `src/lib/types.ts` — shared TypeScript types mirroring Pydantic response shapes.

---

*Last indexed against frontend revision `e6c31a5`, 2026-04-23.*
