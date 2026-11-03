"""근거 보존율과 정답률의 관계. 오류를 넣은 문맥마다 각 문항의 근거(기준 요소 문자, 정답 문자, 기준 요소에의 귀속, 연결 도달 집합)가 남아 있는지를
diagnose_real.classify로 판정해 설정별 근거 보존율을 구하고, 결과 파일이 있으면 정답률과의 상관을 잰다.
  기준 보존   질문의 기준 요소 문자가 문맥에 있음
  답 보존     정답 문자가 문맥 어딘가에 있음(기준 보존 포함)
  근거 보존   정답 문자가 기준 요소 줄에 있음(연결 문항은 도달 집합 일치). 모델이 틀릴 이유가 문맥에 없는 문항의 비율
오류 없는 기준 그래프에서도 T4750의 노즐 2문항은 근거가 없음(그래프에 N3 지름·N4가 없음)이라 근거 보존율 상한은 0.95. 노즐 번호가 기준 장비 줄에서 빠진 경우는 기준 문자 손실로 셈.
정답률 = 근거 보존율 × (근거 있는 문항의 정답률)로 나뉘므로, 뒤 항이 오류 종류와 무관하게 일정하면 그래프 품질은 근거 보존율로 재는 것이 맞음.
사용: python evidence.py [--label <결과 이름>] [--cond full]   (C01 43문항 전용. 연결 의존 문항은 원인 분류 규칙이 없음)
결과: results/<결과 이름>-evidence.md (결과 이름이 없으면 noise/evidence.md)"""
import os, sys, re, json, argparse, collections, math
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from diagnose_real import classify

KINDS = ('none', 'drop', 'add', 'label', 'split', 'merge', 'ocr', 'node', 'mix', 'attr', 'real')
LV = lambda p: float(p) if re.fullmatch(r'[\d.]+', p) else 9

def pearson(xs, ys):
    n = len(xs); mx, my = sum(xs) / n, sum(ys) / n
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs)); sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy) if sx and sy else float('nan')

