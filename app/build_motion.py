"""문서 종류별 대표 예시 한 건씩의 처리 과정을 단계별로 재생하는 정적 화면을 만든다.
실행: python app/build_motion.py [표본 폴더] [출력 html]   (기본: examples/sample-inputs → app/문서-구조화-과정.html)

각 예시마다 경로(벡터 도면·래스터 도면·기계 도면·표/본문 쪽·글자 층 PDF·사진)에 맞는 단계 목록을 만들고,
단계마다 원본 위에 겹쳐 그릴 요소(상자·선·점)와 그 단계에서 생기는 자료의 형태(텍스트 줄)를 담는다.
"""
import os, sys, json, math, random
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import pipeline as pl
import serialize as sz
from build_page import view_image, jpeg_uri, add_relations, QTAG

# 종류별 대표 예시: (파일, 종류 이름, 출처)
EXAMPLES = [
    ('pid-standard-vector.svg', '벡터 P&ID', 'DEXPI 공개 예제 C01, SVG'),
    ('pid-standard-scan.png', '스캔 P&ID', 'DEXPI C01을 200 dpi로 그려 회전·잡음·JPEG 열화'),
    ('mech-iso-tolerance-real.jpg', '기계 도면', 'NIST 공개 치수·공차 도면, 스캔'),
    ('faa-bolt-table-illustrations.jpg', '표·삽화 쪽', 'FAA AC 43.13-1B 볼트 표, 스캔'),
    ('faa-text-page.png', '2단 본문 쪽', 'FAA AC 43.13-1B 본문, 스캔'),
    ('en-report-synthetic-vector.pdf', '글자 층 PDF 보고서', '합성 보고서, PDF 글자 층'),
    ('ko-table-text-scan200.jpg', '한글 표·본문 스캔', '합성 한글 문서, 200 dpi 스캔'),
    ('photo-rocket-launch.jpg', '사진', '공개 사진'),
]
ROLE_KO = {'equipment': '장비', 'instrument': '계기', 'symbol': '기호', 'nozzle': '접속구', 'note': '주석', 'mark': '표식', 'arrow': '화살표',
           'shape': '도형', 'junction': '분기점', 'table': '표', 'row': '행', 'figure': '그림', 'paragraph': '문단', 'callout': '주기',
           'dimension': '치수', 'datum': '기준 문자', 'part': '투상도', 'photo': '사진', 'text': '문자'}
EDGE_KO = {'pipe': '배관', 'signal': '신호선', 'contain': '포함', 'belong': '소속', 'describe': '설명', 'mention': '언급', 'next': '순서', 'point': '지시', 'dimension': '치수'}

def mm_box(b, k):
    return [round(v / k, 1) for v in b]

