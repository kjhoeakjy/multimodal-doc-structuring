"""문서 이미지 한 장을 받아 입력 판별, 요소 추출, 관계 그래프, 직렬화, 색인까지 수행하는 처리 묶음.

examples/public-documents의 추출 코드를 그대로 호출함. 자원(코어·메모리)에 따라 스레드 수, 인식 배치,
입력 크기를 정하고 처리 중 메모리를 감시함. 사용자가 고르는 설정은 없음.
"""
import os, sys, json, time, re, math, threading, collections

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PID = os.path.join(ROOT, 'examples', 'public-documents', 'pid')
PAGES = os.path.join(ROOT, 'examples', 'public-documents', 'pages')
for p in (PID, PAGES):
    if p not in sys.path:
        sys.path.insert(0, p)

import numpy as np, cv2
import extract_graph as eg
import raster_graph as rg
import real_docs as rd
import serialize as sz

try:
    import psutil
except ImportError:
    psutil = None

PART_NO = re.compile(r'^[A-Z]{1,4}\d{2,}[A-Z0-9/.-]*$')      # 부품 번호 형식(AN3-5A, NAS6204-10, MS20365-428)
WORD = re.compile(r'[A-Za-z가-힣0-9][A-Za-z가-힣0-9.\-/]*')
HANGUL = re.compile(r'[가-힣]')
PAPER_SHORT_MM = [('A4', 210), ('A3', 297), ('A2', 420), ('A1', 594), ('A0', 841)]
TEXT_BOX_MM = 4.5          # 문자 상자 높이 가정(본문 10~11 pt, 도면 2.5~3.5 mm 글자의 상자 높이 중앙값)


# ---------------- 자원 ----------------
class Resources:
    """코어·메모리를 읽어 처리 설정을 정함. 부하가 있으면 느린 쪽을 고름."""
    def __init__(self):
        self.cores = os.cpu_count() or 1

    def snapshot(self):
        s = dict(cores=self.cores, total_gb=None, avail_gb=None, cpu_busy=None)
        if psutil:
            vm = psutil.virtual_memory()
            s.update(total_gb=round(vm.total / 2**30, 1), avail_gb=round(vm.available / 2**30, 1),
                     cpu_busy=round(psutil.cpu_percent(interval=0.3), 0))
        elif os.path.exists('/proc/meminfo'):
            m = dict(l.split(':')[0:2] for l in open('/proc/meminfo') if ':' in l)
            s.update(total_gb=round(int(m['MemTotal'].split()[0]) / 2**20, 1),
                     avail_gb=round(int(m['MemAvailable'].split()[0]) / 2**20, 1))
        return s

    def plan(self):
        s = self.snapshot(); why = []
        threads = max(1, self.cores // 2)
        why.append(f"코어 {self.cores}개 중 {threads}개 사용(절반)")
        if s['cpu_busy'] is not None and s['cpu_busy'] > 50:
            threads = max(1, threads // 2); why.append(f"다른 작업 CPU {s['cpu_busy']:.0f}% → 스레드 {threads}")
        avail = s['avail_gb'] if s['avail_gb'] is not None else 4.0
        # 실측: 12 MP 도면 한 장 처리의 최대 상주 메모리 4.8 GB(문자 인식 모델 2종 포함)
        if avail < 3:
            batch, max_mp = 1, 2.0
        elif avail < 5:
            batch, max_mp = 2, 4.0
        elif avail < 8:
            batch, max_mp = 4, 8.0
        else:
            batch, max_mp = 8, 12.0
        why.append(f"가용 메모리 {avail} GB → 인식 배치 {batch}, 입력 상한 {max_mp:g} MP")
        why.append("문자 탐지 원본 해상도(정확도 우선), 한 번에 한 작업")
        return dict(threads=threads, batch=batch, max_mp=max_mp, det_scale=1.0, snapshot=s, why=why)


class MemWatch:
    """처리 중 메모리 감시. 가용 메모리가 바닥나면 경고 표시."""
    def __init__(self, floor_gb=0.5):
        self.floor = floor_gb; self.peak_rss = 0.0; self.min_avail = None; self.abort = False; self._stop = False
        self.t = threading.Thread(target=self.run, daemon=True)

    def run(self):
        if not psutil:
            return
        proc = psutil.Process()
        while not self._stop:
            rss = proc.memory_info().rss / 2**30; av = psutil.virtual_memory().available / 2**30
            self.peak_rss = max(self.peak_rss, rss)
            self.min_avail = av if self.min_avail is None else min(self.min_avail, av)
            if av < self.floor:
                self.abort = True
            time.sleep(0.5)

    def start(self): self.t.start(); return self
    def stop(self): self._stop = True


# ---------------- OCR ----------------
_READERS = {}
_LOCK = threading.Lock()

def get_reader(langs):
    key = tuple(langs)
    with _LOCK:
        if key not in _READERS:
            import easyocr
            _READERS[key] = easyocr.Reader(list(langs), gpu=False, verbose=False)
        return _READERS[key]


class TunedReader:
    """배치 크기를 적용하고 언어를 자동으로 고르는 문자 인식기.

    탐지는 한 번(원본 해상도), 인식은 영어 모델로 먼저 수행함. 큰 문자 상자 표본을 한글 모델로 읽어
    한글이 나오면 전체를 한글 모델로 다시 읽고, 상자별로 한글이 든 결과는 한글 모델, 나머지는 영어 모델을 씀
    (도면 실측: 한글 모델만 쓰면 영문 도면의 복원율 0.44→0.33으로 떨어짐).
    """
    def __init__(self, batch=8):
        self.batch = batch
        self.r_en = get_reader(['en']); self.r_ko = get_reader(['ko', 'en'])
        self.lang_used = 'en'

    def readtext(self, img, **kw):
        kw.pop('batch_size', None)
        det_kw = {k: v for k, v in kw.items() if k in ('min_size', 'text_threshold', 'low_text', 'link_threshold', 'mag_ratio')}
        hl, fl = self.r_en.detect(img, **det_kw); hl, fl = hl[0], fl[0]
        res_en = self.r_en.recognize(img, horizontal_list=hl, free_list=fl, batch_size=self.batch, paragraph=False)
        sample = sorted(hl, key=lambda b: -(b[1] - b[0]) * (b[3] - b[2]))[:12]
        if sample:
            probe = self.r_ko.recognize(img, horizontal_list=sample, free_list=[], batch_size=self.batch, paragraph=False)
            if any(HANGUL.search(t) and c >= 0.4 for _, t, c in probe):
                res_ko = self.r_ko.recognize(img, horizontal_list=hl, free_list=fl, batch_size=self.batch, paragraph=False)
                if len(res_ko) == len(res_en):
                    res_en = [ko if HANGUL.search(ko[1]) else en for en, ko in zip(res_en, res_ko)]
                    self.lang_used = 'ko+en'
        return res_en


def run_ocr(gray, reader, prefix):
    """문자 인식 한 번. 도면 경로(원시 결과)와 쪽 경로(상자 목록) 두 형식으로 저장."""
    t0 = time.time()
    if os.path.exists(prefix + '_ocr.json'):      # 같은 입력을 다시 처리할 때 문자 인식 결과와 그때의 소요 시간을 재사용
        res = json.load(open(prefix + '_ocr.json')); reader.lang_used = getattr(reader, 'lang_used', None) or '저장된 결과'
        secs = float(open(prefix + '_ocr.time').read()) if os.path.exists(prefix + '_ocr.time') else 0.0
    else:
        res = reader.readtext(gray, paragraph=False, min_size=4, text_threshold=0.6, low_text=0.3, mag_ratio=1.5)
        secs = time.time() - t0; open(prefix + '_ocr.time', 'w').write(f'{secs:.1f}')
    raw = [[[[float(v) for v in p] for p in q], s, float(c)] for q, s, c in res]
    json.dump(raw, open(prefix + '_ocr.json', 'w'))
    texts = []
    for q, s, c in res:
        s = s.strip()
        if not s or c < 0.05:
            continue
        xs = [p[0] for p in q]; ys = [p[1] for p in q]
        texts.append(dict(text=s, conf=round(float(c), 2), box=[int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))]))
    return raw, texts, secs


