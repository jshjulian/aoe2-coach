import json
from pathlib import Path
import tempfile
import threading
from http.server import ThreadingHTTPServer
import unittest
import urllib.request
import urllib.error
import app
import military_commitment as model
from coaching_store import CoachingStore
from test_military_commitment import report


class CommitmentHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        store=CoachingStore(Path(self.temp.name)/'journal.sqlite');self.store=store;r=report()
        class Handler(app.Handler):
            coaching_store=store
            def _coaching_review(self,query,*,with_matchup=False):
                if query.get('match_id',[''])[0]!=r['match_id'] or query.get('player',[''])[0]!='Player A':raise ValueError('Source identity mismatch.')
                return {'commitment_context':model.build(r,'Player A',store),'legacy_unchanged':True}
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.base=f'http://127.0.0.1:{self.server.server_port}'
        self.addCleanup(self.stop)
        self.token=Handler.csrf_token
    def stop(self):self.server.shutdown();self.server.server_close();self.thread.join(timeout=2)
    def fields(self):
        p=model.build(report(),'Player A',self.store)
        return dict(operation='commitment_answer',match_id=p['match_id'],player='Player A',game_id='synthetic',situation_id=p['windows'][0]['id'],question_id='military-commitment-v1',constraint='resource_setup',intent='clear_pressure',note='Synthetic private note',expected_revision=0,confirm_identity=True)
    def post(self,fields,token=True,origin='http://127.0.0.1:3000'):
        headers={'Content-Type':'application/json','Origin':origin}
        if token:headers['X-Coaching-Token']=self.token
        req=urllib.request.Request(self.base+'/api/coaching/state',json.dumps(fields).encode(),headers=headers,method='POST')
        try:
            with urllib.request.urlopen(req,timeout=5) as response:return response.status,json.load(response)
        except urllib.error.HTTPError as exc:return exc.code,json.load(exc)
    def test_protected_write_rebuilds_binding_and_only_new_record_kind(self):
        fields=self.fields();fields.update(binding={'forged':True},eligible_for_measurements=True,focus_id='do-not-create')
        status,packet=self.post(fields);self.assertEqual(status,200,packet)
        context=packet['commitment_context']['windows'][0]['reviewed_context']
        self.assertFalse(context['eligible_for_measurements']);self.assertNotIn('forged',context['binding'])
        with self.store._connect() as db:self.assertEqual(db.execute('SELECT kind FROM records').fetchall(),[('military_commitment_context',)])
        self.assertTrue(packet['legacy_unchanged'])
    def test_missing_token_or_foreign_origin_cannot_save(self):
        fields=self.fields()
        self.assertEqual(self.post(fields,token=False)[0],403)
        self.assertEqual(self.post(fields,origin='https://example.invalid')[0],403)
        with self.store._connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM records').fetchone()[0],0)
    def test_content_and_question_identity_checked(self):
        for key,value in [('match_id','b'*64),('player','Player B'),('situation_id','forged'),('question_id','forged')]:
            fields=self.fields();fields[key]=value;self.assertEqual(self.post(fields)[0],400)
    def test_stale_revision_refused_without_new_history(self):
        fields=self.fields();self.assertEqual(self.post(fields)[0],200);self.assertEqual(self.post(fields)[0],400)
        with self.store._connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM revisions').fetchone()[0],1)

if __name__=='__main__':unittest.main()
