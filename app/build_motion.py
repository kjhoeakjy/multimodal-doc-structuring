"""문서 종류별 대표 예시 한 건씩에서 그림의 요소가 텍스트 줄로 바뀌는 과정을 재생하는 정적 화면을 만든다.
실행: python app/build_motion.py [표본 폴더] [출력 html]   (기본: examples/sample-inputs → app/문서-구조화-과정.html)

예시마다 처리 순서대로 '동작' 목록을 만든다. 동작 하나는 그림 위의 요소 하나(상자·선·점)와
그 요소에서 나오는 직렬화 텍스트 한 줄의 짝이다. 요소에 붙는 문자(라벨·칸·낱말)는 부속 상자로 둔다.
"""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from build_page import view_image, jpeg_uri, add_relations

# 종류별 대표 예시: (파일, 종류 이름, 출처)
EXAMPLES = [
    ('pid-standard-vector.svg', '벡터 P&ID', 'DEXPI 공개 예제 C01, SVG'),
    ('pid-standard-scan.png', '스캔 P&ID', 'DEXPI C01을 200 dpi로 그려 회전·잡음·JPEG 열화'),
    ('mech-iso-tolerance-real.jpg', '기계 도면', 'NIST 공개 치수·공차 도면, 스캔'),
    ('faa-bolt-table-illustrations.jpg', '표·삽화 쪽', 'FAA AC 43.13-1B 볼트 표, 스캔'),
    ('faa-text-page.png', '2단 본문 쪽', 'FAA AC 43.13-1B 본문, 스캔'),
    ('en-report-synthetic-vector.pdf', '글자 층 PDF 보고서', '합성 보고서, PDF 글자 층'),
    ('ko-table-text-scan200.jpg', '한글 표·본문 스캔', '합성 한글 문서, 200 dpi 스캔'),
    ('photo-rocket-launch.jpg', '사진', '공개 사진(scikit-image 예제 데이터)'),
]
MAX_ROWS = 5        # 표마다 재생하는 행 수 상한
MAX_SUB = 40        # 요소에 붙는 부속 상자 상한

def px_box(b, k):
    return [round(v / k, 1) for v in b]

def px_pts(coords, k):
    return [[round(x / k, 1), round(y / k, 1)] for x, y in coords]

def center(b):
    return ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)

def inside(b, box, pad):
    cx, cy = center(b)
    return box[0] - pad <= cx <= box[2] + pad and box[1] - pad <= cy <= box[3] + pad

class Serial:
    """직렬화 줄을 절(## 머리글)별로 나누어 id로 찾음."""
    def __init__(self, lines):
        self.sections, self.order, self.title = {}, [], ''
        cur = ''
        for l in lines:
            if l.startswith('## '):
                cur = l; self.order.append(cur); self.sections.setdefault(cur, [])
            elif l.startswith('# '):
                self.title = l
            elif l.strip():
                self.sections.setdefault(cur, []).append(l)
    def head(self, word):
        for h in self.order:
            if word in h:
                return h
        return '## ' + word
    def find(self, word, prefix):
        for l in self.sections.get(self.head(word), []):
            if l.startswith(prefix):
                return l
        return None