# ---------------- 입력 판별 ----------------
def image_dpi(path):
    """파일 메타데이터의 해상도. 없거나 기본값(72·96)이거나 비현실적이면 None."""
    try:
        from PIL import Image
        d = Image.open(path).info.get('dpi')
        v = float(d[0]) if d else 0
        if 100 <= v <= 1200 and round(v) not in (96,):
            return int(round(v))
    except Exception:
        pass
    return None


def is_photo(gray):
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    mid = float(((blur > 60) & (blur < 200)).mean())
    _, ink = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    ink_ratio = float((ink > 0).mean())
    return (mid > 0.45 or ink_ratio > 0.35), dict(midtone=round(mid, 3), ink=round(ink_ratio, 3))


def estimate_dpi(W, H, texts, meta_dpi):
    """해상도 추정: 메타데이터 → 문자 상자 높이와 표준 용지 크기 대조 → 용지 가정."""
    if meta_dpi:
        return meta_dpi, '파일 메타데이터'
    short = min(W, H)
    hs = sorted(t['box'][3] - t['box'][1] for t in texts if t['conf'] >= 0.4)
    if len(hs) >= 10:
        dpi_text = hs[len(hs) // 2] / (TEXT_BOX_MM / 25.4)
        for name, mm in PAPER_SHORT_MM:                       # 작은 용지부터, 문자 추정과 35% 안에서 맞는 용지
            d = short * 25.4 / mm
            if abs(math.log(dpi_text / d)) <= 0.35:
                return int(round(d)), f'문자 높이 {TEXT_BOX_MM} mm 가정과 {name} 용지 일치'
        return int(round(dpi_text)), f'문자 높이 {TEXT_BOX_MM} mm 가정'
    best = min(PAPER_SHORT_MM, key=lambda p: abs(math.log((short * 25.4 / p[1]) / 150)))
    return int(round(short * 25.4 / best[1])), f'문자 적음, {best[0]} 용지 150 dpi 근방 가정'


def classify(gray, texts, dpi):
    """잉크 구성(문자·축 평행 긴 선·그 밖)으로 쪽·도식·도해를 가름."""
    H, W = gray.shape; k = 25.4 / dpi
    _, ink = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU); tot = max(1, int((ink > 0).sum()))
    tm = np.zeros_like(ink)
    for t in texts:
        b = t['box']; cv2.rectangle(tm, (b[0] - 2, b[1] - 2), (b[2] + 2, b[3] + 2), 255, -1)
    hm = rd.axis_mask(ink, k, 15.0, 'h'); vm = rd.axis_mask(ink, k, 8.0, 'v')
    solid_m = cv2.dilate(cv2.bitwise_and(hm, vm), np.ones((5, 5), np.uint8))   # 채워진 면(그래프 막대·사진)
    hm[solid_m > 0] = 0; vm[solid_m > 0] = 0; am = cv2.bitwise_or(hm, vm)
    text_ink = ((ink > 0) & (tm > 0)).sum() / tot
    axis = ((ink > 0) & (am > 0) & (tm == 0)).sum() / tot
    solid = ((ink > 0) & (solid_m > 0) & (tm == 0)).sum() / tot
    free = max(0.0, 1 - text_ink - axis)
    hl, _ = rg.axis_lines(ink, dpi, eg.LONG, 'h'); vl, _ = rg.axis_lines(ink, dpi, eg.LONG, 'v')
    fb = rg.inner_frame(hl + vl, W * k, H * k); inner = fb.buffer(-1.0)
    long_in = sum(1 for l in hl + vl if l['geom'].within(inner))
    # 큰 원(반지름 8 mm 이상): 기계 도면의 특징. 허프 변환 투표 문턱을 높여 선 교차·둥근 모서리는 세지 않음
    # (실측: 플랜지 도면 4개, P&ID 0개, 등각 도면 0개, 표·보고서 0개)
    small = cv2.GaussianBlur(cv2.resize(gray, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA), (3, 3), 0)
    rmin = max(4, int(8.0 / k * 0.5))
    circles = cv2.HoughCircles(small, cv2.HOUGH_GRADIENT, dp=1, minDist=rmin, param1=150, param2=150, minRadius=rmin, maxRadius=int(min(small.shape) / 2))
    n_circ = 0 if circles is None else int(circles.shape[1])
    f = dict(text_ink=round(float(text_ink), 2), axis_ink=round(float(axis), 2), free_ink=round(float(free), 2), solid_ink=round(float(solid), 2), long_lines=int(long_in), big_circles=n_circ, texts=len(texts))
    if text_ink >= 0.6 or (text_ink >= 0.4 and free - solid <= 0.28):      # 선화 잉크(그 밖 − 채워진 면)가 적으면 쪽
        f['reason'] = f'문자 잉크 {text_ink:.0%}, 선화 잉크 {free - solid:.0%}'; return 'page', f
    if axis >= 0.45 and (long_in >= 80 or (long_in >= 40 and n_circ == 0)):
        f['reason'] = f'축 평행 긴 선 {long_in}개, 선 잉크 {axis:.0%}'; return 'drawing', f
    f['reason'] = f'문자 잉크 {text_ink:.0%}, 큰 원 {n_circ}개, 긴 선 {long_in}개'; return 'illustration', f


# ---------------- 임베딩 ----------------
_EMBED = {}

