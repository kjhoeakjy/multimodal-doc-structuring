"""HF 모델(기본 가중치 또는 LoRA 어댑터)을 run_noise.py와 같은 설정·문항으로 평가해 같은 형식의 결과(results/<label>.jsonl·.md)를 쓴다.
기본 가중치도 같은 코드로 다시 평가해야 Ollama 양자화 결과와 섞이지 않는다. 생성은 탐욕(temperature 0), 최대 120 토큰.
사용: python eval_lora.py --model <HF 모델 id> [--adapter adapter/] --label <결과 이름> [--conds full,paths] [--seeds 0] [--settings 정규식] [--qfile questions-conn.json] [--batch 4] [--4bit]
2×2 비교: 가중치(기본/LoRA) × 입력(full/paths). 설정은 --settings '^(none|drop|ocr|attr|mix)-(0|0.2|0.5)-|^add-0.5|^real' 처럼 대표 설정으로 줄여도 됨."""
import os, sys, json, re, time, argparse
HERE = os.path.dirname(os.path.abspath(__file__)); QA = os.path.abspath(os.path.join(HERE, '..'))
sys.path.insert(0, QA)
from run_qa import SYSTEM, score, NONE
from run_noise import report
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

def score_any(q, resp):
    if q.get('kind') == 'none':
        return int(bool(resp) and bool(NONE.search(resp)))
    return score(q, resp)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', required=True); ap.add_argument('--adapter', default=''); ap.add_argument('--label', required=True)
    ap.add_argument('--conds', default='full,paths'); ap.add_argument('--seeds', default='0'); ap.add_argument('--settings', default=''); ap.add_argument('--qfile', default='')
    ap.add_argument('--batch', type=int, default=4); ap.add_argument('--4bit', dest='q4', action='store_true'); ap.add_argument('--max-new', type=int, default=120)
    a = ap.parse_args()
    N = json.load(open(os.path.join(QA, 'noise', 'contexts.json'), encoding='utf-8'))
    if a.qfile:
        qs = [q for q in json.load(open(os.path.join(QA, a.qfile), encoding='utf-8')) if q['doc'] == N['doc']]
    else:
        Q = {q['id']: q for q in json.load(open(os.path.join(QA, 'questions.json'), encoding='utf-8'))}; qs = [Q[i] for i in N['questions']]
    seeds = {f"s{s}" for s in a.seeds.split(',')}
    keys = [k for k in N['contexts'] if k.split('-')[-1] in seeds or k.startswith('none')]
    if a.settings:
        keys = [k for k in keys if re.search(a.settings, k)]
    conds = a.conds.split(',')
    out = os.path.join(QA, 'results', f'{a.label}.jsonl'); done = {}
    if os.path.exists(out):
        for line in open(out, encoding='utf-8'):
            r = json.loads(line); done[(r['id'], r['setting'], r['cond'])] = r
    todo = [(q, k, c) for k in keys for c in conds for q in qs if (q['id'], k, c) not in done]
    print(f'설정 {len(keys)} × 조건 {len(conds)} × 문항 {len(qs)}, 남은 호출 {len(todo)}')
    tok = AutoTokenizer.from_pretrained(a.model); tok.pad_token = tok.pad_token or tok.eos_token; tok.padding_side = 'left'
    kw = dict(torch_dtype=torch.bfloat16, device_map='auto')
    if a.q4:
        from transformers import BitsAndBytesConfig
        kw['quantization_config'] = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4', bnb_4bit_compute_dtype=torch.bfloat16)
    model = AutoModelForCausalLM.from_pretrained(a.model, **kw)
    if a.adapter:
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, a.adapter)
    model.eval()
    with open(out, 'a', encoding='utf-8') as f:
        for i in range(0, len(todo), a.batch):
            chunk = todo[i:i + a.batch]
            users = [f"[자료]\n{N['contexts'][k][c]}\n\n[질문]\n{q['question']}" for q, k, c in chunk]
            prompts = [tok.apply_chat_template([dict(role='system', content=SYSTEM), dict(role='user', content=u)], tokenize=False, add_generation_prompt=True) for u in users]
            enc = tok(prompts, return_tensors='pt', padding=True, add_special_tokens=False).to(model.device)
            t0 = time.time()
            with torch.no_grad():
                gen = model.generate(**enc, max_new_tokens=a.max_new, do_sample=False, pad_token_id=tok.pad_token_id)
            secs = round((time.time() - t0) / len(chunk), 1)
            for (q, k, c), u, row in zip(chunk, users, gen[:, enc['input_ids'].shape[1]:]):
                resp = tok.decode(row, skip_special_tokens=True).strip()
                r = dict(id=q['id'], type=q['type'], setting=k, cond=c, response=resp, correct=score_any(q, resp), secs=secs, chars=len(u))
                f.write(json.dumps(r, ensure_ascii=False) + '\n'); done[(q['id'], k, c)] = r
            if (i // a.batch) % 10 == 0:
                print(i, chunk[0][1], chunk[0][2], repr(resp)[:50], r['correct'], flush=True); f.flush()
    report(a.label, done, conds, len(qs))

if __name__ == '__main__':
    main()
