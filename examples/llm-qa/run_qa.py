"""세 조건(ocr / full / retrieved)으로 LLM에 질문하고 정답률을 잰다.
사용: python run_qa.py --backend api --model <모델 id> --label <결과 이름>   (OpenAI 호환 API, 환경 변수 LLM_API_BASE·LLM_API_KEY)
      python run_qa.py --backend ollama --model <모델 이름>                   (로컬 http://127.0.0.1:11434, 공개 가중치 모델)
      --conds ocr,full,retrieved --limit N --docs pid-standard-vector,...  --dry(호출 없이 프롬프트 수만 셈)
결과: results/<label>.jsonl(문항·조건별 응답, 이어서 실행 가능), results/<label>.md(정답률 표). label 기본값은 모델 id"""
import os, sys, json, re, time, argparse, collections, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__))
SYSTEM = ("주어진 자료만 근거로 답한다. 답은 값·태그·짧은 구만 쓰고 설명은 붙이지 않는다. 여러 개면 쉼표로 나열한다. "
          "자료에 근거가 없으면 '자료에 없음'이라고만 답한다. Answer using only the given material; output only the value, tag or short phrase.")

def ask_api(model, system, user, max_tokens=120):
    """OpenAI 호환 chat/completions 형식의 외부 API. 주소와 키는 환경 변수 LLM_API_BASE, LLM_API_KEY. 공급사 이름은 코드에 두지 않음."""
    base = os.environ.get('LLM_API_BASE', '').rstrip('/'); key = os.environ.get('LLM_API_KEY', '')
    if not base or not key:
        raise RuntimeError('환경 변수 LLM_API_BASE, LLM_API_KEY 필요')
    body = json.dumps(dict(model=model, max_tokens=max_tokens, messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])).encode()
    req = urllib.request.Request(base + '/chat/completions', data=body, headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key})
    r = json.loads(urllib.request.urlopen(req, timeout=120).read())
    return (r['choices'][0]['message']['content'] or '').strip()

def ask_ollama(model, system, user, max_tokens=120):
    body = json.dumps(dict(model=model, system=system, prompt=user, stream=False, options=dict(temperature=0, num_predict=max_tokens, num_ctx=8192))).encode()
    req = urllib.request.Request('http://127.0.0.1:11434/api/generate', data=body, headers={'Content-Type': 'application/json'})
    return json.loads(urllib.request.urlopen(req, timeout=600).read())['response'].strip()

def norm(s):
    s = s.lower().replace('ø', '').replace('⌀', '').replace('–', '-').replace('~', '-').replace(',', '').replace('·', ' ')
    return re.sub(r'\s+', '', s)

TAG = re.compile(r'\b[A-Z]{1,2}\s?\d{3,5}\b')
def score(q, resp):
    if resp is None:
        return 0
    r = norm(resp)
    if q['kind'] == 'set':
        want = set(norm(a) for a in q['answers'])
        got = set(norm(t) for t in TAG.findall(resp)) - {norm(q.get('focus') or '')}   # 질문에 든 기준 태그는 답으로 세지 않음
        return 1 if got == want else 0
    return 1 if any(norm(a) and norm(a) in r for a in q['answers']) else 0

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--backend', default='api'); ap.add_argument('--model', required=True); ap.add_argument('--label', default='')
    ap.add_argument('--conds', default='ocr,full,retrieved'); ap.add_argument('--limit', type=int, default=0); ap.add_argument('--docs', default='')
    ap.add_argument('--dry', action='store_true'); ap.add_argument('--sleep', type=float, default=0.0)
    ap.add_argument('--rescore', action='store_true', help='저장된 응답을 다시 채점해 표만 다시 씀')
    a = ap.parse_args()
    Q = json.load(open(os.path.join(HERE, 'questions.json'), encoding='utf-8')); C = json.load(open(os.path.join(HERE, 'contexts.json'), encoding='utf-8'))
    if a.docs:
        keep = set(a.docs.split(',')); Q = [q for q in Q if q['doc'] in keep]
    if a.limit:
        Q = Q[:a.limit]
    conds = a.conds.split(',')
    os.makedirs(os.path.join(HERE, 'results'), exist_ok=True)
    tag = re.sub(r'[^A-Za-z0-9._-]+', '_', a.label or a.model)
    out_path = os.path.join(HERE, 'results', f'{tag}.jsonl')
    done = {}
    if os.path.exists(out_path):
        for line in open(out_path, encoding='utf-8'):
            r = json.loads(line); done[(r['id'], r['cond'])] = r
    if a.rescore:
        qmap = {q['id']: q for q in Q}
        for r in done.values():
            if r['id'] in qmap:
                r['correct'] = score(qmap[r['id']], r['response'])
        open(out_path, 'w', encoding='utf-8').write(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in done.values()))
        report(Q, conds, done, os.path.join(HERE, 'results', f'{tag}.md'), a.label or a.model); return
    ask = ask_api if a.backend == 'api' else ask_ollama
    todo = [(q, c) for q in Q for c in conds if (q['id'], c) not in done]
    print(f'문항 {len(Q)} × 조건 {len(conds)} = {len(Q) * len(conds)}, 남은 호출 {len(todo)}')
    if a.dry:
        return
    with open(out_path, 'a', encoding='utf-8') as f:
        for i, (q, c) in enumerate(todo):
            user = f"[자료]\n{C[q['id']][c]}\n\n[질문]\n{q['question']}"
            t0 = time.time()
            try:
                resp = ask(a.model, SYSTEM, user)
            except Exception as e:
                resp = None; print('오류', q['id'], c, str(e)[:120])
            r = dict(id=q['id'], doc=q['doc'], type=q['type'], cond=c, question=q['question'], answers=q['answers'], response=resp, correct=score(q, resp), secs=round(time.time() - t0, 1), chars=len(user))
            f.write(json.dumps(r, ensure_ascii=False) + '\n'); f.flush(); done[(q['id'], c)] = r
            if i % 20 == 0:
                print(i, q['doc'], c, repr(resp)[:60], r['correct'], flush=True)
            if a.sleep:
                time.sleep(a.sleep)
    report(Q, conds, done, os.path.join(HERE, 'results', f'{tag}.md'), a.label or a.model)