def embed_images(crops):
    """경량 이미지 임베딩(공개 가중치 분류망의 마지막 특징). 모델이 없으면 사유를 돌려줌."""
    if 'model' not in _EMBED:
        try:
            import torch, torchvision
            m = torchvision.models.resnet18(weights=torchvision.models.ResNet18_Weights.DEFAULT)
            m.fc = torch.nn.Identity(); m.eval()
            _EMBED['model'] = m; _EMBED['torch'] = torch
        except Exception as e:  # 가중치 내려받기 불가(폐쇄망) 등
            msg = str(e).split('\n')[0]
            _EMBED['model'] = None
            _EMBED['err'] = '가중치 내려받기 실패(외부망 차단). 가중치 파일을 torch 캐시 폴더에 두면 동작' if any(w in msg for w in ('urlopen', '403', 'Connection', 'resolve', 'timed out')) else msg[:160]
    if _EMBED['model'] is None:
        return None, _EMBED.get('err', '모델 없음')
    torch = _EMBED['torch']; m = _EMBED['model']
    mean = np.array([0.485, 0.456, 0.406], np.float32); std = np.array([0.229, 0.224, 0.225], np.float32)
    vecs = []
    with torch.no_grad():
        for c in crops:
            im = cv2.resize(cv2.cvtColor(c, cv2.COLOR_GRAY2RGB) if c.ndim == 2 else c, (224, 224)).astype(np.float32) / 255
            x = torch.from_numpy(((im - mean) / std).transpose(2, 0, 1)).unsqueeze(0)
            v = m(x)[0].numpy(); v = v / (np.linalg.norm(v) + 1e-9); vecs.append(v)
    return vecs, None


# ---------------- 부분 그래프 질의 ----------------
def subgraph(g, tag, depth=3):
    nodes = {n['id']: n for n in g['nodes']}
    sz.NOTES.clear()
    def lift(nid):
        n = nodes.get(nid); return n['attached_to'] if n and n.get('attached_to') else nid
    def label(nid):
        return f"{nid}[{nodes[nid]['role']} {sz.name_of(nodes[nid])}]" if nid in nodes else nid
    def where(nid):
        if nid in nodes:
            return 'bbox=(' + ','.join(f"{v:.1f}" for v in nodes[nid]['bbox']) + ')'
        j = next((j for j in g['junctions'] if j['id'] == nid), None)
        return f"pt=({j['pt'][0]:.1f},{j['pt'][1]:.1f})" if j else ''
    start = next((n['id'] for n in g['nodes'] if sz.name_of(n) == tag or tag in n['texts']), None)
    if not start:
        return dict(found=False, lines=[f"'{tag}' 이름의 요소 없음"], nodes=[], runs=[])
    start = lift(start)
    adj = collections.defaultdict(list)
    for r in g['runs']:
        a, b = lift(r['a']), lift(r['b'])
        if a != b:
            adj[a].append((b, r)); adj[b].append((a, r))
    seen, frontier, sub, used = {start}, [start], [], set()
    for _ in range(depth):
        nxt = []
        for v in frontier:
            for w, r in adj[v]:
                if r['id'] in used:
                    continue
                used.add(r['id']); sub.append((v, w, r))
                if w not in seen:
                    seen.add(w); nxt.append(w)
        frontier = nxt
    lines = [f"# 질의 부분 그래프: {tag} 기준 {depth}단계, 간선 {len(sub)}"]
    for v, w, r in sub:
        txt = (f"({'|'.join(r['texts'])})" + sz.line_fields(r['texts'])) if r['texts'] else ''
        lines.append(f"{label(v)} --{r['id']}{txt} {r['kind']}--> {label(w)} 근거={where(v)} {where(w)}")
    lines.append("# 부분 그래프 요소")
    for nid in sorted(seen):
        if nid in nodes and nodes[nid]['role'] not in ('mark', 'arrow'):
            lines.append(sz.node_line(nodes[nid], where(nid)))
    return dict(found=True, start=start, lines=lines, nodes=sorted(seen), runs=sorted(used))


# ---------------- 쪽 · 도해 · 사진의 관계 그래프 ----------------
CAPTION = re.compile(r'^(그림|표|Figure|Fig\.?|Table)\s*(\d+)', re.I)

