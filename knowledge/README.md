# Versioned civilization knowledge — reviewed reference pack

## Situational composition-response v1

`../situational_knowledge.py` / `situational.v1.json` combine reusable conditional
roles/mechanics/exceptions with **separately** locked base catalog facts.
`situational-catalog.lock.json` covers all 56 civilization trees (60 total source
files) at the existing commit/update, without changing the older four-tree lock or
its source bytes. Canonical tree filenames and the reviewed Maya/Mayans source alias
are explicit; normalized identities and old cohorts are not rewritten. Costs cite
the data file; ages/production/availability cite the specific tree. There is no
effective-stat or fieldability calculation. Strategy text is authored, not independently
validated by a catalog or simulator. [Scope, maintenance, provenance and validation](../docs/situational-reasoning.md).

The one-time explicit `tools/expand_situational_catalog.py --download-static-reference`
maintenance command fetches only static public trees at the already pinned commit,
never private replay/context data. Runtime is offline; no automatic download/update.
Legacy packs below keep their previous narrower behavior.

## Preserved civilization-specific reference pack

The coach can use a verified local snapshot for Franks vs Bohemians/Britons/Berbers.
Default unknown-mod behavior is **reference only, tips withheld**. A separate local
per-match user declaration permits explicitly conditional questions, not verified
applicability or a mistake verdict. See the [matchup contract](../docs/matchup-review.md),
[v2 plan](../docs/coaching-v2-plan.md) and [research](../docs/research/knowledge-and-state.md).

`aoe2techtree.lock.json` pins a public source revision, update number, file hashes and
attribution. `tools/audit_techtree.py` verifies a downloaded snapshot **offline**, reports
catalog facts/base stats, and distinguishes build match/mismatch/unknown. It never
reconstructs game state, enables matchup advice or fetches anything during review.
The separate `knowledge_adapter.py` verifies reviewed assertions from
`franks-matchups.v1.json`; `matchup.py` applies the explicit gates in the contract.

The local research snapshot and its audit output live under ignored `data/research/`.
No game `.dat`, artwork, full website or proprietary engine is bundled with this source.

## Situation response menu v1

`../situation_knowledge.py` uses the same hash-verified source for an availability/age-only menu of Building 72 (Palisade Wall), Building 79 (Watch Tower), Building 82 (Castle), Unit 4 (Archer), Unit 7 (Skirmisher), and Unit 93 (Spearman). Names and ages are checked against the four locked civ trees on every compiled menu. It adds no combat/counter assertions or effective-cost calculations. Applied options require exact current provenance/build/dataset/mode/flags, no known mod conflict, a content/player-scoped standard-rules annotation and a recorded age anchor; unknown mods stay independently unverified. Default output is reference-only. Unsupported civs/sources do not block generic command-incident questions. See [situation scope and architecture](../docs/situation-coaching.md).

## Reusable gameplay concepts v1/v2

`gameplay.v1.json` is retained byte-for-byte for shipped siege IDs/feedback. The new
`gameplay.v2.json` adds executable positive-input checkpoints for tactical changes,
economy/army allocation, production investment, map access, walling and upgrades.
Concepts, role families, namespaced entity roles, conditional options, exceptions,
required state and authorship are separate from catalog facts. An unknown unit alias
is not automatically military. These are review checkpoints, not completed-state or
combat-result detectors. Guidance is implementation-reviewed, not externally
expert-validated or a quotation attributed to a pro.

`../gameplay_knowledge.py` hash-checks the same existing snapshot and exposes base
cost/train-time, exact per-civ availability lists and plain-text descriptions for the
namespaced role registry. Own/opposing civilization references and role-family
questions do not infer armies from civilizations or player vision from enemy inputs. This can reference civs beyond the four audited trees without
inventing their age/prerequisite trees or effective bonuses. It never applies a base
number as live state, affordability, a combat result or a counter guarantee. Unknown
patch/civ/source stays explicitly unsupported/reference-only; generic conditional
questions are independent. Pack hashes and versions bind advice/corrections. No new
snapshot download or raw game-asset distribution occurs. See the
[whole-match implementation plan](../docs/milestone-2-gameplay-coach.md).

## Repeat the public-source audit

From the project root, explicitly download only the public reference files. These
requests contain no replay/player information. Normal Replay Lab use does not do this.

```bash
REV=3bb43b1439eef88dfe7fe892d7f7dc41ac9dd76f
SNAP="data/research/aoe2techtree/$REV"
BASE="https://raw.githubusercontent.com/SiegeEngineers/aoe2techtree/$REV"
mkdir -p "$SNAP/trees"
curl --fail --location "$BASE/data/data.json" -o "$SNAP/data.json"
curl --fail --location "$BASE/data/locales/en/strings.json" -o "$SNAP/strings.en.json"
curl --fail --location "$BASE/data/trees/FRANKS.json" -o "$SNAP/trees/FRANKS.json"
curl --fail --location "$BASE/data/trees/BOHEMIANS.json" -o "$SNAP/trees/BOHEMIANS.json"
curl --fail --location "$BASE/data/trees/BRITONS.json" -o "$SNAP/trees/BRITONS.json"
curl --fail --location "$BASE/data/trees/BERBERS.json" -o "$SNAP/trees/BERBERS.json"
curl --fail --location "$BASE/LICENSE" -o "$SNAP/LICENSE"
curl --fail --location "$BASE/index.html" -o "$SNAP/index.html"
./.venv/bin/python tools/audit_techtree.py "$SNAP" --replay-build 185872 \
  > data/research/techtree-audit-185872.json
./.venv/bin/python -m unittest -v test_knowledge test_matchup
```

Only pass `--replay-build` when known from actual parser metadata (`Match.build_version`).
Omit it to report `unknown`; e.g. 180059 reports `build_mismatch`. Never substitute the
version-looking string in a replay filename. A build match is not validation of mods,
modes, entity-ID mapping, effective stats, or strategic recommendations.

For other civs the global availability/base data and description are present, but only
Franks/Bohemians/Britons/Berbers per-civ trees are locked here. The audit returns `not_in_locked_subset`
for missing trees rather than inventing age/prerequisite metadata. Expand the lock via
an explicit reviewed change before enabling another matchup pack.

## Contract and licensing rules

- Stable fact references should be `source commit + kind + numeric ID + field`, with
  civ-specific description IDs / tree node IDs where relevant. Unit and Tech IDs overlap.
- Catalog statuses are never observed game research. Costs/train times are **base** values,
  not automatically civ-adjusted values or completed-production predictions.
- Dynamic prose is plain text; nothing fetched is executed or used as model instructions.
- Hash mismatches fail closed. Updating the lock does not retroactively validate old advice.
- Upstream's software is MIT (HSZemi, 2018); its README separately identifies Microsoft
  game content and Game Content Usage Rules. Retain notices for any redistributed portions;
  verify rights before distributing derived content/assets. This audit does not grant them.
- Existing unlicensed-root viewer remains a separate public-release blocker.
