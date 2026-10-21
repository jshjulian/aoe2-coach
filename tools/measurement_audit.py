#!/usr/bin/env python3
"""Private offline audit packs and scoring. Never launches games or imports state."""
import argparse
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from measurement_audit import dataset_spec,prepare_pack,score_pack,load_json,write_json


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='operation',required=True)
    spec=sub.add_parser('spec');spec.add_argument('--development-match-id',action='append',required=True)
    spec.add_argument('--held-out-match-id',action='append',default=[]);spec.add_argument('--output',type=Path,required=True)
    pack=sub.add_parser('prepare');pack.add_argument('--session',type=Path,required=True);pack.add_argument('--report',type=Path,required=True)
    pack.add_argument('--dataset-spec',type=Path,required=True);pack.add_argument('--frames',nargs='+',type=int,required=True)
    pack.add_argument('--fields',nargs='+',required=True);pack.add_argument('--output',type=Path,required=True)
    pack.add_argument('--window',nargs=2,type=int,metavar=('START_SECONDS','END_SECONDS'))
    score=sub.add_parser('score');score.add_argument('--pack',type=Path,required=True);score.add_argument('--labels',type=Path,required=True)
    score.add_argument('--predictions',type=Path,required=True);score.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    try:
        if a.operation=='spec':
            write_json(a.output,dataset_spec(a.development_match_id,a.held_out_match_id));print('Pinned experiment specification written. No qualification granted.')
        elif a.operation=='prepare':
            task=prepare_pack(a.session,load_json(a.report,64*1024*1024),load_json(a.dataset_spec),a.frames,a.fields,a.output,a.window)
            print('Private audit page:',a.output/'index.html');print('Task:',task['task_id'],'partition:',task['partition'],'samples:',len(task['samples']))
        else:
            result=score_pack(a.pack,load_json(a.labels),load_json(a.predictions))
            write_json(a.output,result)
            print('Counts:',result['counts']);print('Code provenance:',result['source_code_provenance'])
            print('Diagnostic only: no independently verified state, automatic qualification or coaching promotion.')
    except (OSError,ValueError,KeyError,TypeError,AttributeError) as exc:p.exit(2,f'Audit refused: {exc}\n')
if __name__=='__main__':main()
