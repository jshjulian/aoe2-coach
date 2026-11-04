# Replay-first Coach home

The default Coach view now leads with **Watch the moment. Make a plan.**, not a missing civilization-pair guide. The rounded-card visual language and match/library overview remain.

## What is visible first

1. **Moments worth your attention:** up to three timestamped decisions. Each has recorded context, an actionable review tip, an exact shared-clock seek and a compact source sequence.
2. **Army & supporting mix:** a named supported composition, the job of each part, preparation and a specific tactical watch-out. Its opposing-request window (at most five recorded minutes) is shown; it is not a whole-match union of every enemy unit.
3. **How to use the army:** a mobility/screening or one-job-at-a-time playstyle tip, not an inferred skill trend.
4. **Timing & resources:** preparation around actual age/production/research requests, with source links and a question about affordability and safe access at that time. No bank/income/safety values are invented.

**Evidence & reference notes** is one compact expandable note. A known reference patch mismatch remains visible in its summary, rather than recurring as the heading of every card. **Matchup & unit reference book** below the home preserves all eight old matchup cards, age browsing and the mechanics/composition book. The home has an explicit **Jump to replay review** button which focuses the unchanged ranked briefing; practice, charts, corrections and journal remain accessible.

## Deterministic presentation model

`viewer/src/lib/replayCoachHome.ts` uses `buildGuideBoard` for the existing bounded completed-opposing-1v1/schema-5/DE/RM/content/actor/clock/custom-mode gate, and the existing `usableComposition`, `usableReasoning` and `usableTakeaway` validators for optional packets. Bad optional composition data falls back to real command/age anchors, not a generic no-coverage hero. Invalid replay scope withholds this home; the older compatible review remains below.

No backend endpoint, schema, persisted identifier, ranking/cohort, export serializer, AI/provider or collection path is added. All new synthesis is read-only presentation. It never uses outcomes/ratings to rank, saved habits to choose a replay lesson, or conversation/journal notes to fill answers.

Selection:

- Lift the existing validated reasoning primary when usable and not withheld/correction-requiring; otherwise the validated command-review primary. Use recorded requests and original practice text, never the player's private note or an assessment as a measured fact.
- Fill with own Castle follow-through, one supported opposing production-role mix, and opening production, up to three. Duplicate anchors and phase cards within 90 recorded seconds of an already selected primary are suppressed. Phase and mix cards may describe different decisions in the same period. This is declared editorial coverage, not a strategic-importance/mistake/timeliness score.
- Own age-up anchors require exactly one matching **AGE_REACHED / observed_milestone** event. Research requests, duplicate age markers and opponent milestones cannot become own completions.
- Source lists are bounded to 12 per moment, preserve the anchor, and link to exact normalized events. Placements/research remain requests; generic orders are never relabeled as production.
- Castle follow-through cites a next supported own queue within 300 seconds and nearby production/research requests, without declaring an optimal delay or proving a completed transition. No request does not mean inaction.
- Home context is independent of the old four-window fixed-bin selection, which can miss Castle-age support or split Spears/Knights across bin edges. Prefer the first recognized Gbeto request with up to 60 seconds of preceding support in one <=300-second interval; otherwise use the five minutes from the unique own Castle milestone if it contains opposing inputs; otherwise use five minutes from the first supported opposing request. Keep one first request per exact unit ID, bounded to 12 cited types with the focus anchor retained. All named types/roles in the card come from those citations. Remote later units cannot enter an earlier context. Co-requested roles are a mix to inspect, not armies proved alive/together or seen by the player.

## Named plans and age context

Named plans require **all own-civ units to be available in the hash-checked pinned reference**, via the validated composition packet. Missing/unavailable reference data yields a one-main-line/support plan rather than inventing an available unit counter.

Resource preparation uses this plan's context (not an unrelated early Castle marker for a late Imperial recipe) and labels source actors. Original authored role-based plans include Scouts/Archers or Scouts/Spears for a supported Feudal interval before a known own Castle milestone; Knights/Crossbows, Knights/protected Monks or Knights/Elite Skirmishers as Castle-age plans; and protected Hand Cannoneers/cavalry screening for an observed Imperial-period infantry/Gbeto context. Gunpowder explicitly requires Chemistry. Skirmisher support needs an actual target reference Archer-class armour entry, not projectile appearance. A missing Castle marker is not proof of still being Feudal. Recipe age is a reference/planning stage, not completion or readiness.

Supporting Spears/Camels, keeping the two groups connected, protected damage, research and safe funding are part of the recommendation, rather than separate generic caveat cards. These are authored strategies needing independent strategic review, not combat simulations or claims that changing composition would win. Gbeto damage mechanics are surfaced only when its mechanics reference is available.

Actual player vision, banks/income/allocation, completed buildings/research, surviving forces and combat outcomes remain unresolved. Commands are not units; quantities/building selections are not multiplied; cancellations are not subtracted. Facts, tactics to practise and questions about missing context remain distinct in the UI. No habit/answer/journal write or learning-improvement claim occurs on browse, reference selection or replay seek.

## Verification

```bash
node tools/test_replay_coach_home.mjs
cd viewer && ./node_modules/.bin/tsc --noEmit
```

The portable model tests use explicit synthetic reports/source graphs, not private replay fixtures or real unit-stat testimony. Browser coverage uses an ephemeral read-only API/store harness and an existing local completed Franks replay, preferring Georgians (the previously unhelpful general-guide case):

```bash
PLAYWRIGHT_MODULE=/path/to/playwright .venv/bin/python tools/run_replay_coach_home_browser_smoke.py
```

`HOME_TEST_GAME_ID` is an optional explicit local override. The test covers above-reference layout, timed moments, supported plan, reference access, compact evidence note, keyboard/shared-clock seek, missing/corrupt optional data, export exclusion and no writes. Dark/light/mobile UI screenshots are ignored and mode 0600. Existing reference-browser suites now explicitly open the reference book. No runtime install/download, game launch, CaptureAge/capture or live assistance is authorized or added. Existing licensing/release caveats remain.
