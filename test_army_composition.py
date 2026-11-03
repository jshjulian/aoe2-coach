import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import army_composition as model
import unit_knowledge as knowledge


def event(id,t,unit=1013,player=2,**extra):
    names={u['id']:u['name'] for u in knowledge.local_pack()[0]['units']}
    return dict(id=id,time_seconds=t,player_id=player,player='Player A' if player==1 else 'Player B',unit_type_id=unit,unit=names.get(unit,'Unreviewed'),amount=1,kind='queue_command',status='command',action='DE_QUEUE',category='military',**extra)


def report():
    return dict(schema_version=5,match_id='a'*64,duration_seconds=1200,players=[dict(id=1,name='Player A',civilization='Franks',team_id=[1],won=False),dict(id=2,name='Player B',civilization='Malians',team_id=[2],won=True)],replay_provenance=dict(provenance_version=2,edition='DE',dataset_id=100,game_type_id=0,cheats=False,all_technologies=False,build_version=188329),events=[event('own-scout',100,448,1),event('gbeto',200),event('spear',210,93),event('knight',250,38,1),event('own-archer',300,4,1),event('enemy-archer',410,4),event('own-skirm',480,7,1)])


def fake_reference():
    """Synthetic source graph for portable contract tests, not real unit measurements."""
    p=knowledge.local_pack()[0];nodes=[];raw={};available=[]
    for u in p['units']:
        allowed=u['id'] not in (1013,1015,492,1658,1659,1660,1661)
        if allowed:available.append(u['id'])
        nodes.append(dict(node_id=u['id'],name=u['name'],use_type='Unit',node_status='ResearchedCompleted' if allowed else 'NotAvailable',age_id=3,building_id=87))
        raw[str(u['id'])]=dict(Attacks=[] if u['delivery']=='conversion' else [dict(Class=u['damage_class'],Amount=10)],Armours=[dict(Class=1,Amount=0),dict(Class=4,Amount=0),dict(Class=3,Amount=0)],Range=5 if u['delivery'] in ('ranged','conversion') else 0,Speed=1.25,MinRange=0,MeleeArmor=0,PierceArmor=0,Attack=0 if u['delivery']=='conversion' else 10,ReloadTime=2,AttackDelaySeconds=1)
    lock=dict(repository='https://github.com/SiegeEngineers/aoe2techtree',commit=p['source_commit'],declared_update=p['declared_update'],files=[],civilization_trees={'Franks':'trees/FRANKS.json'})
    snapshot={'data.json':dict(data={'Unit':raw},civs={'Franks':{'Unit':available}}),'trees/FRANKS.json':{'units_techs':nodes}}
    return lock,snapshot


def packet(r=None):
    lock,snapshot=fake_reference()
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/'lock.json';path.write_text(json.dumps(lock))
        with patch.object(knowledge,'LOCK_PATH',path),patch.object(knowledge,'_catalog',return_value=snapshot):return model.build(r or report(),'Player A')


