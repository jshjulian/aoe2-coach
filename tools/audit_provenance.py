"""Local extractor-source fingerprint. No execution, networking or application access."""
import hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SOURCE_FILES=('tools/read_captureage_signals.py','tools/prepare_captureage_signals.mjs',
              'tools/read_state_ocr.py','tools/ocr_state_screenshot.ps1','tools/audit_provenance.py')

def fingerprint():
    return {name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in SOURCE_FILES}
