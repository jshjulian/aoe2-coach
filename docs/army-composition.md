# Unit mechanics and composition review v1

Coach now includes **Read the army’s jobs—not just its unit names**, between the matchup dashboard and the existing ranked replay briefing. It combines a bounded recorded-role review, a source-backed unit book, conditional counter-compositions and three transition questions. This is post-match only; the existing dashboard jump still goes directly to the older evidence briefing.

## What is covered

`knowledge/unit-mechanics.v1.json` is original authored metadata for 34 exact Unit-ID/name pairs across ten roles: ranged-melee, ranged damage, anti-Archer support, mobile melee, mobile anti-cavalry/Camels, spear screens, infantry, slow siege support, mounted ranged damage and conversion/healing support. It covers basic/Elite Gbeto plus a deliberately limited set of Archer, cavalry, Camel, spear, infantry/Serjeant, gunpowder, Scorpion/Mangonel, Monk and Mounted Crossbowman variants. Unknown aliases and unlisted unique/naval units remain unsupported, never guessed into a family.

`unit_knowledge.py` separates:

- **Source facts:** base movement speed, range/minimum range, melee/pierce armour, attack, reload/attack delay, raw attack channels and armour-class entries; exact own-civ reference availability, age and production node.
- **Reviewed mechanics mapping:** primary damage class (3 = pierce, 4 = melee), melee/ranged delivery and special exceptions. Monks have conversion/healing delivery, no primary damage class and an explicitly empty source attack-channel array—not invented melee damage. Mounted Crossbowman IDs 2700/2701 are exact, distinct identities, not repaired Cavalry Archer aliases. Mangonels are ranged-delivery/melee-damage siege with area/minimum-range/protection caveats.
- **Authored strategy:** roles/jobs, conditional combinations, prerequisites and failure conditions. These are not independently expert-validated or a combat simulation.

Gbeto is the explicit regression case: Unit 1013/1015 has ranged delivery but primary melee damage. Its infantry armour classes do not turn it into Archer-class prey merely because it attacks at range. The unit book therefore does not recommend Skirmishers based on projectile appearance or pierce armour as protection from its primary attack. A base-speed comparison is shown without claiming a catch: upgrades, age/civ bonuses, pathing, attack timing, terrain and numbers remain unresolved.

The reference is the **existing** 60-file / 56-tree `knowledge/situational-catalog.lock.json`, revision `3bb43b1439eef88dfe7fe892d7f7dc41ac9dd76f`, DE update **185872**. No lock, original role pack, source bytes, asset or engine is replaced. Every local source hash/signature is verified using the existing offline loader. Exact names, primary positive attack channels, delivery/range consistency, armour entries and own availability are checked. The Gbeto description at `strings.en.json:26140` independently describes its ranged melee attack; the node is `trees/MALIANS.json:Unit_1013_82` (Elite: `Unit_1015_82`).

Missing numeric fields stay null; zero is preserved only when actually present. Monk base reload/attack entries are raw catalog values, not conversion duration or success probability. Broken/missing/conflicting source data withholds the entire numeric/availability reference rather than inventing fallback values. The recorded-input review can still run without optional reference bytes. Restoring the public snapshot is an explicit separate setup action, never a startup/runtime download.

Matching build remains reference-only, not verified standard rules or effective state. Mismatched/unknown builds are visibly labeled. Automatic age changes, civilization bonuses, research, health, surviving armies and effective stats are not calculated. The fixed curated slice does not generalize attack delivery from range to arbitrary extended-reach or special units.

## Recognizing production roles

`army_composition.py` adds optional `composition_context` to the full coaching response and `army_composition_version: 1` to health/launcher checks. Normalized schema 5, API 4, old rankings/IDs, stores, journal, clarifications, progress cohorts and explicit legacy Markdown serializer stay unchanged. The lightweight legacy review does not build this context.

Scope requires an exact 64-hex content identity; explicit completed opposing 1v1 participants; DE provenance 2, dataset 100, RM, cheats/all-tech off and no known custom rules; finite clock up to one day; at most 300,000 unique valid actor/time events. Result flags gate completion only; result/rating and saved personal context never select/grade this review. Unsupported input withholds this optional context only.

