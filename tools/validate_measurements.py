#!/usr/bin/env python3
"""Offline Milestone 4 reference agreement; no OCR, launches, imports or qualification."""
import argparse
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from measurement_audit import load_json,write_json
from measurement_validation import assess


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pack',type=Path,required=True)
    parser.add_argument('--dataset-spec',type=Path,required=True)
    parser.add_argument('--labels',type=Path,action='append',required=True,help='Repeat for 1..4 distinct reviewer label sets.')
    parser.add_argument('--predictions',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True,help='New private JSON file; never overwritten.')
    args=parser.parse_args(argv)
    try:
        if args.output.resolve().is_relative_to((ROOT/'viewer/public').resolve()):
            raise ValueError('Private measurement dossiers cannot be written under viewer/public.')
        if not 1<=len(args.labels)<=4:raise ValueError('Use 1..4 reference label files.')
        result=assess(args.pack,load_json(args.dataset_spec),[load_json(p) for p in args.labels],load_json(args.predictions))
        write_json(args.output,result)
        print('Private dossier:',args.output)
        print('Agreement:',result['agreement_counts'])
        print('Timed non-clock readings:',result['non_clock_timeline_pair_match_count'],'of',result['non_clock_sample_count'])
        print('Clock frames:',result['clock_frame_counts'],'of',result['frame_count'])
        print('Blockers:',', '.join(result['blockers']))
        print('Not qualified for application use. Reviewer agreement is not verified engine state.')
    except (OSError,ValueError,KeyError,TypeError,AttributeError) as exc:
        parser.exit(2,f'Measurement validation refused: {exc}\n')
    return 0

if __name__=='__main__':raise SystemExit(main())
