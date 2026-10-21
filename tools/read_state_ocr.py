#!/usr/bin/env python3
"""Research-only local OCR of a prepared screenshot. Never imported by the app.

Requires tools/prepare_state_ocr.mjs output, existing Windows OCR and PowerShell.
Does not launch/capture/control applications, install models or use network services.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
LAYOUT = 'observed_CaptureAge_1.26_3440x1440_two_player_HUD'


def parse_fields(raw, layout):
    if not isinstance(raw, dict) or not isinstance(layout, dict) or layout.get('schema_version') != 1 or layout.get('layout') != LAYOUT or raw.get('width') != 760 or raw.get('height') != 1170:
        raise ValueError('Unsupported OCR sheet/layout; do not guess coordinates.')
    expected = {f'{side}_{resource}' for side in ('left', 'right') for resource in ('wood', 'food', 'gold', 'stone')} | {'clock'}
    fields = layout.get('fields')
    if not isinstance(fields, list) or len(fields) != 9 or any(not isinstance(f, dict) for f in fields) or {f.get('name') for f in fields} != expected:
        raise ValueError('Expected all nine unique HUD fields.')
    words = raw.get('words')
    if not isinstance(words, list):
        raise ValueError('Expected OCR word list.')
    values, statuses = {}, {}
    for field in fields:
        name, box = field['name'], field['ocr_rect']
        if not isinstance(box, dict):
            raise ValueError('Expected field rectangle.')
        if any(type(box.get(k)) not in (int, float) or not math.isfinite(box[k]) or box[k] < 0 for k in ('x', 'y', 'width', 'height')):
            raise ValueError('Malformed field bounds.')
        if box['x']+box['width'] > 760 or box['y']+box['height'] > 1170 or not box['width'] or not box['height']:
            raise ValueError('Field bounds outside OCR sheet.')
        hits = []
        for word in words:
            if not isinstance(word, dict) or not isinstance(word.get('text'), str):
                raise ValueError('Malformed OCR word.')
            if any(type(word.get(k)) not in (int, float) or not math.isfinite(word[k]) or word[k] < 0 for k in ('x', 'y', 'width', 'height')):
                raise ValueError('Malformed OCR bounds.')
            if (box['x'] <= word['x'] and word['x']+word['width'] <= box['x']+box['width'] and
                box['y'] <= word['y'] and word['y']+word['height'] <= box['y']+box['height']):
                hits.append(word['text'])
        text = hits[0] if len(hits) == 1 else None
        value = None
        if text is not None:
            if name == 'clock' and re.fullmatch(r'\d{1,3}:[0-5]\d', text, flags=re.ASCII):
                minutes, seconds = map(int, text.split(':')); value = minutes*60+seconds
            elif name != 'clock' and re.fullmatch(r'\d{1,4}', text, flags=re.ASCII):
                value = int(text)
        values[name] = value
        statuses[name] = 'syntactically_read_not_verified' if value is not None else 'unreadable_or_ambiguous'
    return {'values': values, 'field_status': statuses, 'all_fields_syntactically_read': bool(values) and all(v is not None for v in values.values()),
            'qualification': 'research_only_ocr_not_verified_game_state', 'validated_for_application': False,
            'limitations': ['Valid-looking digit errors are possible; manual/independent checks still required.',
                            'Fixed UI layout and visible fields only; no confidence score, interpolation or zero filling.',
                            'Left/right are UI roles, NOT parser player numbers. Match/player identity must be verified separately.',
                            'A whole-second clock is quantized, not an exact sync timestamp.']}


def recognize_image(sheet):
    """Run installed Windows OCR on one explicit local image; no application access."""
    sheet = Path(sheet).resolve()
    before = hashlib.sha256(sheet.read_bytes()).hexdigest()
    ps = shutil.which('powershell.exe') or '/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe'
    if not Path(ps).is_file(): raise ValueError('Existing Windows PowerShell is required; nothing will be installed.')
    winpath = subprocess.check_output(['wslpath', '-w', str(sheet)], text=True).strip()
    helper = ROOT/'tools/ocr_state_screenshot.ps1'
    command = "$InputImage='"+winpath.replace("'", "''")+"';\n"+helper.read_text()
    process = subprocess.run([ps, '-NoProfile', '-NonInteractive', '-Command', command], capture_output=True,
                             text=True, encoding='utf-8', errors='replace', timeout=45)
    if process.returncode: raise ValueError('Windows OCR failed: '+process.stderr.strip())
    raw = json.loads(process.stdout.lstrip('\ufeff'))
    if hashlib.sha256(sheet.read_bytes()).hexdigest() != before: raise ValueError('OCR input changed during recognition.')
    return raw


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('sheet', type=Path); cli.add_argument('--output', type=Path, required=True)
    args = cli.parse_args()
    try:
        if args.output.exists(): raise ValueError('Output already exists; refusing to overwrite observations.')
        sheet = args.sheet.resolve(); layout_path = Path(str(sheet)+'.layout.json')
        layout = json.loads(layout_path.read_text())
        before = hashlib.sha256(sheet.read_bytes()).hexdigest()
        if before != layout.get('ocr_image_sha256'): raise ValueError('OCR sheet does not match its source layout hash.')
        raw = recognize_image(sheet)
        if hashlib.sha256(sheet.read_bytes()).hexdigest() != before: raise ValueError('OCR input changed during recognition.')
        helper = ROOT/'tools/ocr_state_screenshot.ps1'
        result = parse_fields(raw, layout)
        result.update(layout=layout, raw_ocr=raw, helper_sha256=hashlib.sha256(helper.read_bytes()).hexdigest())
        args.output.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+'\n'
        with args.output.open('x') as stream: stream.write(text)
        print(f'Research-only OCR: {args.output}; all fields read: {result["all_fields_syntactically_read"]}; NOT coaching state.')
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError) as exc:
        cli.exit(2, f'{type(exc).__name__}: {exc}\n')


if __name__ == '__main__': main()
