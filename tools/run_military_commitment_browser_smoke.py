#!/usr/bin/env python3
"""Post-match browser checks with an ephemeral API and journal. Needs a running viewer and local completed replay."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from http.server import ThreadingHTTPServer
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import app
from coaching_store import CoachingStore
from observations import ObservationStore
from reviewed_moments import ReviewedMomentStore


def main():
    with tempfile.TemporaryDirectory(prefix='agewise-commitment-browser-') as directory:
        class Handler(app.Handler):
            library=app.ReplayLibrary()
            coaching_store=CoachingStore(Path(directory)/'journal.sqlite')
            observation_store=ObservationStore(Path(directory)/'observations')
            reviewed_moment_store=ReviewedMomentStore(Path(directory)/'reviewed-moments')
        selected,_=app.select_directories()
        Handler.library.configure(selected if selected is not None else app.discover_replay_directories())
        Handler.library.refresh(force=True)
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            environment={**os.environ,'COMMITMENT_TEST_API_URL':f'http://127.0.0.1:{server.server_port}'}
            result=subprocess.run(['node',str(ROOT/'tools/browser_military_commitment_smoke.mjs')],cwd=ROOT,env=environment).returncode
            if result:return result
            with Handler.coaching_store._connect() as db:
                kinds=db.execute('SELECT DISTINCT kind FROM records').fetchall()
                assert kinds==[('military_commitment_context',)],kinds
                assert db.execute('SELECT COUNT(*) FROM revisions').fetchone()[0]==2
            return 0
        finally:server.shutdown();server.server_close();thread.join(timeout=2)

if __name__=='__main__':raise SystemExit(main())
