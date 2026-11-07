"""Flip one feature's "passes" to true in FEATURES.json, touching nothing else.

Usage: python tools/mark_pass.py F01
(Only after opening that feature's evidence file. Never edits any other text.)
"""
import re
import sys
from pathlib import Path

path = Path(__file__).resolve().parent.parent / "FEATURES.json"
fid = sys.argv[1]
text = path.read_text(encoding="utf-8")
m = re.search(r'"id":\s*"%s".*?"passes":\s*(false|true)' % re.escape(fid), text, re.S)
if not m:
    sys.exit(f"feature {fid} not found")
start, end = m.span(1)
new = text[:start] + "true" + text[end:]
path.write_text(new, encoding="utf-8", newline="")
print(f"{fid}: passes -> true")
