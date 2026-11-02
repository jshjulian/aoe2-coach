"""Launcher subprocess checks with stub workers: no installs, servers or user stores."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parent
HEALTH={
    'api_version':4,'matchup_version':1,'provenance_version':2,
    'situation_version':1,'situation_review_version':2,'observations_version':1,
    'reviewed_moments_version':1,'practice_version':1,'practice_controls_version':1,
    'gameplay_version':2,'progress_version':1,'takeaway_version':1,
    'reasoning_version':1,'library_visuals_version':1,'replay_settings_version':1,'military_commitment_version':1,
}


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='agewise launcher ');self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);shutil.copyfile(ROOT/'run-viewer.sh',self.root/'run-viewer.sh')
        nextfile=self.root/'viewer/node_modules/next/dist/bin/next';nextfile.parent.mkdir(parents=True);nextfile.touch()
        self.stub=self.root/'commands';self.stub.mkdir()
        self.node=self.root/'selected runtime/node';self.node.parent.mkdir()
        self.node.write_text('''#!/bin/bash
if [[ "$1" == "-p" ]]; then echo "${TEST_PLATFORM:-linux}"; exit 0; fi
if [[ "$1" == "--probe-child" ]]; then echo child-ok; exit 0; fi
[[ "$(command -v node)" == "$EXPECTED_NODE" ]] || exit 71
node --probe-child >> "$WORKER_PROBE"
''');self.node.chmod(0o700)
        curl=self.stub/'curl';curl.write_text('#!/bin/bash\nprintf \'%s\\n\' \''+json.dumps(HEALTH)+'\'\n');curl.chmod(0o700)
        self.env={'HOME':str(self.root),'PATH':str(self.stub)+':/usr/bin:/bin',
                  'AOE2_NODE_BIN':str(self.node),'EXPECTED_NODE':str(self.node),
                  'WORKER_PROBE':str(self.root/'workers.log')}

    def run_launcher(self,*args):
        return subprocess.run(['/bin/bash',str(self.root/'run-viewer.sh'),*args],env=self.env,cwd=self.root,capture_output=True,text=True,timeout=15)

    def test_selected_node_is_on_path_for_build_and_start_workers(self):
        result=self.run_launcher('--production','--port','0')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual((self.root/'workers.log').read_text().splitlines(),['child-ok','child-ok'])

    def test_auto_selected_node_is_also_on_child_path(self):
        del self.env['AOE2_NODE_BIN']
        conventional=self.root/'.local/share/pi-node/current/bin';conventional.mkdir(parents=True)
        (conventional/'node').symlink_to(self.node)
        result=self.run_launcher('--port','0')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual((self.root/'workers.log').read_text().splitlines(),['child-ok'])

    def test_non_linux_override_is_rejected(self):
        self.env['TEST_PLATFORM']='win32'
        result=self.run_launcher()
        self.assertEqual(result.returncode,1)
        self.assertIn('Linux Node.js required',result.stderr)
        self.assertFalse((self.root/'workers.log').exists())

    def test_missing_override_is_rejected(self):
        self.env['AOE2_NODE_BIN']=str(self.root/'missing/node')
        self.assertEqual(self.run_launcher().returncode,1)

if __name__=='__main__':unittest.main()
