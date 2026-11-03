"""오답 원인 분류. 오류 통제 실험 결과(results/<결과 이름>.jsonl)의 오답을 문맥과 대조해 원인을 나눈다.
  기준 문자 손실  질문의 기준 요소(장비 태그·라인 번호·계기 번호)가 문맥에 없음(문자 오독 또는 요소 누락)
  답 문자 손실    기준 요소는 있으나 정답 문자가 문맥 어디에도 없음
  귀속 오류       정답 문자가 문맥에 있으나 기준 요소의 줄(또는 장비 간 연결 줄)에 없음(다른 요소에 붙음)
  연결 오류       연결 질문에서 기준 장비의 도달 집합이 정답과 다름
  모델 오류       근거가 문맥에 그대로 있는데 틀림
사용: python diagnose_real.py <결과 이름> [--settings ^real] [--cond full]
결과: results/<결과 이름>-diagnose.md"""
import os, sys, re, json, argparse, collections
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from run_qa import norm

def lines_with(ctx, key):
    pat = re.compile(r'(?<![A-Za-z0-9])' + re.escape(key) + r'(?![A-Za-z0-9])')
    return [l for l in ctx.split('\n') if pat.search(l)]

def has(text, a):
    a = norm(a)
    if re.fullmatch(r'[\d.]+', a):
        return re.search(r'(?<![\d.])' + re.escape(a) + r'(?![\d.])', norm(text)) is not None
    return re.search(r'(?<![a-z0-9가-힣])' + re.escape(a) + r'(?![a-z0-9가-힣])', norm(text)) is not None

def reach_line(ctx, tag):
    for l in ctx.split('\n'):
        if l.startswith(tag + ' →'):
            return l
    return None

def classify(q, ctx):
    focus = q.get('focus') or ''
    if q['type'] == '계기':
        focus = q['question'].split('계기 번호 ')[1].split('의')[0] if '계기 번호 ' in q['question'] else focus
    fl = lines_with(ctx, focus) if focus else []
    if focus and not fl:
        return '기준 문자 손실'
    if q['type'] == '연결':
        rl = reach_line(ctx, focus)
        if rl is None:
            return '연결 오류'
        got = set(re.findall(r'[A-Z]{1,2}\d{4}', rl.split('→')[1]))
        return '모델 오류' if got == set(q['answers']) else '연결 오류'
    if q['type'] == '개수':
        m = [re.search(r'접속구=([^ ]+)', l) for l in fl]
        n = max((len(x.group(1).split(',')) for x in m if x), default=None)
        return '모델 오류' if n is not None and str(n) in q['answers'] else '귀속 오류'
    anywhere = any(has(ctx, a) for a in q['answers'])
    on_focus = any(has(l, a) for l in fl for a in q['answers'])
    if on_focus:
        return '모델 오류'
    return '귀속 오류' if anywhere else '답 문자 손실'

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('label'); ap.add_argument('--settings', default='^real'); ap.add_argument('--cond', default='full')
    a = ap.parse_args()
    Q = {q['id']: q for q in json.load(open(os.path.join(HERE, 'questions.json'), encoding='utf-8'))}
    N = json.load(open(os.path.join(HERE, 'noise', 'contexts.json'), encoding='utf-8'))
    rows = [json.loads(l) for l in open(os.path.join(HERE, 'results', f'{a.label}.jsonl'), encoding='utf-8')]
    rows = [r for r in rows if r['cond'] == a.cond and re.search(a.settings, r['setting'])]
    by = collections.defaultdict(lambda: collections.Counter()); detail = collections.defaultdict(list)
    for r in rows:
        q = Q[r['id']]; k = r['setting']
        if r['correct']:
            by[k]['정답'] += 1; continue
        c = classify(q, N['contexts'][k][a.cond])
        by[k][c] += 1; detail[k].append((q['id'], q['type'], c, q['answers'], (r['response'] or '')[:40]))
    cats = ['정답', '기준 문자 손실', '답 문자 손실', '귀속 오류', '연결 오류', '모델 오류']
    L = [f'# 오답 원인 분류 · {a.label} · {a.cond}', '', '문맥과 대조해 자동 분류. 모델 오류는 근거 줄이 문맥에 그대로 있는 오답.', '',
         '| 설정 | ' + ' | '.join(cats) + ' |', '|---|' + '---|' * len(cats)]
    for k in sorted(by):
        L.append(f'| {k} | ' + ' | '.join(str(by[k][c]) for c in cats) + ' |')
    for k in sorted(detail):
        L += ['', f'## {k}', '', '| 문항 | 종류 | 원인 | 정답 | 응답 |', '|---|---|---|---|---|']
        L += [f'| {i} | {t} | {c} | {", ".join(ans)} | {resp} |' for i, t, c, ans, resp in detail[k]]
    out = os.path.join(HERE, 'results', f'{a.label}-diagnose.md')
    open(out, 'w', encoding='utf-8').write('\n'.join(L) + '\n'); print('\n'.join(L[:6 + len(by)]))

if __name__ == '__main__':
    main()