def relation_graph(kind, k, tables=(), figures=(), paragraphs=(), callouts=(), leaders=(), part_box=None, parts=(), texts=(), page_px=None):
    """도면이 아닌 입력을 같은 노드·간선 형식으로 만든다. 좌표는 mm. 간선 종류: 포함, 소속, 설명, 언급, 순서, 지시."""
    mm = lambda b: [round(v * k, 1) for v in b]
    ctr = lambda b: ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)
    nodes, runs, junctions = [], [], []
    def node(nid, role, box_px, texts_):
        nodes.append(dict(id=nid, role=role, bbox=mm(box_px), texts=[t for t in texts_ if t][:6], degree=0, attached_to=None)); return nid
    def run(a, b, kind_, ca, cb, texts_=(), gap=0):
        runs.append(dict(id=f"r{len(runs)}", a=a, b=b, coords=[[round(ca[0] * k, 2), round(ca[1] * k, 2)], [round(cb[0] * k, 2), round(cb[1] * k, 2)]], kind=kind_, texts=list(texts_), gap=gap))
    row_ids = {}
    def add_tables():
        for ti, t in enumerate(tables):
            tid = node(f"t{ti}", 'table', t['box'], [' | '.join(t['rows'][0])] if t['rows'] else [])
            cbs = t.get('cell_boxes') or []
            for ri, row in enumerate(t['rows']):
                if ri < len(cbs) and cbs[ri]:
                    rb = [min(b[0] for b in cbs[ri]), min(b[1] for b in cbs[ri]), max(b[2] for b in cbs[ri]), max(b[3] for b in cbs[ri])]
                else:
                    y0 = t['box'][1] + (t['box'][3] - t['box'][1]) * ri / max(1, len(t['rows'])); rb = [t['box'][0], int(y0), t['box'][2], int(y0 + (t['box'][3] - t['box'][1]) / max(1, len(t['rows'])))]
                rid = node(f"t{ti}r{ri}", 'row', rb, [' | '.join(c for c in row if c)])
                row_ids[(ti, ri)] = rid
                run(tid, rid, 'contain', ctr(t['box']), ctr(rb))
    if kind == 'page':
        add_tables()
        node_box = {n['id']: n['bbox'] for n in nodes}      # mm
        for fi, f in enumerate(figures):
            fid = node(f"f{fi}", 'figure', f['box'], [' / '.join(f.get('texts', []))] if f.get('texts') else [])
            loc = f.get('table')                                 # [표, 행, 칸] 또는 None
            if isinstance(loc, (list, tuple)) and len(loc) >= 2 and (loc[0], loc[1]) in row_ids:
                rid = row_ids[(loc[0], loc[1])]; rb = node_box[rid]
                run(fid, rid, 'belong', ctr(f['box']), ctr(f['box']), [])
                runs[-1]['coords'][1] = [round((rb[0] + rb[2]) / 2, 2), round((rb[1] + rb[3]) / 2, 2)]
        prev = None
        for pi, p_ in enumerate(paragraphs):
            pid_ = node(f"p{pi}", 'paragraph', p_['box'], [p_['text'][:60]])
            m = CAPTION.match(p_['text'].strip())
            if m:   # 설명문: 가장 가까운 그림 영역 또는 표에 연결
                targets = [(ti, t['box'], 'table') for ti, t in enumerate(tables)] if m.group(1) in ('표', 'Table') else [(fi, f['box'], 'figure') for fi, f in enumerate(figures)]
                if targets:
                    cx, cy = ctr(p_['box'])
                    i_, b_, role = min(targets, key=lambda x: abs(ctr(x[1])[0] - cx) + abs(ctr(x[1])[1] - cy))
                    run(pid_, f"t{i_}" if role == 'table' else f"f{i_}", 'describe', ctr(p_['box']), ctr(b_), [m.group(0)])
            else:
                for (ti, ri), rid in row_ids.items():   # 본문이 표 행의 부품 번호를 언급
                    keys = [c for c in tables[ti]['rows'][ri] if PART_NO.match(c.strip())]
                    hit = [c for c in keys if c.strip() in p_['text']]
                    if hit:
                        run(pid_, rid, 'mention', ctr(p_['box']), ctr([n for n in nodes if n['id'] == rid][0]['bbox']), hit[:2])
                        runs[-1]['coords'][1] = [round(v, 2) for v in ctr([n for n in nodes if n['id'] == rid][0]['bbox'])]
            if prev:
                run(prev, pid_, 'next', ctr(paragraphs[pi - 1]['box']), ctr(p_['box']))
            prev = pid_
    elif kind == 'illustration':
        parts = list(parts) or ([dict(box=part_box)] if part_box else [])
        part_ids = [node(f"part{pi}", 'part', p_['box'], []) for pi, p_ in enumerate(parts)]
        add_tables()
        for ci, c in enumerate(callouts):
            role = {'dimension': 'dimension', 'note': 'note', 'datum': 'datum'}.get(c.get('kind'), 'callout')
            node(f"c{ci}", role, c['box'], [' '.join(c.get('texts', []))])
        with_leader = set()
        for li, l in enumerate(leaders):
            cid = f"c{l['callout']}"; with_leader.add(l['callout'])
            pi = l.get('part') if l.get('part') is not None else (0 if l['end_on_part'] and part_ids else None)
            if pi is not None and pi < len(part_ids):
                run(cid, part_ids[pi], 'point', l['start'], l['end'], [])
            else:
                junctions.append(dict(id=f"j{len(junctions)}", pt=[round(l['end'][0] * k, 2), round(l['end'][1] * k, 2)]))
                run(cid, junctions[-1]['id'], 'point', l['start'], l['end'], [], gap=1)
        for ci, c in enumerate(callouts):      # 지시선 없는 치수는 가장 가까운 투상도에 붙임
            pi = c.get('part')
            if ci not in with_leader and pi is not None and pi < len(part_ids):
                run(f"c{ci}", part_ids[pi], 'dimension', ctr(c['box']), ctr(parts[pi]['box']), [])
    elif kind == 'photo' and page_px:
        ph = node('photo', 'photo', [0, 0, page_px[0], page_px[1]], [])
        for ti, t in enumerate(texts):
            tid = node(f"x{ti}", 'text', t['box'], [t['text']])
            run(ph, tid, 'contain', ctr([0, 0, page_px[0], page_px[1]]), ctr(t['box']))
    # 간선 좌표: 양 끝 노드 중심으로 통일(쪽), 차수 계산
    deg = collections.Counter()
    for r in runs:
        deg[r['a']] += 1; deg[r['b']] += 1
    for n in nodes:
        n['degree'] = deg[n['id']]
    return dict(nodes=nodes, runs=runs, junctions=junctions)

KIND_KO = {'contain': '포함', 'belong': '소속', 'describe': '설명', 'mention': '언급', 'next': '순서', 'point': '지시', 'dimension': '치수'}
ROLE_KO = {'table': '표', 'row': '행', 'figure': '그림', 'paragraph': '문단', 'callout': '주기', 'dimension': '치수', 'note': '주석', 'datum': '기준 문자', 'part': '투상도', 'photo': '사진', 'text': '문자'}

def relation_lines(g):
    nodes = {n['id']: n for n in g['nodes']}
    L = ["## 관계 (노드 종류 · 이름 · 좌표, 간선 종류)"]
    for n in g['nodes']:
        L.append(f"{n['id']} 종류={ROLE_KO.get(n['role'], n['role'])} 이름={(n['texts'][0] if n['texts'] else '-')[:40]} bbox=({','.join(f'{v:.1f}' for v in n['bbox'])})")
    for r in g['runs']:
        lab = f" 라벨={'|'.join(r['texts'])}" if r['texts'] else ''
        L.append(f"{r['id']} 종류={KIND_KO.get(r['kind'], r['kind'])} A={r['a']} B={r['b']}{lab}")
    return L


# ---------------- 색인 ----------------
def build_index(serial_lines, nodes, texts_flat, tables):
    toks = collections.Counter(t.lower() for l in serial_lines for t in WORD.findall(l))
    exact = []
    for n in nodes:
        for t in n.get('texts', []):
            if eg.TAG_EQUIP.match(t) or eg.TAG_LINE.match(t + ' ') or PART_NO.match(t):
                exact.append(dict(key=t, target=n['id'], bbox=n['bbox']))
    for t in texts_flat:
        s = t['text']
        if PART_NO.match(s) or eg.TAG_EQUIP.match(s):
            if not any(e['key'] == s for e in exact):
                exact.append(dict(key=s, target='text', bbox=t.get('bbox') or t.get('box')))
    rows = []
    for ti, tb in enumerate(tables):
        for ri, r in enumerate(tb['rows']):
            rows.append(dict(table=f"t{ti}", row=ri, text=' | '.join(c for c in r)))
    return dict(bm25=dict(tokens=sum(toks.values()), vocab=len(toks), top=toks.most_common(40)), exact=exact, rows=rows)


# ---------------- 본문 묶기 ----------------
HEADING = re.compile(r'^(\d+(\.\d+)*\.?|\d+-\d+\.|[가-힣]\.|\(?[a-zA-Z]\)|[A-Z]{3,}:)\s+\S')

