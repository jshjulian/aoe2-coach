# Matchup-first Coach dashboard v1

The eight-card field guide is now browsed inside **Matchup & unit reference book**, below the [replay-first coaching home](replay-coach-home.md), beside the existing replay-library sidebar. This is an original CSS-only bento layout, not downloaded art or a native replay/minimap load. The match overview stays above it. A visible **Jump to replay review** button gives direct access to the existing evidence briefing; its compact practice/timeline layout is checked after that explicit navigation rather than against the old home viewport. The existing ranked replay briefing, military commitment review, practice guide, journal, charts and deeper references remain below.

## Cards

1. Civilization-pair introduction: what to expect **if** the named strategy is chosen.
2. Opponent's three most frequent recognized military queue-input types, with first exact-source seeks. Retrospective, not player vision or a fielded army.
3. Conditional Feudal/Castle/Imperial response options. Tabs browse educational text, not measured age/readiness.
4. Position/resource-access problem, separate from the army problem.
5. Supporting units and capabilities that change the answer.
6. A plausible mechanism to inspect, never a causal explanation of the result.
7. Own requested units on the same input-count basis, not a cost/efficiency comparison.
8. One unsaved decision cue and explicit navigation to the existing replay/commitment reviews. Navigation opens/focuses details; it never selects a habit, saves an answer or collects anything.

## Authored guides and source boundaries

`viewer/src/lib/matchupGuideData.ts` contains original editorial reference prose for **Franks vs Sicilians, Britons, Bohemians and Berbers**, plus a clearly labeled general land-game fallback for other pairs. It does not assign Frank unit options to another civilization. The general fallback asserts no civilization-specific capability facts. This is not exhaustive matchup coverage or independent expert validation.

Sicilian reference facts were checked offline against the existing `knowledge/situational-catalog.lock.json` source: SiegeEngineers/aoe2techtree revision `3bb43b1439eef88dfe7fe892d7f7dc41ac9dd76f`, declared DE update **185872**. No lock or original knowledge pack is changed. Sources include:

- `trees/SICILIANS.json`: `Unit_1658_82`, `Unit_1659_82`, `Unit_1660_1665`, `Unit_1661_1665`, `Building_1665_1665`, `Tech_756_82`, `Tech_757_82`.
- `strings.en.json`: entries `26538`, `26540`, `26544`, `120186` support Serjeant/Donjon capabilities, bonus-damage resistance, First Crusade and Hauberk.
- `trees/FRANKS.json`: Knight, Scorpion, Monk, Hand Cannoneer and Chemistry nodes support reference availability/age. In particular Hand Cannoneer is research-required; its guide explicitly requires Chemistry. This is not completed or affordable production.
- The other three authored pairs use the already reviewed older pack's capability descriptions and existing locked trees. The older gated engine and rules declarations are untouched.

Reference facts and authored strategic options are distinct. No effective-stat calculation, combat simulation, automatic counter verdict or best-choice score is added. The guide is educational **reference only**, not a source-qualified recommendation applied to this replay. Reference update and current build mismatch/unknown status are visible on the main card, not buried in details. Even a matching build does not verify mods or strategic relevance. Empty mod metadata is not evidence that standard rules are verified. This educational surface does not enable the legacy matchup engine or bypass its explicit declaration gates.

The original prose is compiled into the viewer; it does not require a local research snapshot to read. Local optional reference bytes are checked by `test_matchup_guide_reference.py` when available, with no download. In a fresh source checkout, metadata checks run and optional-byte checks explicitly skip. No source JSON, game artwork or .dat is newly bundled. Existing licensing/release caveats remain unresolved.

## Source summary and eligibility

`matchupGuide.ts` is a pure bounded reader of existing Python analysis. It requires schema 5, 64-hex content identity, a finite recorded clock up to one day, exactly two unambiguous opposing participants, a coherent completed result, DE provenance 2/dataset 100/RM, explicit cheats/all-tech off, no known custom mod/RMS, and at most 300,000 unique valid source events. Unknown identities/actors/clocks, partial teams, unsupported modes or active/unknown-result matches withhold the dashboard, not the existing Coach.

Queue summaries require command status, queue kind, `DE_QUEUE`/`QUEUE`, an exact curated numeric Unit ID/display label pair and a positive integer quantity or explicitly missing quantity. Invalid/zero/negative quantities are not positive investments. Counts are **queue inputs**, never unit totals. Missing quantities are disclosed, multi-building selection is not multiplied, cancellations are not netted. Serjeant Castle/Donjon node variants are explicit reviewed pairs, not guessed IDs or actual producer attribution. Unrecognized military inputs are disclosed; no zero army is invented. Only three groups per actor are rendered. Frequency chooses a readable summary, not importance or the replay main.

Player result flags are a completion gate only. Neither result/rating nor habits, answers, observations or journals rank/select the guide or its cue. No event, existing recommendation ID/ranking, schema/API/store contract, annotation, legacy export or progress cohort is rewritten. Markdown export deliberately remains the old explicit serializer and excludes the guide and cue.

## Validation

```bash
node tools/test_matchup_guide.mjs
.venv/bin/python -m unittest -v test_matchup_guide_reference
```

The optional browser suite requires a running built viewer, Playwright already installed, and a supported local completed Franks–Sicilians replay. No private case is embedded. It uses an ephemeral read-only API/empty stores; `DASHBOARD_TEST_GAME_ID` optionally selects a local case.

```bash
PLAYWRIGHT_MODULE=/path/to/playwright .venv/bin/python tools/run_matchup_dashboard_browser_smoke.py
```

Checks include age-tab keyboard operation, no writes from browsing/navigation, exact queue seeks through the existing shared replay clock, no native replay parse until an explicit source seek, general/invalid-source fallbacks, Markdown exclusion, and dark/light/mobile layouts. Private UI screenshots are ignored under `data/smoke/` with mode 0600. Delivery checks passed: **342 Python tests**, **96 Node tests** (30 new guide checks), TypeScript no-emit, a stopped-viewer production build, and **18 distinct sequential browser suites**. Two older private layout suites now use the dashboard’s explicit review jump before asserting the unchanged compact practice/timeline viewport budget; smooth scrolling is awaited. A fresh production-store dump is compared without restoring older data, and the 509-entry capture plus seven-entry M4 manifests are hash-checked. Fresh source-checkout tests do not require private fixtures or caches.

Tests and screenshots validate software/workflow, not strategic efficacy, causal outcomes or player learning.
