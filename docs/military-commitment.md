# Military commitment review v1

Coach → **Military commitment** is a separate, initially collapsed post-match review. It asks whether to keep producing, support the existing response, change composition, or disengage/stabilise. It covers defensive responses and player-reported offensive objectives without inferring a successful push or recommending a particular counter.

## Evidence and scope

`military_commitment.py` builds additive `commitment_context` on `/api/coaching`. Existing normalized schema 5, API version 4, legacy recommendation IDs, rankings, journal suggestions, habits, progress cohorts and exports are unchanged. Health/launcher feature guard adds `military_commitment_version: 1`.

Scope requires a schema-5 content identity, DE provenance 2, dataset 100, recorded random-map mode, all-tech and cheats off, no known custom mod/RMS, two unambiguous opposing participants, and exactly one coherent parser-reported winner. The result flag is a completion/readiness gate, never an advice ranking input or validation of coaching. Unknown results abstain; missing is not a loss. Empty mod metadata still does not verify standard rules.

No live-ranked/game hooks, capture, memory reads, OCR, external provider, model, installation, new dependency or reference download is added. Runtime is local. No new resource/state measurement is qualified.

## Candidate policy

- An explicit positive or unknown-quantity military queue request is classified only by a curated exact display-label + numeric unit-ID pair into an archetypal Barracks, Range, Stable or Siege Workshop line. This is an adapter classification, not proof of actual production location, civilization availability, effective costs or mod compatibility. Unknowns are never repaired into known aliases.
- A first-use transition between consecutive different recognized lines within 300 seconds creates a question. An intervening unclassified military queue breaks adjacency. Correctly identified civilian requests are ignored. Negative/zero/invalid quantities do not become positive investments; missing quantity remains missing.
- A first matching new-building request between the previous and next queue, within 180 seconds of the latter, is the anchor; otherwise the next queue is the anchor. A building request is not completion. Simultaneous requests do not establish a transition. Returning to an already-used line is not presented as a new commitment.
- Otherwise, the first recognized military request can create an opening/job question when at least 120 seconds of recorded follow-up exists and no nearby transition already covers it. An opening question does not establish an attack, intent, initial army, or unit presence.
- At most four chronological windows. Timing thresholds are editorial review bounds, not optimal timings or targets. Windows may overlap and are not independent measurements. No outcome, rating, answer, saved habit or progress determines selection.
- Up to 300,000 input events and a one-day recorded clock. Each window cites at most 41 distinct events: mandatory anchor/adjacent queues, bounded recent/following own inputs, and bounded retrospective opposing inputs. The public guard permits at most 48. Prior/next-line counts include only cited own queue requests, never opposing inputs. They do not count all window activity, produced units or armies. Unknown quantities across cited queues are separately disclosed in the DTO.

Own nearby building, research, wall and garrison requests provide context. Opponent queues/research are explicitly retrospective—not player vision. Movement and target orders are deliberately unused, including for pressure/attack detection. A Mining Camp request does not establish gold income or safe access; its absence does not establish zero income. No wall closure, worker death, successful garrison, production idle time or resource shortage is inferred.

## Interpretation and clarification

All four options remain conditional questions. There is no optimal-investment score, always-rush advice, mandatory continuous production or sunk-cost rule.

The optional form requires explicit choices for:

1. Intended job: protect resources, clear pressure, raid/intercept, pressure a position, reinforce a push, buy age-up time, other, or uncertain.
2. Constraint/explanation: missing resource setup, denied access, funding/population, lost production, lost units, changed threat, complementary mix, deliberately small group, other/correction, uncertain, or not applicable.
3. Explicit reviewed-player confirmation, with an optional plain-text note up to 1,000 characters.

No choices are preselected for an unanswered question. Browsing, selecting a window, editing drafts and following evidence never save. The conversation is not mined to seed answers. The assessment changes only after explicit save and labels its interpretation as a player account, not reconstructed state. Not-applicable withholds the comparison/options and practice cue while retaining source inspection. Notes are escaped text, not instructions or parsed facts.

The generic practice cue is presentation only: no goal selection, replacement, suggestion injection, cohort membership, progress measurement or journal backfill occurs.

## Persistence and concurrency

Protected existing `/api/coaching/state` accepts `operation: commitment_answer`. The server rebuilds the current source packet; it does not trust browser-supplied bindings or source metrics. Existing Host/Origin/CSRF/JSON/body protections apply.

SQLite uses additive record kind `military_commitment_context` and existing revision history. Identity binds exact content, selected participant, full reported provenance, explicitly unknown historical analysis-generator identity, module/code digest, window/anchor/source event bytes, and question version. `BEGIN IMMEDIATE` plus expected revision provides compare-and-swap. Bad choices, foreign/stale identities, unconfirmed saves, invalid/control-character notes and stale revisions are refused. Corrupt or unbound records are unavailable, never reset/overwritten; old history is retained. No migration or backfill.

This context and its explanations are excluded from Markdown export. They never rank the replay main, enter practice-progress snapshots or replace existing clarifications.

## Tests and limitations

Portable checks:

```bash
.venv/bin/python -m unittest -v test_military_commitment test_military_commitment_api
node tools/test_military_commitment.mjs
```

An optional local browser suite needs a running viewer, Playwright already available, and a supported completed replay in the configured library:

```bash
PLAYWRIGHT_MODULE=/path/to/playwright .venv/bin/python tools/run_military_commitment_browser_smoke.py
```

Optional environment variables `COMMITMENT_TEST_GAME_ID` and `COMMITMENT_TEST_PLAYER` select a local case; no real player names/replay identities are bundled in this test. Its API, journal and hypothetical answers are ephemeral; private UI screenshots go under ignored `data/smoke/`. Do not interpret the simulated answers as player/expert review.

Delivery checks passed: 336 Python tests (including 31 new detector/persistence/HTTP checks), 22 new TypeScript guard tests plus 44 prior Node tests, TypeScript no-emit, Python compilation, stopped-viewer production build, and all 17 distinct sequential browser suites. The new browser suite was also rerun on the user-requested loss after its initial run on a different completed match; that recheck is not an independent strategic evaluation. Private dark/light/mobile screenshots were reviewed. A fresh production journal/clarification dump is compared without restoring older data; legacy packet equality and isolated clarification-only writes are checked with ephemeral stores.

Software and workflow validation do not establish strategic usefulness, feasible alternatives, battle outcomes or learning impact. Resource state, safe gathering, actual forces, completion and player vision remain unknown. Team, unique-unit, naval and complex composition decisions are outside this first slice. No detected window is not praise or proof of safe play.
