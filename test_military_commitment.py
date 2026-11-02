import copy
import json
from pathlib import Path
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
import military_commitment as model
from coaching_store import CoachingStore


def event(id,t,**fields):
    return dict(id=id,time_seconds=t,player_id=1,player='Player A',kind='queue_command',status='command',action='DE_QUEUE',unit='Archer',unit_type_id=4,amount=1,**fields) if not fields else {**event(id,t),**fields}

def report():
    return dict(schema_version=5,match_id='a'*64,duration_seconds=600,
        players=[dict(id=1,name='Player A',civilization='Franks',team_id=[1],won=False),dict(id=2,name='Player B',civilization='Armenians',team_id=[2],won=True)],
        replay_provenance=dict(provenance_version=2,edition='DE',dataset_id=100,game_type_id=0,all_technologies=False,cheats=False,build_version=188329),
        events=[event('range',30,action='BUILD',kind='building_placement_command',unit=None,unit_type_id=None,building='Archery Range',building_type_id=87),
            event('archer1',90),event('archer2',92),
            event('camp',150,action='BUILD',kind='building_placement_command',unit=None,unit_type_id=None,building='Mining Camp',building_type_id=584),
            event('stable',165,action='BUILD',kind='building_placement_command',unit=None,unit_type_id=None,building='Stable',building_type_id=101),
            event('scout',210,unit='Scout Cavalry',unit_type_id=448),
            event('enemy',130,player_id=2,player='Player B',action='RESEARCH',kind='research_command',unit=None,unit_type_id=None,technology='Long Swordsman',technology_id=207)])


def payload(packet,**fields):
    return dict(operation='commitment_answer',situation_id=packet['windows'][0]['id'],question_id='military-commitment-v1',
        constraint='resource_setup',intent='clear_pressure',note='Player account only',expected_revision=0,confirm_identity=True,**fields)


class CommitmentTests(unittest.TestCase):
    def build(self,r=None,store=None):return model.build(r or report(),'Player A',store)
    def test_new_line_with_resource_context_and_exact_anchor(self):
        p=self.build();self.assertEqual(p['status'],'available');self.assertEqual(len(p['windows']),1)
        c=p['windows'][0];self.assertEqual(c['kind'],'new_line');self.assertEqual(c['replay_anchor']['event_id'],'stable')
        self.assertTrue({'camp','archer1','archer2','scout','enemy'}<=set(c['event_ids']))
        self.assertEqual(c['counts']['prior_line_queue_inputs'],2)
        self.assertTrue(all(v is None for v in c['information'].values()))
        self.assertFalse(p['eligible_for_automatic_priority']);self.assertFalse(p['eligible_for_progress'])
        r=report();r['events'] += [event('enemy-archer',120,player_id=2,player='Player B'),event('enemy-scout',220,player_id=2,player='Player B',unit='Scout Cavalry',unit_type_id=448)]
        counts=self.build(r)['windows'][0]['counts']
        self.assertEqual(counts['prior_line_queue_inputs'],2);self.assertEqual(counts['next_line_queue_inputs'],1)
    def test_initial_infantry_investment_can_review_push_job(self):
        r=report();r['events']=[event('militia',100,unit='Militia',unit_type_id=74)]
        c=self.build(r)['windows'][0];self.assertEqual(c['kind'],'opening')
        self.assertIn('reinforce_push',model.INTENTS)
        self.assertEqual({o['id'] for o in c['options']},{'keep','support','switch','disengage'})
    def test_no_invented_opening_at_replay_end(self):
        r=report();r['events']=[event('last',590)];self.assertEqual(self.build(r)['windows'],[])
    def test_simultaneous_inputs_do_not_establish_switch(self):
        r=report();r['events']=[event('a',100),event('b',100,unit='Scout Cavalry',unit_type_id=448)]
        self.assertFalse(any(c['kind']=='new_line' for c in self.build(r)['windows']))
    def test_unknown_military_breaks_adjacency(self):
        r=report();r['events'].append(event('unknown',180,unit='Unreviewed unit',unit_type_id=9000))
        p=self.build(r);self.assertFalse(any(c['kind']=='new_line' for c in p['windows']))
        self.assertEqual(p['coverage']['unknown_military_inputs'],1)
    def test_civilian_inputs_do_not_break_adjacency(self):
        r=report();r['events'].append(event('villager',180,unit='Villager',unit_type_id=83))
        self.assertEqual(self.build(r)['windows'][0]['kind'],'new_line')
    def test_wrong_id_civilian_label_is_not_a_repair(self):
        r=report();r['events'].append(event('villager',180,unit='Villager',unit_type_id=4))
        self.assertFalse(any(c['kind']=='new_line' for c in self.build(r)['windows']))
    def test_missing_amount_is_not_one_unit(self):
        r=report();r['events'][1]['amount']=None;c=self.build(r)['windows'][0]
        self.assertEqual(c['counts']['missing_queue_quantities'],1)
        self.assertNotIn('units_produced',c)
    def test_negative_and_zero_quantity_are_not_positive_investment(self):
        for amount in [-1,0,True,1.5]:
            r=report();r['events'][1]['amount']=amount;r['events'][2]['amount']=amount
            self.assertFalse(any(c['kind']=='new_line' for c in self.build(r)['windows']))
    def test_large_gap_does_not_infer_transition(self):
        r=report();r['duration_seconds']=1200;r['events'][5]['time_seconds']=1000
        self.assertFalse(any(c['kind']=='new_line' for c in self.build(r)['windows']))
    def test_existing_line_reuse_is_not_a_new_commitment(self):
        r=report();r['events'].append(event('oldscout',5,unit='Scout Cavalry',unit_type_id=448))
        changes=[c for c in self.build(r)['windows'] if c['kind']=='new_line']
        self.assertTrue(all(c['next_unit']!='Scout Cavalry' for c in changes))
    def test_movement_never_supplies_push_or_threat_evidence(self):
        r=report();r['events'].append(event('move',170,action='MOVE',kind='order_command'))
        p=self.build(r);self.assertTrue(all('move' not in c['event_ids'] for c in p['windows']))
    def test_outcomes_ratings_habits_and_order_do_not_rank(self):
        r=report();p=self.build(r)
        r['players'][0].update(won=True,elo_snapshot=9999);r['players'][1]['won']=False;r['events'].reverse()
        self.assertEqual(p,self.build(r))
    def test_source_mutation_changes_window_identity(self):
        r=report();a=self.build(r)['windows'][0]['id'];r['events'][1]['amount']=5
        self.assertNotEqual(a,self.build(r)['windows'][0]['id'])
    def test_malformed_source_abstains(self):
        for change in ['duplicate','time','actor','label','schema','content','mode','team','alias']:
            r=report()
            if change=='duplicate':r['events'].append(copy.deepcopy(r['events'][0]))
            if change=='time':r['events'][0]['time_seconds']=float('nan')
            if change=='actor':r['events'][0]['player']='Wrong'
            if change=='label':r['events'][0]['unit']={}
            if change=='schema':r['schema_version']=4
            if change=='content':r['match_id']='invalid'
            if change=='mode':r['replay_provenance']['game_type_id']=True
            if change=='team':r['players'][1]['team_id']=[1]
            if change=='alias':r['players'][1]['name']='Player A'
            self.assertEqual(self.build(r)['status'],'unavailable',change)
    def test_unfinished_or_unknown_outcome_is_not_live_assistance(self):
        for value in [None,True]:
            r=report();r['players'][0]['won']=value
            self.assertEqual(self.build(r)['status'],'unavailable')
    def test_wrong_numeric_unit_identity_withholds_classification(self):
        r=report();r['events']=[event('fake',100,unit_type_id=38)];self.assertEqual(self.build(r)['windows'],[])
    def test_known_custom_rules_abstain_without_override(self):
        r=report();r['replay_provenance']['reported_mod']={'id':100};self.assertEqual(self.build(r)['status'],'unavailable')
    def test_bounded_sources_windows_and_counterfactuals(self):
        r=report();r['events']+=[event(f'extra{i}',220+i/100) for i in range(1000)]
        p=self.build(r);self.assertLessEqual(len(p['windows']),4)
        for c in p['windows']:
            self.assertLessEqual(len(c['event_ids']),48)
            self.assertEqual(len(c['event_ids']),len(c['evidence']))
            self.assertFalse(p['causal_claim'])
    def test_source_is_not_mutated(self):
        r=report();before=copy.deepcopy(r);self.build(r);self.assertEqual(r,before)


class ClarificationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.store=CoachingStore(Path(self.tmp.name)/'journal.sqlite')
    def packet(self):return model.build(report(),'Player A',self.store)
    def test_reads_never_seed_records_or_habits(self):
        self.packet();self.packet()
        with self.store._connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM records').fetchone()[0],0)
    def test_explicit_save_is_bound_and_revisioned(self):
        p=self.packet();model.save_answer(self.store,p,payload(p));p2=self.packet();c=p2['windows'][0]
        self.assertEqual(c['reviewed_context']['revision'],1);self.assertIn('resource setup',c['assessment'])
        fields=payload(p2);fields.update(expected_revision=1,constraint='deliberate_mix')
        model.save_answer(self.store,p2,fields)
        with self.store._connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM revisions').fetchone()[0],2)
            self.assertEqual(db.execute('SELECT kind FROM records').fetchone()[0],'military_commitment_context')
    def test_stale_write_and_missing_confirmation_refused(self):
        p=self.packet();fields=payload(p);fields['confirm_identity']=False
        with self.assertRaises(ValueError):model.save_answer(self.store,p,fields)
        model.save_answer(self.store,p,payload(p))
        with self.assertRaises(ValueError):model.save_answer(self.store,p,payload(p))
    def test_invalid_choices_note_or_revision_refused(self):
        p=self.packet()
        for key,value in [('constraint','invented'),('intent','invented'),('note','x'*1001),('note','\x00'),('expected_revision',True),('question_id','different'),('situation_id','different')]:
            fields=payload(p);fields[key]=value
            with self.assertRaises(ValueError):model.save_answer(self.store,p,fields)
    def test_corruption_is_not_reset_or_overwritten(self):
        p=self.packet();c=p['windows'][0]
        with self.store._connect() as db:self.store._put(db,'military_commitment_context',model._key(p,c),{'bad':'record'})
        p2=self.packet();self.assertEqual(p2['windows'][0]['reviewed_context']['status'],'unavailable')
        with self.assertRaises(ValueError):model.save_answer(self.store,p2,payload(p2))
        with self.store._connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM revisions').fetchone()[0],1)
    def test_concurrent_saves_only_one_wins(self):
        p=self.packet()
        def save(_):
            try:model.save_answer(self.store,p,payload(p));return True
            except ValueError:return False
        with ThreadPoolExecutor(max_workers=2) as pool:self.assertEqual(sum(pool.map(save,range(2))),1)
    def test_correction_withholds_comparison(self):
        p=self.packet();fields=payload(p);fields['constraint']='not_applicable';model.save_answer(self.store,p,fields)
        self.assertIn('withheld',self.packet()['windows'][0]['assessment'])

if __name__=='__main__':unittest.main()
