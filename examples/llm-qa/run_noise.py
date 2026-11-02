"""추출 오류 통제 실험 실행. noise.py가 만든 문맥(오류 종류·비율·씨앗별)으로 C01 벡터 43문항에 답하게 하고 정답률을 잰다.
사용: python run_noise.py --backend ollama --model <모델 이름> --label <결과 이름> [--conds full,relations] [--seeds 0]
      --backend api 는 run_qa.py와 같은 환경 변수(LLM_API_BASE, LLM_API_KEY)를 씀
결과: results/<결과 이름>.jsonl(이어서 실행 가능), results/<결과 이름>.md(오류 종류·비율별 정답률과 실제 재현율·정밀도)"""
import os, sys, json, re, time, argparse, collections
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from run_qa import SYSTEM, ask_api, ask_ollama, score

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--backend', default='ollama'); ap.add_argument('--model', required=True); ap.add_argument('--label', required=True)
    ap.add_argument('--conds', default='full,relations'); ap.add_argument('--seeds', default='0,1,2')
    a = ap.parse_args()
    N = json.load(open(os.path.join(HERE, 'noise', 'contexts.json'), encoding='utf-8'))
    Q = {q['id']: q for q in json.load(open(os.path.join(HERE, 'questions.json'), encoding='utf-8'))}
    qs = [Q[i] for i in N['questions']]
    seeds = {f"s{s}" for s in a.seeds.split(',')}
    keys = [k for k in N['contexts'] if k.split('-')[-1] in seeds or k.startswith('none')]
    conds = a.conds.split(',')
    out = os.path.join(HERE, 'results', f'{a.label}.jsonl')
    done = {}
    if os.path.exists(out):
        for line in open(out, encoding='utf-8'):
            r = json.loads(line); done[(r['id'], r['setting'], r['cond'])] = r
    todo = [(q, k, c) for k in keys for c in conds for q in qs if (q['id'], k, c) not in done]
    print(f'설정 {len(keys)} × 조건 {len(conds)} × 문항 {len(qs)}, 남은 호출 {len(todo)}')
    ask = ask_api if a.backend == 'api' else ask_ollama
    with open(out, 'a', encoding='utf-8') as f:
        for i, (q, k, c) in enumerate(todo):
            user = f"[자료]\n{N['contexts'][k][c]}\n\n[질문]\n{q['question']}"
            t0 = time.time()
            try:
                resp = ask(a.model, SYSTEM, user)
            except Exception as e:
                resp = None; print('오류', q['id'], k, c, str(e)[:120])
            r = dict(id=q['id'], type=q['type'], setting=k, cond=c, response=resp, correct=score(q, resp), secs=round(time.time() - t0, 1), chars=len(user))
            f.write(json.dumps(r, ensure_ascii=False) + '\n'); f.flush(); done[(q['id'], k, c)] = r
            if i % 20 == 0:
                print(i, k, c, repr(resp)[:50], r['correct'], flush=True)
    report(a.label, done, conds)

def report(label, done, conds):
    gm = {}
    gp = os.path.join(HERE, 'noise', 'graphs.md')
    for line in open(gp, encoding='utf-8'):
        m = re.match(r'^\| (\S+) \| ([\d.]+) \| ([\d.]+) \|', line)
        if m:
            gm[m.group(1)] = (float(m.group(2)), float(m.group(3)))
    by = collections.defaultdict(list)
    for (qid, k, c), r in done.items():
        kind, p = k.split('-')[0], k.split('-')[1]
        by[(kind, p, c)].append((r['correct'], k))
    L = [f'# 추출 오류 통제 실험 · {label}', '', 'C01 벡터 43문항. 비율은 넣은 오류의 비율, 재현율·정밀도는 DEXPI XML 대조 실측(씨앗 평균).', '',
         '| 오류 | 비율 | 재현율 | 정밀도 | ' + ' | '.join(conds) + ' |', '|---|---|---|---|' + '---|' * len(conds)]
    for kind in ('none', 'drop', 'add', 'label'):
        for p in sorted({k[1] for k in by if k[0] == kind}, key=float):
            ks = {k for c in conds for _, k in by.get((kind, p, c), [])}
            rr = [gm[k][0] for k in ks if k in gm]; pp = [gm[k][1] for k in ks if k in gm]
            cells = []
            for c in conds:
                v = [x for x, _ in by.get((kind, p, c), [])]
                cells.append(f"{sum(v) / len(v) * 100:.1f}% ({len(v)})" if v else '-')
            L.append(f"| {kind} | {p} | {sum(rr) / len(rr):.2f} | {sum(pp) / len(pp):.2f} | " + ' | '.join(cells) + ' |' if rr else f"| {kind} | {p} | - | - | " + ' | '.join(cells) + ' |')
    open(os.path.join(HERE, 'results', f'{label}.md'), 'w', encoding='utf-8').write('\n'.join(L) + '\n'); print('\n'.join(L))

if __name__ == '__main__':
    main()
