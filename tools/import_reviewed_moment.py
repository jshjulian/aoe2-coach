#!/usr/bin/env python3
"""Explicit local authored-moment import. No apps, networking or annotation writes."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from observations import ObservationStore
from reviewed_moments import ReviewedMomentStore,MAX_JSON


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('input',type=Path);p.add_argument('--report',type=Path,required=True)
    p.add_argument('--confirm-local-reviewed-moment',action='store_true');args=p.parse_args()
    if not args.confirm_local_reviewed_moment:p.error('Explicit --confirm-local-reviewed-moment required.')
    if args.input.stat().st_size>MAX_JSON:p.error('Review input exceeds 32KB.')
    report=json.loads(args.report.read_text());value=json.loads(args.input.read_text())
    identity=ReviewedMomentStore(ROOT/'data/reviewed-moments').import_moment(value,report,ObservationStore(ROOT/'data/observations'))
    print('Imported authored review:',identity,'; NOT independently validated or automatic advice.')
if __name__=='__main__':main()
