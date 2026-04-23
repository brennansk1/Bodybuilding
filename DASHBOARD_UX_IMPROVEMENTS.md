# Dashboard — UX/UI Improvement Backlog

A working list of dashboard widgets that need polish, useful widgets to add, and links to the docs an engineer needs to make progress.

> **Reading the priorities** — `P0` blocks comprehension (user can't tell what the widget says); `P1` materially improves clarity; `P2` is polish; `P3` is exploratory.

---

## 1 — Existing widgets that need work

### P0 — Comprehension blockers

| Widget | Issue | Fix direction |
|---|---|---|
| `illusion` (Illusion & V-Taper) | Three ratios (V-taper / X-frame / waist:height) crammed into one card without legend or what's-good context. User has flagged this as "hard to understand." | Split into a primary readout (X-frame) with V-taper + waist:height as secondary indicators. Add a tier-marker line on each ratio bar. |
| `detail_metrics` (Advanced Anthropometry) | Lat spread, VMO ratio, back width — shown as bare numbers with no "what's good" context, no tier reference. | Add tier-scaled targets per metric, color-code by status, drop the metric if the user has no measurement for it instead of showing 0. |
| `bf_confidence` | Micro-card with a CI range, but the methods badge ("Skinfold / JP-7 / Manual") is more important than the range and gets bottom billing. | Lead with method, secondary line for confidence label, tertiary for range. Add a "log a skinfold" CTA when only manual entry exists. |

### P1 — Material clarity wins

| Widget | Issue | Fix direction |
|---|---|---|
| `spider` (Proportion Spider) | Renders division-ideal vs current but doesn't overlay the *tier* ideal — at T2, hitting the absolute (T4) ring is the wrong target. | Add tier-scaled overlay ring (use `TIER_IDEAL_SCALING`). Show three bands: current / tier ideal / absolute ideal. |
| `natural_ceiling` | Ensemble of 5 ceiling models compressed to median + range; user can't see which model is binding their projection. | Add an expandable section listing each model's prediction. Highlight the binding (lowest) model. |
| `ari` (Autonomic Fuel Gauge) | Single 0–100 score with no driver breakdown — user can't tell *why* recovery is low. | Surface the top 2 contributing signals (HRV trend, sleep debt, RPE trend) directly on the card. |
| `comp_class` | Shows class assignment but doesn't show how close you are to the next class boundary. | Add a "+X kg to next class up" line. Especially relevant for the 10–15 kg gap windows in NPC class structure. |
| `recovery_trend` | HRV-only line. Sleep + resting HR are tracked but not visualized here. | Stack the three series on the same plot with a shared y-axis baseline. |
| `tomorrow_split` | Lists muscle-group names; no visual map of what's getting hit. | Add a tiny `MuscleHeatmap`-style figure with tomorrow's targets highlighted. |
| `strength_progression` | e1RM line per lift; no reference target / division benchmark / trend slope annotation. | Annotate slope (kg/wk gain), add a tier-relevant strength target if available. |
| `body_weight_trend` | 7-day rolling avg, but no annotation for phase changes (cut → bulk transitions). | Add vertical phase-shift markers; expose weekly rate-of-change number on the card itself. |
| `macro_adherence` | Week-only view; week-over-week trend hidden. | Add a 4-week sparkline above the daily bars to show direction. |
| `carb_cycle` | H/M/L cards but no calendar overlay showing which day of the week is which type. | Add a compact 7-day strip showing day-by-day type, mirroring the nutrition page calendar. |
| `pds_trajectory` | Same-day duplicate diagnostic runs created jagged history (already fixed via dedupe). Worth a guard that warns if the user's latest entry is < 7 days old. | Add freshness guard + "log new diagnostic" CTA when entries are stale. |

### P2 — Polish

| Widget | Issue | Fix direction |
|---|---|---|
| `heatmap` (Hypertrophy Heatmap) | No legend showing what colors mean. | Add a discrete 4-stop color legend at the bottom: Far / Developing / Close / Met. |
| `tier_readiness` | Already strong post-V3 — but the cycle progress bar is mid-card, separate from the gate-status strip. | Consider merging into a single header strip. |
| `goal_photo` | Static image; no progress overlay. | Add a 50/50 overlay with the user's most recent progress photo (when one exists) so they see distance to goal. |
| `daily_quote` | Single-line quote; no source attribution or category. | Optional: tag quotes by category (training / mindset / nutrition) and surface the tag. |
| `training_time` | Single number for the week; no historical context. | Add a 4-week comparison sparkline. |
| `weekly_volume` | MEV/MAV/MRV bars per muscle; "MEV breached" / "MRV exceeded" callouts missing. | Add a top-line summary: "3 muscles below MEV · 1 above MRV." |
| `prep_timeline` | Countdown but no "next milestone" callout. | Add "next phase: deload in N days." |
| `conditioning_score` | Gauge; could use intermediate tick marks for the tier bands. | Annotate the 50% / 75% / 90% / 95% tier-floor positions. |
| `unilateral_priority` | Lists lagging side; doesn't show the recommended unilateral set bonus. | Surface the "+N bonus sets per week on left side" prescription directly. |

---

## 2 — Useful widgets to add

### P0 — High coaching value

| Proposed widget | Why | Rough shape | Data source |
|---|---|---|---|
| **Mini-Cut Trigger** | Today the engine flags `mini_cut_active` server-side; no dashboard surface for the user to see the trigger approaching. | Gauge: current BF vs offseason ceiling, with "X% to mini-cut" text. | `/engine3/mini-cut/evaluate` |
| **Time-Since Checkpoint** | Cycle has a fixed cadence; users lose track. | Compact card: "Day 14/98 of cycle 1 · checkpoint in 12 weeks." | `/ppm/status` |
| **Posing Practice Tracker** | Posing is 50% of Classic scoring and 0% of dashboard. | Weekly checklist of poses practiced. | New `/posing/log` endpoint (small lift) |
| **Photo of the Day comparison** | The progress photo stack lives on `/progress` but a dashboard preview drives habit. | 2-column thumbnail (now vs +90d). | `/progress/photos?pose=front_dbl_biceps` |

### P1 — Clarity / motivation

| Proposed widget | Why | Rough shape | Data source |
|---|---|---|---|
| **Sleep Debt Cumulative** | `sleep_quality_week` shows the last 7 nights; no cumulative deficit. | Single number ("−4.5 hr this week") + 28-day trend. | `/checkin/sleep-week` extended |
| **Hydration tracker** | Macro adherence ignores water; affects weight readings + recovery. | Daily oz vs target gauge. | New `/checkin/hydration` (or fold into existing) |
| **Form-rating consistency (RPE)** | RPE tracked per-set; no widget showing whether RPE is matching prescription over time. | Sparkline of `actual_rpe − prescribed_rpe` delta. | `training_sets` table |
| **Macro split visualization** | Daily macros are numbers; no P/C/F donut. | Donut + day-of-week pattern. | `/engine3/prescription/current` |
| **Show countdown** | When comp date is set, no prominent stage countdown distinct from `prep_timeline`. | Massive day count + key milestone next. | `profile.competition_date` |
| **Achieved Tier Badge (large)** | We render a small `T1 → T2` chip; users don't see their *achieved* tier prominently. | Hero card with tier name + "highest demonstrated" copy. | `/ppm/status::current_achieved_tier` |
| **Symmetry Deviation Alert** | Bilateral diff is in `symmetry`; no alert when it crosses a threshold. | Banner-style card that only appears when spread > threshold. | `/engine1/symmetry` |

### P2 — Coaching extension

| Proposed widget | Why | Rough shape | Data source |
|---|---|---|---|
| **Supplement Compliance** | If user logs a stack, surface what was taken / missed. | 7-day grid. | New `/checkin/supplements` |
| **Travel/Life Event Impact** | The sim accounts for life events; users can't see their own. | Manual flag + expected impact estimate. | New `/checkin/life-events` |
| **Wearable Snapshot** | Once Whoop/Oura wired (deferred), surface yesterday's strain + recovery. | 3-stat card. | New `/wearables/snapshot` |
| **Cycle Comparison Mini** | `archive` page does it well; a mini version showing this cycle vs last on key metrics. | 4-row delta table. | `/insights/archive/cycle/{n-1}` |
| **Macro Adherence vs Outcome Correlation** | Show whether weekly adherence actually drove weight trend. | Scatter or quote: "Last 4 wks at 92% adherence → −0.6%/wk loss. On track." | Computed |

### P3 — Exploratory

| Proposed widget | Why |
|---|---|
| **Predicted Stage Photo** | Given current LBM + projected stage BF, render a silhouette estimate. (High effort, low certainty.) |
| **Coach Inbox** | If we add coach review later, surface unread messages. |
| **Community ranking** | Where does your physique sit vs anonymized cohort at same height/division. (Privacy implications — defer.) |

---

## 3 — Cross-cutting UX themes

- **Tier-awareness everywhere.** Every score widget should know the user's `target_tier` and surface the tier-relevant target, not the absolute ideal. Most still don't.
- **Status vocabulary consistency.** The 4-tier ✓ / ◐ / ◔ / ○ classification used in `TierReadinessCard` should propagate to other gate-style widgets (Conditioning Score bands, Macro Adherence thresholds).
- **Empty-state quality.** Many widgets currently show a degenerate value (0, "—") when data is missing. Replace with explicit empty-state cards that direct the user to the right action.
- **"Why is this number bad?"** Most numeric widgets show the score but not the contributing factors. ARI is the worst offender; tier-projection's adherence-product breakdown is the model to copy.
- **Glossary integration.** `ScoreInfoModal` exists — every numeric widget should expose its `scoreKey` so the ⓘ button is one tap to "what does this mean?"

---

## 4 — Where to read first

These docs are the load-bearing context for any dashboard work. All under `/docs/`.

| File | Why you need it |
|---|---|
| `docs/UI_THEME.md` | **Color tokens, type scale, status vocabulary, source-file map.** Read this before opening any component file. |
| `docs/DASHBOARD_WIDGETS.md` | The 35-widget catalog with registry line, render line, renderer component, and endpoint per widget. The "where do I make this change?" lookup table. |
| `docs/COMPETITIVE_TIERS.md` | The 10-gate threshold matrix per tier. Drives every tier-aware widget. Includes `TIER_IDEAL_SCALING` factors. |
| `docs/PPM.md` | Perpetual Progression Mode cycle structure, override pipeline, achieved-tier classification, projection math. Required for any PPM-touching widget. |
| `docs/DIVISION_VECTORS.md` | Per-division proportion vectors (the "ideal" denominator for HQI / Spider / Heatmap / MuscleGaps). |
| `docs/CALCULATIONS.md` | Formula reference. Read before changing how a number is computed. |
| `docs/ENGINES.md` | Engine 1–4 architecture overview. |
| `docs/API_REFERENCE.md` | Every endpoint by router. The dispatcher for "what URL does this widget call?" |
| `docs/DATABASE_SCHEMA.md` | Model + column reference. Touch this when adding fields a new widget needs. |
| `docs/FRONTEND_ROUTES.md` | Next.js page tree. Cross-link from new widgets to relevant deep-dive pages. |

### Code map (single source of truth)

| File | Role |
|---|---|
| `frontend/src/app/dashboard/page.tsx` | Card registry (L251–L367), body dispatcher (L1320–L2455), `ChartCard` wrapper |
| `frontend/src/components/PPMCards.tsx` | All PPM/V2 widget components |
| `frontend/src/components/V3InsightCards.tsx` | V3 insight widget components (TierTiming, LeverSensitivity, WeightTrend) |
| `frontend/src/components/TierReadinessCard.tsx` | Tier readiness — 10 gates, 4-tier status, summary strip |
| `frontend/src/components/ScoreInfoModal.tsx` | Central glossary — wire every score widget through this |
| `frontend/src/components/TierBadge.tsx` | Achieved → target chip |
| `frontend/tailwind.config.ts` | All design tokens |
| `frontend/src/app/globals.css` | Type scale + utility classes |

---

*Maintained 2026-04-23. Touch when shipping any dashboard polish so the backlog stays current.*
