# Setup and replay-folder configuration

## Supported setup

The supplied shell launcher is for Linux/WSL. Use Linux Python/Node/npm inside WSL, not Windows npm.cmd from a Linux shell. Python 3.12 and Node 22+ are recommended. Install prerequisites using your normal environment management; Agewise does not install them at launch.

From the source directory:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
(cd viewer && npm ci)
```

These are explicit installation steps with network access. The parser requirement pins upstream mgz PR #147 commit `def94dd63a23b65435813e5acc8a0b3defafda03` for supported recent DE recordings. Other replay versions may be unsupported; incompatible or incomplete recordings stay visibly unavailable.

## Find the savegame folder

Typical Windows location:

```text
C:\Users\YOUR_WINDOWS_NAME\Games\Age of Empires 2 DE\YOUR_ACCOUNT_FOLDER\savegame
```

Typical WSL spelling of the same directory:

```text
/mnt/c/Users/YOUR_WINDOWS_NAME/Games/Age of Empires 2 DE/YOUR_ACCOUNT_FOLDER/savegame
```

Some installations use Documents/My Games instead. Use the actual folder containing your `.aoe2record` files, not the Steam game-install directory. User/account folder names differ between installations. Quote paths containing spaces.

## One-off folder selection

```bash
./run-viewer.sh --production --replays "/path/to/savegame"
```

Select several folders by repeating the option:

```bash
./run-viewer.sh --replays "/path/to/first/savegame" --replays "/path/to/second/savegame"
```

CLI relative paths are relative to the terminal's working directory. `~` is supported. Folders must exist; they may be empty. Agewise doesn't create missing savegame folders.

## Persistent private settings

Copy `agewise.example.json` to `agewise.local.json` beside `app.py`, then edit the path list. The local settings file is Git-ignored; use `chmod 600 agewise.local.json` to restrict local file access. It is plain JSON, not a shell script; Agewise never executes or rewrites it.

```json
{
  "version": 1,
  "replay_directories": ["/path/to/savegame", "./another-savegame"]
}
```

Paths inside JSON are relative to that settings file, not the caller's working directory. A maximum of 16 folders is supported. Duplicate resolved paths are counted once. An empty list deliberately selects no folders and prevents discovery. An absent default file allows discovery of conventional local folders.

An alternate private file is also supported. Keep it outside the checkout, or use the ignored filename pattern `agewise.NAME.local.json`. Arbitrary custom filenames inside the checkout are **not** automatically Git-ignored:

```bash
./run-viewer.sh --config "/path/to/private-settings.json"
```

Selection precedence is repeated `--replays` options, then a nonempty `AOE2_REPLAY_DIR`, then explicit/default JSON settings, then discovery. The existing environment variable uses `:` between paths on Linux/WSL (`os.pathsep`); prefer JSON or repeated CLI options for folder names containing a colon.

Malformed/oversized settings, unsupported versions and nonexistent configured folders are errors. They are not repaired, reset, or replaced by discovery. The settings file limit is 64 KiB. No machine-specific savegame path is compiled into the app.

**Restart both services after a change.** Stop the previous launcher with Ctrl-C, then relaunch. If the API was started separately, stop that process as well. An already-running API will not silently adopt another launcher's folder configuration; the launcher refuses reuse when overrides are requested. Changing folders retains historical journal/clarification records and cached analyses; it doesn't migrate, backfill or delete them.

## Ports and API-only mode

```bash
AOE2_COACH_API_PORT=8766 ./run-viewer.sh --port 3001 --replays "/path/to/savegame"
./run.sh --port 8765 --replays "/path/to/savegame"
./run-viewer.sh --help
```

The API-only command supports the same `--replays`/`--config` flags. Both services bind to `127.0.0.1`. Read startup errors in ignored `data/replay-lab-api.log`. Startup never runs pip/npm installation or updates; missing dependencies need the explicit setup commands above.

## Reference catalogs and private data

The initial Git snapshot contains source locks, not the local downloaded research cache. To restore only their already-pinned public files, explicitly run:

```bash
.venv/bin/python tools/restore_reference_snapshot.py --download-static-reference
```

No private input is sent; only static public filenames and the locked revision are used in requests. Existing hashes are checked, files are never overwritten, and locks are never regenerated. A run without the flag verifies offline and makes no requests. No reference download occurs during normal browsing. Missing/mismatched sources keep dependent coaching features unavailable/reference-only.

Replays, SQLite journals, clarifications, observations, authored reviews, screenshots, local settings and all `data/` contents are intentionally excluded from Git. Keep separate per-user installations. A new source checkout does not contain another user's replays, habits, personal feedback or statistics.
