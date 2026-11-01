"""질문마다 입력 조건별 문맥을 만든다.
ocr: 문자 인식 결과를 읽는 순서로 이어 붙인 텍스트(구조 없음)
objects: 같은 추출 결과의 요소·속성 목록. 연결·지시 등 관계 줄을 뺌(선의 라벨은 양 끝 없이 남김)
relations: objects + 분기점·연결(관계 그래프). 장비 간 도달 집합은 넣지 않음
full: relations + 장비 간 배관 연결(전처리에서 미리 계산한 도달 집합). 기존 전체 직렬화와 같음
both: ocr + full(질문별 선택 규칙에서 관계 단서가 없는 도면 질문에 씀)
retrieved: 질문 문장에 실제로 적힌 식별자로 찾은 부분 그래프와 질문어 일치 줄
문항 파일의 focus·type·answers는 문맥 생성에 쓰지 않는다(정답 누출 방지)."""
import os, sys, json, re, collections
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'app'))
import pipeline as pl
import serialize as sz
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

GRAPH_DROP = {'objects': ('## 분기점', '## 연결', '## 장비 간'), 'relations': ('## 장비 간',)}
PAGE_DROP = {'objects': ('## 관계', '## 지시선'), 'relations': ()}
RUN_LABEL = re.compile(r' 라벨=(.*?)(?= 간격=| 경로=|$)')

def sections(serial):
    """직렬화 줄을 '## ' 구획 단위로 나눔. 첫 구획(머리 줄)은 이름 ''."""
    out, cur = [], ('', [])
    for line in serial:
        if line.startswith('## '):
            out.append(cur); cur = (line, [])
        else:
            cur[1].append(line)
    out.append(cur)
    return out

def ablate(serial, cond, is_graph):
    """같은 추출 결과에서 관계 줄을 단계적으로 뺀 문맥. full은 원래 직렬화 그대로."""
    if cond == 'full':
        return '\n'.join(serial)
    drop = (GRAPH_DROP if is_graph else PAGE_DROP)[cond]
    L, labels = [], []
    for head, body in sections(serial):
        if head and head.startswith(drop):
            if is_graph and cond == 'objects' and head.startswith('## 연결'):
                for b in body:      # 선 라벨은 속성으로 남기되 양 끝 요소·경로는 뺌
                    m = RUN_LABEL.search(b)
                    if m:
                        labels.append(m.group(1).strip())
            continue
        L += ([head] if head else []) + body
    if labels:
        L += ['## 선 라벨 (연결 대상 정보 없음)'] + labels
    return '\n'.join(L)

def question_keys(g, question):
    """질문 문장에 그대로 적힌 그래프 요소의 이름·라벨(영숫자 경계 기준, 질문 안 위치 순). 문항의 focus 필드는 쓰지 않음."""
    names = set()
    for n in g['nodes']:
        for t in [sz.name_of(n)] + list(n['texts']):
            if len(t) >= 2 and not re.match(r'^(\d{1,3}|n\d+|j\d+)$', t):
                names.add(t)
    hits = []
    for t in names:
        m = re.search(r'(?<![A-Za-z0-9.])' + re.escape(t) + r'(?![A-Za-z0-9])', question)
        if m:
            hits.append((m.start(), -len(t), t))
    keys = []
    for pos, _, t in sorted(hits):
        if not any(pos >= p and pos < p + len(k) for p, k in keys):    # 더 긴 이름 안에 든 짧은 이름은 뺌
            keys.append((pos, t))
    return [t for _, t in keys]

def retrieve(R, d, q, k=18):
    serial = R.get('serial') or []
    out = []
    if os.path.exists(os.path.join(d, 'graph.json')):
        g = json.load(open(os.path.join(d, 'graph.json'), encoding='utf-8'))
        for key in question_keys(g, q['question'])[:2]:
            sg = pl.subgraph(g, key, depth=2)
            if sg.get('found'):
                out += sg['lines']
    toks = set(t.lower() for t in WORD.findall(q['question']) if len(t) >= 2)
    scored = []
    for i, line in enumerate(serial):
        lt = set(t.lower() for t in WORD.findall(line))
        sc = len(toks & lt)
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
            serial = R.get('serial') or []; is_graph = cat[q['doc']]['kind'] == 'graph'
            cache[q['doc']] = dict(R=R, ocr=ocr_text(R, d), **{c: ablate(serial, c, is_graph) for c in ('objects', 'relations', 'full')})
        c = cache[q['doc']]
        ctx[q['id']] = dict(ocr=c['ocr'], objects=c['objects'], relations=c['relations'], full=c['full'], retrieved=retrieve(c['R'], d, q),
                         both='# 문자 인식 텍스트\n' + c['ocr'] + '\n\n' + c['full'])
    json.dump(ctx, open(os.path.join(HERE, 'contexts.json'), 'w'), ensure_ascii=False)
    sizes = collections.defaultdict(list)
    for qid, c in ctx.items():
        for cond, t in c.items():
            sizes[cond].append(len(t))
    print({k: (round(sum(v) / len(v)), max(v)) for k, v in sizes.items()}, '문자 수 평균·최대')

if __name__ == '__main__':
    main()
