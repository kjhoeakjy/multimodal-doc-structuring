"""학습에 쓰지 않은 도면으로 일반화를 재는 평가 묶음을 만든다. CPU에서 돌아감.
입력은 PID2Graph OPEN100(실제 공개 도면의 사람 주석 위상. 학습 자료는 Dataset PID와 C02만 씀). 문자는 없으므로 synth_graph.py로 합성한다.
문항과 답은 오류를 넣기 전 그래프에서 qgen.py로 계산한다. 학습과 달리 문맥이 아니라 원래 도면이 기준이므로 C01 오류 실험과 같은 뜻이다.
사용: python finetune/make_holdout.py <OPEN100 폴더> --out finetune/holdout.json [--per-graph 24] [--max-chars 12000] [--seed 0]
결과: holdout.json, finetune/eval_holdout.py 입력"""
import os, sys, json, random, argparse, collections
HERE = os.path.dirname(os.path.abspath(__file__)); QA = os.path.abspath(os.path.join(HERE, '..'))
sys.path.insert(0, HERE); sys.path.insert(0, QA)
import noise as nz
import qgen
from make_train import contexts
from synth_graph import convert

SETTINGS = (('none', 0.0), ('drop', 0.2), ('drop', 0.5), ('ocr', 0.5), ('attr', 0.5))

def pick(Q, n, rnd):
    by = collections.defaultdict(list)
    for q in Q:
        by[q['type']].append(q)
    for t in by.values():
        rnd.shuffle(t)
    out = []
    while len(out) < n and any(by.values()):
        for t in sorted(by):
            if by[t] and len(out) < n:
                out.append(by[t].pop())
    return out

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('folder'); ap.add_argument('--out', required=True)
    ap.add_argument('--per-graph', type=int, default=24); ap.add_argument('--max-chars', type=int, default=12000)
    ap.add_argument('--max-nodes', type=int, default=80); ap.add_argument('--seed', type=int, default=0)
    a = ap.parse_args(); rnd = random.Random(a.seed); docs = []
    for name in sorted((f for f in os.listdir(a.folder) if f.endswith('.graphml')), key=lambda f: int(f.split('.')[0])):
        doc = 'open100-' + name.split('.')[0]
        g = convert(os.path.join(a.folder, name), rnd, a.max_nodes)
        if g is None:
            print('건너뜀(요소 없음)', doc); continue
        Q = pick(qgen.questions(g, doc, negatives=0, seed=a.seed), a.per_graph, rnd)
        if not Q:
            print('건너뜀(문항 없음)', doc); continue
        ctx = {}
        for si, (kind, p) in enumerate(SETTINGS):
            c = contexts(nz.perturb(g, kind, p, a.seed * 100 + si) if p else g, ('full', 'paths'), a.max_chars)
            if c is None:
                break
            ctx[f'{kind}-{p:g}'] = c
        if len(ctx) < len(SETTINGS):
            print('건너뜀(문맥 상한 초과)', doc); continue
        docs.append(dict(doc=doc, questions=Q, contexts=ctx))
        print(doc, '노드', len(g['nodes']), '선', len(g['runs']), '문항', len(Q), dict(collections.Counter(q['type'] for q in Q)), '문맥', len(ctx['none-0']['full']), len(ctx['none-0']['paths']), flush=True)
    json.dump(dict(settings=[f'{k}-{p:g}' for k, p in SETTINGS], docs=docs), open(a.out, 'w', encoding='utf-8'), ensure_ascii=False)
    print('도면', len(docs), '문항', sum(len(d['questions']) for d in docs), '→', a.out)

if __name__ == '__main__':
    main()