def text_lines(items, k):
    """문자 상자를 같은 줄로 묶음. 세로 중심 차이가 높이의 0.6배 안이면 같은 줄."""
    items = sorted(items, key=lambda t: (t['box'][1], t['box'][0]))
    lines = []
    for t in items:
        h = max(1, t['box'][3] - t['box'][1]); cy = (t['box'][1] + t['box'][3]) / 2
        if lines and abs(lines[-1]['y'] - cy) < 0.6 * min(h, lines[-1]['h']):
            lines[-1]['items'].append(t); lines[-1]['y'] = (lines[-1]['y'] + cy) / 2
        else:
            lines.append(dict(y=cy, h=h, items=[t]))
    for l in lines:
        l['items'].sort(key=lambda t: t['box'][0])
        l['text'] = ' '.join(t['text'] for t in l['items'])
        l['box'] = [min(t['box'][0] for t in l['items']), min(t['box'][1] for t in l['items']), max(t['box'][2] for t in l['items']), max(t['box'][3] for t in l['items'])]
        l['h'] = float(np.median([t['box'][3] - t['box'][1] for t in l['items']]))
    return lines

def find_gutters(items, k):
    """단 사이 빈 세로 띠. 문자 폭 분포의 가운데 6할 안에서 1.2 mm 이상 비고 양쪽에 줄이 3개 이상이면 단 경계."""
    if len(items) < 8:
        return []
    xs0 = sorted(t['box'][0] for t in items); xs1 = sorted(t['box'][2] for t in items)
    L = xs0[len(xs0) // 20]; R = xs1[-1 - len(xs1) // 20]
    if R - L < 40 / k:
        return []
    W = int(R) + 2; cov = np.zeros(W, int)
    for t in items:
        cov[max(0, t['box'][0]):min(W, t['box'][2])] += 1
    lo, hi = int(L + 0.2 * (R - L)), int(R - 0.2 * (R - L))
    lim = max(2, 0.12 * len(text_lines(items, k)))
    gutters, x = [], lo
    while x < hi:
        if cov[x] <= lim:
            x0 = x
            while x < hi and cov[x] <= lim:
                x += 1
            if (x - x0) * k >= 1.2:
                gx = (x0 + x) / 2
                left = [t for t in items if t['box'][2] <= gx]; right = [t for t in items if t['box'][0] >= gx]
                if len(text_lines(left, k)) >= 3 and len(text_lines(right, k)) >= 3:
                    gutters.append(gx)
        x += 1
    return gutters

def paragraphs(texts, exclude_boxes, k):
    """표·그림 밖 OCR 문자를 단, 줄, 문단으로 묶음(좌표 px). 2단 이상이면 단별로 묶고 단을 가로지르는 줄은 따로 둠."""
    items = []
    for t in texts:
        b = t['box']; cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
        if any(x0 <= cx <= x1 and y0 <= cy <= y1 for x0, y0, x1, y1 in exclude_boxes):
            continue
        items.append(t)
    gutters = find_gutters(items, k)
    def col_of(b):
        for gi, gx in enumerate(gutters):
            if b[0] < gx - 3 / k and b[2] > gx + 3 / k:
                return -1                      # 단을 가로지르는 줄(제목·머리글)
        return sum(1 for gx in gutters if (b[0] + b[2]) / 2 > gx)
    groups = collections.defaultdict(list)
    for t in items:
        groups[col_of(t['box'])].append(t)
    paras = []
    for col, its in groups.items():
        lines = text_lines(its, k)
        cur = None
        for l in lines:
            s = l['text'].strip()
            short = (l['box'][2] - l['box'][0]) < 0.55 * (max(t['box'][2] for t in its) - min(t['box'][0] for t in its))
            alone = bool(CAPTION.match(s)) or (bool(HEADING.match(s)) and short)      # 설명문·짧은 제목 줄은 한 줄 문단
            new_para = (cur is None or l['y'] - cur['last_y'] > 1.8 * l['h']
                        or l['h'] > 1.6 * cur['h'] or cur['h'] > 1.6 * l['h']
                        or alone or cur.get('alone') or HEADING.match(s))
            if new_para:
                cur = dict(text=s, box=list(l['box']), last_y=l['y'], h=l['h'], col=col, alone=alone); paras.append(cur)
            else:
                cur['text'] += ' ' + s; cur['last_y'] = l['y']; cur['h'] = (cur['h'] + l['h']) / 2
                cur['box'] = [min(cur['box'][0], l['box'][0]), min(cur['box'][1], l['box'][1]), max(cur['box'][2], l['box'][2]), max(cur['box'][3], l['box'][3])]
    # 읽는 순서: 단을 가로지르는 문단이 띠를 나누고, 띠 안에서는 왼쪽 단부터 위에서 아래로
    spans = sorted([p for p in paras if p['col'] == -1], key=lambda p: p['box'][1])
    def band(p):
        n = sum(1 for sp in spans if sp['box'][3] <= p['box'][1] + 2 / k and sp is not p)
        return n
    paras.sort(key=lambda p: (band(p), p['col'] if p['col'] >= 0 else -1, p['box'][1]))
    for p in paras:
        for key in ('last_y', 'h', 'alone'):
            p.pop(key, None)
        p['bbox_mm'] = [round(v * k, 1) for v in p['box']]
    return paras, gutters


# ---------------- 주 처리 ----------------
class Job:
    def __init__(self, job_dir, name, data, opts, resources, progress):
        self.dir, self.name, self.data, self.opts, self.res, self.progress = job_dir, name, data, opts, resources, progress
        self.times = collections.OrderedDict()

    def step(self, name):
        self.progress(name)
        return time.time()

    def done(self, name, t0):
        self.times[name] = round(time.time() - t0, 1)

    def run(self):
        import torch
        plan = self.res.plan()
        torch.set_num_threads(plan['threads'])
        watch = MemWatch().start()
        out = dict(name=self.name, plan=plan, steps=[])
        try:
            ext = os.path.splitext(self.name)[1].lower()
            src = os.path.join(self.dir, 'input' + ext)
            open(src, 'wb').write(self.data)
            self.prepare(src, ext, plan, out)
            if out['kind'] == 'vector':
                self.vector(out)
            elif out['kind'] == 'drawing':
                self.drawing(out)
            elif out['kind'] == 'page':
                self.page(out)
            elif out['kind'] == 'illustration':
                self.illustration(out)
            else:
                self.photo(out)
            if watch.abort:
                out['warning'] = '가용 메모리가 0.5 GB 아래로 내려감'
        finally:
            watch.stop()
        for key in ('png', 'svg'):
            if out.get(key):
                out[key] = os.path.basename(out[key])
        out['times'] = self.times
        out['memory'] = dict(peak_rss_gb=round(watch.peak_rss, 2), min_avail_gb=(round(watch.min_avail, 2) if watch.min_avail is not None else None))
        out['resources_after'] = self.res.snapshot()
        json.dump(out, open(os.path.join(self.dir, 'result.json'), 'w'), ensure_ascii=False, indent=1, default=str)
        return out

    # ---- 입력: 형식, 사진 여부, 기울기 보정, 문자 인식, 해상도, 종류 ----
    def prepare(self, src, ext, plan, out):
        t0 = self.step('입력 판별')
        if ext == '.svg':
            if self.vector_mechanical(src, out):
                self.done('입력 판별', t0); return
            out.update(kind='vector', svg=src, detect=dict(reason='벡터 SVG'), dpi=None); self.done('입력 판별', t0); return
        dpi_hint = None
        if ext == '.pdf':
            import pymupdf
            doc = pymupdf.open(src); page = doc[int(self.opts.get('page', 0))]
            words = page.get_text('words'); n_draw = len(page.get_drawings())
            if len(words) >= 40 and n_draw <= len(words):
                self.pdf_text_page(page, words, n_draw, out); self.done('입력 판별', t0); return
            if n_draw > 20 or len(page.get_text().strip()) > 50:
                svg = os.path.join(self.dir, 'input.svg'); open(svg, 'w', encoding='utf-8').write(page.get_svg_image(text_as_path=False))
                if self.vector_mechanical(svg, out):
                    self.done('입력 판별', t0); return
                out.update(kind='vector', svg=svg, detect=dict(reason=f'PDF 벡터(경로 {n_draw}개, 문자 있음)'), dpi=None); self.done('입력 판별', t0); return
            pix = page.get_pixmap(dpi=200); src = os.path.join(self.dir, 'input_raster.png'); pix.save(src); dpi_hint = 200
        gray = cv2.imread(src, cv2.IMREAD_GRAYSCALE)
        if gray is None:
            raise ValueError('이미지를 읽지 못함')
        meta_dpi = dpi_hint or image_dpi(src)
        H, W = gray.shape; mp = W * H / 1e6; resized = False
        if mp > plan['max_mp']:
            s = math.sqrt(plan['max_mp'] / mp); gray = cv2.resize(gray, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
            meta_dpi = int(round(meta_dpi * s)) if meta_dpi else None; resized = True; H, W = gray.shape
        photo, pf = is_photo(gray)
        info = dict(px=[int(W), int(H)], resized=resized, **pf)
        if photo:
            png = os.path.join(self.dir, 'input_gray.png'); cv2.imwrite(png, gray)
            dpi, src_ = (meta_dpi, '파일 메타데이터') if meta_dpi else (96, '사진, 해상도 미정(96 가정)')
            info.update(reason='연속 계조 비율이 높음', dpi_source=src_)
            out.update(kind='photo', png=png, dpi=dpi, detect=info, view=dict(url='input_gray.png', w=W, h=H, mm_per_px=25.4 / dpi))
            self.done('입력 판별', t0); return
        gray, skew = rg.deskew(gray)                 # 잡음 제거(중앙값 필터)는 도면 경로 안에서만 수행. 100 dpi 작은 글자가 뭉개짐
        png = os.path.join(self.dir, 'input_gray.png'); cv2.imwrite(png, gray)
        self.done('입력 판별', t0)
        t0 = self.step('문자 인식')
        reader = TunedReader(plan['batch'])
        raw, texts, secs = run_ocr(gray, reader, os.path.join(self.dir, 'doc'))
        json.dump(texts, open(os.path.join(self.dir, 'page_ocr.json'), 'w'), ensure_ascii=False)   # 쪽 경로의 캐시 형식
        self.done('문자 인식', t0); self.times['문자 인식'] = max(self.times['문자 인식'], round(secs, 1))
        t0 = self.step('해상도 · 종류 판별')
        sure = [t for t in texts if t['conf'] >= 0.2]      # 종류·해상도 판별에는 신뢰도 0.2 이상 문자만 사용(낮은 것은 기호 조각일 수 있음)
        dpi, src_ = estimate_dpi(W, H, sure, meta_dpi)
        kind, f = classify(gray, sure, dpi)
        info.update(f, dpi_source=src_, ocr_lang=reader.lang_used, skew_deg=round(skew, 2))
        out.update(kind=kind, png=png, dpi=dpi, detect=info, texts=texts, view=dict(url='input_gray.png', w=W, h=H, mm_per_px=25.4 / dpi))
        self.done('해상도 · 종류 판별', t0)

    # ---- 벡터 ----
    def vector(self, out):
        prefix = os.path.join(self.dir, 'graph')
        t0 = self.step('요소 추출 · 관계 그래프')
        g = eg.main(out['svg'], prefix); self.done('요소 추출 · 관계 그래프', t0)
        import pymupdf
        t0 = self.step('보기 그림')
        doc = pymupdf.open(out['svg']); page = doc[0]; pix = page.get_pixmap(dpi=150); pix.save(os.path.join(self.dir, 'view.png'))
        out['view'] = dict(url='view.png', w=pix.width, h=pix.height, mm_per_px=g['page'][0] / pix.width)
        self.done('보기 그림', t0)
        self.finish_graph(g, out, prefix, texts_px=[])

    # ---- 래스터 도식 ----
    def drawing(self, out):
        prefix = os.path.join(self.dir, 'graph')
        t0 = self.step('선 · 도형 · 기호 · 관계 그래프')
        g = rg.main(out['png'], out['dpi'], prefix, ocr_json=os.path.join(self.dir, 'doc_ocr.json'))
        self.times.update({k: v for k, v in g['times'].items() if k not in ('total', 'ocr')})
        self.done('선 · 도형 · 기호 · 관계 그래프', t0)
        out['view']['url'] = 'graph_input.png'
        self.finish_graph(g, out, prefix, out['texts'])

    def finish_graph(self, g, out, prefix, texts_px):
        t0 = self.step('직렬화')
        # 연결도 문자도 없는 4 mm 미만 조각(래스터 잡음)은 그래프에서 제외
        used = {r['a'] for r in g['runs']} | {r['b'] for r in g['runs']} | {n.get('attached_to') for n in g['nodes']} | {n.get('annotates') for n in g['nodes']}
        def noise(n):
            return (n['role'] in ('symbol', 'mark') and not n['texts'] and n['id'] not in used
                    and max(n['bbox'][2] - n['bbox'][0], n['bbox'][3] - n['bbox'][1]) < 4.0)
        dropped = [n['id'] for n in g['nodes'] if noise(n)]
        if dropped:
            g['nodes'] = [n for n in g['nodes'] if n['id'] not in dropped]
            g['counts'] = dict(g.get('counts', {}), dropped_fragments=len(dropped))
            json.dump(g, open(prefix + '.json', 'w'), ensure_ascii=False, indent=1, default=str)
        sz.main(prefix + '.json', prefix + '.txt')
        serial = open(prefix + '.txt', encoding='utf-8').read().splitlines(); self.done('직렬화', t0)
        t0 = self.step('색인')
        idx = build_index(serial, g['nodes'], texts_px, g.get('tables', [])); self.done('색인', t0)
        out.update(nodes=[dict(id=n['id'], role=n['role'], bbox=n['bbox'], texts=n['texts'], degree=n['degree'], attached_to=n.get('attached_to')) for n in g['nodes']],
                   junctions=g['junctions'], runs=[dict(id=r['id'], a=r['a'], b=r['b'], coords=r['coords'], kind=r['kind'], texts=r['texts'], gap=r['gap']) for r in g['runs']],
                   tables=[dict(bbox=t['bbox'], rows=t['rows']) for t in g.get('tables', [])], texts=texts_px, labels=[l for l in g.get('labels', []) if l.get('owner')],
                   counts=dict(g['counts'], **collections.Counter(n['role'] for n in g['nodes'])), serial=serial, index=idx)
        self.embed_page(out)

    def vector_mechanical(self, svg, out):
        """벡터 도면 중 기계 도면(장비·계기 태그 없음, 치수 문자 있음)은 200 dpi로 그려 도해 경로에 넘기고 문자는 벡터 좌표를 그대로 쓴다."""
        try:
            W, H, prims, vtexts = eg.load_primitives(svg)
        except Exception:
            return False
        norm = lambda t: t[:1] + t[1:].replace('O', '0')
        tags = [t for t in vtexts if eg.TAG_EQUIP.match(norm(t['text']))]
        instr = [t for t in vtexts if eg.TAG_INSTR.match(t['text'])]
        dims = [t for t in vtexts if rd.DIM.search(t['text']) and any(c.isdigit() for c in t['text'])]
        if tags or len(instr) >= 2 or len(dims) < 2:
            return False
        import pymupdf
        dpi = 200
        pix = pymupdf.open(svg)[0].get_pixmap(dpi=dpi, colorspace='gray'); png = os.path.join(self.dir, 'input_gray.png'); pix.save(png)
        sc = pix.width / W
        texts, raw = [], []
        for t in vtexts:
            b = eg.text_bbox(t).bounds; bx = [int(b[0] * sc), int(b[1] * sc), int(b[2] * sc), int(b[3] * sc)]
            texts.append(dict(text=t['text'], conf=1.0, box=bx)); raw.append([[[bx[0], bx[1]], [bx[2], bx[1]], [bx[2], bx[3]], [bx[0], bx[3]]], t['text'], 1.0])
        json.dump(raw, open(os.path.join(self.dir, 'doc_ocr.json'), 'w')); json.dump(texts, open(os.path.join(self.dir, 'page_ocr.json'), 'w'), ensure_ascii=False)
        self.times['문자 인식'] = 0.0
        out.update(kind='illustration', png=png, dpi=dpi, texts=texts, view=dict(url='input_gray.png', w=pix.width, h=pix.height, mm_per_px=25.4 / dpi),
                   detect=dict(px=[pix.width, pix.height], reason=f'벡터 기계 도면(치수 문자 {len(dims)}개, 장비 태그 없음, 200 dpi로 그림)', dpi_source='벡터 200 dpi 렌더', ocr_lang='벡터 문자(문자 인식 생략)'))
        return True

    def pdf_text_page(self, page, words, n_draw, out):
        """글자 층이 있는 PDF 문서 쪽: 문자 인식 없이 글자 좌표를 줄 단위로 묶어 쪽 경로에 넘김."""
        dpi = 200; sc = dpi / 72.0
        pix = page.get_pixmap(dpi=dpi, colorspace='gray'); png = os.path.join(self.dir, 'input_gray.png'); pix.save(png)
        gray = cv2.imread(png, 0); H, W = gray.shape
        lines = collections.OrderedDict()
        for x0, y0, x1, y1, w, b, l, _ in words:
            lines.setdefault((b, l), []).append((x0, y0, x1, y1, w))
        texts, raw = [], []
        for ws in lines.values():
            ws.sort(key=lambda t: t[0])
            x0, y0 = min(t[0] for t in ws) * sc, min(t[1] for t in ws) * sc; x1, y1 = max(t[2] for t in ws) * sc, max(t[3] for t in ws) * sc
            s = ' '.join(t[4] for t in ws).strip()
            if not s:
                continue
            texts.append(dict(text=s, conf=1.0, box=[int(x0), int(y0), int(x1), int(y1)]))
            raw.append([[[x0, y0], [x1, y0], [x1, y1], [x0, y1]], s, 1.0])
        json.dump(raw, open(os.path.join(self.dir, 'doc_ocr.json'), 'w')); json.dump(texts, open(os.path.join(self.dir, 'page_ocr.json'), 'w'), ensure_ascii=False)
        self.times['문자 인식'] = 0.0
        out.update(kind='page', png=png, dpi=dpi, texts=texts, view=dict(url='input_gray.png', w=W, h=H, mm_per_px=25.4 / dpi),
                   detect=dict(px=[int(W), int(H)], reason=f'PDF 글자 층(단어 {len(words)}개, 그림 경로 {n_draw}개)', dpi_source='PDF 200 dpi 렌더', ocr_lang='글자 층(문자 인식 생략)'))

    # ---- 표 · 본문 쪽 ----
    def page(self, out):
        prefix = os.path.join(self.dir, 'page'); dpi = out['dpi']; k = 25.4 / dpi
        t0 = self.step('표 · 그림 영역')
        res = rd.main(out['png'], dpi, 'table', prefix); res['image']['path'] = os.path.basename(res['image']['path'])
        json.dump(res, open(prefix + '.json', 'w'), ensure_ascii=False, indent=1)
        self.times['structure'] = res['times']['structure']; self.done('표 · 그림 영역', t0)
        t0 = self.step('본문 묶기')
        paras, gutters = paragraphs(res['texts'], [t['box'] for t in res['tables']] + [f['box'] for f in res['figures'] if f.get('frame')], k); self.done('본문 묶기', t0)
        t0 = self.step('직렬화')
        serial = ["# 쪽 구조 (좌표 단위 mm, 원점 좌상단)", "## 표"]
        tables = []
        for ti, tb in enumerate(res['tables']):
            bb = [round(v * k, 1) for v in tb['box']]
            serial.append(f"t{ti} bbox=({','.join(map(str, bb))}) 행수={tb['n_rows']} 열수={tb['n_cols']}")
            for ri, row in enumerate(tb['rows']):
                serial.append(f"t{ti} 행{ri}: " + ' | '.join(row))
            tables.append(dict(bbox=bb, box=tb['box'], rows=tb['rows'], cell_boxes=tb.get('cell_boxes')))
        serial.append("## 그림 영역")
        for fi, f in enumerate(res['figures']):
            loc = f.get('table'); owner = f" 소속=t{loc[0]} 행{loc[1]}" if isinstance(loc, (list, tuple)) and len(loc) >= 2 else ''
            inner = f" 안 문자={' / '.join(f['texts'])}" if f.get('texts') else ''
            serial.append(f"f{fi} bbox=({','.join(str(round(v * k, 1)) for v in f['box'])}){owner}{inner}")
        serial.append("## 본문" + (f" ({len(gutters) + 1}단)" if gutters else ''))
        for i, p in enumerate(paras):
            serial.append(f"p{i} bbox=({','.join(map(str, p['bbox_mm']))}) {p['text']}")
        g = relation_graph('page', k, tables=tables, figures=res['figures'], paragraphs=paras); serial += relation_lines(g)
        open(prefix + '.txt', 'w', encoding='utf-8').write('\n'.join(serial) + '\n'); self.done('직렬화', t0)
        t0 = self.step('색인')
        idx = build_index(serial, g['nodes'], res['texts'], tables); self.done('색인', t0)
        out.update(tables=tables, figures=res['figures'], paragraphs=paras, texts=res['texts'], **g,
                   counts=dict(res['summary'], paragraphs=len(paras), texts=len(res['texts']), nodes=len(g['nodes']), runs=len(g['runs'])), serial=serial, index=idx)
        self.embed_page(out, crops=[f['box'] for f in res['figures']])

    # ---- 도해 · 기계 도면(투상도 · 치수 · 주기 · 지시선 · 표제란) ----
    def illustration(self, out):
        prefix = os.path.join(self.dir, 'page'); dpi = out['dpi']; k = 25.4 / dpi
        t0 = self.step('투상도 · 치수 · 지시선 · 표제란')
        res = rd.main(out['png'], dpi, 'drawing', prefix); res['image']['path'] = os.path.basename(res['image']['path'])
        json.dump(res, open(prefix + '.json', 'w'), ensure_ascii=False, indent=1)
        self.times['structure'] = res['times']['structure']; self.done('투상도 · 치수 · 지시선 · 표제란', t0)
        t0 = self.step('직렬화')
        mm = lambda b: ','.join(str(round(v * k, 1)) for v in b)
        parts = res.get('parts') or ([dict(box=res['part_box'])] if res.get('part_box') else [])
        serial = ["# 도해 · 기계 도면 구조 (좌표 단위 mm, 원점 좌상단)", "## 투상도(부품) 영역"]
        serial += [f"part{i} bbox=({mm(p['box'])})" for i, p in enumerate(parts)] or ["없음"]
        tables = []
        serial.append("## 표 (표제란 등)")
        for ti, tb in enumerate(res.get('tables', [])):
            bb = [round(v * k, 1) for v in tb['box']]
            serial.append(f"t{ti} bbox=({','.join(map(str, bb))}) 행수={tb['n_rows']} 열수={tb['n_cols']}")
            for ri, row in enumerate(tb['rows']):
                serial.append(f"t{ti} 행{ri}: " + ' | '.join(row))
            tables.append(dict(bbox=bb, box=tb['box'], rows=tb['rows'], cell_boxes=tb.get('cell_boxes')))
        serial.append("## 치수 · 주기 (문자 묶음)")
        for i, c in enumerate(res['callouts']):
            own = f" 소속=part{c['part']}" if c.get('part') is not None else ''
            serial.append(f"c{i} 종류={ROLE_KO.get(c.get('kind'), '주기')}{own} bbox=({mm(c['box'])}) {c.get('text') or ' '.join(c.get('texts', []))}")
        serial.append("## 지시선 (주기 → 가리키는 위치)")
        for l in res['leaders']:
            tgt = f"part{l['part']}" if l.get('part') is not None else ('부품 위' if l['end_on_part'] else '빈 곳')
            serial.append(f"c{l['callout']} → ({round(l['end'][0] * k, 1)},{round(l['end'][1] * k, 1)}) 길이={l['length_mm']}mm 대상={tgt}")
        g = relation_graph('illustration', k, tables=tables, callouts=res['callouts'], leaders=res['leaders'], parts=parts); serial += relation_lines(g)
        open(prefix + '.txt', 'w', encoding='utf-8').write('\n'.join(serial) + '\n'); self.done('직렬화', t0)
        t0 = self.step('색인')
        idx = build_index(serial, g['nodes'], res['texts'], tables); self.done('색인', t0)
        out.update(tables=tables, callouts=res['callouts'], leaders=res['leaders'], parts=parts, part_box=res.get('part_box'), texts=res['texts'], **g,
                   counts=dict(res['summary'], texts=len(res['texts']), nodes=len(g['nodes']), runs=len(g['runs'])), serial=serial, index=idx)
        self.embed_page(out, crops=[p['box'] for p in parts])

    # ---- 사진 ----
    def photo(self, out):
        gray = cv2.imread(out['png'], 0); k = 25.4 / out['dpi']
        t0 = self.step('문자 인식')
        reader = TunedReader(8)
        raw, texts, secs = run_ocr(gray, reader, os.path.join(self.dir, 'doc')); out['detect']['ocr_lang'] = reader.lang_used
        self.done('문자 인식', t0); self.times['문자 인식'] = max(self.times['문자 인식'], round(secs, 1))
        serial = ["# 사진·렌더링 (구조 추출 없음, 이미지 검색 대상)", f"크기 {gray.shape[1]}×{gray.shape[0]} px", "## 사진 위 문자"]
        serial += [f"{t['text']} bbox=({','.join(str(round(v * k, 1)) for v in t['box'])})" for t in texts]
        g = relation_graph('photo', k, texts=texts, page_px=[gray.shape[1], gray.shape[0]]); serial += relation_lines(g)
        idx = build_index(serial, g['nodes'], texts, [])
        out.update(tables=[], texts=texts, **g, counts=dict(texts=len(texts), nodes=len(g['nodes']), runs=len(g['runs'])), serial=serial, index=idx)
        self.embed_page(out)

    def embed_page(self, out, crops=()):
        t0 = self.step('이미지 임베딩')
        img = cv2.imread(os.path.join(self.dir, out['view']['url']), 0)
        regions = [('page', [0, 0, img.shape[1], img.shape[0]])] + [(f'fig{i}', [int(v) for v in b]) for i, b in enumerate(crops)]
        regions = [(rid, b) for rid, b in regions if b[3] > b[1] and b[2] > b[0]]
        vecs, err = embed_images([img[b[1]:b[3], b[0]:b[2]] for _, b in regions])
        if vecs is None:
            out['embedding'] = dict(available=False, reason=err, regions=len(regions))
        else:
            out['embedding'] = dict(available=True, dims=int(len(vecs[0])), items=[dict(id=rid, bbox=b, head=[round(float(v), 4) for v in vec[:32]]) for (rid, b), vec in zip(regions, vecs)])
        self.done('이미지 임베딩', t0)
