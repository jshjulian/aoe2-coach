# Sharing status and third-party notices

This source snapshot is for local development. Initializing Git does not publish it or establish redistribution rights. Do not treat it as a licensed public release.

## Open release questions

- The inherited replay-viewer project root has no identified license grant. Permission/license clarification is required before public distribution of its code or modifications.
- The Agewise name and any project-owned licensing policy still require review. No new blanket MIT/Apache license is asserted here.
- Game imagery, logos, data and other third-party assets have independent rights. A software license is not a grant of Microsoft game-content rights. Review the applicable Game Content Usage Rules and attribution requirements before distribution.

## Existing notices

- `viewer/src/aoe2rec-js/LICENSE` retains the bundled WASM parser's Apache-2.0 notice. Its package metadata and generated bindings are retained alongside it. That license does not cover the surrounding viewer or unrelated assets.
- The Python mgz parser is an external pinned dependency; its own upstream license applies. Other installed Python/npm dependencies retain their own terms and are not vendored into Git.
- Civilization-reference locks identify `SiegeEngineers/aoe2techtree`, its revision, hashes, software-license attribution and game-content notice. Downloaded snapshots remain ignored. The optional restoration command retrieves only locked public files and retains the locked LICENSE; it does not grant rights to their content.

## Privacy and repository hygiene

The ignore rules exclude runtime data, savegames, journals, annotations, private settings, research, screenshots, secrets, dependencies and build products. Historical local notes and replay-dependent test fixtures also remain outside this initial Git snapshot. No original local file is deleted as part of that exclusion.

Before any future push, inspect `git status`, `git diff --cached` and all tracked files. Never force-add ignored data. Review identifiers in new tests/documentation: filenames, player names, replay content hashes and source-event IDs can identify private matches even without the replay itself.

No Git remote, hosting account, public visibility or upload is implied by local repository initialization. Decide the target and permissions explicitly before any remote operation.
