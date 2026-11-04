"""오류 설정별 정답률 변화를 문항 단위 대응 구간으로 표현한다("효과 없음"을 ±몇 %p 이내로 쓰기 위한 것).
각 설정(오류 종류·비율)에서 문항마다 (설정 정답 평균 − 오류 없음 정답)을 씨앗에 걸쳐 평균하고, 문항을 복원 추출(부트스트랩 10,000회)해 평균 차이의 95% 구간을 구한다.
구간이 ±eq(기본 10 %p) 안이면 '동등', 구간 상한이 0 아래면 '감소', 그 밖은 '불확정'으로 표시한다.
사용: python intervals.py --label api-small-2026-11-noise2 [--cond full] [--eq 10] [--out results/<label>-intervals.md]"""
import os, sys, json, re, random, argparse, collections
HERE = os.path.dirname(os.path.abspath(__file__))

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--label', required=True); ap.add_argument('--cond', default='full'); ap.add_argument('--eq', type=float, default=10)
    ap.add_argument('--boot', type=int, default=10000); ap.add_argument('--seed', type=int, default=0); ap.add_argument('--out', default='')
    a = ap.parse_args(); rnd = random.Random(a.seed)
    rows = [json.loads(l) for l in open(os.path.join(HERE, 'results', f'{a.label}.jsonl'), encoding='utf-8')]
    rows = [r for r in rows if r['cond'] == a.cond]
    by = collections.defaultdict(lambda: collections.defaultdict(list))     # (kind, p) -> qid -> [correct per seed]
    for r in rows:
        kind, p = r['setting'].split('-')[0], r['setting'].split('-')[1]
        by[(kind, p)][r['id']].append(r['correct'])
    base = {q: sum(v) / len(v) for q, v in by[('none', '0')].items()}
    types = {r['id']: r['type'] for r in rows}
    KINDS = ('drop', 'add', 'label', 'split', 'merge', 'ocr', 'node', 'mix', 'attr', 'real')
    lv = lambda p: (0, float(p)) if re.match(r'^[\d.]+$', p) else (1, p)
    L = [f'# 정답률 변화의 대응 구간 · {a.label} · {a.cond}', '',
         f'문항 {len(base)}개. 차이 = 설정 정답(씨앗 평균) − 오류 없음 정답을 문항마다 구해 평균한 값(%p). 구간은 문항 복원 추출 {a.boot:,}회의 2.5~97.5 백분위. 판정: 구간이 ±{a.eq:g} %p 안이면 동등, 상한이 0 아래면 감소, 그 밖은 불확정.', '',
         '| 오류 | 비율 | 오류 없음 | 설정 | 차이(%p) | 95% 구간 | 판정 | 문항 수 |', '|---|---|---|---|---|---|---|---|']
    for kind in KINDS:
        for p in sorted({k[1] for k in by if k[0] == kind}, key=lv):
            d = by[(kind, p)]
            qs = [q for q in d if q in base]
            diff = [sum(d[q]) / len(d[q]) - base[q] for q in qs]
            if not diff:
                continue
            mean = sum(diff) / len(diff)
            boots = []
            for _ in range(a.boot):
                s = [diff[rnd.randrange(len(diff))] for _ in diff]
                boots.append(sum(s) / len(s))
            boots.sort(); lo, hi = boots[int(0.025 * a.boot)], boots[int(0.975 * a.boot) - 1]
            verdict = '동등' if lo > -a.eq / 100 and hi < a.eq / 100 else '감소' if hi < 0 else '증가' if lo > 0 else '불확정'
            b0 = sum(base[q] for q in qs) / len(qs); s1 = sum(sum(d[q]) / len(d[q]) for q in qs) / len(qs)
            L.append(f"| {kind} | {p} | {b0 * 100:.1f}% | {s1 * 100:.1f}% | {mean * 100:+.1f} | [{lo * 100:+.1f}, {hi * 100:+.1f}] | {verdict} | {len(qs)} |")
    # 문항 종류별 차이(구간 없이, 종류별 문항 수가 적음)
    tys = sorted(set(types.values()))
    L += ['', '## 문항 종류별 차이(%p, 설정 − 오류 없음)', '', '| 오류 | 비율 | ' + ' | '.join(f"{t}({sum(1 for q in base if types[q] == t)})" for t in tys) + ' |', '|---|---|' + '---|' * len(tys)]
    for kind in KINDS:
        for p in sorted({k[1] for k in by if k[0] == kind}, key=lv):
            d = by[(kind, p)]; cells = []
            for t in tys:
                qs = [q for q in d if q in base and types[q] == t]
                cells.append(f"{(sum(sum(d[q]) / len(d[q]) - base[q] for q in qs) / len(qs)) * 100:+.0f}" if qs else '-')
            L.append(f"| {kind} | {p} | " + ' | '.join(cells) + ' |')
    out = a.out or os.path.join(HERE, 'results', f'{a.label}-intervals.md')
    open(out, 'w', encoding='utf-8').write('\n'.join(L) + '\n'); print('\n'.join(L[:40]))

if __name__ == '__main__':
    main()
