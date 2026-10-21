"""Render a private offline audit page with a hash-pinned script and no networking."""
import base64
import hashlib
import html
import json
import os
from pathlib import Path


def write_page(root,task):
    script=Path(__file__).with_name('audit_page.js').read_text()
    sha=base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
    csp=f"default-src 'none'; img-src 'self' file: data:; style-src 'unsafe-inline'; script-src 'sha256-{sha}'; connect-src 'none'; base-uri 'none'; form-action 'none'; object-src 'none'; frame-src 'none'"
    payload=html.escape(json.dumps(task,ensure_ascii=False))
    page='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="CSP"><title>Agewise · Private measurement audit</title><style>
body{font:16px system-ui,sans-serif;line-height:1.5;background:#f5f5f1;color:#20251f;max-width:1100px;margin:24px auto;padding:0 18px}h1{margin-bottom:4px}h2{font-size:20px}p{max-width:90ch}.muted{color:#53604f;font-size:14px}button,input,select{font:inherit;max-width:100%;box-sizing:border-box}button{padding:7px 12px;cursor:pointer}input,select{padding:6px;border:1px solid #9bA694;border-radius:4px;min-width:0}label{display:block;margin-top:8px}.toolbar{display:flex;flex-wrap:wrap;gap:12px;align-items:center;margin:16px 0}.panel,article{background:white;border:1px solid #ccd2c6;border-radius:10px;padding:14px;margin:12px 0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(290px,100%),1fr));gap:12px}.grid article{margin:0;min-width:0}.crop{display:block;max-width:100%;height:auto;background:#191919;border:1px solid #aaa;min-height:70px}.original{width:100%;height:auto}.word{overflow-wrap:anywhere}.error{color:#a32819}ul{padding-left:20px}table{border-collapse:collapse;width:100%;font-size:13px}td,th{text-align:left;border-bottom:1px solid #ddd;padding:5px}.scroll{overflow:auto}.compact{font-size:13px}summary{cursor:pointer;font-weight:600}input[type=checkbox]{width:auto}
</style></head><body>
<h1>Agewise measurement audit</h1><p class="muted">Private saved-image review · no game/app launch, networking, automatic imports or qualification</p>
<section class="panel"><b>Label what is visible, not what you expect.</b><p>Candidate OCR values are not shown. Crops retain original colors; use the full screenshot when a crop is clipped or ambiguous. Do not infer a missing clock from frame order, playback speed or another frame. Do not expand rounded values such as 15.7k into exact integers.</p><p class="muted">A human's labels/blinding declaration is an assertion, not independently verified engine state. This page does not diagnose military idle or why a battle was lost.</p><p id="scope" class="word"></p>
<label>Reviewer kind <select id="reviewer-kind"><option value="">Choose explicitly</option><option value="human">Human reviewing visible pixels</option><option value="assistant">Assistant visual labels (not independent)</option></select></label>
<label>Local reviewer pseudonym <input id="reviewer-id" maxlength="64" autocomplete="off" placeholder="e.g. reviewer-1"></label>
<label><input id="blind" type="checkbox"> I labelled these images without inspecting candidate OCR outputs or earlier reference values.</label>
<p class="muted">Labels stay in this page's memory until you explicitly download them. Keep the page open until finished; nothing is automatically saved.</p></section>
<div class="toolbar"><button id="previous">Previous frame</button><b id="frame-title"></b><button id="next">Next frame</button><span id="progress"></span><button id="download">Download labels JSON</button></div><p id="error" role="alert" class="error"></p>
<details class="panel"><summary>Full original screenshot · player names may be visible</summary><a id="original-link" target="_blank" rel="noopener">Open original locally for zoom</a><img id="original" class="original" alt="Original source screenshot"></details>
<p id="identity" class="muted"></p><div id="samples" class="grid"></div>
<details class="panel"><summary>Focused fighting-window review · context, not a diagnosis</summary><div id="context"></div><h3>What still needs actual offline playback</h3><ul><li>Which forces actually met, and where did losses occur?</li><li>Were forces concentrated, dispersed on raids, retreating or arriving late?</li><li>Which production buildings survived, what was actually queued/researched, and which reinforcements completed?</li><li>What was visible to the player before the decision? Observer vision is not player vision.</li><li>Do additional before/during checkpoints support population/resource constraints, rather than just an after-fight bank?</li></ul><p class="muted">The existing Replay view shows recorded command evidence, not CaptureAge's full-state simulation. No fight footage is present in these HUD-only frames.</p></details>
<div id="task-data" hidden>PAYLOAD</div><script>SCRIPT</script></body></html>'''
    page=page.replace('content="CSP"', 'content="'+html.escape(csp,quote=True)+'"',1)
    page=page.replace('<script>SCRIPT</script>','<script>'+script+'</script>',1)
    page=page.replace('<div id="task-data" hidden>PAYLOAD</div>','<div id="task-data" hidden>'+payload+'</div>',1)
    with os.fdopen(os.open(Path(root)/'index.html',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as f:f.write(page)
