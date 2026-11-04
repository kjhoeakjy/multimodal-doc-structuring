"""LoRA 학습 자료(대화 형식 JSONL)를 만든다. CPU에서 돌아감.
입력 그래프: synth_graph.py가 만든 합성 그래프 폴더, 그리고(또는) 실제 추출 그래프(C02 등). C01은 평가 전용이므로 넣지 않는다.
각 그래프마다
  --retag N   태그·계기 번호·라인 번호를 무작위로 바꾼 사본을 N개 더 만듦(같은 위상에 다른 문자. 문자 암기를 막음)
  --noise     clean: 오류 없는 문맥만. mixed: 오류 없는 문맥 + 오류 종류·비율을 --per-graph-noise개 무작위로 넣은 문맥(noise.py와 같은 주입기)
  --conds     full, paths(precompute.py로 연결 정보를 덧붙인 문맥) 가운데 학습에 쓸 조건
문항과 답은 문맥을 만든 그 그래프(오류가 들어간 뒤)에서 qgen.py로 계산하므로 답은 항상 문맥에 충실하다. 그래프에 없는 태그를 묻는 문항의 답은 '자료에 없음'.
프롬프트 형식은 run_noise.py와 같다([자료]\\n문맥\\n\\n[질문]\\n문항, system은 run_qa.SYSTEM).
사용: python make_train.py --graphs <폴더 또는 graph.json ...> --out train.jsonl [--retag 2] [--noise mixed] [--conds full,paths] [--per-graph 24] [--max-chars 12000] [--seed 0]"""
import os, sys, json, re, random, argparse, tempfile, collections
HERE = os.path.dirname(os.path.abspath(__file__)); QA = os.path.abspath(os.path.join(HERE, '..'))
sys.path.insert(0, QA)
import noise as nz
import serialize as sz
import precompute
from contexts import ablate
from run_qa import SYSTEM
import qgen

KINDS = ('drop', 'add', 'label', 'split', 'merge', 'ocr', 'node', 'mix', 'attr'); LEVELS = (0.1, 0.2, 0.3, 0.5)

def serial_lines(g):
    with tempfile.TemporaryDirectory() as d:
        gp = os.path.join(d, 'g.json'); tp = os.path.join(d, 'g.txt')
        json.dump(g, open(gp, 'w', encoding='utf-8'), ensure_ascii=False); sz.main(gp, tp)
        return open(tp, encoding='utf-8').read().rstrip('\n').split('\n')

def contexts(g, conds):
    lines = serial_lines(g); out = {}
    for c in conds:
        out[c] = ablate(lines, 'full', True)
        if c == 'paths':
            out[c] += '\n' + '\n'.join(precompute.section(g))
    return out

TAG = re.compile(r'^([A-Z]{1,2})( ?)(\d{4})$'); INST = re.compile(r'^(\d{4})\.(\d{2})$'); LINE5 = re.compile(r'^\d{5}$')
def retag(g, seed):
    """장비 태그 숫자, 계기 번호 앞자리, 5자리 라인 번호를 일관되게 바꿈(모든 요소·선·표에 같은 대응)."""
    g = json.loads(json.dumps(g)); rnd = random.Random(seed); m4, m5, used = {}, {}, set()
    def new4(k):
        if k not in m4:
            while True:
                v = str(rnd.randrange(1000, 9999))
                if v not in used:
                    used.add(v); m4[k] = v; break
        return m4[k]
    def new5(k):
        if k not in m5:
            m5[k] = str(rnd.randrange(10000, 99999))
        return m5[k]
    def tok(t):
        m = TAG.match(t)
        if m:
            return m.group(1) + m.group(2) + new4(m.group(3))
        m = INST.match(t)
        if m:
            return new4(m.group(1)) + '.' + m.group(2)
        if LINE5.match(t):
            return new5(t)
        return t
    def text(t):
        return ' '.join(tok(x) for x in t.split()) if ' ' in t else tok(t)
    for n in g['nodes']:
        n['texts'] = [text(t) for t in n['texts']]
    for r in g['runs']:
        r['texts'] = [text(t) for t in r['texts']]
    for t in g.get('tables', []):
        t['rows'] = [[text(c) for c in row] for row in t['rows']]
    for l in g.get('labels', []):
        l['text'] = text(l['text'])
    return g

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--graphs', nargs='+', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--retag', type=int, default=0); ap.add_argument('--noise', default='mixed', choices=('clean', 'mixed')); ap.add_argument('--per-graph-noise', type=int, default=2)
    ap.add_argument('--conds', default='full,paths'); ap.add_argument('--per-graph', type=int, default=24, help='그래프·설정·조건당 문항 수 상한(종류별로 고르게)')
    ap.add_argument('--max-chars', type=int, default=12000, help='문맥 글자 수 상한(넘으면 그 그래프는 건너뜀)'); ap.add_argument('--seed', type=int, default=0)
    a = ap.parse_args()
    files = []
    for p in a.graphs:
        files += sorted(os.path.join(d, f) for d, _, fs in os.walk(p) for f in fs if f == 'graph.json') if os.path.isdir(p) else [p]
    conds = a.conds.split(','); rnd = random.Random(a.seed)
    n_ex, n_skip, types = 0, 0, collections.Counter()
    with open(a.out, 'w', encoding='utf-8') as f:
        for fi, path in enumerate(files):
            g0 = json.load(open(path, encoding='utf-8')); doc = os.path.basename(os.path.dirname(os.path.abspath(path)))
            variants = [(doc, g0)] + [(f"{doc}-rt{k}", retag(g0, a.seed * 1000 + fi * 10 + k)) for k in range(a.retag)]
            for vname, g in variants:
                settings = [('none', 0.0)]
                if a.noise == 'mixed':
                    settings += [(rnd.choice(KINDS), rnd.choice(LEVELS)) for _ in range(a.per_graph_noise)]
                for si, (kind, p) in enumerate(settings):
                    gp = nz.perturb(g, kind, p, a.seed * 100 + si) if p > 0 else g
                    try:
                        ctx = contexts(gp, conds)
                    except Exception as e:
                        n_skip += 1; print('건너뜀', vname, kind, p, str(e)[:80]); continue
                    if max(len(v) for v in ctx.values()) > a.max_chars:
                        n_skip += 1; continue
                    Q = qgen.questions(gp, vname, negatives=3, seed=a.seed + si)
                    by = collections.defaultdict(list)
                    for q in Q:
                        by[q['type']].append(q)
                    pick = []     # 종류별로 돌아가며 상한까지
                    for t in by.values():
                        rnd.shuffle(t)
                    while len(pick) < a.per_graph and any(by.values()):
                        for t in list(by):
                            if by[t]:
                                pick.append(by[t].pop())
                            if len(pick) >= a.per_graph:
                                break
                    for c in conds:
                        for q in pick:
                            ex = dict(messages=[dict(role='system', content=SYSTEM), dict(role='user', content=f"[자료]\n{ctx[c]}\n\n[질문]\n{q['question']}"), dict(role='assistant', content=qgen.answer_text(q))],
                                      meta=dict(doc=vname, setting=f"{kind if p else 'none'}-{p:g}", cond=c, type=q['type'], kind=q['kind']))
                            f.write(json.dumps(ex, ensure_ascii=False) + '\n'); n_ex += 1; types[q['type']] += 1
    print(f'그래프 {len(files)}개(사본 포함 {len(files) * (1 + a.retag)}), 예시 {n_ex}개, 건너뜀 {n_skip}, 종류별 {dict(types)} → {a.out}')

if __name__ == '__main__':
    main()
