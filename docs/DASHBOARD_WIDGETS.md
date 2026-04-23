# Dashboard Widgets — Full Reference

The dashboard renders **35 widgets** from a central `CARD_REGISTRY` in
`frontend/src/app/dashboard/page.tsx`. Each widget declares its visibility
predicate, default subtitle, glossary key (for the central `ScoreInfoModal`),
and unlock hint. The render body is a separate `bodies.<key> = (...)`
assignment further down the same file.

This doc maps every widget to:
1. Its **registry entry** line (where the predicate + subtitle live)
2. Its **render body** line (where the JSX is built)
3. The **renderer component** it uses (and which file that component lives in)
4. The **API endpoint** it consumes
5. The visibility predicate

All line numbers below reference the current frontend tree (revision `8312471`, 2026-04-23).

---

## 1 — Overview

| Concept | Detail |
|---|---|
| Total widgets | 35 |
| Default-visible (fresh install) | 6 — `workout_tomorrow`, `macro_adherence`, `mesocycle_progress`, `tier_timing`, `weight_trend_rate`, `lever_sensitivity` |
| Default-hidden | 29 — user opts in via Edit Dashboard |
| Render container | `ChartCard` (defined inline in `dashboard/page.tsx` ~L2616) |
| Status indicators (Tier Readiness only) | 4-tier: ✓ Met / ◐ Close / ◔ Developing / ○ Far |
| Tier badge surfaces | TierReadiness · MuscleGaps · Spider · Heatmap · Illusion · TierTiming |

**Visibility predicates** (`DashboardContext`):
- `ppm_enabled` — Perpetual Progression Mode toggled on
- `competition_date` — explicit comp date set
- `target_tier` — T1–T5 selected
- `current_cycle_start_date` — improvement cycle started
- `division` — division code (drives Classic-only widgets)
- `wrist_circumference_cm`, `ankle_circumference_cm` — for natural ceiling math
- `has_hqi` — at least one diagnostic run
- `has_pds_history` — ≥ 2 PDS entries
- `has_program` — active training program
- `has_rx` — active nutrition prescription
- `has_strength_logs` — ≥ 1 strength log entry
- `has_tape.{site}` — tape measurement present for site

---

## 2 — Widget Catalog

> **Reading the table:** "registry" is the line in `dashboard/page.tsx` where the widget's predicate + subtitle are declared inside `CARD_REGISTRY`. "render" is the line where the JSX body is built. "renderer" is the component used inside that body — `dashboard/page.tsx` means inline JSX (no extracted component); a filename means the component lives there.

### Core / Always-relevant

| Key | Label | Registry | Render | Renderer | Endpoint | Visible when |
|---|---|---:|---:|---|---|---|
| `workout_tomorrow` | Tomorrow's Workout | L266 | L2355 | inline (`dashboard/page.tsx`) | `/engine2/session/{date}` | `has_program` |
| `macro_adherence` | Macro Adherence | L268 | L2129 | `MacroAdherenceChart.tsx` | `/engine3/adherence` | `has_rx` |
| `mesocycle_progress` | Mesocycle Progress | L270 | L2159 | inline (uses `program`) | `/engine2/program/current` | `has_program` |
| `tomorrow_split` | Tomorrow's Split | L273 | L2320 | inline | `/engine2/session/{date}` | `has_program` |
| `daily_quote` | Daily Fire | L275 | L2436 | inline (uses `quotes.ts`) | static | always |
| `goal_photo` | Your Goal | L277 | L2451 | inline | `/auth/goal-photo` | always |
| `sleep_quality_week` | Sleep Quality Week | L279 | L2390 | inline | `/checkin/sleep-week` | always |
| `phase_rec` | Phase Recommendation | L295 | L1605 | inline | `/engine1/phase-recommendation` | always |
| `comp_class` | Competition Class | L297 | L1665 | inline | `/engine1/class-estimate` | `competition_date` OR `ppm_enabled` |

