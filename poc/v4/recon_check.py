"""재구성 검증 실험(v12): 스캔본 1차 판독 결과를 다시 그려 원본과 비교해 누락과 오판독을 찾는다.

입력: data/pdf(스캔본), data/truth.json, 정답 위치용 디지털 재생성본(인자 2)
절차
  1. 1차 판독(수준 1): 130dpi 렌더, 페이지 OCR(단어와 상자), 표 격자 셀 OCR(셀 상자), 상자·원·선 검출
  2. 재구성: 판독한 글자를 같은 상자에 같은 크기로 다시 그리고 검출한 도형을 그림
  3. 오차 1 미설명 잉크: 원본 잉크에서 재구성 요소가 덮는 영역을 지운 뒤 남는 연결 성분
     오차 2 글자 불일치: 판독 단어마다 재구성 글자와 원본 잉크의 Dice 유사도
  4. 정답: 디지털 재생성본의 단어 위치를 130dpi로 환산. 누락(대응 단어 없음), 오판독(대응은 있으나 글자 다름)
  5. 지표: 누락 단어 중 미설명 잉크 영역에 덮인 비율(재현율), 영역 중 실제 누락을 포함한 비율(정밀도),
          오판독 단어의 유사도 분포와 정상 단어 오경보 10% 기준 재현율
출력: data/recon_results.json, 표준 출력 요약
"""
import json, re, sys, os
import numpy as np, cv2, pdfplumber, pytesseract, pypdfium2 as pdfium
from PIL import Image, ImageDraw, ImageFont

DATA = sys.argv[1] if len(sys.argv) > 1 else "data"
DIGI = sys.argv[2]
DPI = 130; S = DPI / 72
FONT_PATH = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
truth = json.load(open(f"{DATA}/truth.json"))


def render(pdf):
    return pdfium.PdfDocument(pdf)[0].render(scale=S).to_pil().convert("L")


def norm(t):
    t = t.replace("—", "-").replace("_", "-").replace("·", "").replace("°", "*").replace("•", "*")
    t = re.sub(r"(?<=[A-Z])l|l(?=[A-Z-])", "I", t)
    return re.sub(r"[^A-Za-z0-9*]", "", t).upper()


def ocr_words(im, psm=6, off=(0, 0)):
    d = pytesseract.image_to_data(im, config=f"--psm {psm}", output_type=pytesseract.Output.DICT)
    out = []
    for i in range(len(d["text"])):
        t = d["text"][i].strip()
        if t and d["conf"][i] != -1:
            out.append({"text": t, "x0": d["left"][i] + off[0], "y0": d["top"][i] + off[1],
                        "x1": d["left"][i] + d["width"][i] + off[0], "y1": d["top"][i] + d["height"][i] + off[1], "src": "page"})
    return out


