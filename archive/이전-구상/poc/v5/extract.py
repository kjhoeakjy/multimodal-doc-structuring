"""1차 추출, 연결 확인, 연결 누락 영역 재해석, 구조화.
좌표는 150dpi 픽셀 기준(좌상단 원점)으로 통일함."""
import re, time
from pathlib import Path
import numpy as np, cv2, pdfplumber

S = 150 / 72
ZONE_RE = re.compile(r"ZONE\s*(\d{3})")
PART_RE = re.compile(r"^\(?([A-H])[-.]?(\d{2})\)?$")
VAL_RE = re.compile(r"(\d{3,4})\s*([*\"'^]*)")
_ocr = None


def imread(p):
    return cv2.imdecode(np.frombuffer(Path(p).read_bytes(), np.uint8), 0)


# ---------- 1차 추출 ----------
def first_pass_digital(pdf_path):
    """텍스트 레이어와 벡터 객체 직접 추출(CPU)."""
    with pdfplumber.open(pdf_path) as pdf:
        pg = pdf.pages[0]
        words = pg.extract_words(keep_blank_chars=False, x_tolerance=1.5)
        rects = [(r["x0"] * S, r["top"] * S, r["x1"] * S, r["bottom"] * S) for r in pg.rects]
    # 같은 줄의 인접 단어를 묶어 항목 생성
    words.sort(key=lambda w: (round(w["top"]), w["x0"]))
    items, cur = [], None
    for w in words:
        if cur and abs(w["top"] - cur["top"]) < 2 and 0 <= w["x0"] - cur["x1"] < 6:
            cur["text"] += " " + w["text"]; cur["x1"] = w["x1"]
        else:
            if cur: items.append(cur)
            cur = dict(text=w["text"], x0=w["x0"], top=w["top"], x1=w["x1"], bottom=w["bottom"])
    items.append(cur)
    items = [{"text": i["text"], "box": (i["x0"] * S, i["top"] * S, i["x1"] * S, i["bottom"] * S), "conf": 1.0} for i in items]
    zones = [r for r in rects if 150 < r[2] - r[0] < 600 and r[3] - r[1] > 150]
    markers = [r for r in rects if (r[2] - r[0]) < 20 and (r[3] - r[1]) < 20]
    return {"items": items, "zones": zones, "markers": markers, "mode": "digital"}


def first_pass_scan(png_path):
    """기본 OCR과 윤곽선 기반 경량 시각 분석(CPU)."""
    global _ocr
    import easyocr
    if _ocr is None:
        _ocr = easyocr.Reader(["en"], gpu=False, verbose=False)
    img = imread(png_path)
    items = []
    for b, t, c in _ocr.readtext(img):
        xs, ys = [p[0] for p in b], [p[1] for p in b]
        items.append({"text": t, "box": (min(xs), min(ys), max(xs), max(ys)), "conf": float(c)})
    bw = (img < 140).astype(np.uint8) * 255
    cnts, _ = cv2.findContours(bw, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    zones, markers = [], []
    for c in cnts:
        x, y, w, h = cv2.boundingRect(c)
        if 150 < w < 600 and h > 150 and cv2.contourArea(c) > 0.8 * w * h:
            zones.append((x, y, x + w, y + h))
        elif 8 <= w <= 20 and 8 <= h <= 20 and cv2.contourArea(c) > 0.6 * w * h:
            markers.append((x, y, x + w, y + h))
    # 중복 제거
    zones = _dedup(zones, 15); markers = _dedup(markers, 5)
    return {"items": items, "zones": zones, "markers": markers, "mode": "scan", "img": img}


def _dedup(rs, tol):
    out = []
    for r in sorted(rs, key=lambda r: (r[2] - r[0]) * (r[3] - r[1])):
        if not any(all(abs(a - b) < tol for a, b in zip(r, o)) for o in out):
            out.append(r)
    return out


def _center(b):
    return ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)


def _inside(pt, r):
    return r[0] <= pt[0] <= r[2] and r[1] <= pt[1] <= r[3]


