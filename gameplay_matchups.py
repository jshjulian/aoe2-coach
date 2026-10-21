"""Cross-civ options, not civ-to-army inference or vision reconstruction."""
from gameplay_knowledge import reference
from situation_coaching import queue
from situations import _opposing

# Generic strategic options. Availability comes only from the hash-pinned catalog.
OPTIONS={
 'cavalry':([93,358,359],'If cavalry was actually scouted, consider available spear-line support, protecting it and avoiding unfavorable concentrations. Local numbers, upgrades and mobility still decide whether to fight.'),
 'archer':([7],'If an archer force was actually scouted, consider an available anti-archer option with suitable upgrades and protection, or change position. Do not treat it as an answer to every ranged composition.'),
 'spear':([4],'If a spear concentration was actually scouted, consider available ranged support, separating the armies or using mobility elsewhere rather than forcing cavalry into it.'),
}


def build_matchups(report,player,pack,own_reference):
    out=dict(evidence_class='conditional_advice',effective_state_established=False,opponents=[],
             limitation='Civilization is not composition. Opponent inputs are retrospective, not proof of player vision. Catalog options require patch/mode, age, buildings, resources, completed upgrades and local support checks; availability is not readiness.')
    for enemy in report['players']:
        if _opposing(player,enemy) is not True:continue
        ref=reference(report,enemy,pack)
        inputs=sorted([e for e in report['events'] if e.get('player_id')==enemy['id'] and queue(e)],key=lambda e:(e['time_seconds'],e['id']))
        context=[];families=[]
        for e in inputs:
            family=next((f['id'] for f in pack['families'] if e.get('unit') in f['units'] and f['id'] in OPTIONS),None)
            if family and family not in families:
                families.append(family);context.append(dict(evidence_class='recorded_command',event_id=e['id'],time_seconds=e['time_seconds'],unit=e['unit'],information='retrospective_opponent_input_not_player_vision'))
        options=[]
        for family in families:
            entity_ids,advice=OPTIONS[family]
            available=[dict(kind=e['kind'],entity_id=e['entity_id'],name=e['name']) for e in own_reference.get('entities',[]) if e['kind']=='Unit' and e['entity_id'] in entity_ids and e['catalog_available']]
            options.append(dict(evidence_class='conditional_advice',family=family,advice=advice,catalog_options=available,
                                qualification='Pinned catalog only; no claim this option was fieldable or the best choice in this match.'))
        out['opponents'].append(dict(player_id=enemy['id'],civilization=enemy.get('civilization'),reference=ref,
            retrospective_inputs=context,options=options,question='Which of these threats did you actually see before the commitment, and what fieldable support or alternative objective did that information justify?'))
    if not out['opponents']:out['reason']='Opposing team identity is unresolved or no opponent is known; no matchup is inferred.'
    return out