def spearman(xs, ys):
    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i]); r = [0.0] * len(v); i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            for k in range(i, j + 1):
                r[order[k]] = (i + j) / 2 + 1
            i = j + 1
        return r
    return pearson(rank(xs), rank(ys))

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--label', default=''); ap.add_argument('--cond', default='full')
    a = ap.parse_args()
    N = json.load(open(os.path.join(HERE, 'noise', 'contexts.json'), encoding='utf-8'))
    Q = {q['id']: q for q in json.load(open(os.path.join(HERE, 'questions.json'), encoding='utf-8'))}
    qs = [Q[i] for i in N['questions']]
    G = {}
    for l in open(os.path.join(HERE, 'noise', 'graphs.md'), encoding='utf-8'):
        m = re.match(r'\| (\S+) \| ([\d.]+) \| ([\d.]+) \| ([\d.]+) \|', l)
        if m:
            G[m.group(1)] = tuple(float(x) for x in m.groups()[1:])
    res = collections.defaultdict(dict)
    if a.label:
        for l in open(os.path.join(HERE, 'results', f'{a.label}.jsonl'), encoding='utf-8'):
            r = json.loads(l)
            if r['cond'] == a.cond:
                res[r['setting']][r['id']] = r['correct']
    S = {}     # 설정 → 문항별 근거 분류
    for k, c in N['contexts'].items():
        S[k] = {q['id']: classify(q, c[a.cond]) for q in qs}
    by = collections.defaultdict(list)
    for k in S:
        by[(k.split('-')[0], k.split('-')[1])].append(k)
    rows = []
    for kind in KINDS:
        for p in sorted({p for kd, p in by if kd == kind}, key=LV):
            ks = by[(kind, p)]; n = 0; focus = ans = ev = 0; acc = [0, 0]; acc_ev = [0, 0]; acc_no = [0, 0]
            for k in ks:
                for qid, cat in S[k].items():
                    n += 1; focus += cat != '기준 문자 손실'; ans += cat not in ('기준 문자 손실', '답 문자 손실'); ev += cat == '모델 오류'
                    if qid in res.get(k, {}):
                        c = res[k][qid]; acc[0] += c; acc[1] += 1
                        t = acc_ev if cat == '모델 오류' else acc_no; t[0] += c; t[1] += 1
            g = [G[k] for k in ks if k in G]
            m = [sum(x[i] for x in g) / len(g) for i in range(3)] if g else [float('nan')] * 3
            rows.append(dict(kind=kind, p=p, recall=m[0], precision=m[1], text=m[2], focus=focus / n, ans=ans / n, ev=ev / n,
                             acc=acc[0] / acc[1] if acc[1] else None, acc_ev=(acc_ev[0] / acc_ev[1]) if acc_ev[1] else None, n_ev=acc_ev[1],
                             acc_no=(acc_no[0] / acc_no[1]) if acc_no[1] else None, n_no=acc_no[1]))
    f = lambda v: '-' if v is None or (isinstance(v, float) and math.isnan(v)) else f'{v:.2f}'
    pc = lambda v, n: '-' if v is None else f'{100 * v:.1f}% ({n})'
    L = [f'# 근거 보존율과 정답률 · {a.label or "문맥만"} · {a.cond}', '', f'문항 {len(qs)}. 근거 보존은 diagnose_real.classify 기준(정답 문자가 기준 요소 줄에 있음, 연결 문항은 도달 집합 일치). 씨앗 평균.', '',
         '| 오류 | 비율 | 재현율 | 정밀도 | 문자 복원 | 기준 보존 | 답 보존 | 근거 보존 | 정답률 | 근거 있음 정답률 | 근거 없음 정답률 |', '|---|---|---|---|---|---|---|---|---|---|---|']
    for r in rows:
        L.append(f"| {r['kind']} | {r['p']} | {f(r['recall'])} | {f(r['precision'])} | {f(r['text'])} | {f(r['focus'])} | {f(r['ans'])} | {f(r['ev'])} | "
                 f"{f(r['acc'])} | {pc(r['acc_ev'], r['n_ev'])} | {pc(r['acc_no'], r['n_no'])} |")
    if a.label:
        rs = [r for r in rows if r['acc'] is not None]
        L += ['', '## 설정(오류 종류·비율) 단위 상관 · 정답률 대비', '', f'설정 {len(rs)}개(실제 추출 포함). 피어슨 / 스피어만.', '', '| 지표 | 피어슨 | 스피어만 |', '|---|---|---|']
        for name, key in (('배관 연결 재현율', 'recall'), ('정밀도', 'precision'), ('문자 복원율', 'text'), ('기준 보존율', 'focus'), ('답 보존율', 'ans'), ('근거 보존율', 'ev')):
            xs = [r[key] for r in rs]; ys = [r['acc'] for r in rs]
            L.append(f'| {name} | {pearson(xs, ys):.2f} | {spearman(xs, ys):.2f} |')
        rs2 = [r for r in rs if r['kind'] != 'real']
        L += ['', '### 실제 추출 제외(통제 오류만)', '', '| 지표 | 피어슨 | 스피어만 |', '|---|---|---|']
        for name, key in (('배관 연결 재현율', 'recall'), ('정밀도', 'precision'), ('문자 복원율', 'text'), ('근거 보존율', 'ev')):
            xs = [r[key] for r in rs2]; ys = [r['acc'] for r in rs2]
            L.append(f'| {name} | {pearson(xs, ys):.2f} | {spearman(xs, ys):.2f} |')
        T = collections.defaultdict(lambda: collections.Counter())     # 종류별 근거 없는 문항 원인
        for k in S:
            kind = k.split('-')[0]
            for qid, cat in S[k].items():
                if cat != '모델 오류':
                    T[kind][cat] += 1
        cats = ['기준 문자 손실', '답 문자 손실', '귀속 오류', '연결 오류']
        L += ['', '## 오류 종류별 근거 손실 원인(문항·설정 합계)', '', '| 오류 | ' + ' | '.join(cats) + ' |', '|---|' + '---|' * len(cats)]
        for kind in KINDS:
            if kind in T:
                L.append(f'| {kind} | ' + ' | '.join(str(T[kind][c]) for c in cats) + ' |')
    out = os.path.join(HERE, 'results', f'{a.label}-evidence.md') if a.label else os.path.join(HERE, 'noise', 'evidence.md')
    open(out, 'w', encoding='utf-8').write('\n'.join(L) + '\n'); print('\n'.join(L))

if __name__ == '__main__':
    main()
