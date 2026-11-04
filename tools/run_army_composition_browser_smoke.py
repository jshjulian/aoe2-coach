#!/usr/bin/env python3
"""Post-match composition checks; ephemeral read-only API/stores, no collection."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from http.server import ThreadingHTTPServer
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import app
from coaching_store import CoachingStore
from observations import ObservationStore
from reviewed_moments import ReviewedMomentStore


def main(script='browser_army_composition_smoke.mjs'):
    with tempfile.TemporaryDirectory(prefix='agewise-army-browser-') as directory:
        class Handler(app.Handler):
            library=app.ReplayLibrary()
            coaching_store=CoachingStore(Path(directory)/'journal.sqlite')
            observation_store=ObservationStore(Path(directory)/'observations')
            reviewed_moment_store=ReviewedMomentStore(Path(directory)/'reviewed-moments')
            def do_POST(self):self._json(403,{'error':'Read-only composition test API.'})
        selected,_=app.select_directories();Handler.library.configure(selected if selected is not None else app.discover_replay_directories());Handler.library.refresh(force=True)
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            environment={**os.environ,'ARMY_TEST_API_URL':f'http://127.0.0.1:{server.server_port}'}
            result=subprocess.run(['node',str(ROOT/'tools'/script)],cwd=ROOT,env=environment).returncode
            with Handler.coaching_store._connect() as db:
                assert db.execute('SELECT COUNT(*) FROM records').fetchone()[0]==0
                assert db.execute('SELECT COUNT(*) FROM revisions').fetchone()[0]==0
            return result
        finally:server.shutdown();server.server_close();thread.join(timeout=2)

if __name__=='__main__':raise SystemExit(main())