class CompositionTests(unittest.TestCase):
    def test_roles_and_mixed_screen_not_reconstructed_army(self):
        p=packet();self.assertEqual(p['status'],'available');self.assertEqual(len(p['windows']),2)
        c=p['windows'][0];self.assertIn('Spear-line',c['mixed_screen_prompt']);self.assertFalse(p['fielded_army_established'])
        self.assertEqual(c['transition']['first_different_role_request']['event_id'],'own-archer');self.assertEqual(c['transition']['first_different_role_request']['seconds_after_anchor'],100)
        self.assertEqual(c['transition']['judgment'],'unknown');self.assertEqual(c['transition']['feasibility'],'unknown');self.assertEqual(c['transition']['player_vision'],'unknown')
    def test_camel_support_is_not_mistaken_for_isolated_gbeto(self):
        r=report();r['events'].append(event('camel',220,329));c=packet(r)['windows'][0]
        self.assertIn('camel',[x['role'] for x in c['summaries'][1]['roles']]);self.assertIn('Spear-line',c['mixed_screen_prompt'])
        r['events']=[e for e in r['events'] if e['id']!='spear'];self.assertIn('Camel-line',packet(r)['windows'][0]['mixed_screen_prompt'])
    def test_conversion_support_is_not_invented_damage(self):
        r=report();r['events'].append(event('monk',260,125,1));p=packet(r)
        monk=next(u for u in p['reference']['profiles'] if u['unit_id']==125)
        self.assertEqual(monk['damage_type'],'none');self.assertIsNone(monk['primary_damage_class']);self.assertEqual(monk['attacks'],[])
    def test_mounted_crossbow_mangonel_and_monk_are_explicit_own_roles(self):
        r=report();r['events'] += [event('mounted',280,2700,1),event('mango',290,280,1),event('monk',295,125,1)]
        p=packet(r);self.assertEqual(p['coverage']['unknown_military_inputs'],0)
        own=p['windows'][0]['summaries'][0]['roles'];self.assertTrue({'mounted_ranged','siege','conversion'}<=set(x['role'] for x in own))
    def test_gbeto_reference_melee_at_range(self):
        p=packet();g=next(x for x in p['reference']['profiles'] if x['unit_id']==1013)
        self.assertEqual((g['damage_type'],g['delivery'],g['primary_damage_class']),('melee','ranged',4));self.assertEqual(g['base_speed'],1.25)
        self.assertEqual(g['base_melee_armor'],0);self.assertFalse(g['own_catalog_available']);self.assertEqual(p['reference']['status'],'patch_mismatch_or_unknown')
    def test_role_requests_not_quantity_or_multibuilding_units(self):
        r=report();r['events'][1]['amount']=20;r['events'][1]['object_ids']=[1,2,3]
        c=packet(r)['windows'][0];enemy=c['summaries'][1]['roles'];self.assertEqual(sum(x['queue_inputs'] for x in enemy),2)
    def test_missing_quantity_remains_missing(self):
        r=report();r['events'][1]['amount']=None;c=packet(r)['windows'][0]
        self.assertEqual(c['summaries'][1]['roles'][0]['missing_quantities'],1)
    def test_zero_negative_boolean_fractional_quantities_not_investments(self):
        for q in [0,-1,True,1.5,'1',32768]:
            r=report();r['events'][1]['amount']=q;p=packet(r)
            self.assertFalse(any('gbeto' in c['event_ids'] for c in p['windows']))
    def test_alias_or_numeric_namespace_never_repaired(self):
        for key,val in [('unit','Gbéto'),('unit_type_id','1013'),('unit_type_id',1014)]:
            r=report();r['events'][1][key]=val;p=packet(r);self.assertEqual(p['coverage']['unknown_military_inputs'],1)
    def test_cancellation_not_subtracted_or_classified(self):
        r=report();e=event('cancel',220);e['kind']='cancel_command';r['events'].append(e)
        self.assertFalse(any('cancel' in c['event_ids'] for c in packet(r)['windows']))
    def test_unknown_own_inputs_withhold_role_transition(self):
        r=report();r['events'].append(event('unknown-own',230,9999,1));c=packet(r)['windows'][0]
        self.assertEqual(c['transition']['status'],'unclassified_own_inputs');self.assertIsNone(c['transition']['first_different_role_request'])
    def test_unknown_enemy_inputs_withhold_role_addition_comparison(self):
        r=report();r['events'].append(event('unknown-enemy',390,9999));c=packet(r)['windows'][1]
        self.assertEqual(c['new_opponent_roles'],[])
    def test_no_prior_own_basis_is_not_late(self):
        r=report();r['events']=[e for e in r['events'] if e['id']!='own-scout'];c=packet(r)['windows'][0]
        self.assertEqual(c['transition']['status'],'no_prior_own_role_basis');self.assertIsNone(c['transition']['first_different_role_request'])
    def test_sustained_same_role_not_a_failure(self):
        r=report();r['events']=[e for e in r['events'] if e['id'] not in ('own-archer','own-skirm')];c=packet(r)['windows'][0]
        self.assertEqual(c['transition']['status'],'no_different_role_request_cited');self.assertEqual(c['transition']['judgment'],'unknown')
    def test_window_endpoint_policy_no_zero_length_window(self):
        r=report();r['duration_seconds']=360;r['events']=[event('a',180),event('b',360)];p=packet(r)
        self.assertEqual(len(p['windows']),1);self.assertEqual(p['windows'][0]['window_seconds'],[180,360]);self.assertTrue(p['windows'][0]['end_inclusive'])
    def test_new_role_in_half_open_next_window(self):
        r=report();r['events']=[event('a',179),event('b',180,93)];p=packet(r)
        self.assertEqual([c['window_seconds'][0] for c in p['windows']],[0,180]);self.assertEqual(p['windows'][1]['new_opponent_roles'],['spear'])
    def test_first_gbeto_window_retained_with_many_windows(self):
        r=report();r['duration_seconds']=4000;r['events']=[event(str(i),i*180+1,1013 if i==8 else 4) for i in range(20)]
        p=packet(r);self.assertEqual(len(p['windows']),4);self.assertTrue(p['coverage']['truncated']);self.assertTrue(any('8' in c['event_ids'] for c in p['windows']))
    def test_evidence_bounds_counts_only_cited_inputs(self):
        r=report();r['events']=[event(f'e{i}',200+i/100) for i in range(1000)]+[event(f'o{i}',200+i/100,4,1) for i in range(1000)]
        c=packet(r)['windows'][0];self.assertLessEqual(len(c['event_ids']),112)
        self.assertTrue(all(x['queue_inputs']<=48 for s in c['summaries'] for x in s['roles']))
    def test_no_commands_no_invented_army(self):
        r=report();r['events']=[];self.assertEqual(packet(r)['windows'],[])
    def test_rating_and_result_do_not_select_or_rank(self):
        a=packet();r=report();r['players'][0]['won']=True;r['players'][1]['won']=False;r['players'][0]['elo_snapshot']=9999
        self.assertEqual(a,packet(r));self.assertFalse(a['eligible_for_automatic_priority']);self.assertFalse(a['eligible_for_progress'])
    def test_inputs_immutable_and_no_journal_dependency(self):
        r=report();before=copy.deepcopy(r);packet(r);self.assertEqual(r,before)
    def test_duplicate_actor_and_clock_corruption_withholds_only_optional(self):
        for change in [lambda r:r['events'].append(r['events'][0]),lambda r:r['events'][0].update(player='Wrong'),lambda r:r['events'][0].update(time_seconds=float('nan')),lambda r:r['events'][0].update(player_id=3)]:
            r=report();change(r);self.assertEqual(packet(r)['status'],'unavailable')
    def test_scope_fail_closed(self):
        for key,val in [('schema_version',4),('match_id','wrong'),('duration_seconds',0),('duration_seconds',86401)]:
            r=report();r[key]=val;self.assertEqual(packet(r)['status'],'unavailable')
        self.assertEqual(model.build(None,'Player A')['status'],'unavailable')
    def test_unfinished_team_and_unknown_identity_withheld(self):
        for change in [lambda r:r['players'][0].update(won=None),lambda r:r['players'][1].update(team_id=[1,2]),lambda r:r['players'][1].update(name='Player A')]:
            r=report();change(r);self.assertEqual(packet(r)['status'],'unavailable')
    def test_known_custom_modes_and_cheats_withheld(self):
        for p in [dict(game_type_id=1),dict(all_technologies=True),dict(cheats=True),dict(reported_mod={'custom':True}),dict(rms_mod_id=22),dict(dataset_id=99),dict(metadata_cheats=True)]:
            r=report();r['replay_provenance'].update(p);self.assertEqual(packet(r)['status'],'unavailable')
    def test_event_budget(self):
        r=report();r['events']=[r['events'][0]]*300001;self.assertEqual(packet(r)['status'],'unavailable')
    def test_missing_snapshot_is_missing_not_zero(self):
        with patch.object(knowledge,'_catalog',side_effect=ValueError('hash mismatch')):
            p=model.build(report(),'Player A');self.assertEqual(p['status'],'available');self.assertEqual(p['reference']['status'],'unavailable');self.assertEqual(p['reference']['profiles'],[])


