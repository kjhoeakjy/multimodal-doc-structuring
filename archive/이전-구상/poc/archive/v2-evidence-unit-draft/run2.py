"""PoC v2: 선택적 추출 -> 정보 단위(Evidence Unit) -> 3층 검증 -> 목적별 조회. 기준선과 비교."""
import json, re, glob, os, sys, time, subprocess, sqlite3, hashlib, random
from collections import Counter, defaultdict
import numpy as np, cv2, pdfplumber, pytesseract
from PIL import Image
from rank_bm25 import BM25Okapi

D = sys.argv[1] if len(sys.argv) > 1 else "data"
truth = json.load(open(f"{D}/truth.json"))
TMP = f"{D}/render"; os.makedirs(TMP, exist_ok=True)
ID_RE = re.compile(r"^[A-Z]{2}-\d{3}$")
ATTR = {"TEMPERATURE": "max_temperature", "PRESSURE": "max_pressure"}
COND = {"NORMAL": "normal", "EMERG": "emergency"}


def render(pdf, dpi):
    out = f"{TMP}/{os.path.basename(pdf)[:-4]}_{dpi}"
    if not os.path.exists(out + ".png"):
        subprocess.run(["pdftoppm", "-r", str(dpi), "-png", "-singlefile", pdf, out], check=True)
    return cv2.imread(out + ".png", cv2.IMREAD_GRAYSCALE)


def norm_unit(h):
    h = h.upper().replace(" ", "")
    if "KPA" in h: return "kPa"
    if "PSI" in h: return "psi"
    if re.search(r"[°º*o]?C\)", h): return "°C"
    return None


def fix_id(s):
    s = s.strip().upper().replace(" ", "").replace("—", "-").replace("–", "-")
    m = re.match(r"^([A-Z]{2})-?(\d{3})$", s)
    return f"{m.group(1)}-{m.group(2)}" if m else s


# ---------- 표 격자 복원 ----------
def grid_from_cells(cells):
    """cells: [(x0,y0,x1,y1,text)] -> 병합을 채운 2차원 격자"""
    xs = sorted(set(round(c[0]) for c in cells) | set(round(c[2]) for c in cells))
    ys = sorted(set(round(c[1]) for c in cells) | set(round(c[3]) for c in cells))
    def merge(v, tol):
        out = []
        for a in v:
            if not out or a - out[-1] > tol: out.append(a)
        return out
    xs, ys = merge(xs, 6), merge(ys, 6)
    near = lambda v, arr: min(range(len(arr)), key=lambda i: abs(arr[i] - v))
    G = [[None] * (len(xs) - 1) for _ in range(len(ys) - 1)]
    span = {}
    for x0, y0, x1, y1, t in cells:
        c0, c1, r0, r1 = near(x0, xs), near(x1, xs), near(y0, ys), near(y1, ys)
        for r in range(r0, r1):
            for c in range(c0, c1):
                G[r][c] = t; span[(r, c)] = (r0, c0, r1 - r0, c1 - c0)
    return G, span


def table_to_units(G, cell_box, doc, config, path):
    """다단 헤더 2행 + 본문. 병합 셀은 격자 채움으로 보존."""
    units = []
    h1, h2 = G[0], G[1]
    for ri in range(2, len(G)):
        row = G[ri]
        group, target = (row[0] or "").strip(), fix_id(row[1] or "")
        for ci in range(2, len(row)):
            top, sub = (h1[ci] or ""), (h2[ci] or "")
            attr = next((v for k, v in ATTR.items() if k in top.upper()), None)
            cond = next((v for k, v in COND.items() if k in sub.upper()), None)
            units.append({"doc": doc, "target": target, "group": group, "attr": attr, "cond": cond, "config": config,
                          "raw": (row[ci] or "").strip(), "unit": norm_unit(top), "src": {"page": 1, "table": 1, "row": ri, "col": ci, "bbox": cell_box.get((ri, ci))},
                          "path": path})
    return units


