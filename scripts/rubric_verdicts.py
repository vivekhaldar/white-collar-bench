"""Count status/brief rubric verdicts (covered, missing, contradicted) per run by regrading answers.

    python scripts/rubric_verdicts.py runs/claude-5.5-pi-lite/haiku runs/gpt-6.1-sol-pi-lite/sol ...

Each argument is a model directory with track-<a|b>/scores-lite/report.json (as written by the
results/*-pi-lite/config/run_all.py orchestrators). Regrades every status and brief answer of the
lite suite with the heuristic judge and prints verdict counts, and the low-scoring answers that
had a contradicted rubric item (a superseded value stated as current).
"""
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, '.')
from wcb.grade.answers import ScoreContext, score_answers
from wcb.grade.judge import HeuristicJudge
from wcb.world.model import World
from wcb.world.state import state_at

J = HeuristicJudge()
runs = {Path(a).name: a for a in sys.argv[1:]}
for m, p in runs.items():
    for t in 'ab':
        rep = json.load(open(f'{p}/track-{t}/scores-lite/report.json'))
        run = Path(rep['run']['dir'])
        c = collections.Counter()
        zero_by_contra = []
        for w in rep['worlds']:
            world = World.load(w['path'])
            for cp in w['checkpoints']:
                doc = json.loads((Path(w['path']) / 'gold/questions' / f"{cp['id']}.json").read_text())
                ans = json.loads((run / w['id'] / 'r1/answers' / f"{cp['id']}.json").read_text())
                ctx = ScoreContext.from_state(world, state_at(world, cp['date']), store_root=run / w['id'] / 'r1/snapshots' / cp['date'])
                for s in score_answers(doc, ans, J, ctx):
                    if s.type in ('status', 'brief') and s.answerable:
                        vs = s.details.get('verdicts') or []
                        for v in vs:
                            c[v['verdict']] += 1
                        if any(v['verdict'] == 'contradicted' for v in vs) and s.base < 0.3:
                            zero_by_contra.append(f"{w['id']} {s.id} base={s.base:.2f}")
        tot = sum(c.values())
        print(m, t.upper(), dict(c), f"contradicted share {c['contradicted']/tot:.2f}", 'low-scoring with contradictions:', zero_by_contra)