def build(name, kind_name, source, folder):
    stem = os.path.splitext(name)[0]
    d = os.path.join(folder, 'output', stem)
    R = json.load(open(os.path.join(d, 'result.json'), encoding='utf-8'))
    img = view_image(os.path.join(folder, 'input', name), R)
    vh, vw = img.shape
    R['view']['w'], R['view']['h'] = vw, vh
    if not R.get('nodes') and R['kind'] in ('page', 'illustration', 'photo'):
        add_relations(R, img, d)
    k = R['view']['mm_per_px']
    kind = R['kind']
    det = R.get('detect', {}); times = R.get('times', {})
    nodes, runs, juncs = R.get('nodes', []), R.get('runs', []), R.get('junctions', [])
    nid = {n['id']: n for n in nodes}
    S = Serial(R.get('serial', []))
    pad = 8 / k   # 문자 귀속 탐색 여유(8 mm)

    # 문자 모음: (문자, 화면 좌표 상자)
    if kind == 'vector':
        labels = R.get('labels') or json.load(open(os.path.join(d, 'graph.json'), encoding='utf-8')).get('labels', [])
        pool = [(l['text'], px_box(l['bbox'], k)) for l in labels]
        text_line = f"문자 {len(pool)}개, 위치와 각도를 글자 층에서 그대로 읽음"
        text_title, text_desc = '문자 좌표', 'SVG 문자 요소의 위치·각도를 읽음. 문자 인식 없음'
    else:
        texts = R.get('texts') or []
        pool = [(t['text'], [int(v) for v in t['box']]) for t in texts]
        if texts and all(t.get('conf', 0) >= 0.999 for t in texts):
            text_line = f"문자 {len(pool)}개, 글자 층의 낱말 좌표"
            text_title, text_desc = '글자 층 좌표', 'PDF 글자 층의 낱말 좌표를 읽음. 문자 인식 없음'
        else:
            t_ocr = times.get('문자 인식')
            text_line = f"문자 인식 {len(pool)}개" + (f", {t_ocr:.0f}초(CPU)" if t_ocr else '')
            text_title, text_desc = '문자 인식', '기울기 보정 후 CPU 문자 인식. 상자·문자·신뢰도를 얻음'

    def subs(words, box, cap=MAX_SUB):
        """요소의 문자 목록에 해당하는 문자 상자를 요소 주변에서 찾음."""
        want = {}
        for w in words:
            for piece in str(w).split('|'):
                want[piece.strip()] = want.get(piece.strip(), 0) + 1
        out = []
        for t, b in pool:
            if want.get(t, 0) > 0 and inside(b, box, pad):
                out.append(dict(box=b, t=t)); want[t] -= 1
        return out[:cap]

    def words_in(box, cap=MAX_SUB):
        return [dict(box=b, t=t) for t, b in pool if inside(b, box, 0)][:cap]

    acts = []
    def stage(title, desc):
        acts.append(dict(kind='stage', title=title, desc=desc, line='# ' + title))
    def act(kind_, line, **kw):
        a = dict(kind=kind_, line=line); a.update(kw); acts.append(a)
    kind_ko = {'vector': '벡터 도면', 'drawing': '래스터 도면', 'page': '표·본문 쪽', 'illustration': '도해·기계 도면', 'photo': '사진·렌더링'}[kind]
    tables = [t for t in R.get('tables', []) if t.get('rows')]
    tbox = lambda t: [int(v) for v in t['box']] if t.get('box') else px_box(t['bbox'], k)
    core = [n for n in nodes if n['role'] in ('equipment', 'instrument', 'symbol', 'note')]

    # 1. 요소 추출
    stage('요소 추출', '문자, 선·도형·기호, 표 칸을 좌표와 함께 추출. 요소별 원본 좌표 보존')
    ext = []
    def act(kind_, line, **kw):   # 1단계에서는 sweep을 모아 한 동작으로 묶음
        if kind_ == 'sweep':
            ext.append(dict(line=line, **kw))
        else:
            a = dict(kind=kind_, line=line); a.update(kw); acts.append(a)
    detect_line = f"판별 {kind_ko} · 근거 {det.get('reason', '')}" + (f" · {R.get('dpi')} dpi" if R.get('dpi') else '')
    if pool:
        act('sweep', text_line, items=[b for _, b in pool], cls='text')
    if kind in ('vector', 'drawing'):
        act('sweep', f"도형·기호 {len(core)}개", items=[px_box(n['bbox'], k) for n in core], cls='shape')
        act('sweep', f"선 구간 {len(runs)}개, 분기점 {len(juncs)}개", lines=[px_pts(r['coords'], k) for r in runs], items=[[j['pt'][0] / k - 3, j['pt'][1] / k - 3, j['pt'][0] / k + 3, j['pt'][1] / k + 3] for j in juncs], cls='line')
        if tables:
            act('sweep', f"표 {len(tables)}개", items=[tbox(t) for t in tables], cls='table')
    elif kind == 'illustration':
        parts = R.get('parts', [])
        if parts:
            act('sweep', f"투상도 영역 {len(parts)}개", items=[[int(v) for v in p['box']] for p in parts], cls='part')
        if tables:
            act('sweep', f"표제란 {len(tables)}개", items=[tbox(t) for t in tables], cls='table')
        act('sweep', f"문자 묶음 {len(R.get('callouts', []))}개", items=[[int(v) for v in c['box']] for c in R.get('callouts', [])], cls='shape')
    elif kind == 'page':
        if tables:
            act('sweep', f"표 {len(tables)}개, 칸 {sum(len(r) for t in tables for r in (t.get('cell_boxes') or []))}개",
                items=[tbox(t) for t in tables] + [[int(v) for v in c] for t in tables for row in (t.get('cell_boxes') or []) for c in row], cls='table')
        if R.get('figures'):
            act('sweep', f"그림 영역 {len(R['figures'])}개", items=[[int(v) for v in f['box']] for f in R['figures']], cls='part')
        if R.get('paragraphs'):
            ncol = len(set(p['col'] for p in R['paragraphs'])) or 1
            act('sweep', f"{ncol}단, 문자 줄 묶음 {len(R['paragraphs'])}개", items=[[int(v) for v in p['box']] for p in R['paragraphs']], cls='shape')
    else:
        act('sweep', f"사진 {vw}×{vh} px, 구조 추출 없음", items=[[0, 0, vw, vh]], cls='part')

    acts.append(dict(kind='extract', groups=ext, lines=[detect_line] + [g['line'] for g in ext]))

    # 2. 관계 복원: 종류가 같은 요소는 한 번에 강조하고 줄도 한 번에 추가
    stage('관계 복원', '거리·방향 기준 최근접 요소에 문자를 할당해 명칭 결정. 선의 양 끝 접점 요소로 연결관계 확인. 요소·연결별 텍스트 1줄 생성')
    def batch(label, items, header=None):
        """같은 종류의 요소 묶음 하나. items: dict(kind, line, box|pts|boxes, cls, sub, ends)"""
        if items:
            acts.append(dict(kind='batch', label=label, header=header, items=items))
    def node_item(n):
        box = px_box(n['bbox'], k)
        return dict(kind='box', line=S.find('요소', n['id'] + ' ') or f"{n['id']} 종류={n['role']}", box=box, cls=n['role'], sub=subs(n.get('texts', []), box))
    def run_item(r, sec='연결'):
        pts = px_pts(r['coords'], k)
        xs = [q[0] for q in pts]; ys = [q[1] for q in pts]
        return dict(kind='poly', line=S.find(sec, r['id'] + ' ') or f"{r['id']} 종류={r['kind']} A={r['a']} B={r['b']}", pts=pts, cls=r['kind'],
                    ends=[px_box(nid[v]['bbox'], k) for v in (r['a'], r['b']) if v in nid], sub=subs(r.get('texts', []), [min(xs), min(ys), max(xs), max(ys)]))
    def row_items(t, i, box, cb=None):
        out = []
        nrow = len(t['rows']); h = (box[3] - box[1]) / max(1, nrow)
        for j in range(min(nrow, MAX_ROWS)):
            if cb and j < len(cb) and cb[j]:
                cells = [[int(v) for v in c] for c in cb[j]]
                rb = [min(c[0] for c in cells), min(c[1] for c in cells), max(c[2] for c in cells), max(c[3] for c in cells)]
                sub = [dict(box=c, t='') for c in cells]
            else:
                rn = nid.get(f't{i}r{j}')
                rb = px_box(rn['bbox'], k) if rn else [box[0], round(box[1] + j * h, 1), box[2], round(box[1] + (j + 1) * h, 1)]
                sub = words_in(rb, 12)
            line = S.find('표', f't{i} 열 이름') if j == 0 else S.find('표', f't{i} 행{j}:')
            out.append(dict(kind='box', line=line or f"t{i} 행{j}: " + ' | '.join(t['rows'][j]), box=rb, cls='row', sub=sub))
        return out
    ROLE_KO = {'equipment': '장비', 'instrument': '계기', 'symbol': '기호', 'note': '주석', 'pipe': '배관', 'signal': '신호선',
               'dimension': '치수', 'note_c': '주기', 'point': '지시선', 'describe': '설명', 'mention': '언급', 'belong': '소속'}
    if kind in ('vector', 'drawing'):
        for role in ('equipment', 'instrument', 'symbol', 'note'):
            grp = [node_item(n) for n in core if n['role'] == role]
            batch(f"{ROLE_KO[role]} {len(grp)}개", grp, header=S.head('요소') if role == 'equipment' or not any(n['role'] == 'equipment' for n in core) else None)
        kinds = []
        for r in runs:
            if r['kind'] not in kinds:
                kinds.append(r['kind'])
        for ki, kd in enumerate(kinds):
            grp = [run_item(r) for r in runs if r['kind'] == kd]
            batch(f"{ROLE_KO.get(kd, kd)} {len(grp)}개", grp, header=S.head('연결') if ki == 0 else None)
        for i, t in enumerate(tables):
            box = tbox(t)
            items = [dict(kind='box', line=S.find('표', f't{i} bbox') or f"t{i}", box=box, cls='table')] + row_items(t, i, box, t.get('cell_boxes'))
            batch(f"표 t{i} 행 {len(t['rows'])}", items, header=S.head('표') if i == 0 else None)
        link = S.sections.get(S.head('장비 간'), [])
        if link:
            byname = {n['texts'][0]: px_box(n['bbox'], k) for n in nodes if n['role'] == 'equipment' and n.get('texts')}
            items = []
            for l in link:
                names = [w.strip(',') for w in l.replace('→', ' ').split()]
                items.append(dict(kind='group', line=l, boxes=[byname[w] for w in names if w in byname][:8], cls='equipment'))
            batch(f"장비 간 배관 연결 {len(items)}개", items, header=S.head('장비 간'))
    elif kind == 'illustration':
        cos = R.get('callouts', [])
        for kd, label in (('dimension', '치수'), ('note', '주기'), ('datum', '기준 문자')):
            grp = []
            for i, c in enumerate(cos):
                if c.get('kind', 'note') == kd or (kd == 'note' and c.get('kind') == 'callout'):
                    box = [int(v) for v in c['box']]
                    grp.append(dict(kind='box', line=S.find('치수', f'c{i} ') or f"c{i}", box=box, cls=kd, sub=words_in(box)))
            batch(f"{label} {len(grp)}개", grp, header=S.head('치수') if kd == 'dimension' else None)
        leaders = R.get('leaders', [])
        if leaders:
            items = [dict(kind='poly', line=S.find('지시선', f"c{l['callout']} ") or f"c{l['callout']} → part{l['part']}",
                          pts=[[int(l['start'][0]), int(l['start'][1])], [int(l['end'][0]), int(l['end'][1])]], cls='point') for l in leaders]
            batch(f"지시선 {len(items)}개", items, header=S.head('지시선'))
        for i, t in enumerate(tables):
            batch(f"표제란 t{i}", row_items(t, i, tbox(t), t.get('cell_boxes')), header=S.head('표') if i == 0 else None)
    elif kind == 'page':
        for i, t in enumerate(tables):
            box = tbox(t)
            items = [dict(kind='box', line=S.find('표', f't{i} bbox') or f"t{i}", box=box, cls='table')] + row_items(t, i, box, t.get('cell_boxes'))
            batch(f"표 t{i} 행 {len(t['rows'])}", items, header=S.head('표') if i == 0 else None)
        figs = R.get('figures', [])
        if figs:
            batch(f"그림 영역 {len(figs)}개", [dict(kind='box', line=S.find('그림', f'f{i} ') or f"f{i}", box=[int(v) for v in f['box']], cls='figure') for i, f in enumerate(figs)], header=S.head('그림'))
        paras = R.get('paragraphs', [])
        if paras:
            items = []
            for i, p in enumerate(paras):
                box = [int(v) for v in p['box']]
                items.append(dict(kind='box', line=S.find('본문', f'p{i} ') or f"p{i} {p['text'][:60]}", box=box, cls='paragraph', sub=words_in(box)))
            batch(f"문단 {len(items)}개", items, header=S.head('본문'))
        rel = [r for r in runs if r['kind'] in ('describe', 'mention', 'belong')]
        if rel:
            batch(f"설명·언급·소속 {len(rel)}개", [run_item(r, '관계') for r in rel], header=S.head('관계'))
    else:
        batch('사진', [dict(kind='box', line=l, box=[0, 0, vw, vh], cls='photo') for l in S.sections.get(S.head('관계'), [])], header=S.head('관계'))

    # 3. 직렬화
    serial = R.get('serial', [])
    stage('직렬화', '오른쪽 텍스트 전체를 텍스트 LLM 프롬프트의 문서로 입력. 답변 근거는 이 텍스트로 한정')
    q, a = '', ''
    link = S.sections.get(S.head('장비 간'), [])
    if kind in ('vector', 'drawing') and link:
        src, dst = link[0].split('→', 1)
        q, a = f"{src.strip()}와 배관으로 연결된 장비는?", dst.strip()
    elif tables and len(tables[0]['rows']) > 1 and len(tables[0]['rows'][0]) > 1:
        hdr, row = tables[0]['rows'][0], tables[0]['rows'][1]
        q, a = f"{hdr[0]}이(가) {row[0]}인 행의 {hdr[1]}은?", row[1]
    elif R.get('paragraphs'):
        q, a = '본문 첫 문단의 내용은?', R['paragraphs'][0]['text'][:60]
    elif kind == 'illustration' and R.get('leaders'):
        q, a = 'part0에 지시선이 닿는 주기는?', ', '.join(f"c{l['callout']}" for l in R['leaders'])
    elif kind == 'photo':
        q, a = '사진의 크기는?', f"{vw}×{vh} px"
    acts.append(dict(kind='final', nlines=len(serial), nchars=sum(len(l) for l in serial), head=serial[:7], q=q, a=a))

    serial = R.get('serial', [])
    total_t = times.get('total', sum(v for kk, v in times.items() if isinstance(v, (int, float))))
    return dict(name=name, kind=kind, kind_name=kind_name, source=source, w=vw, h=vh, img=jpeg_uri(img, 2000, 76), acts=acts,
                nlines=len(serial), nchars=sum(len(l) for l in serial), total=round(total_t, 1))

def main(folder, out_html):
    data = []
    for name, kind_name, source in EXAMPLES:
        if not os.path.exists(os.path.join(folder, 'output', os.path.splitext(name)[0], 'result.json')):
            print('없음', name); continue
        ex = build(name, kind_name, source, folder)
        data.append(ex); print(name, ex['kind'], len(ex['acts']), '동작')
    tpl = open(os.path.join(HERE, 'static', 'motion.html'), encoding='utf-8').read()
    html = tpl.replace('/*__DATA__*/[]', json.dumps(data, ensure_ascii=False, separators=(',', ':')))
    open(out_html, 'w', encoding='utf-8').write(html)
    print('wrote', out_html, f"{os.path.getsize(out_html) // 1024} KB")

if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'examples', 'sample-inputs'),
         sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, '문서-구조화-과정.html'))