class KnowledgeTests(unittest.TestCase):
    def test_missing_or_ambiguous_pack_rejected(self):
        p=copy.deepcopy(knowledge.local_pack()[0]);p['units'].append(p['units'][0]);self.assertRaises(ValueError,knowledge.compile_pack,p)
        p=copy.deepcopy(knowledge.local_pack()[0]);p['units'][0]['damage_class']=True;self.assertRaises(ValueError,knowledge.compile_pack,p)
    def test_unknown_composition_unit_and_missing_requirements_rejected(self):
        for key,val in [('required_units',[99999]),('requires',[])]:
            p=copy.deepcopy(knowledge.local_pack()[0]);p['compositions'][0][key]=val;self.assertRaises(ValueError,knowledge.compile_pack,p)
    def test_bad_mechanics_source_withholds_entire_reference(self):
        lock,snapshot=fake_reference();snapshot['data.json']['data']['Unit']['1013']['Attacks']=[dict(Class=3,Amount=10)]
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'lock';p.write_text(json.dumps(lock))
            with patch.object(knowledge,'LOCK_PATH',p),patch.object(knowledge,'_catalog',return_value=snapshot):self.assertEqual(knowledge.reference(report(),report()['players'][0],knowledge.local_pack()[0])['status'],'unavailable')
    def test_missing_scalar_stays_null_and_zero_preserved(self):
        lock,snapshot=fake_reference();snapshot['data.json']['data']['Unit']['1013'].pop('Speed')
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'lock';p.write_text(json.dumps(lock))
            with patch.object(knowledge,'LOCK_PATH',p),patch.object(knowledge,'_catalog',return_value=snapshot):ref=knowledge.reference(report(),report()['players'][0],knowledge.local_pack()[0])
        g=ref['profiles'][0];self.assertIsNone(g['base_speed']);self.assertEqual(g['base_melee_armor'],0)
    def test_unknown_prerequisite_is_not_age_zero(self):
        lock,snapshot=fake_reference();knight=next(n for n in snapshot['trees/FRANKS.json']['units_techs'] if n['node_id']==38);knight['age_id']=None
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'lock';p.write_text(json.dumps(lock))
            with patch.object(knowledge,'LOCK_PATH',p),patch.object(knowledge,'_catalog',return_value=snapshot):
                self.assertEqual(knowledge.reference(report(),report()['players'][0],knowledge.local_pack()[0])['status'],'unavailable')
                knight['node_status']='NotAvailable';snapshot['data.json']['civs']['Franks']['Unit'].remove(38)
                ref=knowledge.reference(report(),report()['players'][0],knowledge.local_pack()[0]);self.assertNotEqual(ref['status'],'unavailable')
                self.assertTrue(all(o['minimum_reference_age'] is None and not o['own_catalog_available'] for o in ref['compositions'] if 38 in o['required_units']))
    def test_actual_pinned_gbeto_source_optional_offline(self):
        root=knowledge.ROOT/'data/research/aoe2techtree'/knowledge.local_pack()[0]['source_commit']
        if not (root/'data.json').is_file():self.skipTest('Optional public snapshot absent; no download.')
        ref=knowledge.reference(report(),report()['players'][0],knowledge.local_pack()[0]);self.assertNotEqual(ref['status'],'unavailable')
        g=next(p for p in ref['profiles'] if p['unit_id']==1013);self.assertEqual(g['base_speed'],1.25);self.assertEqual(g['base_range'],5);self.assertEqual(g['damage_type'],'melee');self.assertNotIn(15,[x['armor_class'] for x in g['armor_classes']])

if __name__=='__main__':unittest.main()
