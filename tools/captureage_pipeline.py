#!/usr/bin/env python3
"""Opt-in, assisted offline CaptureAge research collector. NOT imported by the app.

Explicit Steam game + CaptureAge lifecycle, explicit operator replay/player binding,
owned-window snapshots, visible-HUD OCR candidates, and fingerprint-scoped cleanup.
No installs, private interfaces, subscriptions, game memory access or SQLite writes.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.read_state_ocr import recognize_image, parse_fields
from tools.validate_state_checkpoints import extract, signature

ALLOWED = {'CaptureAge', 'AoE2DE', 'AoE2DE_s', 'BattleServer', 'gamelaunchhelper'}
PS = '/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe'
QUALIFICATION = 'research_only_operator_bound_ocr_not_verified_game_state'


def now(): return datetime.now(timezone.utc).isoformat()
def load(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def controller_token(pid):
    try: return Path(f'/proc/{pid}/stat').read_text().rpartition(')')[2].split()[19]
    except (OSError, IndexError): return None


def controller_alive(state):
    owner = state.get('controller', {})
    return bool(owner.get('start_ticks')) and controller_token(owner.get('pid')) == owner['start_ticks']


def save(path, value):
    path = Path(path)
    temporary = path.with_name(path.name+'.next')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    temporary.replace(path)


def fingerprint(p):
    if (not isinstance(p, dict) or type(p.get('pid')) is not int or p['pid'] <= 0 or p.get('name') not in ALLOWED or
        not isinstance(p.get('started_utc_ticks'), str) or not p['started_utc_ticks'].isascii() or not p['started_utc_ticks'].isdigit()):
        raise ValueError('Invalid process fingerprint.')
    return p['pid'], p['name'], p['started_utc_ticks']


class WindowsBridge:
    def call(self, action, **kwargs):
        request = json.dumps({'action': action, **kwargs}, ensure_ascii=True)
        command = "$RequestJson='"+request.replace("'", "''")+"';\n"+(ROOT/'tools/captureage_windows.ps1').read_text()
        result = subprocess.run([PS, '-NoProfile', '-NonInteractive', '-Command', command], capture_output=True,
                                text=True, encoding='utf-8', errors='replace', timeout=50, start_new_session=True)
        if result.returncode: raise RuntimeError(result.stderr.strip() or f'Windows bridge failed: {action}')
        return json.loads(result.stdout.lstrip('\ufeff'))

    def inventory(self): return self.call('inventory')

    def windows_path(self, path):
        return subprocess.check_output(['wslpath', '-w', str(Path(path).resolve())], text=True).strip()


def event(directory, kind, **details):
    with (Path(directory)/'events.jsonl').open('a') as stream:
        stream.write(json.dumps({'at': now(), 'kind': kind, **details}, ensure_ascii=False, allow_nan=False)+'\n')


def recover_owned(directory, state):
    """A launch receipt survives a caller interruption before its return value."""
    baseline = {fingerprint(p) for p in state['baseline']}
    owned = {fingerprint(p): p for p in state.get('owned', [])}
    for role in ('game', 'ca', 'steam-relaunch'):
        receipt = Path(directory)/(role+'.launch.json')
        if receipt.exists():
            p = load(receipt); key = fingerprint(p)
            if key in baseline: raise ValueError('Launch returned a pre-existing process; never close it.')
            if role == 'ca' and p['name'] != 'CaptureAge': raise ValueError('Unexpected CA launch receipt.')
            if role in ('game', 'steam-relaunch') and p['name'] not in ('AoE2DE', 'AoE2DE_s', 'gamelaunchhelper'): raise ValueError('Unexpected game launch receipt.')
            if role == 'steam-relaunch' and (p['name'] != 'AoE2DE_s' or p.get('ownership_basis') != 'operator_confirmed_new_steam_relaunch_exact_path_parent_and_time'):
                raise ValueError('Steam relaunch needs explicit path/parent/time ownership confirmation.')
            owned[key] = {**p, 'role': 'game' if role == 'steam-relaunch' else role,
                          'ownership_basis': p.get('ownership_basis', 'OS_launch_returned_pid_and_creation_time')}
    state['owned'] = list(owned.values())
    return state['owned']


def discover_children(state, inventory):
    """Only currently verifiable descendants, never all processes with a name."""
    baseline = {fingerprint(p) for p in state['baseline']}
    owned = {fingerprint(p): p for p in state['owned']}
    current = {p['pid']: p for p in inventory}
    for _ in range(len(inventory)+1):
        changed = False
        for p in inventory:
            key = fingerprint(p); parent = current.get(p.get('parent_pid'))
            if key in baseline or key in owned or p['name'] not in ('CaptureAge', 'BattleServer', 'AoE2DE', 'AoE2DE_s', 'gamelaunchhelper') or not parent: continue
            if fingerprint(parent) in owned and int(p['started_utc_ticks']) >= int(parent['started_utc_ticks']):
                owned[key] = {**p, 'role': 'child', 'ownership_basis': 'live_verified_owned_parent'}; changed = True
        if not changed: break
    state['owned'] = list(owned.values())


def cleanup(directory, state, bridge, grace_seconds=15, force=False):
    """Idempotent, best effort, exact fingerprints only; incomplete cleanup is loud."""
    intent_path = Path(directory)/'game.intent.json'
    if intent_path.exists() and not (Path(directory)/'game.launch.json').exists():
        try:
            recovered = bridge.call('recover_steam_launch', intent=load(intent_path), receipt_path=bridge.windows_path(Path(directory)/'game.launch.json'))
            state['pending_steam_launch_unresolved'] = recovered is None
        except Exception as exc:
            state['pending_steam_launch_unresolved'] = True
            event(directory, 'steam_launch_recovery_error', error=str(exc))
    recover_owned(directory, state)
    if (Path(directory)/'game.launch.json').exists():
        state['pending_steam_launch_unresolved'] = False
    try: discover_children(state, bridge.inventory())
    except Exception as exc: event(directory, 'cleanup_inventory_error', error=str(exc))
    save(Path(directory)/'run.json', state)
    ordered = sorted(state['owned'], key=lambda p: {'game': 0, 'ca': 1, 'child': 2}.get(p['role'], 3))
    for p in ordered:
        try:
            response = bridge.call('close', target=p, force=False)
            event(directory, 'cleanup_request', target=p, response=response)
        except Exception as exc: event(directory, 'cleanup_close_error', target=p, error=str(exc))
    deadline = time.monotonic()+grace_seconds
    remaining = ordered
    while True:
        try:
            current = {fingerprint(p) for p in bridge.inventory()}
            remaining = [p for p in ordered if fingerprint(p) in current]
        except Exception as exc:
            event(directory, 'cleanup_verification_error', error=str(exc)); break
        if not remaining or time.monotonic() >= deadline: break
        time.sleep(0.5)
    if remaining and force:
        for p in remaining:
            try: event(directory, 'cleanup_force_request', target=p, response=bridge.call('close', target=p, force=True))
            except Exception as exc: event(directory, 'cleanup_force_error', target=p, error=str(exc))
        try:
            current = {fingerprint(p) for p in bridge.inventory()}
            remaining = [p for p in ordered if fingerprint(p) in current]
        except Exception as exc: event(directory, 'cleanup_verification_error', error=str(exc))
    try:
        current_inventory = bridge.inventory()
        known = {fingerprint(p) for p in state['owned']} | {fingerprint(p) for p in state['baseline']}
        unknown = [p for p in current_inventory if fingerprint(p) not in known]
    except Exception as exc:
        unknown = [{'verification_error': str(exc)}]
    complete = not remaining and not unknown and not state.get('pending_steam_launch_unresolved', False)
    state['cleanup'] = {'finished_at': now(), 'complete': complete, 'owned_closed': not remaining, 'remaining_owned': remaining,
                        'unowned_relevant_left_untouched': unknown,
                        'preexisting_processes_never_closed': True, 'force_enabled_explicitly': force}
    save(Path(directory)/'run.json', state)
    return complete


def prepare(image, sheet):
    subprocess.run(['node', str(ROOT/'tools/prepare_state_ocr.mjs'), str(image), str(sheet)],
                   cwd=ROOT, check=True, capture_output=True, text=True, timeout=25)
    return load(str(sheet)+'.layout.json')


def patches(layout):
    items = layout.get('identity_patches')
    if not isinstance(items, list) or len(items) != 2 or {p.get('role') for p in items} != {'left', 'right'}:
        raise ValueError('Missing visible-header continuity witness.')
    for p in items:
        if not isinstance(p.get('rgb_sha256'), str) or len(p['rgb_sha256']) != 64: raise ValueError('Invalid witness hash.')
    return {p['role']: (p['rect'], p['rgb_sha256']) for p in items}


def assess(readings, layout, binding, previous_clock):
    reasons = []
    if patches(layout) != patches(binding): reasons.append('visible_header_changed_or_wrong_screen')
    if not readings.get('all_fields_syntactically_read'): reasons.append('missing_or_ambiguous_hud_field')
    clock = readings.get('values', {}).get('clock')
    if type(clock) is not int or clock < 0: reasons.append('invalid_or_unreadable_clock')
    if type(clock) is int and previous_clock is not None and clock <= previous_clock:
        reasons.append('duplicate_or_nonmonotonic_quantized_clock')
    if type(clock) is int and clock > binding['duration_seconds']+1: reasons.append('clock_outside_recording')
    return {'reviewable_candidate': not reasons, 'rejection_reasons': reasons,
            'validated_for_application': False, 'qualification': QUALIFICATION}


def ca_target(state):
    found = [p for p in state['owned'] if p['role'] == 'ca']
    if len(found) != 1: raise ValueError('Exactly one OS-owned CaptureAge root required.')
    return found[0]


def adopt_steam_relaunch(directory, pid, confirmed):
    if not confirmed: raise ValueError('Explicit ownership assertion for this new offline Steam game PID is required.')
    directory = Path(directory); state = load(directory/'run.json')
    if state['launcher']['kind'] != 'steam' or state['baseline']:
        raise ValueError('Only an exclusive Steam session with empty game/CA baseline can adopt a relaunch.')
    original = load(directory/'game.launch.json')
    if not original.get('exe_path'): raise ValueError('Original explicit Steam executable receipt missing.')
    receipt = directory/'steam-relaunch.launch.json'
    if receipt.exists(): raise ValueError('Steam relaunch already recorded.')
    bridge = WindowsBridge()
    result = bridge.call('adopt_steam_relaunch', pid=pid, original_game=original, receipt_path=bridge.windows_path(receipt))
    print('Explicit session-owned Steam relaunch recorded:', result['pid'], '; Steam client will not be closed.')


def confirm(directory, expected_match_id, confirmed):
    if not confirmed: raise ValueError('Explicit offline replay/name/role confirmation required.')
    directory = Path(directory); state = load(directory/'run.json')
    if state['status'] != 'awaiting_ui_confirmation': raise ValueError('Session is not waiting for confirmation.')
    if state['source']['match_id'] != expected_match_id: raise ValueError('Wrong expected content ID.')
    if (directory/'confirmation.json').exists(): raise ValueError('Confirmation already exists; cannot overwrite binding.')
    attempt = 'confirmation-'+uuid.uuid4().hex[:12]
    bridge = WindowsBridge(); image = directory/(attempt+'.png'); sheet = directory/(attempt+'.sheet.png')
    capture = bridge.call('capture', target=ca_target(state), output_path=bridge.windows_path(image))
    layout = prepare(image, sheet)
    readings = parse_fields(recognize_image(sheet), layout)
    if not readings['all_fields_syntactically_read']:
        raise ValueError('Confirmation HUD/clock unreadable. Leave the ordinary HUD visible and retry; evidence retained.')
    save(directory/(attempt+'.ocr.json'), readings)
    binding = {'schema_version': 1, 'session_id': state['session_id'], 'match_id': expected_match_id,
               'basis': 'operator_asserted_offline_replay_filename_players_civs_and_roles_not_parser_facts',
               'captureage_ui_version_operator_confirmed': '1.26.0', 'frame_sha256': digest(image), 'evidence_image': image.name,
               'identity_patches': layout['identity_patches'], 'roles': state['roles'],
               'duration_seconds': state['source']['duration_seconds'], 'confirmed_at': now(), 'capture': capture,
               'limits': ['Header pixel continuity is not cryptographic verification of the loaded replay.',
                          'Repeated games with identical headers cannot be distinguished without operator binding.']}
    if load(directory/'run.json')['status'] != 'awaiting_ui_confirmation':
        raise ValueError('Collector stopped during confirmation; nothing will be adopted.')
    # No partial confirmation visible to the running collector.
    temporary = directory/'confirmation.pending.json'
    with temporary.open('x') as stream: json.dump(binding, stream, ensure_ascii=False, indent=2)
    temporary.replace(directory/'confirmation.json')
    print('Operator research binding recorded. It is NOT a parser fact or verified state provider.')


def collect(replay, directory, left_id, right_id, *, launcher=None, game_exe=None, samples=6, interval=2, setup_timeout=180, max_wall=120, force=False, bridge=None, stop=None):
    if launcher != 'steam' or game_exe is None:
        raise ValueError('Choose --launcher steam and the explicit installed --game-exe; no Xbox fallback.')
    bridge = bridge or WindowsBridge(); external_stop = stop or (lambda: False)
    directory = Path(directory)
    stop = lambda: external_stop() or (directory/'cancel.request').exists()
    baseline = bridge.inventory()
    if baseline: raise ValueError('CaptureAge/game processes already running. Close them yourself first; existing apps are never adopted or closed.')
    before = signature(Path(replay))
    source = extract(Path(replay))
    if signature(Path(replay)) != before: raise ValueError('Replay changed during preflight.')
    players = {p['id']: p for p in source['players']}
    if len(players) != 2 or left_id == right_id or {left_id, right_id} != set(players):
        raise ValueError('This pilot needs two explicit, distinct parser player IDs covering the recording.')
    directory = Path(directory); directory.mkdir(parents=True, exist_ok=False, mode=0o700)
    save(directory/'source.json', source)
    state = {'schema_version': 1, 'session_id': uuid.uuid4().hex, 'started_at': now(), 'status': 'starting',
             'controller': {'pid': os.getpid(), 'start_ticks': controller_token(os.getpid())},
             'launcher': {'kind': launcher, 'game_exe': bridge.windows_path(game_exe), 'steam_client_never_owned_or_closed': True},
             'qualification': QUALIFICATION, 'validated_for_application': False, 'source': {k: source[k] for k in ('match_id', 'duration_seconds', 'replay_provenance')},
             'roles': {'left': {k: players[left_id][k] for k in ('id', 'name', 'civilization')},
                       'right': {k: players[right_id][k] for k in ('id', 'name', 'civilization')}},
             'baseline': baseline, 'owned': [], 'sampling': {'requested': samples, 'minimum_wall_interval_seconds': interval, 'max_collection_wall_seconds': max_wall}, 'frames': []}
    save(directory/'run.json', state)
    print('Exclusive offline Steam session: only the newly launched game and CaptureAge will be managed; Steam itself stays open.', flush=True)
    failure = None
    try:
        for role, action in [('game', 'launch_game'), ('ca', 'launch_ca')]:
            if stop(): raise KeyboardInterrupt('Cancellation requested')
            receipt = directory/(role+'.launch.json')
            launch_options = {'launcher': launcher, 'game_exe': bridge.windows_path(game_exe),
                              'intent_path': bridge.windows_path(directory/'game.intent.json')} if role == 'game' else {}
            bridge.call(action, receipt_path=bridge.windows_path(receipt), **launch_options)
            recover_owned(directory, state); save(directory/'run.json', state)
        state['status'] = 'awaiting_ui_confirmation'; save(directory/'run.json', state)
        print(f'Waiting for operator confirmation in {directory}.\nOpen ONLY the specified offline replay in CaptureAge; verify filename, both names/civs, left/right roles and UI 1.26.0.\nDo not use these managed applications for other work. They will be closed when the session ends.\nExpected content ID: {source["match_id"]}', flush=True)
        deadline = time.monotonic()+setup_timeout
        while not (directory/'confirmation.json').exists():
            if stop(): raise KeyboardInterrupt('Cancellation requested')
            if time.monotonic() >= deadline: raise TimeoutError('Offline replay confirmation timed out.')
            time.sleep(0.25)
        binding = load(directory/'confirmation.json')
        if binding.get('session_id') != state['session_id'] or binding.get('match_id') != source['match_id'] or binding.get('roles') != state['roles']:
            raise ValueError('Confirmation belongs to another session/content/player mapping.')
        if Path(binding['evidence_image']).name != binding['evidence_image']: raise ValueError('Invalid confirmation evidence path.')
        if digest(directory/binding['evidence_image']) != binding['frame_sha256']: raise ValueError('Confirmation evidence changed.')
        if binding['captureage_ui_version_operator_confirmed'] != '1.26.0': raise ValueError('Unsupported UI version.')
        state['status'] = 'collecting'; save(directory/'run.json', state)
        previous = None; collection_deadline = time.monotonic()+max_wall
        for index in range(samples):
            if stop(): raise KeyboardInterrupt('Cancellation requested')
            if time.monotonic() >= collection_deadline:
                state['collection_censored'] = 'wall_time_budget'; break
            started = time.monotonic(); frame = {'index': index, 'started_at': now()}
            image = directory/f'frame-{index:03}.png'; sheet = directory/f'frame-{index:03}.sheet.png'
            try:
                frame['capture'] = bridge.call('capture', target=ca_target(state), output_path=bridge.windows_path(image))
                if stop(): raise KeyboardInterrupt('Cancellation requested')
                layout = prepare(image, sheet)
                if stop(): raise KeyboardInterrupt('Cancellation requested')
                raw = recognize_image(sheet); readings = parse_fields(raw, layout)
                frame.update(assess(readings, layout, binding, previous))
                frame.update(source_sha256=digest(image), values=readings['values'], clock_resolution_seconds=1)
                save(directory/f'frame-{index:03}.ocr.json', {'raw_ocr': raw, 'readings': readings, 'layout': layout})
                if frame['reviewable_candidate']: previous = readings['values']['clock']
            except Exception as exc:
                frame.update(reviewable_candidate=False, rejection_reasons=['capture_or_ocr_error'], error=str(exc), validated_for_application=False)
            frame['processing_wall_seconds'] = round(time.monotonic()-started, 3)
            state['frames'].append(frame); save(directory/'run.json', state)
            print(f'Frame {index+1}/{samples}: {"candidate" if frame["reviewable_candidate"] else "rejected"}; cleanup will run when finished.', flush=True)
            while index+1 < samples and time.monotonic()-started < interval:
                if stop(): raise KeyboardInterrupt('Cancellation requested')
                time.sleep(0.1)
        if signature(Path(replay)) != before:
            state['source_association_invalidated'] = True
            for frame in state['frames']:
                frame.update(reviewable_candidate=False, rejection_reasons=frame.get('rejection_reasons', [])+['source_replay_changed'])
            raise ValueError('Source replay changed during collection; no source association is qualified.')
        state['status'] = 'completed' if any(f['reviewable_candidate'] for f in state['frames']) else 'no_reviewable_candidates'
    except BaseException as exc:
        failure = exc; state.update(status='cancelled' if isinstance(exc, KeyboardInterrupt) else 'failed', error=str(exc))
    finally:
        state['finished_at'] = now()
        # Do not propagate a cancellation flag through cleanup; persist exact roots.
        complete = cleanup(directory, state, bridge, force=force)
        print(f'Cleanup {"verified complete" if complete else "INCOMPLETE: see run.json and use cleanup command"}: {directory}', flush=True)
    if failure: raise failure
    if not complete: raise RuntimeError('Cleanup unverified: remaining owned, unowned/ambiguous processes or a pending launch; inspect run.json.')
    return state


def main():
    cli = argparse.ArgumentParser(description=__doc__); subs = cli.add_subparsers(dest='command', required=True)
    run = subs.add_parser('collect'); run.add_argument('replay', type=Path); run.add_argument('--session', type=Path, required=True)
    run.add_argument('--left-player', type=int, required=True); run.add_argument('--right-player', type=int, required=True)
    run.add_argument('--launcher', choices=['steam'], required=True); run.add_argument('--game-exe', type=Path, required=True)
    run.add_argument('--allow-offline-app-launch', action='store_true'); run.add_argument('--samples', type=int, default=6)
    run.add_argument('--interval', type=float, default=2); run.add_argument('--setup-timeout', type=float, default=180)
    run.add_argument('--max-wall-seconds', type=float, default=120)
    run.add_argument('--force-owned-after-grace', action='store_true')
    check = subs.add_parser('confirm'); check.add_argument('--session', type=Path, required=True); check.add_argument('--expected-match-id', required=True)
    check.add_argument('--confirm-offline-replay-names-civs-roles-and-ui-1-26', action='store_true')
    close = subs.add_parser('cleanup'); close.add_argument('--session', type=Path, required=True); close.add_argument('--force-owned-after-grace', action='store_true')
    cancel_cli = subs.add_parser('cancel'); cancel_cli.add_argument('--session', type=Path, required=True)
    adopt_cli = subs.add_parser('adopt-steam-relaunch'); adopt_cli.add_argument('--session', type=Path, required=True)
    adopt_cli.add_argument('--pid', type=int, required=True); adopt_cli.add_argument('--confirm-new-offline-game-launched-by-this-session', action='store_true')
    args = cli.parse_args()
    cancelled = [False]
    def cancel(signum, frame):
        cancelled[0] = True
        print('Cancellation requested; finishing current bounded operation, then closing owned applications.', flush=True)
    signal.signal(signal.SIGINT, cancel); signal.signal(signal.SIGTERM, cancel)
    try:
        if args.command == 'collect':
            if not args.allow_offline_app_launch: raise ValueError('Explicit --allow-offline-app-launch consent is required.')
            if not 1 <= args.samples <= 100 or not math.isfinite(args.interval) or not 0 <= args.interval <= 30 or not math.isfinite(args.setup_timeout) or not 1 <= args.setup_timeout <= 600 or not math.isfinite(args.max_wall_seconds) or not 1 <= args.max_wall_seconds <= 600:
                raise ValueError('Use 1..100 frames, 0..30s interval and 1..600s setup timeout.')
            collect(args.replay, args.session, args.left_player, args.right_player, samples=args.samples, interval=args.interval,
                    launcher=args.launcher, game_exe=args.game_exe, setup_timeout=args.setup_timeout,
                    max_wall=args.max_wall_seconds, force=args.force_owned_after_grace, stop=lambda: cancelled[0])
        elif args.command == 'confirm':
            confirm(args.session, args.expected_match_id, args.confirm_offline_replay_names_civs_roles_and_ui_1_26)
        elif args.command == 'adopt-steam-relaunch':
            adopt_steam_relaunch(args.session, args.pid, args.confirm_new_offline_game_launched_by_this_session)
        elif args.command == 'cancel':
            state = load(args.session/'run.json')
            if state['status'] not in ('starting', 'awaiting_ui_confirmation', 'collecting'):
                raise ValueError('Session is not active; use cleanup for recovery if needed.')
            (args.session/'cancel.request').touch(exist_ok=True)
            print('Cancellation requested. Wait for cleanup confirmation in run.json.')
        else:
            state = load(args.session/'run.json')
            if state['status'] in ('starting', 'awaiting_ui_confirmation', 'collecting') and controller_alive(state):
                raise ValueError('Use cancel for an active collector; do not race cleanup against collection.')
            if state['status'] in ('starting', 'awaiting_ui_confirmation', 'collecting'):
                state.update(status='interrupted_controller_recovery', recovered_at=now())
            if not cleanup(args.session, state, WindowsBridge(), force=args.force_owned_after_grace): raise RuntimeError('Cleanup incomplete; owned fingerprints retained for recovery.')
    except KeyboardInterrupt: cli.exit(130, 'Cancelled; owned-application cleanup attempted and recorded.\n')
    except Exception as exc: cli.exit(2, f'{type(exc).__name__}: {exc}\n')


if __name__ == '__main__': main()
