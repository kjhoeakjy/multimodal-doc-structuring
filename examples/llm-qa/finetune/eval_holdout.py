"""make_holdout.py 묶음을 평가한다. hf는 eval_lora.py와 같은 생성(탐욕, 최대 120 토큰), ollama는 run_qa.py와 같은 호출.
사용: python finetune/eval_holdout.py --backend hf --model <HF 모델 id> [--adapter finetune/adapter] --label <결과 이름> [--file finetune/holdout.json] [--limit N]
      python finetune/eval_holdout.py --backend ollama --model <모델> --label <결과 이름>
결과: results/<label>.jsonl(이어서 실행 가능), results/<label>.md"""
import os, sys, json, time, argparse
HERE = os.path.dirname(os.path.abspath(__file__)); QA = os.path.abspath(os.path.join(HERE, '..'))
sys.path.insert(0, QA)
from run_qa import SYSTEM, ask_ollama, score, NONE

def score_any(q, resp):
    if q.get('kind') == 'none':
        return int(bool(resp) and bool(NONE.search(resp)))
    return score(q, resp)

def report(label, done, n_docs):
    conds = sorted({k[3] for k in done}); sets = list(dict.fromkeys(k[2] for k in done))
    def pct(rows):
        return f"{100 * sum(r['correct'] for r in rows) / len(rows):.1f}% ({sum(r['correct'] for r in rows)}/{len(rows)})" if rows else '-'
    R = list(done.values()); conn = ('도달여부', '라인도달', '연결수', '경로', '라인경로', '연결')
    L = [f'# 미학습 도면 평가 · {label}', '', f'PID2Graph OPEN100 {n_docs}개 도면(위상 실제, 문자 합성). 답은 오류를 넣기 전 그래프 기준.', '']
    for title, f in (('전체', lambda r: True), ('연결 의존 문항', lambda r: r['type'] in conn), ('그 밖의 문항', lambda r: r['type'] not in conn)):
        L += [f'## {title}', '', '| 설정 | ' + ' | '.join(conds) + ' |', '|---|' + '---|' * len(conds)]
        L += [f"| {s} | " + ' | '.join(pct([r for r in R if r['setting'] == s and r['cond'] == c and f(r)]) for c in conds) + ' |' for s in sets] + ['']
    types = sorted({r['type'] for r in R})
    L += ['## 문항 종류별(오류 없음)', '', '| 종류 | ' + ' | '.join(conds) + ' |', '|---|' + '---|' * len(conds)]
    L += [f"| {t} | " + ' | '.join(pct([r for r in R if r['type'] == t and r['cond'] == c and r['setting'] == sets[0]]) for c in conds) + ' |' for t in types]
    text = '\n'.join(L) + '\n'
    open(os.path.join(QA, 'results', f'{label}.md'), 'w', encoding='utf-8').write(text); print(text)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--backend', default='hf', choices=('hf', 'ollama')); ap.add_argument('--model', required=True)
    ap.add_argument('--adapter', default=''); ap.add_argument('--label', required=True); ap.add_argument('--file', default=os.path.join(HERE, 'holdout.json'))
    ap.add_argument('--conds', default='full,paths'); ap.add_argument('--batch', type=int, default=4); ap.add_argument('--max-new', type=int, default=120); ap.add_argument('--limit', type=int, default=0)
    a = ap.parse_args()
    H = json.load(open(a.file, encoding='utf-8')); conds = a.conds.split(',')
    todo, done = [], {}
    out = os.path.join(QA, 'results', f'{a.label}.jsonl')
    if os.path.exists(out):
        for line in open(out, encoding='utf-8'):
            r = json.loads(line); done[(r['doc'], r['id'], r['setting'], r['cond'])] = r
    for d in H['docs']:
        for s in H['settings']:
            for c in conds:
                for q in d['questions']:
                    if (d['doc'], q['id'], s, c) not in done:
                        todo.append((d, q, s, c))
    if a.limit:
        todo = todo[:a.limit]
    print(f"도면 {len(H['docs'])}, 남은 호출 {len(todo)}", flush=True)
    tok = model = torch = None
    if a.backend == 'hf':
        import torch
        from transformers import AutoTokenizer, AutoModelForCausalLM
        tok = AutoTokenizer.from_pretrained(a.model); tok.pad_token = tok.pad_token or tok.eos_token; tok.padding_side = 'left'
        model = AutoModelForCausalLM.from_pretrained(a.model, dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32, device_map='auto')
        if a.adapter:
            from peft import PeftModel
            model = PeftModel.from_pretrained(model, a.adapter)
        model.eval()
    def ask_batch(chunk):
        users = [f"[자료]\n{d['contexts'][s][c]}\n\n[질문]\n{q['question']}" for d, q, s, c in chunk]
        if a.backend == 'ollama':
            return users, [ask_ollama(a.model, SYSTEM, u) for u in users]
        prompts = [tok.apply_chat_template([dict(role='system', content=SYSTEM), dict(role='user', content=u)], tokenize=False, add_generation_prompt=True) for u in users]
        enc = tok(prompts, return_tensors='pt', padding=True, add_special_tokens=False).to(model.device)
        with torch.no_grad():
            gen = model.generate(**enc, max_new_tokens=a.max_new, do_sample=False, pad_token_id=tok.pad_token_id)
        return users, [tok.decode(row, skip_special_tokens=True).strip() for row in gen[:, enc['input_ids'].shape[1]:]]
    bs = a.batch if a.backend == 'hf' else 1
    with open(out, 'a', encoding='utf-8') as f:
        for i in range(0, len(todo), bs):
            chunk = todo[i:i + bs]; t0 = time.time()
            users, resps = ask_batch(chunk)
            secs = round((time.time() - t0) / len(chunk), 2)
            for (d, q, s, c), u, resp in zip(chunk, users, resps):
                r = dict(doc=d['doc'], id=q['id'], type=q['type'], setting=s, cond=c, response=resp, correct=score_any(q, resp), secs=secs, chars=len(u))
                f.write(json.dumps(r, ensure_ascii=False) + '\n'); done[(d['doc'], q['id'], s, c)] = r
            f.flush()
            if (i // bs) % 25 == 0:
                print(i, chunk[0][0]['doc'], chunk[0][2], chunk[0][3], repr(resps[0])[:50], flush=True)
    report(a.label, done, len(H['docs']))

if __name__ == '__main__':
    main()