def digital_table(page):
    t = page.find_tables({"vertical_strategy": "lines", "horizontal_strategy": "lines"})[0]
    cells = []
    for c in t.cells:
        txt = page.within_bbox(c).extract_text() or ""
        cells.append((c[0], c[1], c[2], c[3], txt.replace("\n", " ")))
    G, span = grid_from_cells(cells)
    boxes = {}
    for c in cells:
        pass
    # 셀 좌표(포인트)
    for (r, cidx), (r0, c0, rs, cs) in span.items():
        boxes[(r, cidx)] = None
    xs = sorted(set(round(c[0]) for c in cells) | set(round(c[2]) for c in cells))
    return G, {k: v for k, v in boxes.items()}, cells


def detect_cells(img):
    """스캔 이미지에서 선 검출로 셀 영역 복원(병합 셀 포함)."""
    bw = cv2.adaptiveThreshold(img, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 25, 15)
    H, W = img.shape
    hl = cv2.morphologyEx(bw, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (W // 12, 1)))
    vl = cv2.morphologyEx(bw, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, 12)))
    lines = cv2.dilate(cv2.bitwise_or(hl, vl), np.ones((3, 3), np.uint8))
    cnts, _ = cv2.findContours(lines, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    tx, ty, tw, th = max((cv2.boundingRect(c) for c in cnts), key=lambda b: b[2] * b[3])
    region = 255 - lines[ty:ty + th, tx:tx + tw]
    n, lab, stats, _ = cv2.connectedComponentsWithStats(region, connectivity=4)
    cells = []
    for i in range(1, n):
        x, y, w, h, a = stats[i]
        if w < 15 or h < 12 or (x == 0 and y == 0 and w == tw): continue
        if x <= 1 or y <= 1 or x + w >= tw - 1 or y + h >= th - 1: continue
        cells.append((tx + x, ty + y, tx + x + w, ty + y + h))
    return cells, (tx, ty, tw, th)


def ocr_cell(img, box, scale=2, psm=7, wl=None):
    x0, y0, x1, y1 = box
    crop = img[y0 + 2:y1 - 2, x0 + 2:x1 - 2]
    crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    crop = cv2.copyMakeBorder(crop, 10, 10, 10, 10, cv2.BORDER_CONSTANT, value=255)
    cfg = f"--psm {psm}" + (f" -c tessedit_char_whitelist={wl}" if wl else "")
    return pytesseract.image_to_string(crop, config=cfg).strip().replace("\n", " ")


def ocr_cell_alt(img, box):
    x0, y0, x1, y1 = box
    crop = img[y0 + 2:y1 - 2, x0 + 2:x1 - 2]
    crop = cv2.resize(crop, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    crop = cv2.medianBlur(crop, 3)
    _, crop = cv2.threshold(crop, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    crop = cv2.copyMakeBorder(crop, 12, 12, 12, 12, cv2.BORDER_CONSTANT, value=255)
    return pytesseract.image_to_string(crop, config="--psm 7 -c tessedit_char_whitelist=0123456789").strip()


def figure_ids(img, box):
    """그림 영역에서 사각형 객체를 탐지하고 객체 내부 주석만 판독."""
    x0, y0, x1, y1 = box
    crop = img[y0:y1, x0:x1]
    bw = cv2.adaptiveThreshold(crop, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 25, 15)
    bw = cv2.morphologyEx(bw, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    cnts, hier = cv2.findContours(bw, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    ids = {}
    for c, hh in zip(cnts, hier[0]):
        if hh[3] < 0: continue  # 사각형 내부(구멍) 윤곽
        x, y, w, h = cv2.boundingRect(c)
        if not (40 < w < 400 and 20 < h < 200 and 1.4 < w / h < 4.5): continue
        inner = crop[y + 3:y + h - 3, x + 3:x + w - 3]
        inner = cv2.resize(inner, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
        inner = cv2.copyMakeBorder(inner, 10, 10, 10, 10, cv2.BORDER_CONSTANT, value=255)
        t = fix_id(pytesseract.image_to_string(inner, config="--psm 7").strip())
        OBJ_CALLS[0] += 1
        if ID_RE.match(t): ids[t] = (x0 + x, y0 + y, x0 + x + w, y0 + y + h)
    return ids


OBJ_CALLS = [0]


def ocr_table_words(img, tb, cells_b):
    """표 영역을 한 번 판독한 뒤 단어를 셀에 배정."""
    tx, ty, tw, th = tb
    region = cv2.resize(img[ty:ty + th, tx:tx + tw], None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    d = pytesseract.image_to_data(region, config="--psm 11", output_type=pytesseract.Output.DICT)
    texts = {b: [] for b in cells_b}
    for t, l, tp, w, h in zip(d["text"], d["left"], d["top"], d["width"], d["height"]):
        if not t.strip(): continue
        cx, cy = tx + (l + w / 2) / 2, ty + (tp + h / 2) / 2
        for b in cells_b:
            if b[0] <= cx <= b[2] and b[1] <= cy <= b[3]: texts[b].append((tp, l, t)); break
    return {b: " ".join(t for _, _, t in sorted(v)) for b, v in texts.items()}


# ---------- 제안 방식: 선택적 추출 ----------
def extract_doc(pdf):
    name = os.path.basename(pdf)[:-4]
    pl = pdfplumber.open(pdf); page = pl.pages[0]
    digital = len(page.chars) > 50
    stats = Counter()
    if digital:
        stats["parser_pages"] += 1
        text = page.extract_text()
        t = page.find_tables({"vertical_strategy": "lines", "horizontal_strategy": "lines"})[0]
        cells = [(c[0], c[1], c[2], c[3], (page.within_bbox(c).extract_text() or "").replace("\n", " ")) for c in t.cells]
        G, span = grid_from_cells(cells)
        sc = 150 / 72
        cell_box = {}
        for x0, y0, x1, y1, tx in cells:
            for (r, c), (r0, c0, rs, cs) in span.items():
                pass
        # 셀 좌표: 격자 위치별 원래 셀 경계
        xs = sorted(set(round(c[0]) for c in cells) | set(round(c[2]) for c in cells))
        img = None
        # 그림: 내장 이미지 영역에 한정해 OCR
        im0 = page.images[0]; img = render(pdf, 150)
        fb = tuple(int(v * sc) for v in (im0["x0"], im0["top"], im0["x1"], im0["bottom"]))
        fig = figure_ids(img, fb)
        path = "parser"
        cell_src = {}
        for x0, y0, x1, y1, tx in cells:
            cell_src[(round(x0), round(y0))] = (x0, y0, x1, y1)
    else:
        stats["ocr_pages"] += 1
        img = render(pdf, 150)
        cells_b, tb = detect_cells(img)
        # 표 밖 텍스트·그림: 표 위 본문, 표 아래 그림 영역
        H, W = img.shape
        text = pytesseract.image_to_string(img[:tb[1], :], config="--psm 6")
        stats["ocr_regions"] += 1
        below = img[tb[1] + tb[3]:, :]
        fig_top = tb[1] + tb[3]
        fig = figure_ids(img, (0, fig_top, W, min(H, fig_top + int(H * 0.35))))
        words = ocr_table_words(img, tb, cells_b); stats["ocr_regions"] += 1
        cells = [(b[0], b[1], b[2], b[3], words[b]) for b in cells_b]
        G, span = grid_from_cells(cells)
        path = "ocr"
    m = re.search(r"apply to Configuration\s+([A-Z])", text or "")
    config = m.group(1) if m else None
    # 셀 좌표 매핑
    xs = sorted(set(round(c[0]) for c in cells) | set(round(c[2]) for c in cells))
    box = {}
    for (r, c), (r0, c0, rs, cs) in span.items():
        pass
    # 행·열 위치를 셀 경계로 역매핑
    def cell_at(r, c):
        # span 의 기준 셀을 찾아 원 셀 좌표 반환
        r0, c0, rs, cs = span[(r, c)]
        for x0, y0, x1, y1, t in cells:
            if (r, c) in span and t == G[r][c]:
                pass
        return None
    # 간단히: 셀 중심이 격자 칸에 들어가는 셀
    ys_all = sorted(set(round(c[1]) for c in cells) | set(round(c[3]) for c in cells))
    cell_box = {}
    for x0, y0, x1, y1, t in cells:
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        cell_box[(x0, y0)] = (x0, y0, x1, y1)
    rows_y = sorted(set((round(c[1]), round(c[3])) for c in cells))
    # 격자 인덱스별 bbox: span 정보로 계산
    xs_m, ys_m = [], []
    for v in sorted(set(round(c[0]) for c in cells) | set(round(c[2]) for c in cells)):
        if not xs_m or v - xs_m[-1] > 6: xs_m.append(v)
    for v in sorted(set(round(c[1]) for c in cells) | set(round(c[3]) for c in cells)):
        if not ys_m or v - ys_m[-1] > 6: ys_m.append(v)
    for (r, c) in span:
        cell_box[(r, c)] = (xs_m[c], ys_m[r], xs_m[c + 1], ys_m[r + 1])
    units = table_to_units(G, cell_box, name, config, path)
    return {"doc": name, "digital": digital, "text": text, "config": config, "fig": fig, "units": units, "img": img, "stats": stats}


# ---------- 3층 검증 ----------
def verify(ex):
    img = ex["img"]; units = ex["units"]; fig = ex["fig"]
    by_t = defaultdict(dict)
    for u in units:
        u["checks"] = {}
        try: u["value"] = float(u["raw"].replace(",", ""))
        except ValueError: u["value"] = None
    def struct_ok(u):
        return u["value"] is not None and u["unit"] in ("°C", "kPa", "psi") and u["attr"] and u["cond"] and ID_RE.match(u["target"] or "") and u["config"]
    def rel_ok(u, idx):
        if u["target"] not in fig: return False, "그림 객체 미대응"
        pair = idx.get((u["target"], u["attr"]), {})
        n, e = pair.get("normal"), pair.get("emergency")
        if n is not None and e is not None and e < n: return False, "비상 한계 < 정상 한계"
        lo, hi = {"°C": (-60, 400), "kPa": (100, 50000), "psi": (15, 7500)}[u["unit"]]
        if not (lo <= u["value"] <= hi): return False, "물리 범위 이탈"
        return True, ""
    def build_idx():
        idx = defaultdict(dict)
        for u in units:
            if u["value"] is not None and u["attr"] and u["cond"]: idx[(u["target"], u["attr"])][u["cond"]] = u["value"]
        return idx
    idx = build_idx()
    for u in units:
        s = bool(struct_ok(u)); r, why = rel_ok(u, idx) if s else (False, "구조 오류")
        # 원문 검증: 셀 영역 재판독
        if ex["digital"]:
            src = True
        else:
            alt = ocr_cell_alt(img, u["src"]["bbox"]) if u["src"]["bbox"] else ""
            u["alt"] = alt
            src = s and alt != "" and u["value"] == float(alt) if alt.isdigit() else False
        u["checks"] = {"structure": s, "relation": r, "source": src, "why": why}
        u["status"] = "verified" if (s and r and src) else "recheck"
    # 재분석: 실패 셀은 대체 판독값으로 재구성 후 재검증
    for u in units:
        if u["status"] == "recheck" and not ex["digital"]:
            alt = u.get("alt", "")
            if alt.isdigit():
                old = u["value"]; u["value"] = float(alt)
                idx = build_idx()
                s = bool(struct_ok(u)); r, why = rel_ok(u, idx) if s else (False, "구조 오류")
                if s and r:
                    u["status"] = "verified_reanalysis"; continue
                u["value"] = old
        if u["status"] == "recheck": u["status"] = "review"
    return units


# ---------- 실행 ----------
t0 = time.time()
EX = [extract_doc(p) for p in sorted(glob.glob(f"{D}/pdf/*.pdf"))]
t_extract = time.time() - t0
for ex in EX: verify(ex)
t_prop = time.time() - t0
U = [u for ex in EX for u in ex["units"]]

# 정답 대조
F = {(f["doc"], f["target"], f["attr"], f["cond"]): f for f in truth["facts"]}
def correct(u):
    f = F.get((u["doc"], u["target"], u["attr"], u["cond"]))
    return bool(f and u["value"] is not None and abs(u["value"] - f["value"]) < 1e-9 and u["unit"] == f["unit"] and u["config"] == f["config"])
for u in U: u["correct"] = correct(u)
gold = len(truth["facts"])
pred_keys = set((u["doc"], u["target"], u["attr"], u["cond"]) for u in U)

def block(us):
    n = len(us); c = sum(u["correct"] for u in us)
    return n, c
res = {}
for path in ["parser", "ocr"]:
    us = [u for u in U if u["path"] == path]
    n, c = block(us)
    ver = [u for u in us if u["status"].startswith("verified")]; rev = [u for u in us if u["status"] == "review"]
    res[path] = {"정보 단위": n, "1차 추출 정확도": c / n,
                 "검증 통과": len(ver), "검증 통과 정확도": (sum(u["correct"] for u in ver) / len(ver)) if ver else None,
                 "재분석 복구": sum(1 for u in us if u["status"] == "verified_reanalysis"),
                 "검토 분리": len(rev), "검토 분리 중 실제 오류": sum(1 for u in rev if not u["correct"]),
                 "오류 포착률": (sum(1 for u in us if not u["correct"] and not u["status"].startswith("verified")) / max(1, sum(1 for u in us if not u["correct"])))}
# 추출 전과 검증 후 확정 정보 기준 오류율
first_err = sum(1 for u in U if not u["correct"])
# 1차 추출값 기준 오류(재분석 이전) 계산 위해 재분석 복구 건은 1차에서 오류였음
reanal = [u for u in U if u["status"] == "verified_reanalysis"]
conf = [u for u in U if u["status"].startswith("verified")]
summary = {"정답 사실 수": gold, "추출 정보 단위": len(U), "재현율": len(pred_keys & set(F)) / gold,
           "확정 정보 정확도": sum(u["correct"] for u in conf) / len(conf), "확정 비율": len(conf) / len(U),
           "검토 분리": sum(1 for u in U if u["status"] == "review")}

# 그림-표 연결
links = sum(1 for ex in EX for t in set(u["target"] for u in ex["units"]) if t in ex["fig"])
targets = sum(len(set(u["target"] for u in ex["units"])) for ex in EX)

# ---------- 기준선: 전 페이지 OCR -> 텍스트 청크 -> BM25 ----------
t1 = time.time()
base_text = {}
for p in sorted(glob.glob(f"{D}/pdf/*.pdf")):
    img = render(p, 150)
    base_text[os.path.basename(p)[:-4]] = pytesseract.image_to_string(img, config="--psm 3")
t_base = time.time() - t1

def chunks_of(doc, text, size=400, ov=80):
    out = []; i = 0
    while i < len(text):
        out.append((doc, text[i:i + size])); i += size - ov
    return out
B_CH = [c for d, t in base_text.items() for c in chunks_of(d, t)]
# 비교군: 구조 보존 직렬화(표를 행 단위 마크다운으로, 헤더 경로 포함) + 적용 조항
S_CH = []
for ex in EX:
    head = f"{ex['doc']} Configuration {ex['config']}"
    rows = defaultdict(list)
    for u in ex["units"]:
        rows[u["target"]].append(f"{u['attr']} {u['cond']} = {u['raw']} {u['unit']}")
    for t, cs in rows.items():
        S_CH.append((ex["doc"], f"{head} | {t} | " + " ; ".join(cs)))
tok = lambda s: re.findall(r"[A-Za-z]+|\d+", s.lower())
bm_b = BM25Okapi([tok(c[1]) for c in B_CH]); bm_s = BM25Okapi([tok(c[1]) for c in S_CH])

random.seed(3)
Q = random.sample(truth["facts"], 120)
DOC_CFG = {d["doc"]: d["config"] for d in truth["docs"]}
def qtext(f):
    return f"{f['target']} {'temperature' if 'temp' in f['attr'] else 'pressure'} {'normal' if f['cond']=='normal' else 'emerg emergency'} configuration {f['config']}"

def eval_chunks(bm, CH, f, k=3):
    sc = bm.get_scores(tok(qtext(f))); top = np.argsort(sc)[::-1][:k]
    hit = False; ctx = 0; wrong_top1 = DOC_CFG[CH[top[0]][0]] != f["config"]
    for i in top:
        doc, txt = CH[i]; ctx += len(txt)
        if DOC_CFG[doc] == f["config"] and f["target"] in txt.replace(" ", "") and re.search(rf"(?<!\d){f['value']}(?!\d)", txt):
            hit = True
    return hit, ctx, wrong_top1

db = sqlite3.connect(":memory:")
db.execute("create table eu(doc, target, attr, cond, config, value, unit, status, page, row, col)")
db.executemany("insert into eu values(?,?,?,?,?,?,?,?,?,?,?)",
               [(u["doc"], u["target"], u["attr"], u["cond"], u["config"], u["value"], u["unit"], u["status"], 1, u["src"]["row"], u["src"]["col"]) for u in U])
qr = Counter(); ctx_b = ctx_s = ctx_p = 0
for f in Q:
    h, c, w = eval_chunks(bm_b, B_CH, f); qr["b_hit"] += h; ctx_b += c; qr["b_wrong"] += w
    h, c, w = eval_chunks(bm_s, S_CH, f); qr["s_hit"] += h; ctx_s += c; qr["s_wrong"] += w
    row = db.execute("select value, unit, status, doc, row, col from eu where target=? and attr=? and cond=? and config=?", (f["target"], f["attr"], f["cond"], f["config"])).fetchone()
    if row is None: qr["p_none"] += 1; continue
    ctx_p += len(json.dumps(row))
    if row[2] == "review": qr["p_review"] += 1
    elif abs(row[0] - f["value"]) < 1e-9: qr["p_ok"] += 1
    else: qr["p_wrong"] += 1
nq = len(Q)
query = {"질의 수": nq,
         "기준선(전체 OCR·텍스트 청크) 근거 포함률": qr["b_hit"] / nq, "기준선 상위 1건 다른 적용 조건 문서": qr["b_wrong"] / nq,
         "비교군(표 구조 보존 청크) 근거 포함률": qr["s_hit"] / nq, "비교군 상위 1건 다른 적용 조건 문서": qr["s_wrong"] / nq,
         "제안(정보 단위 조회) 정답": qr["p_ok"] / nq, "제안 미확정 반환": qr["p_review"] / nq, "제안 오답": qr["p_wrong"] / nq, "제안 미조회": qr["p_none"] / nq,
         "질의당 입력 문자: 기준선": ctx_b / nq, "비교군": ctx_s / nq, "제안": ctx_p / nq}

st = Counter()
for ex in EX: st.update(ex["stats"])
out = {"요약": summary, "경로별": res, "그림-표 객체 연결": f"{links}/{targets}", "처리량": dict(st),
       "처리 시간(초)": {"제안 추출+검증": round(t_prop, 1), "기준선 전 페이지 OCR": round(t_base, 1)},
       "질의": query,
       "검토 사유": dict(Counter(u["checks"]["why"] or ("원문 재판독 불일치" if not u["checks"]["source"] else "") for u in U if u["status"] == "review"))}
json.dump(out, open(f"result_{os.path.basename(D)}.json", "w"), ensure_ascii=False, indent=1, default=str)
json.dump([{k: v for k, v in u.items() if k not in ("img",)} for u in U], open(f"units_{os.path.basename(D)}.json", "w"), ensure_ascii=False, indent=0, default=str)
print(json.dumps(out, ensure_ascii=False, indent=1, default=str))