### Diagnostic / HQI-driven

| Key | Label | Registry | Render | Renderer | Endpoint | Visible when |
|---|---|---:|---:|---|---|---|
| `spider` | Proportion Spider | L281 | L1320 | `SpiderChart.tsx` | `/engine1/muscle-gaps` (site_scores) | `has_hqi` |
| `muscle_gaps` | Muscle Gaps | L284 | L1343 | inline list (tier-aware) | `/engine1/muscle-gaps` (tier-scaled) | `has_hqi` |
| `pds_trajectory` | PDS Trajectory | L287 | L1417 | `MiniLineChart.tsx` | `/engine1/pds` | `has_pds_history` |
| `heatmap` | Hypertrophy Heatmap | L290 | L1450 | `MuscleHeatmap.tsx` | `/engine1/muscle-gaps` (tier-scaled) | `has_hqi` |
| `symmetry` | Bilateral Symmetry | L293 | L1540 | inline | `/engine1/symmetry` | `has_tape.bicep` |
| `detail_metrics` | Advanced Anthropometry | L303 | L1701 | inline | `/engine1/diagnostic` (advanced) | `has_hqi` |
| `bf_confidence` | BF Estimate Confidence | L357 | L2058 | `BFConfidenceCard` (`PPMCards.tsx` L725) | `/engine1/diagnostic` | `has_hqi` |

### Training / Volume

| Key | Label | Registry | Render | Renderer | Endpoint | Visible when |
|---|---|---:|---:|---|---|---|
| `weekly_volume` | Weekly Volume | L315 | L2139 | `WeeklyVolumeChart.tsx` | `/engine2/volume/weekly` | `has_program` |
| `strength_progression` | Strength Progression | L310 | L2105 | `StrengthProgressionChart.tsx` | `/engine2/strength-log` | `has_strength_logs` |
| `training_time` | Weekly Training Time | L323 | L2258 | inline | `/engine2/training-time` | always |

### Recovery / Autoregulation

| Key | Label | Registry | Render | Renderer | Endpoint | Visible when |
|---|---|---:|---:|---|---|---|
| `ari` | Autonomic Fuel Gauge | L305 | L1743 | inline | `/engine2/ari` | always |
| `recovery_trend` | Recovery Trend | L318 | L2149 | `RecoveryTrendChart.tsx` | `/engine2/recovery` | always |

### Nutrition

| Key | Label | Registry | Render | Renderer | Endpoint | Visible when |
|---|---|---:|---:|---|---|---|
| `carb_cycle` | Carb Cycle | L339 | L1956 | `CarbCycleCard` (`PPMCards.tsx` L235) | `/engine3/carb-cycle` | `has_rx` |
| `energy_availability` | Energy Availability | L320 | L2208 | inline | `/engine3/energy-availability` | `has_rx` |
| `body_weight_trend` | Body Weight Trend | L313 | L2115 | `BodyWeightTrendChart.tsx` | `/checkin/weight-history` | always |

### Competition prep

| Key | Label | Registry | Render | Renderer | Endpoint | Visible when |
|---|---|---:|---:|---|---|---|
| `prep_timeline` | Competition Countdown | L308 | L1811 | inline | `/engine1/diagnostic` (prep_timeline) | `competition_date != null` |
| `conditioning_score` | Conditioning Score | L354 | L2039 | `ConditioningCard` (`PPMCards.tsx` L670) | client-side from `/engine1/diagnostic.body_fat` | `competition_date != null` |
| `conditioning_style` | Conditioning Style | L343 | L1973 | `ConditioningStyleCard` (`PPMCards.tsx` L299) | manual + `/ppm/checkpoint` | Classic + (`competition_date` OR `ppm_enabled`) |

### PPM / V2 metrics