def grid_cells(a):
    """표 영역의 격자선으로 셀 상자 목록을 돌려줌."""
    th = cv2.threshold(a, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    hk = cv2.getStructuringElement(cv2.MORPH_RECT, (max(10, a.shape[1] // 8), 1)); vk = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(10, a.shape[0] // 8)))
    hor = cv2.morphologyEx(th, cv2.MORPH_OPEN, hk); ver = cv2.morphologyEx(th, cv2.MORPH_OPEN, vk)
    ys = np.where(hor.sum(axis=1) > a.shape[1] * 0.15 * 255)[0]; xs = np.where(ver.sum(axis=0) > a.shape[0] * 0.3 * 255)[0]
    def merge(v):
        out = []
        for x in sorted(set(int(i) for i in v)):
            if out and x - out[-1][-1] <= 3: out[-1].append(x)
            else: out.append([x])
        return [int(np.mean(g)) for g in out]
    ys, xs = merge(ys), merge(xs)
    cells = []
    for i in range(len(ys) - 1):
        for j in range(len(xs) - 1):
            if ys[i + 1] - ys[i] > 8 and xs[j + 1] - xs[j] > 8: cells.append((xs[j] + 2, ys[i] + 2, xs[j + 1] - 2, ys[i + 1] - 2))
    return cells, hor, ver


def first_pass(im):
    """수준 1 판독: 페이지 OCR + 표 셀 OCR + 도형 검출. 판독 단어(상자 포함)와 도형 마스크를 돌려줌."""
    a = np.asarray(im); H, W = a.shape
    words = ocr_words(im)
    # 표 영역: TABLE 캡션 행과 각주(*) 행 사이
    cap = sorted([w for w in words if w["text"].upper() == "TABLE"], key=lambda w: w["y0"])[:1]   # 캡션(가장 위의 TABLE)
    fn = [w for w in words if w["text"].startswith("*")]
    table_region = None
    if cap:
        y0 = cap[0]["y1"] + 2
        y1 = (min(w["y0"] for w in fn if w["y0"] > y0) - 2) if any(w["y0"] > y0 for w in fn) else min(H, y0 + int(180 * S))
        table_region = (0, y0, W, y1)
    cells = []; hor = ver = None
    if table_region:
        x0, y0, x1, y1 = table_region
        cells, hor, ver = grid_cells(a[y0:y1, x0:x1])
        cells = [(c[0] + x0, c[1] + y0, c[2] + x0, c[3] + y0) for c in cells]
        if cells:
            y1 = max(c[3] for c in cells) + 4; table_region = (x0, y0, x1, y1)   # 격자선 범위로 한정
        words = [w for w in words if not (y0 <= (w["y0"] + w["y1"]) / 2 <= y1)]
        for (cx0, cy0, cx1, cy1) in cells:
            c = im.crop((cx0 + 1, cy0 + 1, cx1 - 1, cy1 - 1)); k = 48 / max(1, c.height)
            c = c.resize((max(1, int(c.width * k)), 48), Image.LANCZOS)
            b = cv2.threshold(cv2.GaussianBlur(np.asarray(c), (3, 3), 0), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
            pad = 16; cim = Image.fromarray(np.pad(b, pad, constant_values=255))
            for w in ocr_words(cim, psm=7):
                words.append({"text": w["text"], "x0": cx0 + 1 + (w["x0"] - pad) / k, "y0": cy0 + 1 + (w["y0"] - pad) / k,
                              "x1": cx0 + 1 + (w["x1"] - pad) / k, "y1": cy0 + 1 + (w["y1"] - pad) / k, "src": "cell"})
    # 도형: 긴 선(격자, 상자, 연결선), 원
    th = cv2.threshold(cv2.GaussianBlur(a, (3, 3), 0), 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    hk = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1)); vk = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 40))
    lines = cv2.morphologyEx(th, cv2.MORPH_OPEN, hk) | cv2.morphologyEx(th, cv2.MORPH_OPEN, vk)
    circ = cv2.HoughCircles(cv2.medianBlur(a, 3), cv2.HOUGH_GRADIENT, 1, 25, param1=120, param2=18, minRadius=12, maxRadius=22)
    circles = [(float(x), float(y), float(r)) for x, y, r in (circ[0] if circ is not None else [])]
    return words, lines, circles, th, table_region


def second_reader(pdf):
    """2차 판독기: 300dpi 렌더 OCR. 상자는 130dpi 좌표로 환산."""
    global S
    im2 = pdfium.PdfDocument(pdf)[0].render(scale=300 / 72).to_pil().convert("L")
    k = DPI / 300; S0 = S; S = 300 / 72
    try: ws = first_pass(im2)[0]
    finally: S = S0
    return [{"text": w["text"], "x0": w["x0"] * k, "y0": w["y0"] * k, "x1": w["x1"] * k, "y1": w["y1"] * k} for w in ws]


def overlap(a, b):
    acx, acy = (a["x0"] + a["x1"]) / 2, (a["y0"] + a["y1"]) / 2; bcx, bcy = (b["x0"] + b["x1"]) / 2, (b["y0"] + b["y1"]) / 2
    return iou(a, b) > 0.3 or (b["x0"] <= acx <= b["x1"] and b["y0"] <= acy <= b["y1"]) or (a["x0"] <= bcx <= a["x1"] and a["y0"] <= bcy <= a["y1"])


def reconstruct(im, words, lines, circles):
    """판독 결과를 다시 그림. 설명 마스크(요소가 덮는 영역)와 글자 재구성 이미지를 돌려줌."""
    H, W = im.size[1], im.size[0]
    glyph = Image.new("L", (W, H), 255); dr = ImageDraw.Draw(glyph)
    for w in words:
        h = max(6, w["y1"] - w["y0"]); size = int(h * 1.25)
        try: f = ImageFont.truetype(FONT_PATH, size)
        except Exception: f = ImageFont.load_default()
        dr.text((w["x0"], w["y0"] - int(h * 0.15)), w["text"], fill=0, font=f)
    explained = np.zeros((H, W), np.uint8)
    for w in words:
        cv2.rectangle(explained, (int(w["x0"]) - 2, int(w["y0"]) - 2), (int(w["x1"]) + 2, int(w["y1"]) + 2), 255, -1)
    explained |= cv2.dilate(lines, np.ones((5, 5), np.uint8))
    for x, y, r in circles:
        cv2.circle(explained, (int(x), int(y)), int(r) + 3, 255, 6)
    return explained, glyph


def residual_regions(th, explained):
    res = cv2.bitwise_and(th, cv2.bitwise_not(explained))
    res = cv2.morphologyEx(res, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))   # 점 잡음 제거
    grp = cv2.dilate(res, np.ones((9, 9), np.uint8))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(grp)
    regions = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        ink = int((res[y:y + h, x:x + w] > 0).sum())
        if ink >= 25 and w >= 6 and h >= 6: regions.append({"x0": int(x), "y0": int(y), "x1": int(x + w), "y1": int(y + h), "ink": ink})
    return regions, res


def dice(th, glyph, w):
    x0, y0, x1, y1 = int(w["x0"]), int(w["y0"]), int(w["x1"]), int(w["y1"])
    if x1 - x0 < 3 or y1 - y0 < 3: return 0.0
    a = th[y0:y1, x0:x1] > 0; g = np.asarray(glyph.crop((x0, y0, x1, y1))) < 128
    # 글자 재구성의 수평 위치 오차를 보정: 최대 3픽셀 이동 중 최댓값
    best = 0.0
    for dx in range(-3, 4):
        gg = np.roll(g, dx, axis=1)
        inter = (a & gg).sum(); s = a.sum() + gg.sum()
        best = max(best, 2 * inter / s if s else 0.0)
    return float(best)


def truth_words(doc):
    with pdfplumber.open(f"{DIGI}/pdf/{doc}.pdf") as p:
        pg = p.pages[0]
        return [{"text": w["text"], "x0": w["x0"] * S, "y0": w["top"] * S, "x1": w["x1"] * S, "y1": w["bottom"] * S} for w in pg.extract_words()]


def iou(a, b):
    ix0, iy0, ix1, iy1 = max(a["x0"], b["x0"]), max(a["y0"], b["y0"]), min(a["x1"], b["x1"]), min(a["y1"], b["y1"])
    inter = max(0, ix1 - ix0) * max(0, iy1 - iy0)
    ua = (a["x1"] - a["x0"]) * (a["y1"] - a["y0"]) + (b["x1"] - b["x0"]) * (b["y1"] - b["y0"]) - inter
    return inter / ua if ua else 0


def category(tw, layout):
    cx, cy = (tw["x0"] + tw["x1"]) / 2 / S, (tw["y0"] + tw["y1"]) / 2 / S
    H = 841.89; y_pdf = H - cy   # reportlab 좌표(아래 기준)
    tb = layout["table"]
    if tb[0] <= cx <= tb[2] and tb[1] <= y_pdf <= tb[3]: return "table_cell"
    if abs(y_pdf - layout["footnote_y"] - 3) < 8: return "footnote"
    for k, (gx, gy) in layout["callouts"].items():
        if abs(cx - gx) < 10 and abs(y_pdf - gy) < 10: return "callout"
    fg = layout["figure"]
    if fg[0] <= cx <= fg[2] and fg[1] <= y_pdf <= fg[3]: return "figure_label"
    return "body"


def main():
    out = {"docs": []}
    allw = []
    for d in truth["docs"]:
        if not d["scanned"]: continue
        doc = d["doc"]; layout = truth["layout"][doc]
        im = render(f"{DATA}/pdf/{doc}.pdf")
        words, lines, circles, th, table_region = first_pass(im)
        explained, glyph = reconstruct(im, words, lines, circles)
        regions, res = residual_regions(th, explained)
        tws = truth_words(doc); w2 = second_reader(f"{DATA}/pdf/{doc}.pdf")
        rec = {"doc": doc, "n_truth": len(tws), "n_read": len(words), "n_regions": len(regions), "missed": [], "misread": [], "correct": 0}
        for tw in tws:
            cand = [(iou(tw, w), w) for w in words if overlap(tw, w)]
            cat = category(tw, layout)
            cx, cy = (tw["x0"] + tw["x1"]) / 2, (tw["y0"] + tw["y1"]) / 2
            covered = any(r["x0"] - 4 <= cx <= r["x1"] + 4 and r["y0"] - 4 <= cy <= r["y1"] + 4 for r in regions)
            if not cand:
                rec["missed"].append({"text": tw["text"], "cat": cat, "covered": covered})
                continue
            _, w = max(cand, key=lambda c: c[0])
            sim = dice(th, glyph, w)
            m2 = [v for v in w2 if overlap(w, v)]
            import difflib
            disagree = (not m2) or all(difflib.SequenceMatcher(None, norm(v["text"]), norm(w["text"])).ratio() < 0.75 for v in m2)
            a_, b_ = norm(w["text"]), norm(tw["text"])
            ok = bool(b_) and (a_ == b_ or b_ in a_ or (a_ in b_ and len(a_) >= 2))
            if ok: rec["correct"] += 1
            else: rec["misread"].append({"truth": tw["text"], "read": w["text"], "cat": cat, "sim": sim, "disagree": disagree})
            allw.append({"doc": doc, "ok": ok, "sim": sim, "cat": cat, "truth": tw["text"], "read": w["text"], "disagree": disagree})
        # 영역 정밀도: 영역 안에 누락 단어 중심이 있는 비율
        hit = 0
        for r in regions:
            if any(r["x0"] - 4 <= (tw["x0"] + tw["x1"]) / 2 <= r["x1"] + 4 and r["y0"] - 4 <= (tw["y0"] + tw["y1"]) / 2 <= r["y1"] + 4
                   and not any(overlap(tw, w) for w in words) for tw in tws): hit += 1
        rec["regions_with_missed"] = hit
        out["docs"].append(rec)
        print(f"{doc}: 정답 단어 {len(tws)}, 판독 {len(words)}, 누락 {len(rec['missed'])}(덮임 {sum(m['covered'] for m in rec['missed'])}), 오판독 {len(rec['misread'])}, 미설명 영역 {len(regions)}(누락 포함 {hit})")
    # 집계
    M = [m for r in out["docs"] for m in r["missed"]]; R = sum(r["n_regions"] for r in out["docs"]); RH = sum(r["regions_with_missed"] for r in out["docs"])
    print(f"\n누락 단어 {len(M)}건 중 미설명 잉크 영역에 덮인 비율: {sum(m['covered'] for m in M)}/{len(M)}")
    from collections import Counter
    cats = Counter(m["cat"] for m in M); cov = Counter(m["cat"] for m in M if m["covered"])
    print("유형별 누락(덮임/전체): " + ", ".join(f"{k} {cov[k]}/{v}" for k, v in cats.items()))
    print(f"미설명 영역 {R}개 중 실제 누락 단어를 포함한 영역: {RH} (정밀도 {RH / R:.0%}), 문서당 영역 {R / len(out['docs']):.1f}개")
    okv = sorted(w["sim"] for w in allw if w["ok"]); badv = [w for w in allw if not w["ok"]]
    thr = okv[int(len(okv) * 0.10)] if okv else 0   # 정상 단어 하위 10%를 경보로 허용
    rec_bad = sum(1 for w in badv if w["sim"] < thr)
    print(f"글자 불일치: 정상 단어 {len(okv)}건 Dice 중앙값 {np.median(okv):.2f}, 오판독 {len(badv)}건 중앙값 {np.median([w['sim'] for w in badv]) if badv else 0:.2f}")
    print(f"정상 단어 오경보 10% 기준 임계값 {thr:.2f}: 오판독 탐지 {rec_bad}/{len(badv)}")
    bc = Counter(w["cat"] for w in badv); bd = Counter(w["cat"] for w in badv if w["sim"] < thr)
    print("유형별 오판독(탐지/전체): " + ", ".join(f"{k} {bd[k]}/{v}" for k, v in bc.items()))
    okd = sum(1 for w in allw if w["ok"] and w["disagree"]); badd = sum(1 for w in badv if w["disagree"])
    print(f"2차 판독기 불일치: 정상 단어 오경보 {okd}/{len(okv)} ({okd / len(okv):.0%}), 오판독 탐지 {badd}/{len(badv)}")
    bdd = Counter(w["cat"] for w in badv if w["disagree"])
    print("유형별 오판독 불일치 탐지: " + ", ".join(f"{k} {bdd[k]}/{v}" for k, v in bc.items()))
    print("오판독 예: " + "; ".join(f"{w['truth']}->{w['read']}({w['sim']:.2f})" for w in badv[:12]))
    errs = len(M) + len(badv); det = sum(m["covered"] for m in M) + sum(1 for w in badv if w["disagree"])
    flagged = R + sum(1 for w in allw if w["disagree"])
    print(f"종합: 오류 {errs}건(누락 {len(M)}, 오판독 {len(badv)}) 중 미설명 잉크 또는 2차 판독 불일치로 표시된 것 {det}건({det / errs:.0%}). 문서당 표시 단위 {flagged / len(out['docs']):.1f}개(영역 {R / len(out['docs']):.1f} + 불일치 단어 {(flagged - R) / len(out['docs']):.1f}), 정상 단어 오경보 {okd / len(okv):.0%}")
    out["summary"] = {"errors": errs, "detected": det, "flagged_per_doc": flagged / len(out["docs"]), "missed": len(M), "missed_covered": sum(m["covered"] for m in M), "regions": R, "regions_with_missed": RH,
                      "ok_words": len(okv), "misread": len(badv), "thr": thr, "misread_detected": rec_bad, "ok_median": float(np.median(okv)) if okv else 0,
                      "disagree_false_alarm": okd, "disagree_detected": badd}
    out["words"] = allw
    json.dump(out, open(f"{DATA}/recon_results.json", "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