def layout_graph(nodes, runs, junctions, keep_roles, max_nodes=90):
    """힘 기반 배치. 그림 좌표에서 출발해 풀어 놓음. 결과는 0~1 정규화 좌표."""
    nid = {n['id']: n for n in nodes}
    jid = {j['id']: j for j in junctions}
    deg = {}
    for r in runs:
        for v in (r['a'], r['b']):
            deg[v] = deg.get(v, 0) + 1
    gnodes = [n['id'] for n in nodes if n['role'] in keep_roles and not n.get('attached_to') and (deg.get(n['id'], 0) > 0 or n['role'] in ('equipment', 'instrument', 'table', 'part', 'figure', 'paragraph', 'photo'))]
    gnodes = gnodes[:max_nodes]
    gnodes += [j['id'] for j in junctions if deg.get(j['id'], 0) > 0]
    gset = set(gnodes)
    def pos(v):
        if v in nid:
            b = nid[v]['bbox']; return [(b[0] + b[2]) / 2, (b[1] + b[3]) / 2]
        if v in jid:
            return list(jid[v]['pt'])
        return None
    edges = [(r['a'], r['b'], r) for r in runs if r['a'] in gset and r['b'] in gset and r['a'] != r['b']]
    if not gnodes:
        return {}, []
    random.seed(3)
    P = {v: pos(v) for v in gnodes}
    xs = [p[0] for p in P.values()]; ys = [p[1] for p in P.values()]
    bx0, bx1, by0, by1 = min(xs) - 5, max(xs) + 5, min(ys) - 5, max(ys) + 5   # 배치 범위: 원본 좌표 범위에 고정
    cx, cy = (bx0 + bx1) / 2, (by0 + by1) / 2
    area = max(1.0, (bx1 - bx0) * (by1 - by0))
    k = 0.45 * math.sqrt(area / max(1, len(gnodes)))   # 노드 수와 그림 크기에 맞춘 목표 간격
    for it in range(300):
        temp = (k / 2) * (1 - it / 300) + 0.3
        disp = {v: [0.0, 0.0] for v in gnodes}
        for i, a in enumerate(gnodes):
            for b in gnodes[i + 1:]:
                dx = P[a][0] - P[b][0]; dy = P[a][1] - P[b][1]
                d = math.hypot(dx, dy) + 1e-3
                f = k * k / d
                disp[a][0] += dx / d * f; disp[a][1] += dy / d * f
                disp[b][0] -= dx / d * f; disp[b][1] -= dy / d * f
        for a, b, _ in edges:
            dx = P[a][0] - P[b][0]; dy = P[a][1] - P[b][1]
            d = math.hypot(dx, dy) + 1e-3
            f = d * d / k
            disp[a][0] -= dx / d * f; disp[a][1] -= dy / d * f
            disp[b][0] += dx / d * f; disp[b][1] += dy / d * f
        for v in gnodes:
            dx, dy = disp[v]
            dx += (cx - P[v][0]) * 0.08; dy += (cy - P[v][1]) * 0.08   # 약한 중심 인력
            d = math.hypot(dx, dy) + 1e-3
            P[v][0] = min(bx1, max(bx0, P[v][0] + dx / d * min(d, temp)))
            P[v][1] = min(by1, max(by0, P[v][1] + dy / d * min(d, temp)))
    xs = [p[0] for p in P.values()]; ys = [p[1] for p in P.values()]
    x0, x1, y0, y1 = min(xs), max(xs) + 1e-6, min(ys), max(ys) + 1e-6
    out = {}
    for v in gnodes:
        n = nid.get(v)
        out[v] = dict(x=round((P[v][0] - x0) / (x1 - x0), 4), y=round((P[v][1] - y0) / (y1 - y0), 4),
                      role=n['role'] if n else 'junction', name=(sz.name_of(n) if n else '')[:14], src=pos(v))
    return out, [dict(a=a, b=b, kind=r['kind']) for a, b, r in edges]

