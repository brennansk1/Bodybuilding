# Exercise Priority Lists by Division

---

## Validation Prompt

> **This section is a prompt for AI-assisted review. When validating this document, follow the instructions below exactly.**

You are reviewing the exercise priority cascade lists for a competitive bodybuilding coaching algorithm. Your job is to validate that each division's exercise ordering and set caps are **correct, complete, and aligned with how that division is actually judged and trained** in competitive bodybuilding.

For each division and muscle group, evaluate the following:

---

### 1. Judging Alignment
Search your knowledge of how each division is judged on stage. Ask:
- Does the exercise selection reflect what that division's judges reward? (e.g. Men's Physique is judged primarily on V-taper, upper chest shelf, and waist tightness — not squat strength or trap size)
- Are exercises that build mass in penalised areas appropriately capped or omitted? (e.g. heavy flat bench for Men's Physique builds lower chest and makes the waist appear wider — it should be low priority)
- Are exercises that build judged features given top priority? (e.g. Women's Bikini is judged primarily on glute shape and roundness — hip thrust must be Priority 1 for glutes)

**Flag** any case where Priority 1 builds a feature that is neutral or penalised for that division, or where a highly rewarded feature is buried at a low priority.

---

### 2. Biomechanical Effectiveness
For each muscle group, verify that the priority order reflects the actual stimulus-to-fatigue hierarchy for that muscle. Ask:
- Is the most mechanically effective compound movement for this muscle at or near Priority 1? (e.g. Romanian Deadlift for hamstrings, Hip Thrust for glutes, Barbell Row for back thickness)
- Are isolation exercises appropriately placed after compounds, not before?
- Are there exercises in the list that have poor stimulus-to-fatigue ratio for the target muscle that should be ranked lower or removed? (e.g. Upright Row is a poor primary shoulder exercise for most divisions due to impingement risk and trap involvement)
- Are exercises missing that are commonly considered best-in-class for that muscle in that division's training style?

**Flag** any ordering that contradicts established hypertrophy evidence (Israetel, Schoenfeld, etc.) or that a knowledgeable coach would dispute.

---

### 3. Max Set Caps
For each exercise, evaluate whether the set cap is appropriate. Ask:
- Is 4 sets a reasonable upper limit for compounds (barbell bench, squat, row)? Should any be higher or lower?
- Are isolation exercises (cable flys, lateral raises, leg extensions) appropriately capped at 3–4 sets before variety is introduced?
- Are any low-priority exercises (those placed late in the cascade as "junk volume insurance") correctly capped at 2–3 sets?
- For divisions where a muscle should receive minimal volume (e.g. traps for Men's Physique, chest for Women's Bikini), are the caps low enough that even a 12-set allocation would not over-develop that muscle?

**Flag** any cap that seems too high (could lead to junk volume in a single exercise) or too low (cuts off a key exercise before meaningful volume is delivered).

---

### 4. Division-Specific Omissions
For each division, check whether exercises are correctly absent from the priority list:
- **Men's Physique:** No heavy barbell back squat (quad/glute overdevelopment), barbell overhead press should be low-cap (trap growth compresses V-taper)
- **Women's Bikini:** No heavy barbell squat, no barbell overhead press, flat bench should be low-cap or absent
- **Women's Figure / Women's Physique:** Barbell movements are lower priority than dumbbell/cable (shoulder joint safety, aesthetic roundness preference)
- **Classic Physique:** All muscle groups should be represented — omitting any major group is an error since the division rewards complete development

**Flag** any exercise that appears in a division's priority list but clearly contradicts that division's training philosophy, and any obvious omission of a movement that should be present.

---

### 5. Cross-Division Consistency
Compare the same muscle group across all six divisions. Ask:
- Are differences in priority ordering logically explained by judging criteria, not arbitrary?
- Is the same exercise appearing as Priority 1 in divisions where it shouldn't be priority?
- Are the women's divisions internally consistent with each other on a spectrum (Bikini → Figure → Physique should show progressively more volume, heavier loading, and compound emphasis)?

**Flag** any inconsistency that cannot be explained by a judging rationale.

---

### 6. Output Format for Flagged Issues
For each issue found, respond in this format:

```
DIVISION: [division name]
MUSCLE: [muscle group]
ISSUE TYPE: [Judging Alignment | Biomechanical | Set Cap | Omission | Consistency]
CURRENT: [what the list currently says]
SUGGESTED: [what it should say and why]
CONFIDENCE: [High | Medium | Low]
```

After listing all flagged issues, provide a brief **Overall Assessment** for each division (1–2 sentences) summarising whether the list is ready to implement or needs revision.

---

Each muscle group lists exercises in cascade order. The engine fills Priority 1 up to its set cap,
then overflows to Priority 2, and so on. **Max Sets** is the cap before cascading.

**Gap Adjustment** (applied automatically — not user-configurable):
- HQI < 40 on a muscle → Priority 1 cap ×1.5 (severe lag: concentrate stimulus on best movement)
- HQI 40–65 → Priority 1 cap ×1.25 (moderate lag)
- HQI ≥ 65 → no adjustment

---

## Men's Open
> **Philosophy:** All muscle groups developed equally. Heavy compound movements anchor every session before any isolation work. Mass is the primary judging criterion.

### Chest
| Priority | Exercise | Max Sets |
|----------|----------|----------|
| 1 | Barbell Bench Press | 4 |
| 2 | Incline Barbell Press | 4 |
| 3 | Incline Dumbbell Press | 4 |
| 4 | Dumbbell Bench Press | 3 |
| 5 | Cable Fly / Cable Crossover | 4 |
| 6 | Pec Deck | 3 |
| 7 | Dips (Chest) | 3 |

### Back
| Priority | Exercise | Max Sets |
|----------|----------|----------|
| 1 | Barbell Row | 4 |
| 2 | Conventional Deadlift | 3 |
| 3 | T-Bar Row | 4 |
| 4 | Dumbbell Row | 4 |
| 5 | Seated Cable Row | 4 |
| 6 | Lat Pulldown | 4 |
| 7 | Weighted Pull-Up | 3 |
| 8 | Straight Arm Pulldown | 3 |

### Shoulders
| Priority | Exercise | Max Sets |
|----------|----------|----------|
| 1 | Overhead Press (Barbell) | 4 |
| 2 | Dumbbell Shoulder Press | 4 |
| 3 | Lateral Raise | 4 |
| 4 | Cable Lateral Raise | 4 |
| 5 | Upright Row | 3 |
| 6 | Rear Delt Fly / Face Pull | 4 |

### Quads
| Priority | Exercise | Max Sets |
|----------|----------|----------|
| 1 | Barbell Back Squat | 4 |
| 2 | Front Squat | 3 |
| 3 | Leg Press | 4 |
| 4 | Hack Squat | 3 |
| 5 | Walking Lunge / Bulgarian Split Squat | 3 |
| 6 | Leg Extension | 3 |

### Hamstrings
| Priority | Exercise | Max Sets |
|----------|----------|----------|
| 1 | Romanian Deadlift | 4 |
| 2 | Stiff-Leg Deadlift | 3 |
| 3 | Lying Leg Curl | 4 |
| 4 | Seated Leg Curl | 3 |
| 5 | Good Morning | 3 |

### Glutes
| Priority | Exercise | Max Sets |
|----------|----------|----------|
| 1 | Hip Thrust | 4 |
| 2 | Glute Bridge | 3 |
| 3 | Cable Pull-Through | 3 |
| 4 | Romanian Deadlift | 3 |
| 5 | Bulgarian Split Squat | 3 |

### Biceps
| Priority | Exercise | Max Sets |
|----------|----------|----------|
| 1 | Barbell Curl | 4 |
| 2 | Incline Dumbbell Curl / Dumbbell Curl | 4 |
| 3 | Hammer Curl | 3 |
| 4 | Preacher Curl | 3 |
| 5 | Cable Curl | 3 |

### Triceps
| Priority | Exercise | Max Sets |
|----------|----------|----------|
| 1 | Close-Grip Bench Press | 4 |
| 2 | Skull Crusher | 4 |
| 3 | Dips (Triceps) | 3 |
| 4 | Tricep Pushdown | 4 |
| 5 | Overhead Tricep Extension | 3 |

### Calves
| Priority | Exercise | Max Sets |
|----------|----------|----------|
| 1 | Standing Calf Raise | 4 |
| 2 | Seated Calf Raise | 4 |

### Traps
| Priority | Exercise | Max Sets |
|----------|----------|----------|
| 1 | Barbell Shrug | 3 |
| 2 | Dumbbell Shrug | 3 |
| 3 | Farmer's Walk | 2 |

### Abs
| Priority | Exercise | Max Sets |
|----------|----------|----------|
| 1 | Cable Crunch | 4 |
| 2 | Hanging Leg Raise | 4 |
| 3 | Ab Wheel Rollout | 3 |
| 4 | Plank | 3 |

### Forearms
| Priority | Exercise | Max Sets |
|----------|----------|----------|
| 1 | Wrist Curl | 3 |
| 2 | Reverse Wrist Curl | 3 |
| 3 | Farmer's Walk | 2 |

---

## Men's Physique
> **Philosophy:** V-taper upper body. Incline chest (upper chest shelf over lower chest mass). Wide-grip pulling for lat sweep. Side delts are the #1 priority shoulder movement. No heavy free-bar squats (excess quad/glute mass hurts aesthetics). Barbell overhead press deprioritised (large traps compress the V-taper). Tricep long-head prioritised for fullness in the side pose. DB/cable curls preferred over barbell for arm aesthetics.

### Chest
| Priority | Exercise | Max Sets | Notes |
|----------|----------|----------|-------|
| 1 | Incline Barbell Press | 4 | Upper chest shelf |
| 2 | Incline Dumbbell Press | 4 | Upper chest shelf |
| 3 | Cable Fly / Cable Crossover | 4 | Stretch + peak contraction |
| 4 | Pec Deck | 3 | Detail/separation |
| 5 | Barbell / Dumbbell Bench Press (flat) | 2 | Low cap — lower chest dominance hurts aesthetics |

### Back
| Priority | Exercise | Max Sets | Notes |
|----------|----------|----------|-------|
| 1 | Lat Pulldown | 4 | Width first |
| 2 | Weighted Pull-Up | 4 | Wide-grip sweep |
| 3 | Seated Cable Row | 4 | Thickness |
| 4 | Dumbbell Row | 3 | Thickness |
| 5 | T-Bar Row | 3 | Thickness |
| 6 | Straight Arm Pulldown | 3 | Lat isolation |
| 7 | Barbell Row | 3 | Low priority — less specificity for lat sweep |

### Shoulders
| Priority | Exercise | Max Sets | Notes |
|----------|----------|----------|-------|
| 1 | Lateral Raise | 4 | Width = most judged feature |
| 2 | Cable Lateral Raise | 4 | Constant tension |
| 3 | Dumbbell Shoulder Press | 4 | Volume without BB trap growth |
| 4 | Rear Delt Fly / Face Pull | 4 | Rear delt balance |
| 5 | Overhead Press (Barbell) | 2 | Low cap — trap hypertrophy compresses V-taper |

### Quads
| Priority | Exercise | Max Sets | Notes |
|----------|----------|----------|-------|
| 1 | Leg Press | 4 | Conditioning without axial load |
| 2 | Hack Squat | 3 | Quad sweep |
| 3 | Walking Lunge / Bulgarian Split Squat | 3 | |
| 4 | Leg Extension | 3 | Detail |
> No heavy barbell back squat in priority list — excess quad/glute mass detracts from upper body focus

### Hamstrings
| Priority | Exercise | Max Sets |
|----------|----------|----------|
| 1 | Romanian Deadlift | 3 |
| 2 | Lying Leg Curl | 4 |
| 3 | Seated Leg Curl | 3 |

### Glutes
| Priority | Exercise | Max Sets |
|----------|----------|----------|
| 1 | Hip Thrust | 3 |
| 2 | Cable Pull-Through | 3 |
| 3 | Glute Bridge | 3 |

### Biceps
| Priority | Exercise | Max Sets | Notes |
|----------|----------|----------|-------|
| 1 | Dumbbell Curl | 4 | Fuller peak, more aesthetic |
| 2 | Hammer Curl | 3 | Brachialis for arm thickness |
| 3 | Cable Curl | 4 | Constant tension |
| 4 | Preacher Curl | 3 | Peak development |
| 5 | Barbell Curl | 2 | Low cap — less aesthetic for peak contraction |

### Triceps
| Priority | Exercise | Max Sets | Notes |
|----------|----------|----------|-------|
| 1 | Overhead Tricep Extension | 4 | Long-head = fullness in side pose |
| 2 | Tricep Pushdown | 4 | Lateral + medial head |
| 3 | Skull Crusher | 3 | |
| 4 | Close-Grip Bench Press | 2 | Low cap — chest involvement |

### Calves
| Priority | Exercise | Max Sets |
|----------|----------|----------|
| 1 | Standing Calf Raise | 4 |
| 2 | Seated Calf Raise | 4 |

### Traps
| Priority | Exercise | Max Sets | Notes |
|----------|----------|----------|-------|
| 1 | Dumbbell Shrug | 2 | Minimal volume — large traps hurt V-taper |
| 2 | Farmer's Walk | 2 | |

### Abs
| Priority | Exercise | Max Sets |
|----------|----------|----------|
| 1 | Cable Crunch | 4 |
| 2 | Hanging Leg Raise | 4 |
| 3 | Ab Wheel Rollout | 3 |

### Forearms
| Priority | Exercise | Max Sets |
|----------|----------|----------|
| 1 | Wrist Curl | 2 |
| 2 | Reverse Wrist Curl | 2 |

---

## Classic Physique
> **Philosophy:** Mass + proportion + detail. Compound anchors similar to Men's Open but with more isolation variety to develop muscular separation. Weight cap means bulk must be controlled — exercise selection avoids runaway mass in any single group.

### Chest
| Priority | Exercise | Max Sets |
|----------|----------|----------|
| 1 | Barbell Bench Press | 4 |
| 2 | Incline Barbell Press | 4 |
| 3 | Incline Dumbbell Press | 4 |
| 4 | Cable Fly / Cable Crossover | 3 |
| 5 | Pec Deck | 3 |

### Back
| Priority | Exercise | Max Sets |
|----------|----------|----------|
| 1 | Barbell Row | 4 |
| 2 | T-Bar Row | 4 |
| 3 | Seated Cable Row | 4 |
| 4 | Lat Pulldown | 4 |
| 5 | Dumbbell Row | 3 |
| 6 | Weighted Pull-Up | 3 |
| 7 | Straight Arm Pulldown | 3 |

### Shoulders
| Priority | Exercise | Max Sets |
|----------|----------|----------|
| 1 | Overhead Press (Barbell) | 4 |
| 2 | Dumbbell Shoulder Press | 3 |
| 3 | Lateral Raise | 4 |
| 4 | Cable Lateral Raise | 3 |
| 5 | Rear Delt Fly / Face Pull | 4 |

### Quads
| Priority | Exercise | Max Sets |
|----------|----------|----------|
| 1 | Barbell Back Squat | 4 |
| 2 | Front Squat | 3 |
| 3 | Leg Press | 4 |
| 4 | Hack Squat | 3 |
| 5 | Leg Extension | 3 |

### Hamstrings
| Priority | Exercise | Max Sets |
|----------|----------|----------|
| 1 | Romanian Deadlift | 4 |
| 2 | Lying Leg Curl | 4 |
| 3 | Seated Leg Curl | 3 |
| 4 | Stiff-Leg Deadlift | 3 |

### Glutes
| Priority | Exercise | Max Sets |
|----------|----------|----------|
| 1 | Hip Thrust | 4 |
| 2 | Bulgarian Split Squat / Walking Lunge | 3 |
| 3 | Cable Pull-Through | 3 |

### Biceps
| Priority | Exercise | Max Sets |
|----------|----------|----------|
| 1 | Barbell Curl | 4 |
| 2 | Dumbbell Curl | 3 |
| 3 | Preacher Curl | 3 |
| 4 | Hammer Curl | 3 |
| 5 | Cable Curl | 3 |

### Triceps
| Priority | Exercise | Max Sets |
|----------|----------|----------|
| 1 | Close-Grip Bench Press | 4 |
| 2 | Skull Crusher | 4 |
| 3 | Tricep Pushdown | 3 |
| 4 | Overhead Tricep Extension | 3 |

### Calves
| Priority | Exercise | Max Sets |
|----------|----------|----------|
| 1 | Standing Calf Raise | 4 |
| 2 | Seated Calf Raise | 4 |

### Traps
| Priority | Exercise | Max Sets |
|----------|----------|----------|
| 1 | Barbell Shrug | 3 |
| 2 | Dumbbell Shrug | 2 |

### Abs
| Priority | Exercise | Max Sets |
|----------|----------|----------|
| 1 | Cable Crunch | 4 |
| 2 | Hanging Leg Raise | 3 |
| 3 | Ab Wheel Rollout | 3 |

### Forearms
| Priority | Exercise | Max Sets |
|----------|----------|----------|
| 1 | Wrist Curl | 3 |
| 2 | Reverse Wrist Curl | 2 |

---

## Women's Bikini
> **Philosophy:** Glute-dominant. Hip hinge and kickback patterns are the #1 priority for every lower body session. Avoid upper-body and quad mass — no heavy pressing, no heavy barbell squats. Shoulders get lateral raises only (width without mass). Chest volume is minimal (cable flys for tone). Peak week protocol is subtle relative to other divisions.

### Glutes *(primary focus)*
| Priority | Exercise | Max Sets | Notes |
|----------|----------|----------|-------|
| 1 | Hip Thrust | 4 | Best glute activator |
| 2 | Glute Bridge | 4 | |
| 3 | Cable Pull-Through | 4 | Constant tension hip hinge |
| 4 | Romanian Deadlift | 3 | Hip hinge pattern |
| 5 | Bulgarian Split Squat | 3 | Unilateral glute load |

### Hamstrings
| Priority | Exercise | Max Sets |
|----------|----------|----------|
| 1 | Romanian Deadlift | 4 |
| 2 | Lying Leg Curl | 4 |
| 3 | Seated Leg Curl | 3 |
| 4 | Good Morning | 2 |

### Quads
| Priority | Exercise | Max Sets | Notes |
|----------|----------|----------|-------|
| 1 | Leg Press | 4 | High-foot placement targets glutes |
| 2 | Walking Lunge | 3 | |
| 3 | Bulgarian Split Squat | 3 | |
| 4 | Leg Extension | 3 | |
> No heavy barbell squat or hack squat — excessive quad/glute bulk is penalised

### Back
| Priority | Exercise | Max Sets | Notes |
|----------|----------|----------|-------|
| 1 | Seated Cable Row | 4 | Moderate volume for width |
| 2 | Lat Pulldown | 4 | |
| 3 | Dumbbell Row | 3 | |
| 4 | Straight Arm Pulldown | 3 | Lat isolation |

### Shoulders
| Priority | Exercise | Max Sets | Notes |
|----------|----------|----------|-------|
| 1 | Lateral Raise | 4 | Width without mass |
| 2 | Cable Lateral Raise | 4 | |
| 3 | Rear Delt Fly / Face Pull | 3 | Balance |
| 4 | Dumbbell Shoulder Press | 2 | Low cap — avoid shoulder mass |
> No barbell overhead press

### Chest
| Priority | Exercise | Max Sets | Notes |
|----------|----------|----------|-------|
| 1 | Cable Fly / Cable Crossover | 3 | Tone, no mass |
| 2 | Pec Deck | 3 | |
| 3 | Dumbbell Bench / Incline Dumbbell | 2 | Low cap |
> Minimal chest volume — tone without mass accumulation

### Biceps
| Priority | Exercise | Max Sets |
|----------|----------|----------|
| 1 | Dumbbell Curl | 3 |
| 2 | Hammer Curl | 3 |
| 3 | Cable Curl | 3 |

### Triceps
| Priority | Exercise | Max Sets |
|----------|----------|----------|
| 1 | Overhead Tricep Extension | 3 |
| 2 | Tricep Pushdown | 3 |

### Calves
| Priority | Exercise | Max Sets |
|----------|----------|----------|
| 1 | Standing Calf Raise | 4 |
| 2 | Seated Calf Raise | 3 |

### Abs
| Priority | Exercise | Max Sets |
|----------|----------|----------|
| 1 | Cable Crunch | 3 |
| 2 | Hanging Leg Raise | 3 |
| 3 | Plank | 3 |

### Traps
| Priority | Exercise | Max Sets | Notes |
|----------|----------|----------|-------|
| 1 | Dumbbell Shrug | 2 | Minimal — large traps look masculine |

### Forearms
| Priority | Exercise | Max Sets |
|----------|----------|----------|
| 1 | Wrist Curl | 2 |

---

## Women's Figure
> **Philosophy:** More muscle development than Bikini but shoulders-to-waist ratio still matters. Back and glutes are co-dominant. Moderate pressing for upper body roundness. More total volume than Bikini across all groups.

### Back *(co-priority with Glutes)*
| Priority | Exercise | Max Sets |
|----------|----------|----------|
| 1 | Seated Cable Row | 4 |
| 2 | Lat Pulldown | 4 |
| 3 | Dumbbell Row | 4 |
| 4 | T-Bar Row | 3 |
| 5 | Weighted Pull-Up | 3 |
| 6 | Straight Arm Pulldown | 3 |

### Glutes *(co-priority with Back)*
| Priority | Exercise | Max Sets |
|----------|----------|----------|
| 1 | Hip Thrust | 4 |
| 2 | Romanian Deadlift | 4 |
| 3 | Glute Bridge | 3 |
| 4 | Cable Pull-Through | 3 |
| 5 | Bulgarian Split Squat | 3 |

### Shoulders
| Priority | Exercise | Max Sets | Notes |
|----------|----------|----------|-------|
| 1 | Lateral Raise | 4 | Width |
| 2 | Cable Lateral Raise | 3 | |
| 3 | Dumbbell Shoulder Press | 4 | Roundness |
| 4 | Rear Delt Fly / Face Pull | 4 | Balance |
| 5 | Overhead Press (Barbell) | 2 | Low cap |

### Quads
| Priority | Exercise | Max Sets |
|----------|----------|----------|
| 1 | Leg Press | 4 |
| 2 | Bulgarian Split Squat / Walking Lunge | 3 |
| 3 | Hack Squat | 3 |
| 4 | Leg Extension | 3 |

### Hamstrings
| Priority | Exercise | Max Sets |
|----------|----------|----------|
| 1 | Romanian Deadlift | 4 |
| 2 | Lying Leg Curl | 4 |
| 3 | Seated Leg Curl | 3 |

### Chest
| Priority | Exercise | Max Sets | Notes |
|----------|----------|----------|-------|
| 1 | Incline Dumbbell Press | 3 | Upper chest shape |
| 2 | Cable Fly / Cable Crossover | 4 | |
| 3 | Pec Deck | 3 | |

### Biceps
| Priority | Exercise | Max Sets |
|----------|----------|----------|
| 1 | Dumbbell Curl | 3 |
| 2 | Hammer Curl | 3 |
| 3 | Cable Curl | 3 |
| 4 | Preacher Curl | 2 |

### Triceps
| Priority | Exercise | Max Sets |
|----------|----------|----------|
| 1 | Overhead Tricep Extension | 3 |
| 2 | Tricep Pushdown | 4 |
| 3 | Skull Crusher | 2 |

### Calves
| Priority | Exercise | Max Sets |
|----------|----------|----------|
| 1 | Standing Calf Raise | 4 |
| 2 | Seated Calf Raise | 3 |

### Abs
| Priority | Exercise | Max Sets |
|----------|----------|----------|
| 1 | Cable Crunch | 4 |
| 2 | Hanging Leg Raise | 3 |
| 3 | Ab Wheel Rollout | 2 |

### Traps
| Priority | Exercise | Max Sets |
|----------|----------|----------|
| 1 | Dumbbell Shrug | 2 |

### Forearms
| Priority | Exercise | Max Sets |
|----------|----------|----------|
| 1 | Wrist Curl | 2 |

---

## Women's Physique
> **Philosophy:** Full-body development closest to Men's Open proportionally. Dumbbell and cable exercises preferred over barbell for shoulder roundness and joint safety. Glutes remain important but back, quads, and shoulders all receive serious volume. Leg development is expected.

### Chest
| Priority | Exercise | Max Sets | Notes |
|----------|----------|----------|-------|
| 1 | Incline Dumbbell Press | 4 | Upper chest + shoulder roundness |
| 2 | Dumbbell Bench Press | 4 | |
| 3 | Cable Fly / Cable Crossover | 4 | |
| 4 | Pec Deck | 3 | |
| 5 | Incline Barbell Press | 3 | Lower priority than DB |

### Back
| Priority | Exercise | Max Sets |
|----------|----------|----------|
| 1 | Seated Cable Row | 4 |
| 2 | Lat Pulldown | 4 |
| 3 | Dumbbell Row | 4 |
| 4 | Weighted Pull-Up | 3 |
| 5 | Barbell Row | 3 |
| 6 | Straight Arm Pulldown | 3 |

### Shoulders
| Priority | Exercise | Max Sets |
|----------|----------|----------|
| 1 | Dumbbell Shoulder Press | 4 |
| 2 | Lateral Raise | 4 |
| 3 | Cable Lateral Raise | 4 |
| 4 | Rear Delt Fly / Face Pull | 4 |

### Quads
| Priority | Exercise | Max Sets |
|----------|----------|----------|
| 1 | Leg Press | 4 |
| 2 | Bulgarian Split Squat / Walking Lunge | 4 |
| 3 | Hack Squat | 3 |
| 4 | Barbell Back Squat | 3 |
| 5 | Leg Extension | 3 |

### Hamstrings
| Priority | Exercise | Max Sets |
|----------|----------|----------|
| 1 | Romanian Deadlift | 4 |
| 2 | Lying Leg Curl | 4 |
| 3 | Seated Leg Curl | 3 |
| 4 | Stiff-Leg Deadlift | 3 |

### Glutes
| Priority | Exercise | Max Sets |
|----------|----------|----------|
| 1 | Hip Thrust | 4 |
| 2 | Romanian Deadlift | 3 |
| 3 | Cable Pull-Through | 3 |
| 4 | Glute Bridge | 3 |

### Biceps
| Priority | Exercise | Max Sets |
|----------|----------|----------|
| 1 | Dumbbell Curl | 4 |
| 2 | Hammer Curl | 3 |
| 3 | Preacher Curl | 3 |
| 4 | Cable Curl | 3 |

### Triceps
| Priority | Exercise | Max Sets |
|----------|----------|----------|
| 1 | Overhead Tricep Extension | 4 |
| 2 | Tricep Pushdown | 4 |
| 3 | Skull Crusher | 3 |

### Calves
| Priority | Exercise | Max Sets |
|----------|----------|----------|
| 1 | Standing Calf Raise | 4 |
| 2 | Seated Calf Raise | 4 |

### Abs
| Priority | Exercise | Max Sets |
|----------|----------|----------|
| 1 | Cable Crunch | 4 |
| 2 | Hanging Leg Raise | 3 |
| 3 | Ab Wheel Rollout | 3 |

### Traps
| Priority | Exercise | Max Sets |
|----------|----------|----------|
| 1 | Dumbbell Shrug | 2 |

### Forearms
| Priority | Exercise | Max Sets |
|----------|----------|----------|
| 1 | Wrist Curl | 2 |
| 2 | Reverse Wrist Curl | 2 |

---

## Quick Comparison — Key Differences by Division

| Muscle | Men's Open | Men's Physique | Classic | Women's Bikini | Women's Figure | Women's Physique |
|--------|-----------|----------------|---------|----------------|----------------|-----------------|
| **Chest P1** | Flat BB Bench | Incline BB | Flat BB Bench | Cable Fly | Incline DB | Incline DB |
| **Back P1** | Barbell Row | Lat Pulldown | Barbell Row | Cable Row | Cable Row | Cable Row |
| **Shoulders P1** | BB Overhead Press | Lateral Raise | BB Overhead Press | Lateral Raise | Lateral Raise | DB Shoulder Press |
| **Quads P1** | Back Squat | Leg Press | Back Squat | Leg Press | Leg Press | Leg Press |
| **Glutes P1** | Hip Thrust | Hip Thrust | Hip Thrust | Hip Thrust | Hip Thrust | Hip Thrust |
| **Biceps P1** | Barbell Curl | Dumbbell Curl | Barbell Curl | Dumbbell Curl | Dumbbell Curl | Dumbbell Curl |
| **Triceps P1** | Close-Grip Bench | Overhead Ext. | Close-Grip Bench | Overhead Ext. | Overhead Ext. | Overhead Ext. |
| **Traps max cap** | 3+3+2 | **2+2** | 3+2 | **2** | **2** | **2** |
| **Flat bench cap** | 4 | **2** | 4 | **2** | — | — |
| **Heavy squat** | Yes (P1) | **No** | Yes (P1) | **No** | No | P4 only |

---

## Notes for Review

- **Keyword matching** is substring-based (case-insensitive). "romanian deadlift" matches any exercise whose name contains that string.
- If two priority slots have overlapping keywords (e.g. "romanian deadlift" appearing in both hamstrings and glutes priority lists), each muscle's cascade runs independently — the exercise can appear in both muscle groups' sessions if the split programs them on the same day.
- The fallback (for exercises not matched by any priority slot) uses the existing SFR (Stimulus-to-Fatigue Ratio) sort, so no volume is ever lost.
- To adjust any priority ordering or cap, edit `backend/app/constants/exercise_priorities.py`.
