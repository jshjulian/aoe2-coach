import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from tools.restore_reference_snapshot import restore


class ReferenceSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        (self.root/'knowledge').mkdir();self.raw=b'public pinned reference'
        self.lock={'repository':'https://github.com/SiegeEngineers/aoe2techtree','commit':'a'*40,'files':[{'path':'data.json','upstream_path':'data/data.json','sha256':hashlib.sha256(self.raw).hexdigest()}]}
        self.write();self.target=self.root/'data/research/aoe2techtree'/('a'*40)/'data.json'
    def write(self):
        for name in ['aoe2techtree.lock.json','situational-catalog.lock.json']:(self.root/'knowledge'/name).write_text(json.dumps(self.lock))
    def test_missing_cache_does_not_request_network_without_consent(self):
        with self.assertRaises(ValueError):restore(self.root,opener=lambda *a,**k:self.fail('Unexpected network'))
        self.assertFalse(self.target.exists())
    def test_explicit_download_is_pinned_and_locks_unchanged(self):
        before=(self.root/'knowledge/aoe2techtree.lock.json').read_bytes();urls=[]
        def opened(url,**kwargs):urls.append(url);return io.BytesIO(self.raw)
        self.assertEqual(restore(self.root,download=True,opener=opened),1)
        self.assertEqual(urls,['https://raw.githubusercontent.com/SiegeEngineers/aoe2techtree/'+('a'*40)+'/data/data.json'])
        self.assertEqual(self.target.read_bytes(),self.raw)
        self.assertEqual((self.root/'knowledge/aoe2techtree.lock.json').read_bytes(),before)
        self.assertEqual(restore(self.root,opener=lambda *a,**k:self.fail('Cache must stay offline')),1)
    def test_bad_download_is_not_written(self):
        with self.assertRaises(ValueError):restore(self.root,download=True,opener=lambda *a,**k:io.BytesIO(b'wrong'))
        self.assertFalse(self.target.exists())
    def test_changed_existing_cache_is_not_replaced(self):
        self.target.parent.mkdir(parents=True);self.target.write_bytes(b'changed')
        with self.assertRaises(ValueError):restore(self.root,download=True,opener=lambda *a,**k:self.fail('No repair download'))
        self.assertEqual(self.target.read_bytes(),b'changed')
    def test_path_escape_and_foreign_repository_are_rejected(self):
        for field,value in [('path','../../escape'),('upstream_path','https://other.invalid/file')]:
            self.lock['files'][0][field]=value;self.write()
            with self.assertRaises(ValueError):restore(self.root,download=True,opener=lambda *a,**k:self.fail('Unsafe URL'))
            self.lock['files'][0][field]='data.json'
        self.lock['repository']='https://other.invalid';self.write()
        with self.assertRaises(ValueError):restore(self.root)

if __name__=='__main__':unittest.main()