def serial_block(serial, head, limit=40):
    """직렬화 줄 중 특정 머리글 절의 줄만 뽑음."""
    out, on = [], False
    for l in serial:
        if l.startswith('## '):
            on = l.startswith(head)
            if on:
                out.append(l)
            continue
        if on and l.strip():
            out.append(l)
    return out[:limit]

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
    det = R.get('detect', {}); counts = R.get('counts', {}); times = R.get('times', {})
    nodes, runs, juncs = R.get('nodes', []), R.get('runs', []), R.get('junctions', [])
    serial = R.get('serial', [])
    steps = []
    def step(title, desc, layers, form, note=''):
        steps.append(dict(title=title, desc=desc, layers=layers, form=form, note=note))

    # 0. 입력과 판별
    reason = det.get('reason', '')
    dpi_s = f"{R.get('dpi')} dpi({det.get('dpi_source')})" if R.get('dpi') else ''
    kind_ko = {'vector': '벡터 도면', 'drawing': '래스터 도면', 'page': '표·본문 쪽', 'illustration': '도해·기계 도면', 'photo': '사진·렌더링'}[kind]
    form0 = [f"파일 {name}", f"판별 {kind_ko}", f"근거 {reason}"] + ([f"해상도 {dpi_s}"] if dpi_s else []) + ([f"기울기 {det['skew_deg']}°" for _ in [0] if det.get('skew_deg')])
    step('입력과 판별', '잉크 구성(문자·축 평행 선·채움)과 문자 수로 처리 경로를 정함', [], form0)

    # 문자
    texts = R.get('texts') or []
    if kind == 'vector':
        labels = R.get('labels') or json.load(open(os.path.join(d, 'graph.json'), encoding='utf-8')).get('labels', [])
        tb = [dict(box=mm_box(l['bbox'], k), t=l['text']) for l in labels]
        step('문자 좌표', 'SVG 문자 요소의 위치·각도를 그대로 읽음(문자 인식 없음)',
             [dict(kind='box', cls='text', items=tb)],
             [f"문자 {len(tb)}개"] + [f"{l['text']}  ({l['x']:.1f}, {l['y']:.1f}) mm" for l in labels[:14]])
    elif texts:
        tb = [dict(box=[int(v) for v in t['box']], t=t['text']) for t in texts]
        title = '글자 층 좌표' if all(t.get('conf', 0) >= 0.999 for t in texts) else '문자 인식'
        desc = 'PDF 글자 층의 낱말 좌표를 읽음(문자 인식 없음)' if title == '글자 층 좌표' else ('기울기 보정 후 CPU 문자 인식. 상자·문자·신뢰도를 얻음' + (f", {times.get('문자 인식', 0):.0f}초" if times.get('문자 인식') else ''))
        step(title, desc, [dict(kind='box', cls='text', items=tb)],
             [f"문자 {len(tb)}개"] + [f"{t['text'][:28]}  conf {t.get('conf', 1):.2f}  box {t['box']}" for t in texts[:14]])

    if kind in ('vector', 'drawing'):
        # 선·도형·기호
        shape_items = [dict(box=mm_box(n['bbox'], k), t=ROLE_KO.get(n['role'], n['role'])) for n in nodes if n['role'] not in ('mark',)]
        run_items = [dict(pts=[[round(x / k, 1), round(y / k, 1)] for x, y in r['coords']], t=r['kind']) for r in runs]
        step('선·도형·기호', '축 평행 긴 선을 선 후보로, 닫힌 윤곽을 도형으로, 남은 잉크 덩이를 기호로 나눔' if kind == 'drawing' else '선·곡선·타원 기본 요소를 선 후보와 닫힌 도형·기호로 나눔',
             [dict(kind='poly', cls='run-raw', items=run_items), dict(kind='box', cls='shape', items=shape_items)],
             [f"선 후보 {counts.get('primitives', len(runs))}개, 도형·기호 {len(shape_items)}개"] + [f"{n['id']} bbox={[round(v, 1) for v in n['bbox']]} mm" for n in nodes[:12]])
        # 틀·표
        tbl = [dict(box=mm_box(t['bbox'], k), t='표') for t in R.get('tables', [])]
        if tbl:
            step('틀·표 분리', '격자 모양 선 묶음을 표로 읽어 칸과 문자를 행으로 묶고 도면 요소에서 뺌',
                 [dict(kind='box', cls='table', items=tbl)],
                 [f"표 {len(tbl)}개"] + [f"t{i} 행 {len(t['rows'])}: " + ' / '.join(t['rows'][0])[:60] for i, t in enumerate(R.get('tables', []))])
        # 연결
        jpts = [dict(pt=[round(j['pt'][0] / k, 1), round(j['pt'][1] / k, 1)], t=j['id']) for j in juncs]
        step('연결과 분기점', '선 끝이 도형·기호에 닿는 점, 선 위에 놓인 기호, 다른 선의 끝이 닿는 분기점에서 선을 자르고 구간으로 이음. 모서리는 한 꼭짓점으로 맞춤',
             [dict(kind='poly', cls='run', items=run_items, draw=True), dict(kind='dot', cls='junction', items=jpts)],
             [f"선 구간 {len(runs)}개, 분기점 {len(juncs)}개"] + [f"{r['id']} {r['a']} — {r['b']}  {EDGE_KO.get(r['kind'], r['kind'])}" for r in runs[:14]])
        # 문자 귀속·역할
        role_items = [dict(box=mm_box(n['bbox'], k), t=(f"{ROLE_KO.get(n['role'], n['role'])} {sz.name_of(n)}"[:24] if n['role'] in ('equipment', 'instrument') else ''), role=n['role']) for n in nodes if n['role'] in ('equipment', 'instrument', 'symbol', 'note', 'nozzle')]
        step('문자 귀속과 역할', '문자를 거리·방향으로 가장 가까운 요소나 선에 붙이고, 태그 형식·연결 수·크기로 장비·계기·기호·접속구를 정함',
             [dict(kind='box', cls='role', items=role_items)],
             [f"장비 {counts.get('equipment', 0)} · 계기 {counts.get('instrument', 0)} · 기호 {counts.get('symbol', 0)} · 접속구 {counts.get('nozzle', 0)}"] + serial_block(serial, '## 요소', 14)[1:])
        keep = ('equipment', 'instrument', 'symbol', 'nozzle', 'note')
    elif kind == 'illustration':
        tbl = [dict(box=mm_box(t['bbox'], k), t='표제란') for t in R.get('tables', [])]
        if tbl:
            step('표제란', '괘선 격자를 표로 읽음', [dict(kind='box', cls='table', items=tbl)],
                 [f"표 {len(tbl)}개"] + [f"t{i}: " + ' / '.join(t['rows'][0])[:60] for i, t in enumerate(R.get('tables', []))])
        parts = [dict(box=[int(v) for v in p['box']], t=f"투상도 {p['area_mm2']:.0f} mm²") for p in R.get('parts', [])]
        step('투상도 영역', '문자·표제란을 지운 뒤 남는 큰 잉크 덩이를 투상도(부품 그림) 영역으로 잡음',
             [dict(kind='box', cls='part', items=parts)], [f"투상도 영역 {len(parts)}개"] + [p['t'] for p in parts])
        kinds = {'dimension': '치수', 'note': '주기', 'datum': '기준 문자', 'callout': '주기'}
        co = [dict(box=[int(v) for v in c['box']], t=kinds.get(c.get('kind'), '주기'), role=c.get('kind', 'callout')) for c in R.get('callouts', [])]
        step('치수·주기 분류', '문자 묶음을 치수(수치·공차·지름 기호), 주기(NOTE·설명문), 기준 문자로 나눔',
             [dict(kind='box', cls='role', items=co)],
             [f"치수 {sum(1 for c in co if c['role'] == 'dimension')} · 주기 {sum(1 for c in co if c['role'] in ('note', 'callout'))} · 기준 문자 {sum(1 for c in co if c['role'] == 'datum')}"] + [f"{c['t']}: " + ' '.join(x['texts'])[:50] for c, x in zip(co, R.get('callouts', []))][:14])
        ld = [dict(pts=[[int(l['start'][0]), int(l['start'][1])], [int(l['end'][0]), int(l['end'][1])]], t='지시선') for l in R.get('leaders', [])]
        step('지시선', '문자 묶음에서 나와 투상도에 닿는 직선을 지시선으로 잡아 치수·주기를 부품에 연결',
             [dict(kind='poly', cls='run', items=ld, draw=True)],
             [f"지시선 {len(ld)}개"] + [f"주기 {l['callout']} → 투상도 {l['part']}  {l['length_mm']:.0f} mm" for l in R.get('leaders', [])])
        keep = ('part', 'callout', 'dimension', 'note', 'datum', 'table')
    elif kind == 'page':
        tables = R.get('tables', [])
        cells = [dict(box=[int(v) for v in c], t='') for t in tables for row in (t.get('cell_boxes') or []) for c in row]
        tbl = [dict(box=[int(v) for v in t['box']] if t.get('box') else mm_box(t['bbox'], k), t='표') for t in tables]
        if tables:
            step('괘선과 표 칸', '괘선으로 칸을 나누고 문자를 칸에 배정. 괘선 없이 쌓인 행은 문자 줄로 나눔',
                 [dict(kind='box', cls='cell', items=cells), dict(kind='box', cls='table', items=tbl)],
                 [f"표 {len(tables)}개"] + [f"t{i} 행 {len(t['rows'])} × 열 {len(t['rows'][0])}: " + ' | '.join(t['rows'][0])[:60] for i, t in enumerate(tables)])
        figs = [dict(box=[int(v) for v in f['box']], t='그림') for f in R.get('figures', [])]
        if figs:
            step('그림 영역', '표 밖의 큰 잉크 덩이와 틀 안의 조각·문자를 그림 영역으로 묶고, 같은 행의 표 칸에 소속시킴',
                 [dict(kind='box', cls='figure', items=figs)],
                 [f"그림 영역 {len(figs)}개"] + [f"f{i} {f['area_mm2']:.0f} mm²" + (f"  소속 표 {f['table']}" if f.get('table') else '') for i, f in enumerate(R.get('figures', []))][:14])
        paras = [dict(box=[int(v) for v in p['box']], t=f"단{p['col'] + 1}", role=f"col{p['col']}") for p in R.get('paragraphs', [])]
        ncol = len(set(p['col'] for p in R.get('paragraphs', []))) or 1
        step('단과 문단', '문자 줄 사이의 세로 빈 띠로 단을 나누고, 줄 간격·글자 크기·제목 형식으로 문단을 끊어 읽는 순서를 정함',
             [dict(kind='box', cls='para', items=paras)],
             [f"{ncol}단, 문단 {len(paras)}개"] + [f"p{i} 단{p['col'] + 1}: {p['text'][:50]}" for i, p in enumerate(R.get('paragraphs', []))][:14])
        keep = ('table', 'row', 'figure', 'paragraph')
    else:   # photo
        keep = ('photo',)

    if kind != 'photo':
        lay, edges = layout_graph(nodes, runs, juncs, keep)
        src_px = {v: [round(p['src'][0] / k, 1), round(p['src'][1] / k, 1)] for v, p in lay.items() if p['src']}
        for v in lay:
            lay[v].pop('src', None)
        step('관계 그래프', '요소를 노드로, 연결·포함·소속·지시를 간선으로 둔 그래프. 좌표는 노드마다 남김',
             [dict(kind='graph', nodes=lay, edges=edges, src=src_px)],
             [f"노드 {len(lay)}개, 간선 {len(edges)}개"] + [f"{e['a']} —{EDGE_KO.get(e['kind'], e['kind'])}— {e['b']}" for e in edges[:14]])
    # 직렬화
    step('직렬화', '그래프를 좌표가 붙은 텍스트 줄로 씀. 이 텍스트가 텍스트 LLM의 입력',
         [], serial[:60], note=f"전체 {len(serial)}줄, {sum(len(l) for l in serial):,}자")
    # 질의 부분 그래프
    qtag = QTAG.get(name)
    if qtag and kind != 'photo':
        sg = pl.subgraph(dict(nodes=nodes, runs=runs, junctions=juncs), qtag, depth=2)
        if sg.get('found'):
            ids = set()
            for l in sg['lines']:
                for tok in l.replace('[', ' ').replace(']', ' ').replace('(', ' ').replace(')', ' ').split():
                    ids.add(tok)
            nb = {n['id']: n for n in nodes}
            hl = [dict(box=mm_box(nb[v]['bbox'], k), t=sz.name_of(nb[v])[:16]) for v in ids if v in nb]
            step('질의 부분 그래프', f"질문의 태그 {qtag}에서 연결을 2단계 따라간 부분만 추려 짧은 문맥을 만듦. 줄마다 원본 좌표가 있어 근거 영역을 되짚음",
                 [dict(kind='box', cls='focus', items=hl)], sg['lines'][:40], note=f"{len(sg['lines'])}줄")
    return dict(name=name, kind=kind, kind_name=kind_name, source=source, w=vw, h=vh, img=jpeg_uri(img, 2000, 76), steps=steps,
                total=round(times.get('total', sum(v for kk, v in times.items() if isinstance(v, (int, float)))), 1))

def main(folder, out_html):
    data = []
    for name, kind_name, source in EXAMPLES:
        if not os.path.exists(os.path.join(folder, 'output', os.path.splitext(name)[0], 'result.json')):
            print('없음', name); continue
        ex = build(name, kind_name, source, folder)
        data.append(ex); print(name, ex['kind'], len(ex['steps']), '단계')
    tpl = open(os.path.join(HERE, 'static', 'motion.html'), encoding='utf-8').read()
    html = tpl.replace('/*__DATA__*/[]', json.dumps(data, ensure_ascii=False, separators=(',', ':')))
    open(out_html, 'w', encoding='utf-8').write(html)
    print('wrote', out_html, f"{os.path.getsize(out_html) // 1024} KB")

if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'examples', 'sample-inputs'),
         sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, '문서-구조화-과정.html'))
