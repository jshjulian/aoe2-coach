"""Offline experiment boundary, NOT an AI integration or transport.

Checking a citation cannot prove free-form prose. The only prototype accepted here
selects existing deterministic alternatives; it cannot add facts or wording.
No provider, network, subprocess, replay export, local-model download or UI toggle.
"""

def validate_proposal(packet,proposal):
    if not isinstance(proposal,dict) or set(proposal)!={'situation_id','alternative','evidence_event_ids'}:
        raise ValueError('Only existing source/alternative/evidence selections are supported; no free-form claims.')
    if packet.get('status')!='available' or packet.get('causal_claim') is not False or packet.get('validated_state_measurements')!=[]:
        raise ValueError('Qualified deterministic source packet required.')
    c=next((x for x in packet['situations'] if x['id']==proposal['situation_id']),None)
    if not c:raise ValueError('Unknown situation.')
    choice=proposal['alternative']
    if not isinstance(choice,str) or choice not in ('unit','position') or choice=='unit' and c['comparison']['alternative'] is None:
        raise ValueError('Unknown/unavailable conditional alternative.')
    ids=proposal['evidence_event_ids']
    required=set(c['transition']['event_ids'])|{c['threat']['focus_event_id']}
    if not isinstance(ids,list) or not 1<=len(ids)<=48 or any(not isinstance(x,str) for x in ids) or len(set(ids))!=len(ids) or not required<=set(ids)<=set(c['event_ids']):
        raise ValueError('Missing, duplicated or unbound evidence.')
    return dict(situation_id=c['id'],alternative=choice,evidence_event_ids=ids,mode='selection_only_not_new_reasoning',causal_claim=False)
