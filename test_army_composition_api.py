from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
import app
from test_army_composition import report


class CompositionIntegrationTests(unittest.TestCase):
    def setup_handler(self):
        handler=object.__new__(app.Handler);handler.library=Mock();handler._path_from_query=Mock(return_value=Path('synthetic.aoe2record'))
        handler.coaching_store=Mock();handler.coaching_store.read.return_value={'plan':None,'rules_context':None}
        handler.observation_store=Mock();handler.observation_store.context.return_value={'observation':'unchanged'}
        handler.reviewed_moment_store=Mock();handler.reviewed_moment_store.read.return_value={'authored':'unchanged'}
        return handler
    def legacy_mocks(self,stack):
        review={'match_id':'a'*64,'player':{'id':1,'name':'Player A'}}
        for target,result in [('app.report_for',(report(),None,None)),('app.build_review',review),('app.build_situation_review',{'situation':'unchanged'}),('app.reference_options',{'knowledge':'unchanged'}),('app.gameplay.build',{'gameplay':'unchanged'}),('app.military_reasoning.build',{'reasoning':'unchanged'}),('app.practice.context',{'journal':'unchanged'}),('app.practice_progress.snapshot',{'snapshot':'unchanged'}),('app.practice_progress.context',{'progress':'unchanged'}),('app.balanced_takeaway.build',{'takeaway':'unchanged'}),('app.military_commitment.build',{'commitment':'unchanged'}),('app.build_matchup',{'matchup':'unchanged'})]:
            stack.enter_context(patch(target,return_value=result))
    def test_additive_packet_does_not_change_legacy_outputs_or_call_saves(self):
        h=self.setup_handler();query={'player':['Player A'],'match_id':['a'*64]}
        with ExitStack() as stack:
            self.legacy_mocks(stack)
            with patch('app.army_composition.build',return_value={'new':'composition'}):p=h._coaching_review(query,with_matchup=True)
            self.assertEqual(p['composition_context'],{'new':'composition'});self.assertEqual(p['takeaway_context'],{'takeaway':'unchanged'});self.assertEqual(p['practice_context']['journal'],'unchanged');self.assertEqual(p['reasoning_context'],{'reasoning':'unchanged'});self.assertEqual(p['commitment_context'],{'commitment':'unchanged'})
        self.assertTrue(all(c[0]=='read' for c in h.coaching_store.mock_calls))
    def test_lightweight_legacy_review_does_not_build_optional_context(self):
        h=self.setup_handler()
        with ExitStack() as stack:
            self.legacy_mocks(stack)
            with patch('app.army_composition.build') as build:
                self.assertEqual(h._coaching_review({'player':['Player A']})['match_id'],'a'*64);build.assert_not_called()
    def test_content_identity_gate_precedes_new_context(self):
        h=self.setup_handler()
        with patch('app.report_for',return_value=(report(),None,None)),patch('app.army_composition.build') as build:
            self.assertRaisesRegex(ValueError,'Replay content changed',h._coaching_review,{'match_id':['b'*64],'player':['Player A']},with_matchup=True);build.assert_not_called()

if __name__=='__main__':unittest.main()