- Fixed half-open 180-second recorded-input windows; final match endpoint is included in the final bin, not a zero-length extra window.
- Exact recognized Unit-ID/name pairs, command status, queue kind, DE_QUEUE/QUEUE and positive integer or missing quantity. No producer-ID repair, selected-building multiplier, cancellation subtraction or invented quantity.
- At most four chronological windows: first/latest opposing-input windows, first ranged-melee-role example (Gbeto, not every ranged melee-damage unit) and latest supported role addition; fill chronologically. The displayed default prefers the first Gbeto-role window if present, otherwise the first selected window. This is declared editorial coverage, not strategic importance or changes to the replay main.
- Same-window co-requested roles are a **composition to inspect**, not units proved alive, together or simultaneous. Spear/Camel + ranged-melee requests explicitly ask whether an anti-cavalry screen was actually present.
- First per-role plus bounded first/latest requests retain coverage. At most 112 exact citations per window, including prior/follow-up anchors. Counts describe cited queue inputs only, not full-window units or all activity. UI source inspection paginates 24 at a time.
- A role addition means absence from the preceding supported input window (at most two bins apart), not first player sight or army appearance. Unclassified opposing military inputs withhold that comparison.

## Transition review, not a reaction-time score

An opposing request anchors a bounded review. The preceding 300 recorded seconds establish a supported own-role request basis; the next 300 seconds may cite a first own request outside that role basis. Unclassified own inputs break this transition coverage. Missing prior basis, no cited role change, sustained same-role production or a deliberately small group are not mistakes.

Elapsed source time is descriptive only: **not reaction time, completion, lateness, optimal timing, affordability or causal combat outcome**. The player may not have seen the retrospective opposing request. Upgrade-only changes and positioning are not qualified transitions here.

The three self-checks ask what the player actually saw, what useful job remained for the current response, and what safe income/production/upgrades/protection would sustain support or adaptation. These are unsaved questions. The conversation is not mined for answers or used to establish improving economy/Scout play.

## Conditional counter-compositions

The initial authored options cover mobile melee protection plus ranged damage, protected gunpowder plus a mobile screen, and protected ranged damage/frontline against an infantry-focused threat. Gbeto with Spears/Camels explicitly cautions against chasing through anti-cavalry protection. These are combinations with jobs, not single-unit strong/weak labels.

All required units must be available in the exact own-civ pinned tree to present a named option as available **in reference**. Otherwise it is withheld. Minimum age/production/upgrade/funding/protection requirements are shown, never interpreted as met. UI options follow the selected recorded window; the unit book can be browsed independently. Actual resources, safe income, completed research/buildings, force size and vision stay unknown.

The review lens is presentation only. No automatic habit selection/replacement, practice suggestion injection, progress snapshot, clarification, annotation or journal write occurs. Browsing/selecting windows/units/comparisons and following exact shared-clock sources are read-only. No AI/model/provider, game launch, CaptureAge/capture, live hook, memory read, dependency installation or deliberate external transfer is added. Reference licensing/game-content and inherited viewer release caveats are unchanged.

## Tests

```bash
.venv/bin/python -m unittest -v test_army_composition test_army_composition_api
node tools/test_army_composition.mjs
```

Synthetic source graphs are explicitly test data, not real units or player/expert testimony. The optional actual pinned Gbeto test skips without a restored public snapshot; nothing downloads. Browser checks need a built running viewer, Playwright already available, local completed Franks replay and restored reference snapshot:

```bash
PLAYWRIGHT_MODULE=/path/to/playwright .venv/bin/python tools/run_army_composition_browser_smoke.py
```

It prefers a local Malian opponent, embeds no private identity/replay, and accepts `ARMY_TEST_GAME_ID` as an explicit local override. Its API/stores are ephemeral and read-only; private dark/light/mobile UI screenshots go under ignored `data/smoke/` with mode 0600. It checks Gbeto mechanics, reference comparisons, conditional options, source seeks, no eager native parse, missing/corrupt fallbacks, export exclusion and no writes. Software checks do not establish strategic relevance, feasibility, timely decisions or learning improvement.
