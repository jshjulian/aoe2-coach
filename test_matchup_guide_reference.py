"""Offline reference checks; missing optional local public snapshot never downloads."""
import hashlib
import json
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parent
REV='3bb43b1439eef88dfe7fe892d7f7dc41ac9dd76f'


class GuideReferenceTests(unittest.TestCase):
    def lock(self):return json.loads((ROOT/'knowledge/situational-catalog.lock.json').read_text())
    def snapshot(self):
        p=ROOT/'data/research/aoe2techtree'/REV
        if not (p/'trees/SICILIANS.json').is_file():self.skipTest('Optional pinned public reference snapshot not restored; no download attempted.')
        return p
    def test_source_paths_already_locked_no_lock_expansion(self):
        entries={e['path'] for e in self.lock()['files']}
        for name in ['FRANKS','SICILIANS','BRITONS','BOHEMIANS','BERBERS']:self.assertIn(f'trees/{name}.json',entries)
        self.assertIn('strings.en.json',entries)
    def test_reference_constants_are_the_existing_revision(self):
        text=(ROOT/'viewer/src/lib/matchupGuideData.ts').read_text()
        self.assertIn(f"REFERENCE_COMMIT='{REV}'",text);self.assertIn('REFERENCE_BUILD=185872',text)
    def test_selected_reference_bytes_match_existing_lock(self):
        p=self.snapshot();paths={'strings.en.json',*[f'trees/{n}.json' for n in ['FRANKS','SICILIANS','BRITONS','BOHEMIANS','BERBERS']]}
        for e in self.lock()['files']:
            if e['path'] in paths:self.assertEqual(hashlib.sha256((p/e['path']).read_bytes()).hexdigest(),e['sha256'])
    def test_serjeant_variants_and_donjon_are_distinct_namespaced_nodes(self):
        t=json.loads((self.snapshot()/'trees/SICILIANS.json').read_text());nodes={n['id']:n for n in t['buildings']+t['units_techs']}
        for id,producer,age,name in [(1658,82,3,'Serjeant'),(1659,82,4,'Elite Serjeant'),(1660,1665,2,'Serjeant'),(1661,1665,4,'Elite Serjeant')]:
            n=nodes[f'Unit_{id}_{producer}'];self.assertEqual(n['name'],name);self.assertEqual(n['age_id'],age)
        self.assertEqual(nodes['Building_1665_1665']['name'],'Donjon')
        self.assertEqual(nodes['Tech_756_82']['name'],'First Crusade');self.assertEqual(nodes['Tech_757_82']['name'],'Hauberk')
    def test_frank_options_have_reference_nodes_not_live_feasibility(self):
        t=json.loads((self.snapshot()/'trees/FRANKS.json').read_text());nodes={n['id']:n for n in t['units_techs']}
        for id,name,age in [('Unit_38_101','Knight',3),('Unit_279_49','Scorpion',3),('Unit_125_104','Monk',3),('Unit_5_87','Hand Cannoneer',4),('Tech_47_209','Chemistry',4)]:
            self.assertEqual(nodes[id]['name'],name);self.assertEqual(nodes[id]['age_id'],age)
        self.assertEqual(nodes['Unit_5_87']['node_status'],'ResearchRequired')
    def test_capability_prose_has_pinned_description_support(self):
        s=json.loads((self.snapshot()/'strings.en.json').read_text())
        self.assertIn('construct Donjons',s['26538']);self.assertIn('train your Unique Unit',s['26544'])
        for phrase in ['bonus damage','First Crusade','Hauberk','resistant to conversion']:self.assertIn(phrase,s['120186'])

if __name__=='__main__':unittest.main()
