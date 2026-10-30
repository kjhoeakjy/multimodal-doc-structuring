"""질문마다 세 조건의 문맥을 만든다: ocr(문자 인식 결과를 읽는 순서로 이어 붙인 텍스트), full(전체 직렬화), retrieved(부분 그래프 또는 질문어 일치 줄)."""
import os, sys, json, re, collections
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'app'))
import pipeline as pl
from prepare_docs import catalog
WORD = re.compile(r'[A-Za-z0-9가-힣][A-Za-z0-9가-힣./\-]*')

def ocr_text(R, d):
    """문자 상자를 줄로 묶어 위에서 아래, 왼쪽에서 오른쪽으로 이어 붙임(구조 없음)."""
    texts = R.get('texts') or []
    if not texts and os.path.exists(os.path.join(d, 'graph.json')):      # 벡터 도면: SVG 문자(좌표 mm)
        g = json.load(open(os.path.join(d, 'graph.json'), encoding='utf-8'))
        texts = [dict(text=l['text'], box=[v * 10 for v in l['bbox']]) for l in g.get('labels', [])]
    if not texts:
        return ''
    k = R['view']['mm_per_px'] if R.get('view') else 0.1
    lines = pl.text_lines([dict(text=t['text'], box=[int(v) for v in t['box']]) for t in texts], k)
    return '\n'.join(l['text'] for l in lines)

def retrieve(R, d, q, k=18):
    serial = R.get('serial') or []
    out = []
    if os.path.exists(os.path.join(d, 'graph.json')) and q.get('focus'):
        g = json.load(open(os.path.join(d, 'graph.json'), encoding='utf-8'))
        sg = pl.subgraph(g, q['focus'], depth=2)
        if sg.get('found'):
            out += sg['lines']
    toks = set(t.lower() for t in WORD.findall(q['question'] + ' ' + (q.get('focus') or '')) if len(t) >= 2)
    scored = []
    for i, line in enumerate(serial):
        lt = set(t.lower() for t in WORD.findall(line))
        sc = len(toks & lt) + (3 if q.get('focus') and q['focus'].lower() in line.lower() else 0)
        if sc > 0:
            scored.append((sc, i, line))
    scored.sort(key=lambda x: (-x[0], x[1]))
    hits = [l for _, _, l in scored[:k]]
    # 표 행이 걸리면 그 표의 머리글 행(최대 3줄)을 앞에 붙임
    heads = []
    for h in hits:
        m = re.match(r'^(t\d+) 행(\d+):', h)
        if m:
            for l in serial:
                if re.match(rf'^{m.group(1)} 행[0-2]:', l) and l not in hits and l not in heads:
                    heads.append(l)
    hits = heads + hits
    head = [l for l in serial[:1]]
    return '\n'.join(head + out + ['# 질문어와 겹치는 줄'] + hits) if (out or hits) else '\n'.join(serial[:k])

def main():
    cat = catalog(); Q = json.load(open(os.path.join(HERE, 'questions.json'), encoding='utf-8'))
    cache = {}
    ctx = {}
    for q in Q:
        d = cat[q['doc']]['dir']
        if q['doc'] not in cache:
            R = json.load(open(os.path.join(d, 'result.json'), encoding='utf-8'))
            cache[q['doc']] = dict(R=R, ocr=ocr_text(R, d), full='\n'.join(R.get('serial') or []))
        c = cache[q['doc']]
        ctx[q['id']] = dict(ocr=c['ocr'], full=c['full'], retrieved=retrieve(c['R'], d, q))
    json.dump(ctx, open(os.path.join(HERE, 'contexts.json'), 'w'), ensure_ascii=False)
    sizes = collections.defaultdict(list)
    for qid, c in ctx.items():
        for cond, t in c.items():
            sizes[cond].append(len(t))
    print({k: (round(sum(v) / len(v)), max(v)) for k, v in sizes.items()}, '문자 수 평균·최대')

if __name__ == '__main__':
    main()