| Key | Label | Registry | Render | Renderer | Endpoint | Visible when |
|---|---|---:|---:|---|---|---|
| `tier_readiness` | Tier Readiness | L326 | L1909 | `TierReadinessCard.tsx` (root) | `/ppm/evaluate` | `ppm_enabled` + `target_tier` |
| `cycle_progress` | Improvement Cycle | L329 | L1896 | `CycleProgressCard` (`PPMCards.tsx` L33) | `/ppm/status` + `/ppm/plan/{week}` | `ppm_enabled` + `current_cycle_start_date` |
| `parity_check` | Arm-Calf-Neck Parity | L334 | L1928 | `ParityCheckCard` (`PPMCards.tsx` L99) | `/ppm/evaluate` (per_metric.parity) | `ppm_enabled` + Classic + neck/bicep/calf tape |
| `chest_waist` | Chest : Waist Ratio | L337 | L1944 | `ChestWaistCard` (`PPMCards.tsx` L159) | `/ppm/evaluate` (per_metric) | chest + waist tape |
| `natural_ceiling` | Natural Ceiling | L345 | L1983 | `NaturalCeilingCard` (`PPMCards.tsx` L368) | `/ppm/attainability` | `ppm_enabled` + wrist + ankle |
| `illusion` | Illusion & V-Taper | L349 | L2005 | `IllusionCard` (`PPMCards.tsx` L490) | `/ppm/evaluate` (per_metric.illusion_score) | shoulders + waist tape |
| `unilateral_priority` | Unilateral Priority | L352 | L2029 | `UnilateralPriorityCard` (`PPMCards.tsx` L599) | `/engine1/symmetry` | `has_tape.bicep` |

### V3 insight widgets

| Key | Label | Registry | Render | Renderer | Endpoint | Visible when |
|---|---|---:|---:|---|---|---|
| `tier_timing` | Tier Timing | L360 | L2073 | `TierTimingCard` (`V3InsightCards.tsx` L35) | `/insights/tier-projection` | `ppm_enabled` + `target_tier` |
| `lever_sensitivity` | What Moves the Needle | L363 | L2085 | `LeverSensitivityCard` (`V3InsightCards.tsx` L106) | `/insights/sensitivity` | always |
| `weight_trend_rate` | Weight Trend + Rate | L365 | L2095 | `WeightTrendCard` (`V3InsightCards.tsx` L158) | `/insights/weight-trend?days=90` | always |

---

## 3 — Status & Glossary Hooks

### Score glossary modal — `frontend/src/components/ScoreInfoModal.tsx`

Each widget that uses an internal score declares a `scoreKey` (and optional `scoreExtraKeys`) that opens the central glossary entry. **17 entries today** (see `ScoreInfoModal.tsx::ENTRIES`):

`hqi · pds · illusion · xframe · vtaper · waist_height · conditioning_pct · ffmi · mev_mav_mrv · ari · energy_availability · parity · casey_butt · kouri_band · ceiling_envelope · tier_readiness · carb_cycle · e1rm · natural_attainability`

Each entry carries:
- **What** — plain-English description
- **Good** — what's competitive in real numbers
- **How** — one-line computation summary

`ScoreInfoButton` (same file, exported separately) is the trigger embedded in `ChartCard` headers — see `dashboard/page.tsx::ChartCard` ~L2616.

### Tier badge — `frontend/src/components/TierBadge.tsx`

`TierBadge` renders an achieved + target chip (`T1 → T2`) on:
- TierReadiness · MuscleGaps · Spider · Heatmap · Illusion · TierTiming

Pulls `current_achieved_tier` (V3, written by `/ppm/checkpoint`) and `target_tier` from `/ppm/status`. Coerces raw `number | null` from API into the `CompetitiveTier` enum.

### Tier Readiness 4-tier status (V3) — `TierReadinessCard.tsx`

Per-gate status classification (`STATUS_COPY` constant):

| Status | Threshold | Color | Glyph |
|---|---|---|---|
| Met | `pct_progress ≥ 1.00` | laurel | ✓ |
| Close | `≥ 0.85` | aureus | ◐ |
| Developing | `≥ 0.60` | adriatic | ◔ |
| Far | `< 0.60` | centurion | ○ |