# ---------- 구조화와 연결 확인 ----------
def structure(fp):
    items, gaps = fp["items"], []
    # 그림: 구역
    zone_of_rect = {}
    for r in fp["zones"]:
        for it in items:
            m = ZONE_RE.search(it["text"].upper())
            if m and _inside(_center(it["box"]), r):
                zone_of_rect[r] = m.group(1)
    # 그림: 부품 표지와 라벨
    parts = []
    for mk in fp["markers"]:
        cy = (mk[1] + mk[3]) / 2
        cand = [it for it in items if 0 <= it["box"][0] - mk[2] < 30 and it["box"][1] - 6 < cy < it["box"][3] + 6]
        label = None
        for it in cand:
            m = PART_RE.match(it["text"].strip().upper().replace(" ", ""))
            if m:
                label = f"{m.group(1)}-{m.group(2)}"
        zr = [r for r in fp["zones"] if _inside(_center(mk), r)]
        zone = zone_of_rect.get(zr[0]) if zr else None
        parts.append({"marker": mk, "label": label, "zone": zone})
        if label is None:
            gaps.append({"type": "부품 표지에 대응하는 라벨 없음", "marker": mk})
    # 표
    head = [it for it in items if it["text"].strip().startswith("INTERVAL")]  # 표 머리글(대문자)
    rows, foot = {}, []
    if head:
        hb = head[0]["box"]
        zone_col = [it for it in items if it["text"].strip().upper() == "ZONE" and abs(it["box"][1] - hb[1]) < 12]
        zx = zone_col[0]["box"][0] if zone_col else hb[0] - 250
        body = sorted([it for it in items if it["box"][1] > hb[3] - 2 and it["box"][1] < hb[3] + 160], key=lambda i: i["box"][1])
        for it in body:
            t = it["text"].strip()
            if abs(it["box"][0] - zx) < 30 and re.fullmatch(r"\d{3}", t):
                val = [v for v in items if abs(v["box"][1] - it["box"][1]) < 12 and abs(v["box"][0] - hb[0]) < 30]
                vals = VAL_RE.findall(val[0]["text"]) if val else []
                rows[t] = {"vals": [int(v) for v, _ in vals], "raw_marks": [m for _, m in vals], "box": it["box"]}
        last_y = max([r["box"][3] for r in rows.values()] or [hb[3]])
        foot = sorted([it for it in items if last_y + 5 < it["box"][1] < last_y + 90 and it["box"][0] < hb[0]], key=lambda i: i["box"][1])
    # 표의 표시 기호 정규화: 두 값이 있는 칸은 앞에서부터 *, ** 순서(표기 관례)
    for z, r in rows.items():
        if len(r["vals"]) == 2:
            r["marks"] = ["*", "**"]
        else:
            r["marks"] = ["*" * min(2, sum(ch in "*\"'^" for ch in m)) for m in r["raw_marks"]]
    used = sorted({m for r in rows.values() for m in r["marks"] if m}, key=len)
    # 각주 연결 확인
    notes = {}
    for it in foot:
        t = it["text"].strip()
        m = re.match(r"^(\*{1,2})\s*(.+)", t)
        if m:
            notes[m.group(1)] = {"text": m.group(2), "item": it}
    unresolved = [m for m in used if m not in notes]
    if unresolved:
        gaps.append({"type": "각주 기호에 대응하는 각주 없음", "marks": unresolved, "lines": [it for it in foot if not re.match(r"^\*", it["text"].strip())]})
    # 구역 대조
    fig_z = set(zone_of_rect.values())
    for z in rows:
        if z not in fig_z:
            gaps.append({"type": "표의 구역이 그림에서 확인되지 않음", "zone": z})
    return {"parts": parts, "rows": rows, "notes": notes, "used": used, "gaps": gaps, "zone_of_rect": zone_of_rect}


# ---------- 연결 누락 영역 재해석 ----------
def repair(fp, st, use_vlm=True):
    """연결 누락 영역에 한해 소형 VLM을 적용함. 디지털 문서는 원본 텍스트를 다시 참조함."""
    log = []
    if fp["mode"] != "scan" or not st["gaps"]:
        return log
    import vlm
    img = fp["img"]
    for g in st["gaps"]:
        if g["type"].startswith("부품 표지") and use_vlm:
            x0, y0, x1, y1 = map(int, g["marker"])
            crop = img[max(0, y0 - 10):y1 + 10, x1 + 2:x1 + 70]
            lines, dt, n, _ = vlm.read_region(crop, max_new_tokens=24)
            lab = None
            for t in lines:
                m = PART_RE.match(t.strip().upper().replace(" ", ""))
                if m: lab = f"{m.group(1)}-{m.group(2)}"
            for p in st["parts"]:
                if p["marker"] == g["marker"]:
                    p["label"] = lab
            log.append({"gap": g["type"], "sec": dt, "tokens": n, "result": lab})
        elif g["type"].startswith("각주") and use_vlm:
            # 각주 문장을 한 줄씩 재해석하고 표의 표시 기호 순서에 따라 연결(각주 기재 순서 관례)
            texts = []
            for it in g["lines"]:
                x0, y0, x1, y1 = map(int, it["box"])
                crop = img[max(0, y0 - 4):y1 + 4, max(0, x0 - 4):x1 + 4]
                lines, dt, n, _ = vlm.read_region(crop, max_new_tokens=32)
                txt = " ".join(l for l in lines if len(l) > 2)
                # VLM 출력 검증: 1차 OCR 문장과 유사도가 낮으면 환각으로 보고 OCR 문장을 유지하고 검토 필요로 표시
                import difflib
                sim = difflib.SequenceMatcher(None, txt.lower(), it["text"].lower().lstrip("*· ")).ratio()
                accepted = sim >= 0.5
                texts.append(txt if accepted else it["text"])
                log.append({"gap": g["type"], "sec": dt, "tokens": n, "result": txt, "ocr": it["text"], "sim": round(sim, 2), "accepted": accepted})
            for m, t in zip(g["marks"], texts):
                st["notes"][m] = {"text": t.lstrip("*· ").strip(), "item": None}
    return log


def facts(st, doc_id):
    out = []
    for p in st["parts"]:
        if p["label"] and p["zone"]:
            out.append({"대상": p["label"], "속성": "소속 구역", "값": p["zone"], "조건": "", "출처": f"{doc_id} 그림 1 구역 경계"})
    for z, r in st["rows"].items():
        for v, m in zip(r["vals"], r["marks"]):
            cond = st["notes"].get(m, {}).get("text", "") if m else ""
            out.append({"대상": f"ZONE {z}", "속성": "점검 주기(FH)", "값": v, "조건": cond, "출처": f"{doc_id} 표 1 {z} 행" + (f", 각주 {m}" if m else "")})
    return out
