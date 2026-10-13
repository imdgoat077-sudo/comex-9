"""Re-score every saved rocket trial under the current rubric and show it next to the score recorded when the run was made."""
import glob, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from benchmarks.rocket_rubric import score, RUBRIC_VERSION

print(f"rubric version {RUBRIC_VERSION}")
for f in sorted(glob.glob(os.path.join(os.path.dirname(__file__), "rocket", "*", "trial_*.json"))):
    r = json.load(open(f))
    new = score(r["scene"])
    miss = [k for k, v in new["components"].items() if not v]
    print(f"{f.split('/rocket/')[1]:45s} recorded {r['score']}/9 ({'v1' if 'rubric_version' not in r else 'v%s' % r['rubric_version']})  -> v{RUBRIC_VERSION}: {new['score']}/9  missing: {miss}")