Plus a Gate Status summary strip at the top: `✓ N · ◐ N · ◔ N · ○ N` (counts auto-derived from `per_metric` distribution).

---

## 4 — Edit Dashboard / Layout

User can:
- **Toggle visibility** per widget via the Edit Dashboard pencil — `dashboard/page.tsx::hideCard` / `showCard`
- **Reorder** via drag-and-drop (`@dnd-kit/sortable`) — `SortableCard.tsx` + `DndContext` handlers in `dashboard/page.tsx::handleDragEnd`
- **Persist** to `localStorage` keys: `cpos_card_order`, `cpos_card_viz`

`DEFAULT_CARD_ORDER` (`dashboard/page.tsx` ~L296) derives from registry definition order. `ONBOARDING_DEFAULT_VIZ` (~L373) enables 6 widgets on first install (the rest are hidden until the user adds them).

---

## 5 — Code Pointers (Single Source of Truth)

| File | Role | Key symbols |
|---|---|---|
| `frontend/src/app/dashboard/page.tsx` | Card registry, body dispatcher, render layer | `CARD_REGISTRY` (L251–L367), `bodies.<key> = ...` (L1320–L2455), `ChartCard` (~L2616), `DashboardContext` (L228), `DEFAULT_CARD_ORDER` (~L296), `ONBOARDING_DEFAULT_VIZ` (~L373) |
| `frontend/src/components/ScoreInfoModal.tsx` | Central glossary | `ENTRIES`, `ScoreInfoButton` |
| `frontend/src/components/TierBadge.tsx` | T1–T5 achieved/target chip | `coerce()`, `TierBadge` default export |
| `frontend/src/components/TierReadinessCard.tsx` | Tier readiness — 10 gates with 4-tier status | `STATUS_COPY`, `classifyMetric`, `GROUPS`, `METRIC_LABELS` |
| `frontend/src/components/PPMCards.tsx` | PPM / V2 widget components | `CycleProgressCard` (L33), `ParityCheckCard` (L99), `ChestWaistCard` (L159), `CarbCycleCard` (L235), `ConditioningStyleCard` (L299), `NaturalCeilingCard` (L368), `IllusionCard` (L490), `UnilateralPriorityCard` (L599), `ConditioningCard` (L670), `BFConfidenceCard` (L725), `TierReadinessSummary` (L777) |
| `frontend/src/components/V3InsightCards.tsx` | V3 insight widgets | `TierTimingCard` (L35), `LeverSensitivityCard` (L106), `WeightTrendCard` (L158) |
| `frontend/src/components/SortableCard.tsx` | DnD wrapper + edit-mode hide button | `SortableCard` default export |
| `frontend/src/components/SpiderChart.tsx` | Radar viz for proportions | `SpiderChart` default export |
| `frontend/src/components/MuscleHeatmap.tsx` | Body-map heatmap | `MuscleHeatmap` default export |
| `frontend/src/components/MiniLineChart.tsx` | PDS trajectory sparkline | `MiniLineChart` default export |
| `frontend/src/components/MacroAdherenceChart.tsx` | Macro adherence chart | `MacroAdherenceChart` default export |
| `frontend/src/components/WeeklyVolumeChart.tsx` | MEV/MAV/MRV bars | `WeeklyVolumeChart` default export |
| `frontend/src/components/RecoveryTrendChart.tsx` | HRV + sleep trend | `RecoveryTrendChart` default export |
| `frontend/src/components/StrengthProgressionChart.tsx` | e1RM-per-lift graph | `StrengthProgressionChart` default export |
| `frontend/src/components/BodyWeightTrendChart.tsx` | BW + 7d rolling avg | `BodyWeightTrendChart` default export |

---

*Generated 2026-04-23. Aligned with frontend revision `8312471`.*
