#!/usr/bin/env python3
"""Research-only OCR of explicit saved, visible HUD images. Never an application provider.

No capture, launch, network, interpolation, abbreviated-number expansion or digit correction.
Assistant visual checks are not independent human/engine validation.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.read_state_ocr import recognize_image

LAYOUT='observed_CA_1.26_3440x1440_signals_v3'
METRICS={'resource_wood','resource_food','resource_gold','resource_stone',
         'workers_on_wood','workers_on_food','workers_on_gold','workers_on_stone',
         'population_used','population_limit','military_count','economic_unit_count','idle_workers',
         'tc_idle_seconds','housed_seconds','army_value','relic_gold_collected','relic_count',
         'unit_kills','unit_deaths','eco_kills','eco_deaths'}

def _write_private(path,data):
    with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as f:
        json.dump(data,f,indent=2)

def duration(text):
    if not isinstance(text,str) or not re.fullmatch(r'[0-9]{1,3}:[0-5][0-9](?::[0-5][0-9])?',text):return None
    parts=list(map(int,text.split(':')))
    return parts[0]*60+parts[1] if len(parts)==2 else parts[0]*3600+parts[1]*60+parts[2]

def parse_signals(raw,layout):
    if not isinstance(raw,dict) or not isinstance(layout,dict) or type(layout.get('schema_version')) is not int or layout['schema_version']!=1 or layout.get('layout')!=LAYOUT or raw.get('width')!=1500 or raw.get('height')!=2760:
        raise ValueError('Unsupported fixed research layout')
    fields=layout.get('fields');expected={'clock'}|{f'{s}_{m}' for s in ('left','right') for m in METRICS}
    if not isinstance(fields,list) or len(fields)!=45 or any(not isinstance(f,dict) for f in fields) or {f.get('name') for f in fields}!=expected:raise ValueError('Expected 45 distinct visible fields')
    words=raw.get('words')
    if not isinstance(words,list):raise ValueError('Missing OCR word list')
    def box_ok(b):return isinstance(b,dict) and all(type(b.get(k)) in (int,float) and math.isfinite(b[k]) and b[k]>=0 for k in ('x','y','width','height')) and b['x']+b['width']<=1500 and b['y']+b['height']<=2760 and b['width']>0 and b['height']>0
    if any(not box_ok(w) or not isinstance(w.get('text'),str) for w in words):raise ValueError('Invalid OCR word bounds/text')
    values={};texts={}
    for i,f in enumerate(fields):
        b=f.get('ocr_rect');s=f.get('source_rect')
        if not box_ok(b) or not isinstance(s,dict) or any(type(s.get(k)) is not int for k in ('x','y','width','height')) or not (0<=s['x']<s['x']+s['width']<=3440 and 0<=s['y']<s['y']+s['height']<=1440) or b!={'x':(i//23)*750+360,'y':(i%23)*120+8,'width':s['width']*3,'height':s['height']*3}:raise ValueError('Invalid fixed grid/source bounds')
        name=f['name'];kind='duration' if name=='clock' or name.endswith(('_tc_idle_seconds','_housed_seconds')) else 'integer'
        if f.get('kind')!=kind:raise ValueError('Wrong numeric/duration type')
        hits=[w['text'] for w in words if b['x']<=w['x'] and w['x']+w['width']<=b['x']+b['width'] and b['y']<=w['y'] and w['y']+w['height']<=b['y']+b['height']]
        text=hits[0] if len(hits)==1 else None
        values[name]=duration(text) if kind=='duration' else int(text) if text is not None and re.fullmatch(r'[0-9]{1,6}',text) else None
        texts[name]=hits
    return {'values':values,'raw_field_words':texts,'validated_for_application':False,
            'qualification':'research_only_visible_signals_not_verified_game_state',
            'limitations':['Fixed HUD/layout only; values and metric definitions are not independently validated.',
                           'No military idle/utilization measurement. Commands do not establish activity or combat.',
                           'Abbreviated values, O-for-zero and ambiguous/missing values remain null.',
                           'TC idle sums across TCs; late idle is not necessarily a mistake.',
                           'Kills/deaths count is not resource-adjusted combat efficiency or a cause of loss.']}

def main():
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('images',type=Path,nargs='+');cli.add_argument('--output',type=Path,required=True);args=cli.parse_args()
    if args.output.exists():raise ValueError('Output exists; refusing overwrite')
    from tools.audit_provenance import fingerprint
    source_fingerprint=fingerprint();result=[];runtimes=[]
    for image in args.images:
        sheet=image.with_name(image.stem+'.signals-v3.png')
        subprocess.run(['node',str(Path(__file__).with_name('prepare_captureage_signals.mjs')),str(image),str(sheet)],check=True,stdout=subprocess.DEVNULL)
        layout=json.loads(Path(str(sheet)+'.layout.json').read_text());raw=recognize_image(sheet)
        if hashlib.sha256(sheet.read_bytes()).hexdigest()!=layout['ocr_image_sha256'] or hashlib.sha256(image.read_bytes()).hexdigest()!=layout['source_sha256']:raise ValueError('Evidence changed')
        runtimes.append({'preprocessing':layout.get('runtime',{}),'ocr_provider':raw.get('provider'),'ocr_language':raw.get('language')})
        entry={'image':image.name,'source_sha256':layout['source_sha256'],**parse_signals(raw,layout)}
        _write_private(sheet.with_suffix('.raw.json'),raw);result.append(entry)
        print(image.name,entry['values']['clock'],sum(v is not None for v in entry['values'].values()),'/45',flush=True)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    if fingerprint()!=source_fingerprint:raise ValueError('Extractor source changed during recognition; refusing mixed-version result.')
    _write_private(args.output,{'extractor_version':'research-visible-signals-v3','source_code_sha256':source_fingerprint,'runtime_observations':runtimes,'validated_for_application':False,'frames':result})
if __name__=='__main__':main()
