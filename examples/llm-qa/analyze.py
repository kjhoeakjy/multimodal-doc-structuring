"""결과 파일(results/<label>.jsonl)의 신뢰구간·조건 간 대응 비교·오답 유형을 계산해 results/<label>-analysis.md로 씀.
사용: python analyze.py <label> [--seed 0] [--n 2000]"""
import os, sys, json, random, argparse, collections
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from run_qa import GROUP

def boot_ci(vals, n=2000, seed=0):
    rnd = random.Random(seed); k = len(vals); means = []
    for _ in range(n):
        means.append(sum(vals[rnd.randrange(k)] for _ in range(k)) / k)
    means.sort()
    return means[int(n * 0.025)], means[int(n * 0.975) - 1]

def kind_of(r):
    resp = (r['response'] or '').strip()
    if r['correct']:
        return '정답'
    if not resp:
        return '빈 응답'
    if '자료에 없음' in resp or 'not found' in resp.lower() or '없음' == resp:
        return '자료에 없음'
    if len(resp) > 60:
        return '긴 응답(설명 포함)'
    return '다른 값'

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('label'); ap.add_argument('--n', type=int, default=2000); ap.add_argument('--seed', type=int, default=0)
    a = ap.parse_args()
    rows = [json.loads(l) for l in open(os.path.join(HERE, 'results', a.label + '.jsonl'), encoding='utf-8')]
    conds = list(collections.OrderedDict((r['cond'], 1) for r in rows))
    by = {c: {r['id']: r for r in rows if r['cond'] == c} for c in conds}
    ids = sorted(set(r['id'] for r in rows))
    L = [f"# 결과 분석 · {a.label}", '', f"문항 {len(ids)}, 부트스트랩 재표집 {a.n}회(고정 씨앗 {a.seed}), 구간은 95%.", '']
    L += ['## 조건별 정답률과 95% 신뢰구간', '', '| 조건 | 정답률 | 95% 구간 | 평균 입력 길이(자) | 평균 응답 시간(초) |', '|---|---|---|---|---|']
    for c in conds:
        v = [by[c][i]['correct'] for i in ids if i in by[c]]
        lo, hi = boot_ci(v, a.n, a.seed)
        ch = sum(by[c][i]['chars'] for i in ids if i in by[c]) / len(v); sec = sum(by[c][i]['secs'] for i in ids if i in by[c]) / len(v)
        L.append(f"| {c} | {sum(v) / len(v) * 100:.1f}% | [{lo * 100:.1f}, {hi * 100:.1f}] | {ch:,.0f} | {sec:.1f} |")
    L += ['', '## 조건 간 대응 비교(같은 문항에서 한쪽만 맞춘 수)', '', '| 비교 | 앞만 정답 | 뒤만 정답 | 둘 다 정답 | 둘 다 오답 | 차이의 95% 구간(%p) |', '|---|---|---|---|---|---|']
    for i in range(len(conds)):
        for j in range(i + 1, len(conds)):
            x, y = conds[i], conds[j]
            pair = [(by[x][k]['correct'], by[y][k]['correct']) for k in ids if k in by[x] and k in by[y]]
            d = [p - q for p, q in pair]; lo, hi = boot_ci(d, a.n, a.seed)
            L.append(f"| {x} 대 {y} | {sum(1 for p, q in pair if p and not q)} | {sum(1 for p, q in pair if q and not p)} | {sum(1 for p, q in pair if p and q)} | {sum(1 for p, q in pair if not p and not q)} | [{lo * 100:+.1f}, {hi * 100:+.1f}] |")
    L += ['', '## 질문 종류별 정답률', '', '| 종류 | 문항 | ' + ' | '.join(conds) + ' |', '|---|---|' + '---|' * len(conds)]
    types = list(collections.OrderedDict((by[conds[0]][i]['type'], 1) for i in ids))
    for t in types:
        sub = [i for i in ids if by[conds[0]][i]['type'] == t]
        L.append(f"| {t} | {len(sub)} | " + ' | '.join(f"{sum(by[c][i]['correct'] for i in sub) / len(sub) * 100:.0f}%" for c in conds) + ' |')
    L += ['', '## 오답 유형(조건별)', '', '| 유형 | ' + ' | '.join(conds) + ' |', '|---|' + '---|' * len(conds)]
    kinds = ['자료에 없음', '다른 값', '긴 응답(설명 포함)', '빈 응답']
    cnt = {c: collections.Counter(kind_of(by[c][i]) for i in ids) for c in conds}
    for k in kinds:
        L.append(f"| {k} | " + ' | '.join(str(cnt[c][k]) for c in conds) + ' |')
    L += ['', '## 자료별 오답 유형(full 조건)', '', '| 자료 | 문항 | 정답 | 자료에 없음 | 다른 값 | 긴 응답 |', '|---|---|---|---|---|---|']
    g = collections.OrderedDict()
    for i in ids:
        g.setdefault(GROUP.get(by['full'][i]['doc'], by['full'][i]['doc']), []).append(kind_of(by['full'][i]))
    for name, ks in g.items():
        c = collections.Counter(ks)
        L.append(f"| {name} | {len(ks)} | {c['정답']} | {c['자료에 없음']} | {c['다른 값']} | {c['긴 응답(설명 포함)']} |")
    out = os.path.join(HERE, 'results', a.label + '-analysis.md')
    open(out, 'w', encoding='utf-8').write('\n'.join(L) + '\n'); print(out); print('\n'.join(L[:12]))

if __name__ == '__main__':
    main()