GROUP = {'pid-standard-vector': 'P&ID 벡터(C01)', 'pid-c02-vector': 'P&ID 벡터(C02·C03)', 'pid-c03-vector': 'P&ID 벡터(C02·C03)', 'pid-standard-200dpi': 'P&ID 래스터(C01 200 dpi)', 'pid-standard-scan': 'P&ID 래스터(C01 스캔)',
         'en-report-synthetic-vector': '보고서 PDF 글자 층', 'en-report-synthetic-scan150': '보고서 스캔(영문)', 'ko-report-synthetic': '보고서(한글)', 'ko-table-text-scan200': '표·본문 스캔(한글)',
         'mech-flange-synthetic-vector': '기계 도면 벡터', 'mech-flange-synthetic-200dpi': '기계 도면 래스터', 'faa-torque-table': 'FAA 토크 표', 'faa-torque-table-scan': 'FAA 토크 표 스캔', 'faa-bolt-table-illustrations': 'FAA 볼트 표', 'faa-text-page': 'FAA 본문 2단'}

def report(Q, conds, done, path, model):
    def acc(rows):
        rows = [r for r in rows if r]
        return f"{sum(r['correct'] for r in rows) / len(rows) * 100:.0f}% ({sum(r['correct'] for r in rows)}/{len(rows)})" if rows else '-'
    L = [f"# 질의응답 정답률 · 모델 {model}", '', f"문항 {len(Q)}, 조건: ocr=문자 인식 결과를 읽는 순서로 이어 붙인 텍스트, full=전체 직렬화(관계 그래프·표·문단), retrieved=질문 태그 기준 부분 그래프와 질문어 일치 줄.", '',
         '| 자료 | 문항 | ' + ' | '.join(conds) + ' |', '|---|---|' + '---|' * len(conds)]
    groups = collections.OrderedDict()
    for q in Q:
        groups.setdefault(GROUP.get(q['doc'], q['doc']), []).append(q)
    for g, qs in groups.items():
        L.append(f"| {g} | {len(qs)} | " + ' | '.join(acc([done.get((q['id'], c)) for q in qs]) for c in conds) + ' |')
    L.append(f"| 전체 | {len(Q)} | " + ' | '.join(acc([done.get((q['id'], c)) for q in Q]) for c in conds) + ' |')
    L += ['', '| 질문 종류 | 문항 | ' + ' | '.join(conds) + ' |', '|---|---|' + '---|' * len(conds)]
    types = collections.OrderedDict()
    for q in Q:
        types.setdefault(q['type'], []).append(q)
    for t, qs in types.items():
        L.append(f"| {t} | {len(qs)} | " + ' | '.join(acc([done.get((q['id'], c)) for q in qs]) for c in conds) + ' |')
    rows = [r for r in done.values()]
    L += ['', '| 조건 | 평균 입력 문자 수 | 평균 응답 시간(초) |', '|---|---|---|']
    for c in conds:
        rs = [r for r in rows if r['cond'] == c]
        if rs:
            L.append(f"| {c} | {sum(r['chars'] for r in rs) // len(rs)} | {sum(r['secs'] for r in rs) / len(rs):.1f} |")
    open(path, 'w', encoding='utf-8').write('\n'.join(L) + '\n'); print('\n'.join(L))

if __name__ == '__main__':
    main()
