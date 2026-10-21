# Agewise

**Your local-first AoE2 replay coach.**

Agewise combines a local replay library, source-linked whole-match coaching, replay/minimap navigation, command charts, a practice journal, map previews and local opponent/civilization statistics.

Replay files and personal coaching data stay on your computer. There is no account service, automatic replay upload, model provider, game launch or capture session. Command inputs are not completed production, surviving armies or proof of combat outcomes. Experimental coaching is conditional, not independently established expert judgement.

## Setup and start

Supported launcher environment: **Linux or Windows with WSL**, Python 3.12, Linux Node.js 22+, npm, Git and curl. Install dependencies explicitly once; launching Agewise never installs or updates them.

```bash
cd aoe2-coach
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
(cd viewer && npm ci)
```

Select your savegame folder directly:

```bash
./run-viewer.sh --production --replays "/path/to/your/savegame"
```

Open **http://127.0.0.1:3000**. Stop with Ctrl-C. Omit `--production` for development. Both services bind to loopback; don't expose them to the internet.

### Remember your folder

```bash
cp agewise.example.json agewise.local.json
chmod 600 agewise.local.json
```

Edit `agewise.local.json` to contain **your** folder(s), then start normally:

```json
{
  "version": 1,
  "replay_directories": ["/path/to/your/savegame"]
}
```

```bash
./run-viewer.sh --production
```

On WSL use `/mnt/c/Users/...`, not `C:\\Users\\...`. Folder changes take effect after stopping/restarting both services. The launcher refuses to silently reuse an already-running API when folder overrides are requested.

- Repeat `--replays PATH` for multiple folders.
- `--config FILE` selects another private settings file.
- Existing `AOE2_REPLAY_DIR` is supported (OS path-separated paths).
- Precedence: **CLI folders → environment → explicit/default settings file → auto-discovery**.
- Empty existing folders work; `replay_directories: []` deliberately selects none.
- Invalid settings fail clearly without rewriting them or falling back to unrelated folders.
- Changing folders does not delete existing journal entries or replay analyses.

See **[setup and configuration](docs/setup.md)** for WSL paths, ports, optional reference data and troubleshooting.

## What you can do

- Browse saved matches with locally rendered recorded-map previews.
- Open Coach, follow an evidence reference to the exact replay clock, or inspect Events.
- Explore military queue-input composition, observed age milestones, technology requests and Villager queue patterns. Cancellations are a separate ledger, not a net army count.
- Choose one explicit practice habit and record your own opportunities/adaptations. Browsing does not save a habit or clarification.
- Use **My stats** for local records against opponent display names and civilizations. Exact-content duplicate copies count once; unknown outcomes are shown separately and excluded from win-rate denominators. These are not official lifetime account statistics.

Choose your own recorded player name in the interface. Display names are not verified account identities.

## Optional pinned reference data

Downloaded reference snapshots are not included in Git. Without them, dependent reference/coaching features abstain rather than inventing catalog facts; the library, replay views, command charts and statistics remain usable.

To explicitly retrieve the public files named by the existing source locks:

```bash
.venv/bin/python tools/restore_reference_snapshot.py --download-static-reference
```

This makes GET requests only for pinned public reference files; it sends no replay/player data, installs no packages and does not change either lock. Running the command **without** the flag verifies existing files offline. Changed files are never silently replaced. Runtime does not fetch reference data.

## Tests

Portable checks included in this initial Git snapshot:

```bash
.venv/bin/python -m unittest -v test_replay_settings test_map_previews test_reference_snapshot
node tools/test_library_stats.mjs
node tools/test_command_charts.mjs
(cd viewer && npx --no-install tsc --noEmit)
bash -n run.sh run-viewer.sh
```

Historical research notes, private replay-dependent tests/browser fixtures and their data remain local and ignored, not deleted. The initial shared test subset intentionally does not claim to reproduce those private regression suites. Existing maintainer replay checks can use an ignored `CHART_LIVE_CASES_FILE`; no real replay identities are distributed in the Node unit tests.

## Git and sharing status

`data/`, personal settings, replays, journals, annotations, screenshots, research, dependencies, secrets and build outputs are excluded from Git. Keep each user's installation and private data separate. Don't force-add ignored files.

**This is a private development repository, not a cleared public release.** The inherited viewer root has no identified project license; bundled dependencies have separate terms. No blanket license is asserted. Review **[sharing and third-party notices](SHARING.md)** before distributing or publishing it. A local Git commit does not upload anything.
